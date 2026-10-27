"""Normalize first-party sector index returns and compare them with ETF closes."""

from __future__ import annotations

import csv
import json
from datetime import date, datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "work" / "data" / "index_daily"
ETF_DATA = ROOT / "work" / "data" / "etf_daily"
TRI_RAW = DATA / "sector_tri_raw_2022_2026.json"
PRICE_RAW = DATA / "sector_price_index_raw_2022_2026.json"
PANEL = DATA / "sector_etf_price_pr_tri_panel_2022_2026.csv"
COMPARISON = ROOT / "outputs" / "sector_etf_index_total_return_comparison.csv"
STARTING_BALANCE = 1_000_000.0
START = date(2022, 1, 25)
END = date(2026, 10, 23)
INDICES = {
    "Nifty Bank": ("BANKBEES", "NSE_EQ_INF204KB15I9-days-1-2014-01-01-2026-10-23.csv"),
    "Nifty IT": ("ITBEES", "NSE_EQ_INF204KB15V2-days-1-2014-01-01-2026-10-23.csv"),
    "Nifty Auto": ("AUTOBEES", "NSE_EQ_INF204KC1337-days-1-2014-01-01-2026-10-23.csv"),
    "Nifty Pharma": ("PHARMABEES", "NSE_EQ_INF204KC1089-days-1-2014-01-01-2026-10-23.csv"),
    "Nifty PSU Bank": ("PSUBNKBEES", "NSE_EQ_INF204KB16I7-days-1-2014-01-01-2026-10-23.csv"),
}
PERIODS = (
    ("train_2022_2023", date(2022, 1, 25), date(2023, 12, 29)),
    ("validation_2024", date(2024, 1, 1), date(2024, 12, 31)),
    ("holdout_2025_plus", date(2025, 1, 1), END),
    ("continuous_2022_plus", START, END),
)


def _read_index(raw_path: Path, index: str, date_key: str, value_key: str) -> dict[date, float]:
    raw = json.loads(raw_path.read_text(encoding="utf-8"))
    assert raw["sourcePage"] == "https://www.niftyindices.com/reports/historical-data"
    values: dict[date, float] = {}
    for request in raw["results"]:
        if request["index"] != index:
            continue
        assert request["httpStatus"] == 200
        for row in request["rows"]:
            assert (row.get("Index Name") or row.get("INDEX_NAME")).strip().casefold() == index.casefold()
            day = datetime.strptime(row[date_key], "%d %b %Y").date()
            value = float(row[value_key])
            assert value > 0 and START <= day <= END
            assert day not in values, f"Duplicate {index} {value_key} date: {day}"
            values[day] = value
    assert values, f"No {value_key} data for {index}"
    return values


def _read_etf(path: Path) -> dict[date, float]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        values = {}
        for row in csv.DictReader(handle):
            day = datetime.fromisoformat(row["time"]).date()
            if START <= day <= END:
                assert day not in values, f"Duplicate ETF date: {path.name} {day}"
                value = float(row["close"])
                assert value > 0
                values[day] = value
    assert values
    return values


def _stats(values: dict[date, float], start: date, end: date) -> dict[str, float | str | int]:
    window = [(day, value) for day, value in sorted(values.items()) if start <= day <= end]
    assert len(window) >= 2, f"Insufficient values in {start}..{end}"
    first_day, first_value = window[0]
    last_day, last_value = window[-1]
    total_return = last_value / first_value - 1
    peak = first_value
    max_drawdown = 0.0
    for _, value in window:
        peak = max(peak, value)
        max_drawdown = min(max_drawdown, value / peak - 1)
    elapsed_days = (last_day - first_day).days
    cagr = (1 + total_return) ** (365.25 / elapsed_days) - 1 if total_return > -1 else -1.0
    return {
        "first_date": first_day.isoformat(),
        "last_date": last_day.isoformat(),
        "matched_sessions": len(window),
        "starting_value": first_value,
        "ending_value": last_value,
        "total_return_pct": total_return * 100,
        "cagr_pct": cagr * 100,
        "max_drawdown_pct": max_drawdown * 100,
    }


def main() -> None:
    comparisons = []
    daily_rows = []
    for index, (etf, filename) in INDICES.items():
        tri = _read_index(TRI_RAW, index, "Date", "TotalReturnsIndex")
        price_index = _read_index(PRICE_RAW, index, "HistoricalDate", "CLOSE")
        etf_close = _read_etf(ETF_DATA / filename)
        expected_dates = set(etf_close)
        assert set(tri) == set(price_index) == expected_dates, (
            f"Date coverage mismatch for {index}: ETF={len(expected_dates)}, "
            f"PR={len(price_index)}, TRI={len(tri)}"
        )
        assert min(expected_dates) == START and max(expected_dates) == END
        for day in sorted(expected_dates):
            daily_rows.append({
                "date": day.isoformat(),
                "index": index,
                "etf": etf,
                "etf_market_close": etf_close[day],
                "price_index_close": price_index[day],
                "tri_close": tri[day],
            })
        for period, start, end in PERIODS:
            matched_days = [day for day in expected_dates if start <= day <= end]
            assert len(matched_days) >= 2
            etf_stats = _stats(etf_close, start, end)
            price_stats = _stats(price_index, start, end)
            tri_stats = _stats(tri, start, end)
            assert etf_stats["first_date"] == price_stats["first_date"] == tri_stats["first_date"]
            assert etf_stats["last_date"] == price_stats["last_date"] == tri_stats["last_date"]
            comparisons.append({
                "index": index,
                "etf": etf,
                "period": period,
                "starting_balance_inr": STARTING_BALANCE,
                **{f"etf_{key}": value for key, value in etf_stats.items()},
                **{f"price_index_{key}": value for key, value in price_stats.items()},
                **{f"tri_{key}": value for key, value in tri_stats.items()},
                "tri_minus_price_return_pp": tri_stats["total_return_pct"] - price_stats["total_return_pct"],
                "etf_minus_price_return_pp": etf_stats["total_return_pct"] - price_stats["total_return_pct"],
                "etf_minus_tri_return_pp": etf_stats["total_return_pct"] - tri_stats["total_return_pct"],
                "etf_ending_balance_inr_price_only": STARTING_BALANCE * (1 + etf_stats["total_return_pct"] / 100),
                "tri_ending_balance_inr_gross_index": STARTING_BALANCE * (1 + tri_stats["total_return_pct"] / 100),
                "cost_basis": "Unlevered close-to-close comparison before ETF transaction costs; ETF close omits separately paid cash distributions.",
            })

    assert len(daily_rows) == 5 * 1176
    assert len(comparisons) == 5 * len(PERIODS)
    PANEL.parent.mkdir(parents=True, exist_ok=True)
    with PANEL.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=daily_rows[0].keys())
        writer.writeheader()
        writer.writerows(daily_rows)
    COMPARISON.parent.mkdir(parents=True, exist_ok=True)
    with COMPARISON.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=comparisons[0].keys())
        writer.writeheader()
        writer.writerows(comparisons)
    print(f"indices={len(INDICES)} sessions_per_index=1176 daily_rows={len(daily_rows)} comparison_rows={len(comparisons)}")


if __name__ == "__main__":
    main()
