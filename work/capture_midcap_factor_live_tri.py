"""Capture live-launch TRI history for Midcap 150, its Momentum 50 index, and NIFTY 50."""

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

START = date(2022, 8, 16)
END = date(2026, 10, 23)
INDICES = ("Nifty Midcap150 Momentum 50", "Nifty Midcap 150", "Nifty 50")
RAW = ROOT / "work" / "data" / "index_daily" / "midcap_factor_live_tri_2022_2026.json"
PANEL = ROOT / "work" / "data" / "index_daily" / "midcap_factor_live_tri_2022_2026.csv"
SUMMARY = ROOT / "outputs" / "midcap_factor_live_comparison.csv"


def _periods() -> list[tuple[date, date]]:
    periods = []
    cursor = START
    while cursor <= END:
        period_end = min(END, cursor + timedelta(days=364))
        periods.append((cursor, period_end))
        cursor = period_end + timedelta(days=1)
    assert periods and all((last - first).days <= 364 for first, last in periods)
    return periods


def _metrics(values: list[tuple[date, float]]) -> dict[str, float | int | str]:
    first_day, first_value = values[0]
    last_day, last_value = values[-1]
    peak = first_value
    mdd = 0.0
    for _, value in values:
        peak = max(peak, value)
        mdd = min(mdd, value / peak - 1.0)
    elapsed_days = (last_day - first_day).days
    assert len(values) > 2 and elapsed_days > 0 and first_value > 0 and last_value > 0
    total_return = last_value / first_value - 1.0
    return {
        "period_start": first_day.isoformat(), "period_end": last_day.isoformat(),
        "sessions": len(values), "total_return_pct": total_return * 100,
        "cagr_pct": ((1.0 + total_return) ** (365.25 / elapsed_days) - 1.0) * 100,
        "close_mdd_pct": mdd * 100,
    }


def main() -> None:
    by_index: dict[str, dict[date, float]] = {name: {} for name in INDICES}
    requests = []
    for name in INDICES:
        for start, end in _periods():
            rows = capture._get_rows(name, start, end)
            assert rows, f"No official TRI rows for {name} {start}..{end}"
            for row in rows:
                assert row["Index Name"].strip().casefold() == name.casefold()
                day = datetime.strptime(row["Date"], "%d %b %Y").date()
                value = float(row["TotalReturnsIndex"])
                assert start <= day <= end and value > 0 and day not in by_index[name]
                by_index[name][day] = value
            requests.append({"index": name, "requested_from": start.isoformat(), "requested_to": end.isoformat(), "rows": rows})
            time.sleep(0.15)

    date_sets = [set(values) for values in by_index.values()]
    assert all(days == date_sets[0] for days in date_sets[1:])
    sessions = sorted(date_sets[0])
    assert sessions[0] == START and sessions[-1] == END and len(sessions) > 1_000

    RAW.parent.mkdir(parents=True, exist_ok=True)
    RAW.write_text(json.dumps({
        "retrieved_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_page": capture.SOURCE_PAGE,
        "source_route": capture.SOURCE_ROUTE,
        "source_limit": "First-party page-backed route, not a documented public API; each request spans at most 365 calendar days.",
        "launch_start": START.isoformat(), "end": END.isoformat(),
        "series_note": "Only dates from the factor index launch are included; no pre-launch backfill is treated as live evidence.",
        "requests": requests,
    }, indent=2), encoding="utf-8")

    with PANEL.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["date", *INDICES])
        writer.writerows([day.isoformat(), *(by_index[name][day] for name in INDICES)] for day in sessions)

    rows_out = []
    for label, start in (("live_since_launch", START), ("2023_plus", date(2023, 1, 1)), ("2025_plus", date(2025, 1, 1))):
        for name in INDICES:
            values = [(day, value) for day, value in sorted(by_index[name].items()) if start <= day <= END]
            rows_out.append({"segment": label, "index": name, **_metrics(values)})
    with SUMMARY.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows_out[0]))
        writer.writeheader()
        writer.writerows(rows_out)
    print(f"indices={len(INDICES)} sessions={len(sessions)} range={sessions[0]}..{sessions[-1]} summaries={len(rows_out)}")


if __name__ == "__main__":
    main()

