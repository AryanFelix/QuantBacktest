import csv
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode

import requests


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "work" / "data" / "universe_sources"
PAGE = "https://www.nseindia.com/companies-listing/corporate-filings-actions"
API = "https://www.nseindia.com/api/corporates-corporateActions"
OUT = SOURCE / "nse_corporate_actions_2000_2026.json"
DATE_RANGE = {"from_date": "01-01-2000", "to_date": "26-10-2026"}

with (SOURCE / "upstox_stock_keys.csv").open(encoding="utf-8-sig", newline="") as f:
    symbols = {row["trading_symbol"] for row in csv.DictReader(f)}
with (SOURCE / "nifty50_member_events.csv").open(encoding="utf-8-sig", newline="") as f:
    for row in csv.DictReader(f):
        symbols.update(x for x in (row["symbol"], row["raw_symbol"]) if x)
symbols.update({"HDFC", "LTIM", "INFRATEL", "ZOMATO", "TATAMOTORS"})
symbols = sorted(symbols)
assert len(symbols) == 89

session = requests.Session()
headers = {
    "User-Agent": "Mozilla/5.0",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}
landing = session.get(PAGE, headers=headers, timeout=30)
landing.raise_for_status()
api_headers = {
    "User-Agent": "Mozilla/5.0",
    "Referer": landing.url,
    "Accept": "application/json, text/plain, */*",
    "X-Requested-With": "XMLHttpRequest",
}
responses = {}
errors = {}
for i, symbol in enumerate(symbols):
    params = urlencode({"index": "equities", "symbol": symbol, **DATE_RANGE})
    url = f"{API}?{params}"
    for attempt in range(3):
        try:
            response = session.get(url, headers=api_headers, timeout=30)
            if response.status_code == 200:
                data = response.json()
                if not isinstance(data, list):
                    errors[symbol] = f"Expected a list, got {type(data).__name__}"
                else:
                    responses[symbol] = data
                break
            if response.status_code not in (429, 500, 502, 503, 504) or attempt == 2:
                errors[symbol] = f"HTTP {response.status_code}"
                break
        except (requests.RequestException, ValueError) as exc:
            if attempt == 2:
                errors[symbol] = f"{type(exc).__name__}: {exc}"
                break
        time.sleep(2 ** attempt)
    if i + 1 < len(symbols):
        time.sleep(0.35)

expected = {
    ("VEDL", "30-Apr-2026"): "Demerger",
    ("ITC", "06-Jan-2025"): "Demerger",
    ("HINDUNILVR", "05-Dec-2025"): "Demerger",
    ("RELIANCE", "20-Jul-2023"): "Demerger",
    ("TMPV", "14-Oct-2025"): "Demerger",
}
checks = {
    f"{symbol}:{event_date}:{subject}": any(
        row.get("exDate") == event_date and row.get("subject") == subject
        for row in responses.get(symbol, [])
    )
    for (symbol, event_date), subject in expected.items()
}
result = {
    "source_page": PAGE,
    "source_endpoint": API,
    "retrieved_at_utc": datetime.now(timezone.utc).isoformat(),
    "query": {"index": "equities", **DATE_RANGE},
    "symbols_requested": symbols,
    "responses": responses,
    "errors": errors,
    "known_demerger_checks": checks,
}
OUT.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
event_count = sum(len(rows) for rows in responses.values())
print(
    f"symbols={len(symbols)} responses={len(responses)} errors={len(errors)} "
    f"nonempty={sum(bool(rows) for rows in responses.values())} events={event_count} "
    f"known_demerger_checks={sum(checks.values())}/{len(checks)} output={OUT}"
)
assert not errors, f"NSE request errors saved in {OUT}: {errors}"
assert all(checks.values()), f"Known demerger evidence missing; inspect {OUT}: {checks}"
