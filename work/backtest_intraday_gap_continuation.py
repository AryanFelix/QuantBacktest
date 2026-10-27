"""Backtest a confirmed long continuation after a large NIFTY opening gap."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pandas as pd

import backtest_intraday_gap_fade as gap
import upstox_quant as q


ROOT = Path(__file__).resolve().parents[1]
RUN_ROOT = ROOT / "work" / "backtests" / "intraday_gap_continuation"
OUTPUT = ROOT / "outputs" / "intraday_gap_continuation_sensitivity.csv"
GAP_THRESHOLDS = (0.30, 0.50, 0.75)
SLIPPAGE_LEVELS = (10.0, 25.0, 50.0, 100.0)
PERIODS = (
    ("train_2022_2023", date(2022, 1, 3), date(2023, 12, 29)),
    ("validation_2024", date(2024, 1, 1), date(2024, 12, 31)),
    ("holdout_2025_plus", date(2025, 1, 1), date(2026, 10, 23)),
    ("full_2022_plus", date(2022, 1, 3), date(2026, 10, 23)),
)


def continuation_direction(
    gap_pct: float, first_open: float, first_close: float, prior_close: float, threshold_pct: float,
) -> str | None:
    if gap_pct >= threshold_pct and first_close > first_open and first_close > prior_close:
        return "long"
    return None


def _candidate_map(signal: dict[date, pd.DataFrame], trade: dict[date, pd.DataFrame], threshold: float) -> dict[date, dict]:
    common = sorted(set(signal) & set(trade))
    candidates = {}
    for i in range(1, len(common)):
        day, prior = common[i], common[i - 1]
        index_day, stock_day = signal[day], trade[day]
        if len(index_day) != 13 or len(stock_day) != 13 or not index_day["time"].equals(stock_day["time"]):
            continue
        prior_index_close = float(signal[prior].iloc[-1]["close"])
        first = index_day.iloc[0]
        gap_pct = 100 * (float(first["open"]) / prior_index_close - 1)
        direction = continuation_direction(
            gap_pct, float(first["open"]), float(first["close"]), prior_index_close, threshold,
        )
        if direction is None:
            continue
        entry = float(stock_day.iloc[1]["open"])
        stop = float(stock_day.iloc[0]["low"])
        target = entry + (entry - stop)
        candidates[day] = {
            "direction": direction,
            "gap_pct": gap_pct,
            "entry_time": stock_day.iloc[1]["time"],
            "entry_raw": entry,
            "stop": stop,
            "target": target,
            "bars": stock_day.iloc[1:].reset_index(drop=True),
        }
    return candidates


def self_check() -> None:
    assert continuation_direction(0.50, 100.5, 101.0, 100.0, 0.50) == "long"
    assert continuation_direction(0.50, 100.5, 100.4, 100.0, 0.50) is None
    assert continuation_direction(0.30, 100.3, 100.4, 100.0, 0.50) is None
    assert 101.0 + (101.0 - 100.0) == 102.0


def main() -> None:
    self_check()
    signal_frames, _ = q._read_prices([f"NIFTY50={gap.SIGNAL_FILE}"])
    trade_frames, _ = q._read_prices([f"NIFTYBEES={gap.TRADE_FILE}"])
    signal = gap._sessions(next(iter(signal_frames.values())).reset_index())
    trade = gap._sessions(next(iter(trade_frames.values())).reset_index())
    common_days = sorted(set(signal) & set(trade))
    aligned_days = [
        day for day in common_days
        if len(signal[day]) == len(trade[day]) == 13 and signal[day]["time"].equals(trade[day]["time"])
    ]
    assert len(aligned_days) > 1_000
    print(f"common_sessions={len(common_days)} complete_aligned_sessions={len(aligned_days)} excluded={len(common_days) - len(aligned_days)}")
    rows = []
    for threshold in GAP_THRESHOLDS:
        candidates = _candidate_map(signal, trade, threshold)
        for slippage in SLIPPAGE_LEVELS:
            for period, start, end in PERIODS:
                equity, trades, stats = gap.simulate(
                    signal, trade, candidates, "both", start, end, slippage,
                )
                run_name = f"long_gap{threshold:.2f}__{period}__{slippage:g}bps"
                run_dir = RUN_ROOT / run_name
                run_dir.mkdir(parents=True, exist_ok=True)
                equity.to_csv(run_dir / "equity.csv", index=False)
                trades.to_csv(run_dir / "trades.csv", index=False)
                stats.update({
                    "strategy": "NIFTY opening-gap continuation",
                    "mode": "long_gap_up",
                    "gap_threshold_pct": threshold,
                    "profit_target_r": 1.0,
                    "slippage_bps_per_side": slippage,
                    "source_artifact": f"{run_dir.relative_to(ROOT).as_posix()}/summary.json",
                })
                (run_dir / "summary.json").write_text(json.dumps(stats, indent=2), encoding="utf-8")
                rows.append({
                    "strategy": "NIFTY opening-gap continuation",
                    "mode": "long_gap_up",
                    "gap_threshold_pct": threshold,
                    "profit_target_r": 1.0,
                    "period": period,
                    "period_start": start.isoformat(),
                    "period_end": end.isoformat(),
                    "starting_balance_inr": gap.CAPITAL,
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
                    "signal_count": stats["signal_count"],
                    "rejected_signals": stats["rejected_signals"],
                    "win_rate_pct": stats["win_rate_pct"],
                    "profit_factor": stats["profit_factor"],
                    "source_artifact": f"{run_dir.relative_to(ROOT).as_posix()}/summary.json",
                })
    expected = len(GAP_THRESHOLDS) * len(SLIPPAGE_LEVELS) * len(PERIODS)
    assert len(rows) == expected == 48
    keys = [(r["gap_threshold_pct"], r["period"], r["slippage_bps_per_side"]) for r in rows]
    assert len(keys) == len(set(keys))
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(OUTPUT, index=False)
    print(f"cases={len(rows)} thresholds={GAP_THRESHOLDS} slippage={SLIPPAGE_LEVELS}; one-R target")


if __name__ == "__main__":
    main()
