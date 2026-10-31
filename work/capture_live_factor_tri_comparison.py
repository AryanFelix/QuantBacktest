"""Compare live-launched NSE momentum/quality TRIs with matched parent indices."""

from __future__ import annotations

import csv
import json
import sys
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "work"))
import capture_sector_tri_signal_history as capture

END = date(2026, 10, 23)
PAIRS = (
    ("Nifty200 Momentum 30", "Nifty 200", date(2020, 8, 25)),
    ("Nifty Smallcap250 Momentum Quality 100", "Nifty Smallcap 250", date(2023, 12, 21)),
    ("Nifty500 Multicap Momentum Quality 50", "Nifty 500", date(2024, 9, 4)),
)
RAW = ROOT / "work/data/index_daily/live_momentum_quality_tri_2020_2026.json"
PANEL = ROOT / "work/data/index_daily/live_momentum_quality_tri_2020_2026.csv"
SUMMARY = ROOT / "outputs/live_factor_tri_comparison.csv"


def _metrics(rows: list[tuple[date, float]]) -> dict[str, float | int | str]:
    first_day, first_value = rows[0]
    last_day, last_value = rows[-1]
    peak = first_value
    drawdown = 0.0
    for _, value in rows:
        peak = max(peak, value)
        drawdown = min(drawdown, value / peak - 1)
    days = (last_day - first_day).days
    total = last_value / first_value - 1
    assert len(rows) > 100 and days > 0 and first_value > 0 and last_value > 0
    return {"period_start": first_day.isoformat(), "period_end": last_day.isoformat(),
            "sessions": len(rows), "total_return_pct": total * 100,
            "cagr_pct": ((1 + total) ** (365.25 / days) - 1) * 100,
            "close_mdd_pct": drawdown * 100}


def main() -> None:
    series: dict[str, dict[date, float]] = {}
    requests = []
    for factor, parent, launch in PAIRS:
        for name in (factor, parent):
            if name in series:
                continue
            series[name] = {}
            cursor = launch
            while cursor <= END:
                last = min(END, cursor + timedelta(days=364))
                rows = capture._get_rows(name, cursor, last)
                assert rows, f"No live TRI rows for {name} {cursor}..{last}"
                for row in rows:
                    assert row["Index Name"].strip().casefold() == name.casefold()
                    day = datetime.strptime(row["Date"], "%d %b %Y").date()
                    value = float(row["TotalReturnsIndex"])
                    assert cursor <= day <= last and value > 0 and day not in series[name]
                    series[name][day] = value
                requests.append({"index": name, "from": cursor.isoformat(), "to": last.isoformat(), "rows": rows})
                cursor = last + timedelta(days=1)
                time.sleep(0.15)
        factor_days, parent_days = set(series[factor]), set(series[parent])
        assert factor_days == parent_days and min(factor_days) == launch and max(factor_days) == END

    RAW.write_text(json.dumps({
        "retrieved_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_page": capture.SOURCE_PAGE,
        "source_route": capture.SOURCE_ROUTE,
        "source_limit": "First-party page-backed route, not a documented public API; only dates on or after each live launch are retained.",
        "requests": requests,
    }, indent=2), encoding="utf-8")
    with PANEL.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["date", "factor_index", "factor_tri", "parent_index", "parent_tri"])
        for factor, parent, _ in PAIRS:
            for day in sorted(series[factor]):
                writer.writerow([day.isoformat(), factor, series[factor][day], parent, series[parent][day]])

    summaries = []
    for factor, parent, launch in PAIRS:
        for segment, start in (("live_since_launch", launch), ("2025_plus", date(2025, 1, 1))):
            for name in (factor, parent):
                rows = [(day, value) for day, value in sorted(series[name].items()) if day >= start]
                summaries.append({"segment": segment, "index": name, **_metrics(rows)})
    with SUMMARY.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(summaries[0]))
        writer.writeheader()
        writer.writerows(summaries)
    print(f"factor_indexes={len(PAIRS)} series={len(series)} comparisons={len(summaries)} end={END}")


if __name__ == "__main__":
    main()

