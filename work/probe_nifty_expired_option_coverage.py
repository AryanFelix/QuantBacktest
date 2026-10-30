"""Probe date-stratified NIFTY expired-option contract availability."""

from __future__ import annotations

import csv
import json
from datetime import date, datetime, timezone
from pathlib import Path

import upstox_quant as q


ROOT = Path(__file__).resolve().parents[1]
UNDERLYING = "NSE_INDEX|Nifty 50"
EXPIRIES = [
    date(2022, 1, 27), date(2022, 6, 30), date(2022, 12, 29),
    date(2023, 6, 29), date(2023, 12, 28),
    date(2024, 10, 31), date(2026, 9, 29),
]
CSV_PATH = ROOT / "outputs" / "nifty_expired_option_contract_history_probe.csv"
RAW_PATH = ROOT / "work" / "data" / "api_probes" / "nifty_expired_option_contract_history_probe.json"


def main() -> None:
    rows = []
    raw = []
    for expiry in EXPIRIES:
        try:
            contracts = q.fetch_expired_contracts(UNDERLYING, expiry, "option")
        except Exception as error:
            rows.append({
                "underlying": UNDERLYING, "expiry": expiry.isoformat(), "status": "request_error",
                "contract_count": 0, "call_count": 0, "put_count": 0, "weekly_count": 0,
                "sample_instrument_key": "", "error": f"{type(error).__name__}: {error}"[:240],
            })
            raw.append({"expiry": expiry.isoformat(), "status": "request_error", "error": rows[-1]["error"]})
            continue
        assert isinstance(contracts, list)
        for contract in contracts:
            assert contract["underlying_key"] == UNDERLYING
            assert date.fromisoformat(contract["expiry"]) == expiry
            assert contract["instrument_type"] in {"CE", "PE"}
        calls = [item for item in contracts if item["instrument_type"] == "CE"]
        puts = [item for item in contracts if item["instrument_type"] == "PE"]
        rows.append({
            "underlying": UNDERLYING, "expiry": expiry.isoformat(), "status": "success",
            "contract_count": len(contracts), "call_count": len(calls), "put_count": len(puts),
            "weekly_count": sum(bool(item.get("weekly")) for item in contracts),
            "sample_instrument_key": contracts[0]["instrument_key"] if contracts else "", "error": "",
        })
        raw.append({"expiry": expiry.isoformat(), "status": "success", "contracts": contracts})
    fields = list(rows[0])
    CSV_PATH.parent.mkdir(parents=True, exist_ok=True)
    with CSV_PATH.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    RAW_PATH.parent.mkdir(parents=True, exist_ok=True)
    RAW_PATH.write_text(json.dumps({
        "source": "Upstox expired option contracts endpoint",
        "underlying": UNDERLYING, "retrieved_at_utc": datetime.now(timezone.utc).isoformat(),
        "results": raw,
    }, indent=2), encoding="utf-8")
    for row in rows:
        print(f"{row['expiry']}: {row['status']}; contracts={row['contract_count']}; calls={row['call_count']}; puts={row['put_count']}")
    print(f"CSV: {CSV_PATH.relative_to(ROOT)}; raw response: {RAW_PATH.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
