import csv
import json
from datetime import date, datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "work" / "data" / "index_daily"
RAW = DATA / "nifty50_tri_raw_2020_2026.json"
RAW_FULL = DATA / "nifty50_tri_raw_2014_2026.json"
TRI = DATA / "NIFTY50TR-days-1-2020-01-01-2026-10-23.csv"
TRI_FULL = DATA / "NIFTY50TR-days-1-2014-01-01-2026-10-23.csv"
PRICE = DATA / "NIFTY50-days-1-2014-01-01-2026-10-23.csv"
SCREEN = ROOT / "outputs" / "stock_momentum_action_aware_screen.csv"
COMPARISON = ROOT / "outputs" / "stock_momentum_benchmark_comparison.csv"
CAPITAL = 1_000_000.0


source_files = [DATA / f"nifty50_tri_nse_ui_{year}.json" for year in range(2014, 2020)] + [RAW]
raw_rows = []
for source in source_files:
    assert source.is_file(), f"Missing official NSE TRI source window: {source.name}"
    window = json.loads(source.read_text(encoding="utf-8"))
    assert window, f"Empty official NSE TRI source window: {source.name}"
    if source.name.startswith("nifty50_tri_nse_ui_"):
        year = int(source.stem[-4:])
        assert {datetime.strptime(row["Date"], "%d %b %Y").year for row in window} == {year}
    raw_rows.extend(window)

all_tri = {}
rows_by_day = {}
for row in raw_rows:
    day = datetime.strptime(row["Date"], "%d %b %Y").date()
    assert day not in all_tri, f"Duplicate NIFTY 50 TR date: {day}"
    assert row["Index Name"].strip().upper() == "NIFTY 50"
    tr, ntr = float(row["TotalReturnsIndex"]), float(row["NTR_Value"])
    assert tr > 0 and ntr > 0
    all_tri[day] = (tr, ntr)
    rows_by_day[day] = row

with PRICE.open(encoding="utf-8-sig", newline="") as handle:
    price_dates = {
        datetime.fromisoformat(row["time"]).date()
        for row in csv.DictReader(handle)
    }
assert set(all_tri) == price_dates, (
    f"Full-history TR dates must match NIFTY 50 price dates; {len(set(all_tri) - price_dates)} extra, "
    f"{len(price_dates - set(all_tri))} missing"
)
assert min(all_tri) == date(2014, 1, 1) and max(all_tri) == date(2026, 10, 23)
assert len(all_tri) == len(price_dates)

RAW_FULL.write_text(
    json.dumps([rows_by_day[day] for day in sorted(rows_by_day, reverse=True)], ensure_ascii=False, indent=2) + "\n",
    encoding="utf-8",
)
with TRI_FULL.open("w", encoding="utf-8", newline="") as handle:
    writer = csv.writer(handle)
    writer.writerow(["date", "tri", "ntr"])
    writer.writerows((day.isoformat(), *all_tri[day]) for day in sorted(all_tri))

tri = {
    day: values for day, values in all_tri.items()
    if date(2020, 1, 1) <= day <= date(2026, 10, 23)
}
price_dates_2020_onward = {day for day in price_dates if date(2020, 1, 1) <= day <= date(2026, 10, 23)}
assert set(tri) == price_dates_2020_onward, (
    f"Existing 2020+ TR dates must match NIFTY 50 price dates; {len(set(tri) - price_dates_2020_onward)} extra, "
    f"{len(price_dates_2020_onward - set(tri))} missing"
)
assert min(tri) == date(2020, 1, 1) and max(tri) == date(2026, 10, 23)

with TRI.open("w", encoding="utf-8", newline="") as handle:
    writer = csv.writer(handle)
    writer.writerow(["date", "tri", "ntr"])
    writer.writerows((day.isoformat(), *tri[day]) for day in sorted(tri))


def metrics(values: list[float], start: date, end: date) -> tuple[float, float, float]:
    start_value, end_value = values[0], values[-1]
    total_return = end_value / start_value - 1
    elapsed_days = (end - start).days
    cagr = (end_value / start_value) ** (365.25 / elapsed_days) - 1
    peak = values[0]
    max_drawdown = 0.0
    for value in values:
        peak = max(peak, value)
        max_drawdown = min(max_drawdown, value / peak - 1)
    return total_return, cagr, max_drawdown


with SCREEN.open(encoding="utf-8-sig", newline="") as handle:
    screen_rows = list(csv.DictReader(handle))
candidate_rows = [
    row for row in screen_rows
    if row["strategy"].startswith("stock_top10_mom12_1_trend200_market200@95%_full_universe")
]
periods = {}
for row in candidate_rows:
    period = row["period"]
    window = (date.fromisoformat(row["period_start"]), date.fromisoformat(row["period_end"]))
    assert period not in periods or periods[period] == window
    periods[period] = window
assert len(candidate_rows) == 12 and len(periods) == 4

comparison = []
for period, (requested_start, requested_end) in periods.items():
    window = [(day, values) for day, values in sorted(tri.items()) if requested_start <= day <= requested_end]
    assert window, f"No official TRI values for {period}"
    days = [item[0] for item in window]
    for offset, field, label in ((0, "tri", "NIFTY 50 Total Return"), (1, "ntr", "NIFTY 50 Net Total Return")):
        values = [item[1][offset] for item in window]
        total_return, cagr, max_drawdown = metrics(values, days[0], days[-1])
        comparison.append({
            "row_type": "official_index",
            "scenario": label,
            "period": period,
            "period_start": days[0].isoformat(),
            "period_end": days[-1].isoformat(),
            "starting_balance_inr": CAPITAL,
            "ending_balance_inr": CAPITAL * (1 + total_return),
            "total_return_pct": 100 * total_return,
            "cagr_pct": 100 * cagr,
            "max_drawdown_pct": 100 * max_drawdown,
            "fees_inr": "",
            "slippage_cost_inr": "",
            "trade_count": "",
            "slippage_bps_per_side": "",
            "model_basis": "Official index series; dividends reinvested for TR. NTR uses publisher's stated tax assumptions. No direct ETF costs.",
        })
    for row in candidate_rows:
        if row["period"] == period:
            comparison.append({
                "row_type": "strategy_screen",
                "scenario": row["strategy"],
                "period": period,
                "period_start": row["period_start"],
                "period_end": row["period_end"],
                "starting_balance_inr": row["starting_balance_inr"],
                "ending_balance_inr": row["ending_balance_inr"],
                "total_return_pct": row["total_return_pct"],
                "cagr_pct": row["cagr_pct"],
                "max_drawdown_pct": row["max_drawdown_pct"],
                "fees_inr": row["fees_inr"],
                "slippage_cost_inr": row["slippage_cost_inr"],
                "trade_count": row["trade_count"],
                "slippage_bps_per_side": row["slippage_bps_per_side"],
                "model_basis": "Exploratory stock screen; charges/slippage included, corporate-action ledger incomplete.",
            })

assert len(comparison) == 20
fields = list(comparison[0])
with COMPARISON.open("w", encoding="utf-8", newline="") as handle:
    writer = csv.DictWriter(handle, fieldnames=fields)
    writer.writeheader()
    writer.writerows(comparison)

print(
    f"tri_rows={len(tri)} full_tri_rows={len(all_tri)} first={min(all_tri)} last={max(all_tri)} "
    f"matched_price_dates=yes comparison_rows={len(comparison)}"
)
