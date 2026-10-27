"""Capture official NSE Indices sector TRI histories for signal warm-up."""

from __future__ import annotations

import json
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "work" / "data" / "index_daily" / "sector_tri_raw_2014_2026.json"
SOURCE_PAGE = "https://www.niftyindices.com/reports/historical-data"
SOURCE_ROUTE = "/BackPage/getTotalReturnIndexString"
URL = "https://www.niftyindices.com" + SOURCE_ROUTE
START = date(2014, 1, 1)
END = date(2026, 10, 23)
INDICES = ("Nifty Bank", "Nifty IT", "Nifty Auto", "Nifty Pharma", "Nifty PSU Bank")


def _periods() -> list[tuple[date, date]]:
    result = []
    start = START
    while start <= END:
        end = min(END, start + timedelta(days=364))
        result.append((start, end))
        start = end + timedelta(days=1)
    assert all((end - start).days <= 365 for start, end in result)
    return result


def _get_rows(index_name: str, start: date, end: date) -> list[dict]:
    cinfo = json.dumps({
        "name": index_name.upper(),
        "startDate": start.strftime("%d-%b-%Y"),
        "endDate": end.strftime("%d-%b-%Y"),
        "indexName": index_name,
    }, separators=(",", ":"))
    body = json.dumps({"cinfo": cinfo}).encode("utf-8")
    headers = {
        "User-Agent": "Mozilla/5.0",
        "Referer": SOURCE_PAGE,
        "Origin": "https://www.niftyindices.com",
        "Content-Type": "application/json; charset=utf-8",
        "Accept": "application/json, text/javascript, */*; q=0.01",
    }
    for attempt in range(3):
        try:
            request = Request(URL, data=body, headers=headers, method="POST")
            with urlopen(request, timeout=30) as response:
                if response.status != 200:
                    raise RuntimeError(f"NSE Indices returned HTTP {response.status}")
                result = json.loads(response.read())
            if isinstance(result, dict) and isinstance(result.get("d"), str):
                result = json.loads(result["d"])
            if not isinstance(result, list):
                raise ValueError(f"Unexpected TRI response for {index_name}: {type(result).__name__}")
            return result
        except (HTTPError, URLError, TimeoutError, json.JSONDecodeError, ValueError, RuntimeError):
            if attempt == 2:
                raise
            time.sleep(1.5 * (attempt + 1))
    raise AssertionError("unreachable retry loop")


def main() -> None:
    requests = []
    dates_by_index: dict[str, set[date]] = {name: set() for name in INDICES}
    for index_name in INDICES:
        for start, end in _periods():
            rows = _get_rows(index_name, start, end)
            if not rows:
                raise ValueError(f"Empty official TRI response for {index_name} {start}..{end}")
            for row in rows:
                assert row["Index Name"].strip().casefold() == index_name.casefold()
                day = datetime.strptime(row["Date"], "%d %b %Y").date()
                value = float(row["TotalReturnsIndex"])
                assert start <= day <= end and value > 0
                assert day not in dates_by_index[index_name], f"Duplicate {index_name} TRI date {day}"
                dates_by_index[index_name].add(day)
            requests.append({
                "index": index_name,
                "startDate": start.strftime("%d-%b-%Y"),
                "endDate": end.strftime("%d-%b-%Y"),
                "httpStatus": 200,
                "rows": rows,
            })
            time.sleep(0.15)

    for index_name, dates in dates_by_index.items():
        assert min(dates) <= date(2021, 1, 1), f"Insufficient warm-up history for {index_name}"
        assert max(dates) == END, f"Latest TRI bar missing for {index_name}"
        assert len(dates) > 2_500, f"Insufficient TRI observations for {index_name}: {len(dates)}"

    result = {
        "retrievedAtUtc": datetime.now(timezone.utc).isoformat(),
        "sourcePage": SOURCE_PAGE,
        "sourceRoute": SOURCE_ROUTE,
        "sourceLimit": "Observed first-party page JavaScript rejects date spans over 365 days; chunks use at most a 364-day difference. This route is not a documented public API contract.",
        "series": "Official daily Total Returns Index values; NTR fields are preserved when returned.",
        "requests": requests,
        "coverage": {
            name: {
                "firstDate": min(days).isoformat(),
                "lastDate": max(days).isoformat(),
                "rowCount": len(days),
            }
            for name, days in dates_by_index.items()
        },
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    temporary = OUTPUT.with_suffix(".tmp")
    temporary.write_text(json.dumps(result, indent=2), encoding="utf-8")
    temporary.replace(OUTPUT)
    print(" ".join(f"{name}={len(days)}:{min(days)}..{max(days)}" for name, days in dates_by_index.items()))
    print(f"saved={OUTPUT.relative_to(ROOT).as_posix()} requests={len(requests)}")


if __name__ == "__main__":
    main()
