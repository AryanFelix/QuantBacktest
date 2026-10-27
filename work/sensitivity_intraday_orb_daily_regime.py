"""Compare the NIFTY intraday ORB with a prior-close 200-day regime gate."""

from __future__ import annotations

import csv
import json
import math
from datetime import date
from pathlib import Path

import pandas as pd

import upstox_quant as q


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "work" / "data"
SIGNAL_PATH = DATA / "intraday" / "NSE_INDEX_Nifty_50-minutes-30-2022-01-01-2026-10-23.csv"
TRADE_PATH = DATA / "intraday" / "NSE_EQ_INF204KB14I2-minutes-30-2022-01-01-2026-10-23.csv"
DAILY_PATH = DATA / "index_daily" / "NIFTY50-days-1-2014-01-01-2026-10-23.csv"
RUN_ROOT = ROOT / "work" / "backtests" / "intraday_orb_daily_regime"
OUTPUT = ROOT / "outputs" / "intraday_orb_daily_regime.csv"
BASELINE = ROOT / "outputs" / "intraday_orb_range_sensitivity.csv"
CAPITAL = 1_000_000.0
PERIODS = (
    ("train", date(2022, 1, 3), date(2023, 12, 29)),
    ("validation", date(2024, 1, 1), date(2024, 12, 31)),
    ("holdout", date(2025, 1, 1), date(2026, 10, 23)),
    ("full", date(2022, 1, 3), date(2026, 10, 23)),
)
SLIPPAGE_LEVELS = (10.0, 25.0, 50.0, 100.0)


def prior_close_trend_sessions(daily_close: pd.Series) -> set[date]:
    if not daily_close.index.is_monotonic_increasing or not daily_close.index.is_unique:
        raise ValueError("daily NIFTY closes need unique chronological session timestamps")
    prior_close = daily_close.shift(1)
    prior_sma = daily_close.rolling(200, min_periods=200).mean().shift(1)
    gate = prior_close > prior_sma
    return {timestamp.date() for timestamp in daily_close.index[gate.fillna(False)]}


def main() -> None:
    q._self_check()
    signal_frames, _ = q._read_prices([f"NIFTY50={SIGNAL_PATH}"])
    trade_frames, _ = q._read_prices([f"NIFTYBEES={TRADE_PATH}"])
    _, daily_panels = q._read_prices([f"NIFTY50={DAILY_PATH}"])
    signal_bars = next(iter(signal_frames.values()))
    trade_bars = next(iter(trade_frames.values()))
    daily_close = daily_panels["close"]["NIFTY50"].dropna()
    trend_sessions = prior_close_trend_sessions(daily_close)
    baseline_rows = list(csv.DictReader(BASELINE.open(encoding="utf-8-sig", newline="")))
    baseline_returns = {
        (row["period"], float(row["slippage_bps_per_side"])): float(row["total_return_pct"])
        for row in baseline_rows if float(row["min_opening_range_pct"]) == 0.0
    }

    rows = []
    for gate_name, allowed_sessions in (("none", None), ("prior_close_above_sma200", trend_sessions)):
        for slippage in SLIPPAGE_LEVELS:
            for period, start, end in PERIODS:
                equity, trades, stats = q._intraday_orb(
                    signal_bars, trade_bars, CAPITAL, risk_fraction=0.005,
                    max_exposure=0.95, slippage_bps=slippage, drawdown_limit_pct=20.0,
                    mode="long", start=start, end=end, min_opening_range_pct=0.0,
                    fee_product="equity_fund_intraday", allowed_sessions=allowed_sessions,
                )
                run_name = f"{gate_name}__slip{slippage:g}__{period}"
                run_dir = RUN_ROOT / run_name
                run_dir.mkdir(parents=True, exist_ok=True)
                equity.to_csv(run_dir / "equity.csv", index_label="time")
                trades.to_csv(run_dir / "trades.csv", index=False)
                stats.update({
                    "strategy": "NIFTY 30m ORB long-only",
                    "regime_filter": gate_name,
                    "period": period,
                    "period_start": start.isoformat(),
                    "period_end": end.isoformat(),
                    "slippage_bps_per_side": slippage,
                    "trend_gate_definition": "prior completed NIFTY close above prior-close SMA200" if allowed_sessions is not None else "none",
                    "trend_sessions_in_data": len(trend_sessions),
                    "source_artifact": f"{run_dir.relative_to(ROOT).as_posix()}/summary.json",
                })
                (run_dir / "summary.json").write_text(json.dumps(stats, indent=2), encoding="utf-8")
                rows.append({
                    "strategy": "NIFTY 30m ORB long-only",
                    "regime_filter": gate_name,
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
                    "regime_filtered_sessions": stats["regime_filtered_sessions"],
                    "average_trade_exposure_pct": stats["average_trade_exposure_pct"],
                    "source_artifact": stats["source_artifact"],
                })
    assert len(rows) == 2 * len(SLIPPAGE_LEVELS) * len(PERIODS) == 32
    for row in rows:
        if row["regime_filter"] == "none" and row["slippage_bps_per_side"] == 10.0:
            key = (row["period"], 10.0)
            if key in baseline_returns:
                assert math.isclose(row["total_return_pct"], baseline_returns[key], rel_tol=0, abs_tol=1e-8)
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(OUTPUT, index=False)
    print(f"cases={len(rows)} daily_sma200_allowed_sessions={len(trend_sessions)}; no broker orders placed")


if __name__ == "__main__":
    main()
