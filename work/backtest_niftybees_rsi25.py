"""Chronological, fee-aware NIFTYBEES RSI(4) pullback test."""

from __future__ import annotations

import json
import math
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

import upstox_quant as q


ROOT = Path(__file__).resolve().parents[1]
PRICE_FILE = ROOT / "work" / "data" / "etf_daily" / "NSE_EQ_INF204KB14I2-days-1-2014-01-01-2026-10-23.csv"
RUN_ROOT = ROOT / "work" / "backtests" / "niftybees_rsi25"
OUTPUT = ROOT / "outputs" / "niftybees_rsi25_sensitivity.csv"
CAPITAL = 1_000_000.0
DD_LIMIT = 20.0
SLIPPAGE_LEVELS = (10.0, 25.0, 50.0, 100.0)
PERIODS = (
    ("train_2014_2019", date(2014, 1, 1), date(2019, 12, 31)),
    ("validation_2020_2022", date(2020, 1, 1), date(2022, 12, 31)),
    ("holdout_2023_plus", date(2023, 1, 1), date(2026, 10, 23)),
    ("full_2014_plus", date(2014, 1, 1), date(2026, 10, 23)),
)
RULES = {
    "connors_rsi25_staged_50_50": {"starter": 0.50, "add": 0.50},
    "rsi25_single_50": {"starter": 0.50, "add": 0.0},
    "rsi25_single_100": {"starter": 1.00, "add": 0.0},
}
DIVIDENDS = [
    ("NIFTYBEES", date(2014, 3, 10), 0.70),
    ("NIFTYBEES", date(2015, 2, 18), 0.80),
]
ACTION_CASES = ("price_only", "candidate_total_return")


def wilder_rsi(close: pd.Series, period: int = 4) -> pd.Series:
    changes = close.astype(float).diff().to_numpy()
    gains = np.maximum(changes, 0.0)
    losses = np.maximum(-changes, 0.0)
    values = np.full(len(close), np.nan)
    if len(close) <= period:
        return pd.Series(values, index=close.index)
    avg_gain = float(np.nanmean(gains[1:period + 1]))
    avg_loss = float(np.nanmean(losses[1:period + 1]))
    for i in range(period, len(close)):
        if i > period:
            avg_gain = ((period - 1) * avg_gain + gains[i]) / period
            avg_loss = ((period - 1) * avg_loss + losses[i]) / period
        values[i] = 50.0 if avg_gain == 0 and avg_loss == 0 else (100.0 if avg_loss == 0 else 100 - 100 / (1 + avg_gain / avg_loss))
    return pd.Series(values, index=close.index)


def build_targets(
    close: pd.Series, trend: pd.Series, rsi: pd.Series, starter: float, add: float,
) -> tuple[pd.DataFrame, pd.Series]:
    if starter < 0 or add < 0 or starter + add > 1.0 + 1e-12:
        raise ValueError("starter and add weights must be non-negative and total no more than 100%")
    targets = pd.DataFrame(0.0, index=close.index, columns=["NIFTYBEES"])
    rebalance = pd.Series(False, index=close.index)
    units = 0
    for i, timestamp in enumerate(close.index):
        score = rsi.iloc[i]
        if units and pd.notna(score) and score > 55:
            units = 0
        elif units == 0 and pd.notna(score) and score < 25 and bool(trend.iloc[i]):
            units = 1
        elif units == 1 and add > 0 and pd.notna(score) and score < 20:
            units = 2
        weight = starter + (add if units == 2 else 0.0) if units else 0.0
        targets.loc[timestamp, "NIFTYBEES"] = weight
        if i == 0:
            rebalance.iloc[i] = units > 0
        elif targets.iloc[i, 0] != targets.iloc[i - 1, 0]:
            rebalance.iloc[i] = True
    assert targets.to_numpy().min() >= 0 and targets.to_numpy().max() <= 1.0 + 1e-12
    return targets, rebalance


