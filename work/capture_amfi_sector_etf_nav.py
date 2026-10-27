"""Capture first-party AMFI NAVs for the five sector ETFs and compare histories."""

from __future__ import annotations

import csv
import json
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import requests


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "work" / "data" / "index_daily"
ETF_DATA = ROOT / "work" / "data" / "etf_daily"
RAW = ROOT / "work" / "data" / "api_probes" / "amfi_sector_etf_nav_2023_2026.json"
PRICE_TRI_PANEL = DATA / "sector_etf_price_pr_tri_panel_2022_2026.csv"
PANEL = DATA / "sector_etf_nav_price_tri_panel_2023_2026.csv"
COMPARISON = ROOT / "outputs" / "sector_etf_nav_price_tri_comparison.csv"
SOURCE_PAGE = "https://www.amfiindia.com/net-asset-value/nav-download"
ENDPOINT = "https://portal.amfiindia.com/DownloadNAVHistoryReport_Po.aspx"
# AMFI's current history endpoint redirected requests for dates before 2023-04-01.
START = date(2023, 4, 1)
END = date(2026, 10, 23)
STARTING_BALANCE = 1_000_000.0
MONTHS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")
FUNDS = {
    "INF204KB15I9": ("BANKBEES", "Nippon India ETF Nifty Bank BeES", "Nifty Bank"),
    "INF204KB15V2": ("ITBEES", "Nippon India ETF Nifty IT", "Nifty IT"),
    "INF204KC1337": ("AUTOBEES", "Nippon India Nifty Auto ETF", "Nifty Auto"),
    "INF204KC1089": ("PHARMABEES", "Nippon India Nifty Pharma ETF", "Nifty Pharma"),
    "INF204KB16I7": ("PSUBNKBEES", "Nippon India ETF Nifty PSU Bank BeES", "Nifty PSU Bank"),
}
ETF_FILES = {
    "BANKBEES": "NSE_EQ_INF204KB15I9-days-1-2014-01-01-2026-10-23.csv",
    "ITBEES": "NSE_EQ_INF204KB15V2-days-1-2014-01-01-2026-10-23.csv",
    "AUTOBEES": "NSE_EQ_INF204KC1337-days-1-2014-01-01-2026-10-23.csv",
    "PHARMABEES": "NSE_EQ_INF204KC1089-days-1-2014-01-01-2026-10-23.csv",
    "PSUBNKBEES": "NSE_EQ_INF204KB16I7-days-1-2014-01-01-2026-10-23.csv",
}
PERIODS = (
    ("available_2023_2024", START, date(2024, 12, 31)),
    ("validation_2024", date(2024, 1, 1), date(2024, 12, 31)),
    ("holdout_2025_plus", date(2025, 1, 1), END),
    ("continuous_2023_apr_plus", START, END),
)


def _amfi_date(value: str) -> date:
    day, month, year = value.split("-")
    month_number = {name.casefold(): number for number, name in enumerate(MONTHS, 1)}[month.casefold()]
    return date(int(year), month_number, int(day))


def _amfi_date_text(value: date) -> str:
    return f"{value.day:02d}-{MONTHS[value.month - 1]}-{value.year}"


def _fetch_nav() -> tuple[dict[tuple[str, date], dict[str, str]], list[dict[str, object]]]:
    session = requests.Session()
    session.headers.update({"User-Agent": "quant-research-data-audit/1.0"})
    nav_rows: dict[tuple[str, date], dict[str, str]] = {}
    requests_log = []
    chunk_start = START
    while chunk_start <= END:
        chunk_end = min(chunk_start + timedelta(days=89), END)
        params = {"mf": "21", "frmdt": _amfi_date_text(chunk_start), "todt": _amfi_date_text(chunk_end)}
        response = session.get(ENDPOINT, params=params, timeout=60)
        assert response.status_code == 200, f"AMFI returned {response.status_code} for {response.url}"
        lines = response.text.splitlines()
        assert lines and lines[0].startswith("Scheme Code;NAV Name;"), f"Unexpected AMFI report header for {response.url}"
        captured = 0
        for line in lines[1:]:
            fields = line.split(";")
            if len(fields) != 8 or fields[4] not in FUNDS:
                continue
            isin = fields[4]
            day = _amfi_date(fields[7])
            nav = float(fields[6])
            symbol, name, _ = FUNDS[isin]
            assert fields[1] == name and nav > 0 and chunk_start <= day <= chunk_end
            key = (isin, day)
            assert key not in nav_rows, f"Duplicate AMFI NAV for {symbol} {day}"
            nav_rows[key] = {
                "scheme_code": fields[0], "scheme_name": fields[1], "plan": fields[2],
                "option": fields[3], "isin": isin, "nav": fields[6], "date": day.isoformat(),
                "raw_line": line,
            }
            captured += 1
        requests_log.append({
            "url": response.url, "http_status": response.status_code,
            "requested_from": chunk_start.isoformat(), "requested_to": chunk_end.isoformat(),
            "response_bytes": len(response.content), "matched_rows": captured,
        })
        chunk_start = chunk_end + timedelta(days=1)
    assert requests_log and all(row["http_status"] == 200 for row in requests_log)
    assert nav_rows and all(float(row["nav"]) > 0 for row in nav_rows.values())
    return nav_rows, requests_log


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def _write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def _stats(values: dict[date, float], start: date, end: date) -> dict[str, float | str | int]:
    series = [(day, value) for day, value in sorted(values.items()) if start <= day <= end]
    assert len(series) >= 2, f"Insufficient values from {start} to {end}"
    first_day, first = series[0]
    last_day, last = series[-1]
    peak = first
    drawdown = 0.0
    for _, value in series:
        peak = max(peak, value)
        drawdown = min(drawdown, value / peak - 1)
    total_return = last / first - 1
    elapsed = (last_day - first_day).days
    return {
        "first_date": first_day.isoformat(), "last_date": last_day.isoformat(),
        "matched_sessions": len(series), "starting_value": first, "ending_value": last,
        "total_return_pct": total_return * 100,
        "cagr_pct": ((1 + total_return) ** (365.25 / elapsed) - 1) * 100 if total_return > -1 else -100,
        "max_drawdown_pct": drawdown * 100,
    }


