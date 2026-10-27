"""Capture official AMFI NAV history for the legacy LiquidBeES IDCW ETF."""

from __future__ import annotations

import csv
import json
from datetime import date, datetime, timezone
from pathlib import Path
from statistics import median

import requests

from capture_amfi_goldman_etf_nav import SCHEMES, _fetch


ROOT = Path(__file__).resolve().parents[1]
START = date(2019, 1, 1)
END = date(2026, 10, 23)
AMFI_SCHEME = ("140086", "Nippon India ETF Nifty 1D Rate Liquid BeES - DAILY IDCW Option", "INF732E01037")
CSV_PATH = ROOT / "outputs" / "liquidbees_amfi_nav_2019_2026.csv"
RAW_PATH = ROOT / "work" / "data" / "api_probes" / "liquidbees_amfi_nav_2019_2026.json"


def main() -> None:
    code, name, isin = AMFI_SCHEME
    SCHEMES.clear()
    SCHEMES[code] = (name, isin, "LIQUIDBEES")
    session = requests.Session()
    session.headers.update({"User-Agent": "quant-research-data-audit/1.0"})
    rows, requests_log = _fetch(session, 21, START, END)
    assert rows and all(row["scheme_code"] == code and row["isin"] == isin for row in rows)
    assert len({row["date"] for row in rows}) == len(rows)
    assert rows[0]["date"] <= "2019-01-02" and rows[-1]["date"] == END.isoformat()
    navs = [float(row["nav"]) for row in rows]
    fields = list(rows[0])
    CSV_PATH.parent.mkdir(parents=True, exist_ok=True)
    with CSV_PATH.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    RAW_PATH.parent.mkdir(parents=True, exist_ok=True)
    RAW_PATH.write_text(json.dumps({
        "source": "AMFI historical NAV endpoint",
        "endpoint": "https://portal.amfiindia.com/DownloadNAVHistoryReport_Po.aspx",
        "retrieved_at_utc": datetime.now(timezone.utc).isoformat(),
        "amfi_amc_selector": 21,
        "scheme_code": code,
        "scheme_name": name,
        "isin": isin,
        "requested_from": START.isoformat(),
        "requested_to": END.isoformat(),
        "requests": requests_log,
        "records": len(rows),
        "nav_min": min(navs),
        "nav_max": max(navs),
        "distinct_nav_values": len(set(navs)),
        "median_nav": median(navs),
        "rows": rows,
    }, indent=2), encoding="utf-8")
    print(f"Rows: {len(rows)}; windows: {len(requests_log)}; NAV range: {min(navs)}–{max(navs)}")
    print(f"Distinct NAVs: {len(set(navs))}; median NAV: {median(navs)}")
    print(f"CSV: {CSV_PATH.relative_to(ROOT)}; raw response log: {RAW_PATH.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