def candidate_total_return_close(close: pd.Series) -> pd.Series:
    cash = pd.Series(0.0, index=close.index)
    for _, ex_date, amount in DIVIDENDS:
        matching = close.index.date == ex_date
        cash.loc[matching] += amount
    gross = (close + cash) / close.shift(1)
    gross.iloc[0] = 1.0
    return close.iloc[0] * gross.cumprod()


def modeled_slippage(orders: pd.DataFrame, panels: dict[str, pd.DataFrame]) -> float:
    total = 0.0
    for order in orders.itertuples(index=False):
        terminal = bool(getattr(order, "terminal_liquidation", False))
        raw = panels["close"].loc[order.time, order.symbol] if terminal else panels["open"].loc[order.time, order.symbol]
        if pd.notna(raw):
            total += int(order.quantity) * abs(float(order.fill_price) - float(raw))
    return total


def self_check() -> None:
    index = pd.RangeIndex(5)
    close = pd.Series(100.0, index=index)
    trend = pd.Series(True, index=index)
    rsi = pd.Series([50.0, 10.0, 18.0, 30.0, 56.0], index=index)
    staged, events = build_targets(close, trend, rsi, 0.50, 0.50)
    assert staged["NIFTYBEES"].tolist() == [0.0, 0.5, 1.0, 1.0, 0.0]
    assert events.tolist() == [False, True, True, False, True]
    single, _ = build_targets(close, trend, rsi, 1.0, 0.0)
    assert single["NIFTYBEES"].tolist() == [0.0, 1.0, 1.0, 1.0, 0.0]
    filtered, _ = build_targets(close, pd.Series(False, index=index), rsi, 0.5, 0.5)
    assert filtered["NIFTYBEES"].eq(0.0).all()
    assert wilder_rsi(pd.Series([1.0, 2.0, 1.0, 2.0, 1.0, 2.0]), 4).dropna().between(0, 100).all()