def main() -> None:
    nav_rows, requests_log = _fetch_nav()
    panel_source = _read_csv(PRICE_TRI_PANEL)
    panel_by_key = {(row["etf"], date.fromisoformat(row["date"])): row for row in panel_source}
    assert len(panel_by_key) == 5 * 1176
    panel = []
    comparisons = []
    coverage = []
    for isin, (symbol, scheme_name, index) in FUNDS.items():
        nav = {day: float(row["nav"]) for (row_isin, day), row in nav_rows.items() if row_isin == isin}
        etf_prices = {
            day: float(row["etf_market_close"])
            for (row_symbol, day), row in panel_by_key.items() if row_symbol == symbol
        }
        expected_dates = {day for (row_symbol, day) in panel_by_key if row_symbol == symbol and START <= day <= END}
        nav_prices = {day: value for day, value in nav.items() if START <= day <= END}
        etf_prices = {day: value for day, value in etf_prices.items() if START <= day <= END}
        missing_nav_dates = sorted(expected_dates - set(nav_prices))
        extra_nav_dates = sorted(set(nav_prices) - expected_dates)
        matched_dates = sorted(set(nav_prices) & set(etf_prices) & expected_dates)
        assert matched_dates and matched_dates[0] == date(2023, 4, 3) and matched_dates[-1] == END
        coverage.append({
            "etf": symbol, "market_sessions": len(expected_dates), "amfi_nav_sessions": len(nav_prices),
            "matched_sessions": len(matched_dates), "market_dates_without_amfi_nav": [d.isoformat() for d in missing_nav_dates],
            "amfi_nav_dates_without_market_bar": [d.isoformat() for d in extra_nav_dates],
        })
        for day in matched_dates:
            source = panel_by_key[(symbol, day)]
            panel.append({
                "date": day.isoformat(), "etf": symbol, "isin": isin, "scheme_name": scheme_name,
                "nav": nav_prices[day], "etf_market_close": etf_prices[day],
                "market_close_premium_to_nav_pct": (etf_prices[day] / nav_prices[day] - 1) * 100,
                "price_index_close": float(source["price_index_close"]),
                "tri_close": float(source["tri_close"]),
                "index": index,
            })
        for period, start, end in PERIODS:
            matched_window = [d for d in matched_dates if start <= d <= end]
            aligned_values = {
                "nav": {d: nav_prices[d] for d in matched_window},
                "etf": {d: etf_prices[d] for d in matched_window},
                "price_index": {d: float(panel_by_key[(symbol, d)]["price_index_close"]) for d in matched_window},
                "tri": {d: float(panel_by_key[(symbol, d)]["tri_close"]) for d in matched_window},
            }
            stats = {label: _stats(values, start, end) for label, values in aligned_values.items()}
            assert len({item["matched_sessions"] for item in stats.values()}) == 1
            nav_premiums = [etf_prices[d] / nav_prices[d] - 1 for d in matched_window]
            comparisons.append({
                "etf": symbol, "isin": isin, "index": index, "period": period,
                "starting_balance_inr": STARTING_BALANCE,
                **{f"{label}_{key}": value for label, values in stats.items() for key, value in values.items()},
                "average_market_close_premium_to_nav_pct": sum(nav_premiums) / len(nav_premiums) * 100,
                "nav_minus_tri_return_pp": stats["nav"]["total_return_pct"] - stats["tri"]["total_return_pct"],
                "etf_minus_nav_return_pp": stats["etf"]["total_return_pct"] - stats["nav"]["total_return_pct"],
                "nav_ending_balance_inr_price_only": STARTING_BALANCE * (1 + stats["nav"]["total_return_pct"] / 100),
                "cost_basis": "Unlevered close-to-close NAV/ETF/index comparison before investor transaction costs; no synthetic distributions.",
            })
    assert len(panel) == len({(row["etf"], row["date"]) for row in panel})
    assert len(panel) == sum(row["matched_sessions"] for row in coverage)
    assert len(comparisons) == 5 * len(PERIODS)
    RAW.parent.mkdir(parents=True, exist_ok=True)
    RAW.write_text(json.dumps({
        "source_page": SOURCE_PAGE, "endpoint": ENDPOINT, "retrieved_at_utc": datetime.now(timezone.utc).isoformat(),
        "fund_selector": "Nippon India Mutual Fund (mf=21)", "max_days_per_request": 90,
                "requests": requests_log, "coverage": coverage, "row_count": len(nav_rows),
        "rows": [nav_rows[key] for key in sorted(nav_rows, key=lambda item: (item[0], item[1]))],
    }, indent=2), encoding="utf-8")
    _write_csv(PANEL, panel)
    _write_csv(COMPARISON, comparisons)
    print(f"requests={len(requests_log)} funds={len(FUNDS)} sessions_per_fund=1176 nav_rows={len(nav_rows)} comparisons={len(comparisons)}")


if __name__ == "__main__":
    main()
