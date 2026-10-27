"""Capture AMFI NAV history for the Goldman NIFTY/Gold ETFs and their 2016 successors."""

from __future__ import annotations

import hashlib
import json
import re
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from statistics import median

import requests
import csv


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "work" / "data" / "api_probes" / "etf_nav_lineage_2014_2026.json"
PRICE_RECONCILIATION_CSV = ROOT / "outputs" / "etf_nav_market_close_reconciliation.csv"
ENDPOINT = "https://portal.amfiindia.com/DownloadNAVHistoryReport_Po.aspx"
NIPPON_ENDPOINT = "https://mf.nipponindiaim.com/_vti_bin/RMF.Services/MobileAppService.svc/GetTrackNAVs"
START = date(2014, 1, 1)
MERGER_LAST_GOLDMAN_NAV = date(2016, 11, 3)
DATA_END = date(2026, 10, 23)
MONTHS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")
SPLIT_FACTOR = {"NIFTYBEES": 10, "GOLDBEES": 100}
NIPPON_SCHEMES = {
    503: ("140084", "NIFTYBEES", "INF204KB14I2"),
    495: ("140088", "GOLDBEES", "INF204KB17I5"),
}
SCHEMES = {
    "115728": ("Goldman Sachs Nifty Exchange Traded Scheme (GS Nifty BeES)", "INF732E01011", "NIFTYBEES"),
    "115744": ("Goldman Sachs Gold Exchange Traded Scheme (GS Gold BeES)", "INF732E01102", "GOLDBEES"),
    "140084": ("Nippon India ETF Nifty 50 BeES", "INF204KB14I2", "NIFTYBEES"),
    "140088": ("Nippon India ETF Gold BeES", "INF204KB17I5", "GOLDBEES"),
}


def _amfi_date(value: str) -> date:
    day, month, year = value.split("-")
    return date(int(year), MONTHS.index(month.title()) + 1, int(day))


def _date_text(value: date) -> str:
    return f"{value.day:02d}-{MONTHS[value.month - 1]}-{value.year}"


def _nippon_date(value: str) -> date:
    match = re.fullmatch(r"/Date\((\d+)([+-])(\d{2})(\d{2})\)/", value)
    assert match, f"Unexpected Nippon NAV date: {value}"
    milliseconds, sign, hours, minutes = match.groups()
    offset = (int(hours) * 60 + int(minutes)) * (1 if sign == "+" else -1)
    return (datetime.fromtimestamp(int(milliseconds) / 1000, timezone.utc) + timedelta(minutes=offset)).date()


def _fetch(session: requests.Session, amc_id: int, start: date, end: date) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    rows: dict[tuple[str, date], dict[str, object]] = {}
    requests_log = []
    cursor = start
    while cursor <= end:
        chunk_end = min(cursor + timedelta(days=89), end)
        response = session.get(ENDPOINT, params={
            "mf": str(amc_id), "frmdt": _date_text(cursor), "todt": _date_text(chunk_end),
        }, timeout=60)
        response.raise_for_status()
        lines = response.text.splitlines()
        assert lines and lines[0].startswith("Scheme Code;NAV Name;"), f"Unexpected AMFI header for {response.url}"
        matched = 0
        for line in lines[1:]:
            fields = line.split(";")
            if len(fields) != 8 or fields[0] not in SCHEMES:
                continue
            code, (name, isin, symbol) = fields[0], SCHEMES[fields[0]]
            day, nav = _amfi_date(fields[7]), float(fields[6])
            assert fields[1] == name and fields[4] == isin and nav > 0, f"AMFI scheme identity changed: {line}"
            assert cursor <= day <= chunk_end, f"NAV outside requested window: {line}"
            key = (code, day)
            assert key not in rows, f"Duplicate AMFI NAV for {code} on {day}"
            rows[key] = {
                "scheme_code": code, "scheme_name": name, "isin": isin, "etf": symbol,
                "nav": nav, "date": day.isoformat(), "source_amc_id": amc_id,
            }
            matched += 1
        requests_log.append({
            "url": response.url, "http_status": response.status_code,
            "requested_from": cursor.isoformat(), "requested_to": chunk_end.isoformat(),
            "response_bytes": len(response.content), "response_sha256": hashlib.sha256(response.content).hexdigest(),
            "matched_rows": matched,
        })
        cursor = chunk_end + timedelta(days=1)
    return [rows[key] for key in sorted(rows)], requests_log


def _fetch_nippon(session: requests.Session, scheme_id: int) -> list[dict[str, object]]:
    code, symbol, isin = NIPPON_SCHEMES[scheme_id]
    response = session.get(NIPPON_ENDPOINT, params={
        "SchemeIDs": str(scheme_id), "NAVPeriod": "Historical",
        "FromDate": START.isoformat(), "ToDate": DATA_END.isoformat(),
    }, timeout=60)
    response.raise_for_status()
    result = response.json()[0]
    assert result["ResponseMessage"] == "Success" and result["StatusCode"] == "0"
    rows = []
    for item in result["TrackNAVs"]:
        day, nav = _nippon_date(item["NAVDate"]), float(item["NAV"])
        assert item["AMFICode"] == code and nav > 0 and START <= day <= DATA_END
        rows.append({
            "scheme_code": code, "scheme_name": item["Scheme"], "isin": isin,
            "etf": symbol, "nav": nav, "date": day.isoformat(),
            "source_nippon_scheme_id": scheme_id,
        })
    rows.sort(key=lambda row: row["date"])
    assert rows and rows[0]["date"] == "2015-11-01" and rows[-1]["date"] == DATA_END.isoformat()
    assert len({row["date"] for row in rows}) == len(rows)
    return rows


