import csv
import json
import math
from datetime import date
from pathlib import Path

from upstox_quant import ROOT, _intraday_orb, _read_prices


DATA = ROOT / "work" / "data" / "intraday"
SIGNAL_PATH = DATA / "NSE_INDEX_Nifty_50-minutes-30-2022-01-01-2026-10-23.csv"
TRADE_PATH = DATA / "NSE_EQ_INF204KB14I2-minutes-30-2022-01-01-2026-10-23.csv"
RUN_ROOT = ROOT / "work" / "backtests" / "intraday_orb_range_sensitivity"
OUTPUT = ROOT / "outputs" / "intraday_orb_range_sensitivity.csv"
LEDGER = ROOT / "outputs" / "backtest_summary.csv"
CAPITAL = 1_000_000.0
RISK_FRACTION = 0.005
MAX_EXPOSURE = 0.95
DRAWNDOWN_LIMIT = 20.0
RANGE_THRESHOLDS = (0.0, 0.30, 0.40, 0.50)
SLIPPAGE_LEVELS = (10.0, 25.0, 50.0, 100.0)
PERIODS = (
    ("train", date(2022, 1, 3), date(2023, 12, 29)),
    ("validation", date(2024, 1, 1), date(2024, 12, 31)),
    ("holdout", date(2025, 1, 1), date(2026, 10, 23)),
    ("full", date(2022, 1, 3), date(2026, 10, 23)),
)


signals, _ = _read_prices([f"NIFTY50={SIGNAL_PATH}"])
trades, _ = _read_prices([f"NIFTYBEES={TRADE_PATH}"])
signal_bars = next(iter(signals.values()))
trade_bars = next(iter(trades.values()))
baseline_ledger = list(csv.DictReader(LEDGER.open(encoding="utf-8-sig", newline="")))
rows = []

for threshold in RANGE_THRESHOLDS:
    for slippage in SLIPPAGE_LEVELS:
        for period, start, end in PERIODS:
            equity, order_rows, stats = _intraday_orb(
                signal_bars,
                trade_bars,
                CAPITAL,
                risk_fraction=RISK_FRACTION,
                max_exposure=MAX_EXPOSURE,
                slippage_bps=slippage,
                drawdown_limit_pct=DRAWNDOWN_LIMIT,
                mode="long",
                start=start,
                end=end,
                min_opening_range_pct=threshold,
                fee_product="equity_fund_intraday",
            )
            key = f"long_min{threshold:.2f}_slip{slippage:g}_{period}"
            run_dir = RUN_ROOT / key
            run_dir.mkdir(parents=True, exist_ok=True)
            equity.to_csv(run_dir / "equity.csv", index_label="time")
            order_rows.to_csv(run_dir / "trades.csv", index=False)
            stats.update({
                "strategy": "NIFTY 30m opening-range breakout, long-only",
                "period": period,
                "period_start": start.isoformat(),
                "period_end": end.isoformat(),
                "minimum_opening_range_pct": threshold,
                "slippage_bps_per_side": slippage,
            })
            (run_dir / "summary.json").write_text(json.dumps(stats, indent=2), encoding="utf-8")
            rows.append({
                "strategy": "NIFTY 30m opening-range breakout, long-only",
                "mode": "long",
                "min_opening_range_pct": threshold,
                "period": period,
                "period_start": start.isoformat(),
                "period_end": end.isoformat(),
                "starting_balance_inr": stats["starting_balance_inr"],
                "ending_balance_inr": stats["ending_balance_inr"],
                "total_return_pct": stats["total_return_pct"],
                "cagr_pct": stats["cagr_pct"],
                "max_drawdown_pct": stats["max_drawdown_pct"],
                "sharpe_zero_rf": stats["sharpe_zero_rf"],
                "within_20pct": stats["within_drawdown_limit"],
                "slippage_bps_per_side": slippage,
                "fees_inr": stats["total_fees_inr"],
                "slippage_cost_inr": stats["total_slippage_inr"],
                "trade_count": stats["trade_count"],
                "order_count": stats["order_count"],
                "eligible_sessions": stats["eligible_sessions"],
                "range_filtered_sessions": stats["range_filter_sessions"],
                "source_artifact": f"{run_dir.relative_to(ROOT).as_posix()}/summary.json",
            })

assert len(rows) == len(RANGE_THRESHOLDS) * len(SLIPPAGE_LEVELS) * len(PERIODS) == 64
baseline = {
    (row["period"], float(row["slippage_bps_per_side"])): float(row["total_return_pct"])
    for row in baseline_ledger
    if row["simulation_type"] == "intraday_orb"
    and row["strategy"] == "NIFTY 30m opening-range breakout (long)"
}
for row in rows:
    if (row["min_opening_range_pct"] == 0.0 and row["slippage_bps_per_side"] == 10.0
            and (row["period"], 10.0) in baseline):
        assert math.isclose(
            row["total_return_pct"],
            baseline[(row["period"], 10.0)],
            rel_tol=0,
            abs_tol=1e-8,
        ), f"Baseline mismatch for {row['period']}"

fields = list(rows[0])
with OUTPUT.open("w", encoding="utf-8", newline="") as handle:
    writer = csv.DictWriter(handle, fieldnames=fields)
    writer.writeheader()
    writer.writerows(rows)

print(f"cases={len(rows)} range_thresholds={RANGE_THRESHOLDS} slippage_levels_bps={SLIPPAGE_LEVELS}")
