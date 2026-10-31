"""Capture matched official Nifty Midcap 150 and Nifty 50 TRI for MID150BEES."""

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

START = date(2019, 2, 4)
END = date(2026, 10, 23)
INDICES = ("Nifty Midcap 150", "Nifty 50")
RAW = ROOT / "work/data/index_daily/midcap_etf_benchmark_raw_2019_2026.json"
PANEL = ROOT / "work/data/index_daily/midcap_etf_benchmark_2019_2026.csv"


def main() -> None:
    values: dict[str, dict[date, float]] = {name: {} for name in INDICES}
    requests = []
    for name in INDICES:
        cursor = START
        while cursor <= END:
            last = min(END, cursor + timedelta(days=364))
            rows = capture._get_rows(name, cursor, last)
            assert rows, f"No official TRI rows for {name} {cursor}..{last}"
            for row in rows:
                assert row["Index Name"].strip().casefold() == name.casefold()
                day = datetime.strptime(row["Date"], "%d %b %Y").date()
                value = float(row["TotalReturnsIndex"])
                assert cursor <= day <= last and value > 0 and day not in values[name]
                values[name][day] = value
            requests.append({"index": name, "from": cursor.isoformat(), "to": last.isoformat(), "rows": rows})
            cursor = last + timedelta(days=1)
            time.sleep(0.15)

    assert set(values[INDICES[0]]) == set(values[INDICES[1]])
    sessions = sorted(values[INDICES[0]])
    assert sessions[0] == START and sessions[-1] == END and len(sessions) > 1_800
    RAW.write_text(json.dumps({
        "retrieved_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_page": capture.SOURCE_PAGE,
        "source_route": capture.SOURCE_ROUTE,
        "source_limit": "First-party page-backed route, not a documented public API; request windows are at most 365 calendar days.",
        "benchmark_window": [START.isoformat(), END.isoformat()],
        "requests": requests,
    }, indent=2), encoding="utf-8")
    with PANEL.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["date", *INDICES])
        writer.writerows([day.isoformat(), *(values[name][day] for name in INDICES)] for day in sessions)
    print(f"sessions={len(sessions)} range={sessions[0]}..{sessions[-1]} indices={len(INDICES)}")


if __name__ == "__main__":
    main()