def _price_close(symbol: str) -> dict[str, float]:
    name = ("NSE_EQ_INF204KB14I2-days-1-2014-01-01-2026-10-23.csv"
            if symbol == "NIFTYBEES" else "GOLDBEES-days-1-2014-01-01-2026-10-23.csv")
    path = ROOT / "work" / "data" / "etf_daily" / name
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return {row["time"][:10]: float(row["close"]) for row in csv.DictReader(handle)}


def main() -> None:
    session = requests.Session()
    session.headers.update({"User-Agent": "quant-research-data-audit/1.0"})
    goldman, goldman_requests = _fetch(session, 49, START, MERGER_LAST_GOLDMAN_NAV)
    successor, successor_requests = _fetch(session, 21, date(2016, 11, 4), date(2016, 11, 10))
    nippon = [row for scheme_id in NIPPON_SCHEMES for row in _fetch_nippon(session, scheme_id)]
    old_by_key = {(row["etf"], row["date"]): row["nav"] for row in goldman}
    current_by_key = {(row["etf"], row["date"]): row["nav"] for row in nippon}
    reconciliations = {}
    for symbol in SPLIT_FACTOR:
        overlap = sorted(set(old_by_key) & set(current_by_key) & {key for key in old_by_key if key[0] == symbol})
        differences = [abs(float(old_by_key[key]) - float(current_by_key[key])) for key in overlap]
        assert len(overlap) == 246 and overlap[0][1] == "2015-11-02" and overlap[-1][1] == "2016-11-03"
        assert max(differences) == 0, f"Goldman/Nippon overlap changed for {symbol}"
        reconciliations[symbol] = {
            "overlap_sessions": len(overlap), "first_overlap": overlap[0][1],
            "last_overlap": overlap[-1][1], "max_absolute_nav_difference": max(differences),
        }
    current_amfi = {(row["scheme_code"], row["date"]): row["nav"] for row in successor}
    for row in nippon:
        day = row["date"]
        if "2016-11-07" <= day <= "2016-11-10":
            assert abs(float(row["nav"]) - float(current_amfi[(row["scheme_code"], day)])) < 1e-9
    canonical = [row for row in goldman if row["date"] <= MERGER_LAST_GOLDMAN_NAV.isoformat()]
    canonical.extend(row for row in nippon if row["date"] > MERGER_LAST_GOLDMAN_NAV.isoformat())
    canonical.sort(key=lambda row: (row["etf"], row["date"]))
    for row in canonical:
        split = SPLIT_FACTOR[row["etf"]]
        row["split_factor_to_current_unit"] = split if row["date"] <= "2019-12-20" else 1
        row["nav_current_unit_basis"] = float(row["nav"]) / row["split_factor_to_current_unit"]
    price_reconciliation = {}
    price_reconciliation_rows = []
    for symbol, split in SPLIT_FACTOR.items():
        prices = _price_close(symbol)
        nav_by_date = {row["date"]: float(row["nav_current_unit_basis"])
                       for row in canonical if row["etf"] == symbol}
        market_dates = set(prices)
        nav_dates = set(nav_by_date)
        matched_dates = sorted(market_dates & nav_dates)
        rows = [{"date": day, "nav": nav_by_date[day]} for day in matched_dates]
        premiums = sorted(100 * (prices[row["date"]] / row["nav"] - 1) for row in rows)
        assert len(rows) > 2500
        price_reconciliation[symbol] = {
            "market_sessions": len(market_dates), "nav_sessions": len(nav_dates),
            "matched_sessions": len(rows), "first_matched_date": rows[0]["date"],
            "last_matched_date": rows[-1]["date"], "split_factor": split,
            "market_sessions_without_nav": len(market_dates - nav_dates),
            "nav_dates_without_market": len(nav_dates - market_dates),
            "median_market_premium_pct": median(premiums),
            "p05_market_premium_pct": premiums[int(0.05 * (len(premiums) - 1))],
            "p95_market_premium_pct": premiums[int(0.95 * (len(premiums) - 1))],
        }
        price_reconciliation_rows.append({"etf": symbol, **price_reconciliation[symbol]})
    with PRICE_RECONCILIATION_CSV.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(price_reconciliation_rows[0]))
        writer.writeheader()
        writer.writerows(price_reconciliation_rows)
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps({
        "source": "AMFI official historical NAV endpoint and Nippon first-party NAV history service",
        "endpoint": ENDPOINT,
        "retrieved_at_utc": datetime.now(timezone.utc).isoformat(),
        "goldman_amc_selector": 49,
        "nippon_amc_selector": 21,
        "goldman_last_nav_date": MERGER_LAST_GOLDMAN_NAV.isoformat(),
        "nippon_endpoint": NIPPON_ENDPOINT,
        "nippon_scheme_ids": {str(k): v[0] for k, v in NIPPON_SCHEMES.items()},
        "records": len(canonical),
        "goldman_amfi_requests": goldman_requests,
        "successor_amfi_requests": successor_requests,
        "goldman_nippon_overlap_reconciliation": reconciliations,
        "market_price_reconciliation": price_reconciliation,
        "goldman_rows": goldman,
        "nippon_rows": nippon,
        "successor_amfi_rows": successor,
        "canonical_split_adjusted_nav_rows": canonical,
    }, indent=2), encoding="utf-8")
    print(f"Goldman NAV rows: {len(goldman)}; Nippon service rows: {len(nippon)}; canonical NAV rows: {len(canonical)}")
    print(f"Overlap: {reconciliations}")
    print(f"Price reconciliation: {price_reconciliation}")
    print(f"Price summary: {PRICE_RECONCILIATION_CSV.relative_to(ROOT)}")
    print(f"Output: {OUTPUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
