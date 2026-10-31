"""Minimal regression check for terminal sales and calendar-time CAGR."""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "work"))
import backtest_stock_momentum as stock
import upstox_quant as q


def case(terminal_quote: bool):
    dates = pd.date_range("2024-01-02", periods=4, freq="B")
    a_dates = dates if terminal_quote else dates[:2]
    a = pd.DataFrame({"open": [100.0] * len(a_dates), "high": [102.0] * len(a_dates),
                      "low": [99.0] * len(a_dates), "close": [101.0, 102.0, 103.0, 110.0][:len(a_dates)],
                      "volume": [1_000] * len(a_dates)}, index=a_dates)
    b = pd.DataFrame({"open": [100.0] * 4, "high": [102.0] * 4, "low": [99.0] * 4,
                      "close": [101.0] * 4, "volume": [1_000] * 4}, index=dates)
    bars = {"A": a, "B": b}
    panels = {field: pd.DataFrame({symbol: frame[field] for symbol, frame in bars.items()}).reindex(dates)
              for field in ("open", "high", "low", "close", "volume")}
    targets = pd.DataFrame(0.0, index=dates, columns=["A", "B"])
    targets.loc[dates[0], "A"] = 0.95
    rebalance = pd.Series(False, index=dates)
    rebalance.iloc[0] = True
    return dates, bars, panels, targets, rebalance


def main() -> None:
    dates, bars, panels, targets, rebalance = case(False)
    for run in (
        lambda: q._simulate(panels, targets, rebalance, 1_000_000, 1.0, 0),
        lambda: stock.simulate("terminal_gap", bars, {},
                               {dates[1]: {"signal_date": dates[0], "weights": {"A": 0.95}}},
                               1.0, 0, dates[0], dates[-1]),
    ):
        try:
            run()
        except ValueError as error:
            assert "terminal liquidation lacks a raw close" in str(error)
        else:
            raise AssertionError("stale terminal quote was accepted")

    dates, bars, panels, targets, rebalance = case(True)
    _, shared_orders, shared_stats = q._simulate(panels, targets, rebalance, 1_000_000, 1.0, 0)
    stock_equity, stock_orders, stock_stats = stock.simulate(
        "terminal_quote", bars, {}, {dates[1]: {"signal_date": dates[0], "weights": {"A": 0.95}}},
        1.0, 0, dates[0], dates[-1],
    )
    for orders, stats in ((shared_orders, shared_stats), (stock_orders, stock_stats)):
        terminal = orders.loc[orders["terminal_liquidation"].eq(True)].iloc[0]
        order_date = pd.Timestamp(terminal.get("time", terminal.get("date")))
        assert order_date.date() == dates[-1].date()
        expected = q._calendar_cagr_pct(1_000_000, float(stats["ending_balance_inr"]), dates[0], dates[-1])
        assert np.isclose(float(stats["cagr_pct"]), expected)
    assert stock_equity.index[-1] == dates[-1]


if __name__ == "__main__":
    main()