def main() -> None:
    self_check()
    _, panels = q._read_prices([f"NIFTYBEES={PRICE_FILE}"])
    close = panels["close"]["NIFTYBEES"].astype(float)
    total_return_close = candidate_total_return_close(close)
    signal_panels = {field: panel.copy() for field, panel in panels.items()}
    adjustment_factor = total_return_close / close
    for field in ("open", "high", "low", "close"):
        signal_panels[field]["NIFTYBEES"] *= adjustment_factor
    rows = []
    for action_case in ACTION_CASES:
        signal_close = close if action_case == "price_only" else total_return_close
        trend = signal_close > signal_close.rolling(200, min_periods=200).mean()
        rsi = wilder_rsi(signal_close, 4)
        cash_distributions = [] if action_case == "price_only" else DIVIDENDS
        for rule, weights in RULES.items():
            targets, rebalance = build_targets(signal_close, trend, rsi, weights["starter"], weights["add"])
            for slippage in SLIPPAGE_LEVELS:
                for period, start, end in PERIODS:
                    equity, orders, stats = q._simulate(
                        panels, targets, rebalance, CAPITAL, 1.0, slippage,
                        "equity_delivery", start, end, DD_LIMIT,
                        cash_distributions=cash_distributions,
                    )
                    key = f"{rule}__{action_case}__{period}__{slippage:g}bps"
                    run_dir = RUN_ROOT / key
                    run_dir.mkdir(parents=True, exist_ok=True)
                    equity.to_csv(run_dir / "equity.csv", index_label="time")
                    orders.to_csv(run_dir / "orders.csv", index=False)
                    stats.update({
                        "strategy": rule,
                        "action_case": action_case,
                        "period": period,
                        "period_start": start.isoformat(),
                        "period_end": end.isoformat(),
                        "slippage_bps_per_side": slippage,
                        "starter_exposure_pct": weights["starter"] * 100,
                        "add_exposure_pct": weights["add"] * 100,
                        "source_artifact": f"{run_dir.relative_to(ROOT).as_posix()}/summary.json",
                    })
                    (run_dir / "summary.json").write_text(json.dumps(stats, indent=2), encoding="utf-8")
                    rows.append({
                        "strategy": rule,
                        "action_case": action_case,
                        "period": period,
                        "period_start": start.isoformat(),
                        "period_end": end.isoformat(),
                        "starting_balance_inr": CAPITAL,
                        "ending_balance_inr": stats["ending_balance_inr"],
                        "total_return_pct": stats["total_return_pct"],
                        "cagr_pct": stats["cagr_pct"],
                        "max_drawdown_pct": stats["max_drawdown_pct"],
                        "sharpe_zero_rf": stats["sharpe_zero_rf"],
                        "within_20pct": stats["within_drawdown_limit"],
                        "starter_exposure_pct": weights["starter"] * 100,
                        "add_exposure_pct": weights["add"] * 100,
                        "slippage_bps_per_side": slippage,
                        "fees_inr": stats["total_fees_inr"],
                        "slippage_cost_inr": modeled_slippage(orders, panels),
                        "cash_distributions_inr": stats["cash_distributions_inr"],
                        "order_count": stats["order_count"],
                        "cash_distribution_events": sum(event["eligible_quantity"] > 0 for event in stats["cash_distribution_events"]),
                        "source_artifact": f"{run_dir.relative_to(ROOT).as_posix()}/summary.json",
                    })
    for benchmark in ("buyhold", "trend200", "donchian55_20"):
        targets, rebalance = q.make_targets(signal_panels, benchmark)
        for period, start, end in PERIODS:
            equity, orders, stats = q._simulate(
                panels, targets, rebalance, CAPITAL, 1.0, 50.0,
                "equity_delivery", start, end, DD_LIMIT,
                cash_distributions=DIVIDENDS,
            )
            key = f"benchmark_{benchmark}__candidate_total_return__{period}__50bps"
            run_dir = RUN_ROOT / "benchmarks" / key
            run_dir.mkdir(parents=True, exist_ok=True)
            equity.to_csv(run_dir / "equity.csv", index_label="time")
            orders.to_csv(run_dir / "orders.csv", index=False)
            stats.update({
                "strategy": f"benchmark_{benchmark}",
                "action_case": "candidate_total_return",
                "period": period,
                "period_start": start.isoformat(),
                "period_end": end.isoformat(),
                "slippage_bps_per_side": 50.0,
                "source_artifact": f"{run_dir.relative_to(ROOT).as_posix()}/summary.json",
            })
            (run_dir / "summary.json").write_text(json.dumps(stats, indent=2), encoding="utf-8")
            rows.append({
                "strategy": f"benchmark_{benchmark}",
                "action_case": "candidate_total_return",
                "period": period,
                "period_start": start.isoformat(),
                "period_end": end.isoformat(),
                "starting_balance_inr": CAPITAL,
                "ending_balance_inr": stats["ending_balance_inr"],
                "total_return_pct": stats["total_return_pct"],
                "cagr_pct": stats["cagr_pct"],
                "max_drawdown_pct": stats["max_drawdown_pct"],
                "sharpe_zero_rf": stats["sharpe_zero_rf"],
                "within_20pct": stats["within_drawdown_limit"],
                "starter_exposure_pct": "",
                "add_exposure_pct": "",
                "slippage_bps_per_side": 50.0,
                "fees_inr": stats["total_fees_inr"],
                "slippage_cost_inr": modeled_slippage(orders, panels),
                "cash_distributions_inr": stats["cash_distributions_inr"],
                "order_count": stats["order_count"],
                "cash_distribution_events": sum(event["eligible_quantity"] > 0 for event in stats["cash_distribution_events"]),
                "source_artifact": f"{run_dir.relative_to(ROOT).as_posix()}/summary.json",
            })
    expected = len(ACTION_CASES) * len(RULES) * len(SLIPPAGE_LEVELS) * len(PERIODS) + 3 * len(PERIODS)
    assert len(rows) == expected == 108
    keys = [(r["strategy"], r["action_case"], r["period"], r["slippage_bps_per_side"]) for r in rows]
    assert len(keys) == len(set(keys))
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(OUTPUT, index=False)
    print(f"cases={len(rows)} rules={len(RULES)} costs={SLIPPAGE_LEVELS} periods={len(PERIODS)} action_cases={len(ACTION_CASES)}")


if __name__ == "__main__":
    main()
