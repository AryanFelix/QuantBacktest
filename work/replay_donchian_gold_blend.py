"""Reproducible 50/50 NIFTYBEES Donchian + GOLDBEES trend portfolio replay."""

from __future__ import annotations

import json
import math
from datetime import date
from pathlib import Path

import pandas as pd

import upstox_quant as q


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "work" / "data" / "etf_daily"
OUT = ROOT / "work" / "backtests" / "donchian_gold_clean"
CAPITAL = 1_000_000


def build_portfolio():
    files, panels = q._read_prices([
        f"NIFTYBEES={DATA / 'NSE_EQ_INF204KB14I2-days-1-2014-01-01-2026-10-23.csv'}",
        f"GOLDBEES={DATA / 'GOLDBEES-days-1-2014-01-01-2026-10-23.csv'}",
    ])
    nifty = {key: value[["NIFTYBEES"]] for key, value in panels.items()}
    gold = {key: value[["GOLDBEES"]] for key, value in panels.items()}
    nifty_targets, nifty_events = q.make_targets(nifty, "donchian55_20")
    gold_targets, gold_events = q.make_targets(gold, "trend200")
    targets = pd.concat([
        nifty_targets.mul(0.5).rename(columns={"NIFTYBEES": "NIFTYBEES"}),
        gold_targets.mul(0.5).rename(columns={"GOLDBEES": "GOLDBEES"}),
    ], axis=1).reindex(columns=["NIFTYBEES", "GOLDBEES"]).fillna(0.0)
    events = nifty_events.reindex(targets.index).fillna(False) | gold_events.reindex(targets.index).fillna(False)
    month_ends = pd.Series(targets.index, index=targets.index).groupby(targets.index.strftime("%Y-%m")).last()
    events.loc[pd.DatetimeIndex(month_ends.to_list())] = True
    assert targets.columns.tolist() == ["NIFTYBEES", "GOLDBEES"]
    assert (targets >= 0).all().all() and (targets.sum(axis=1) <= 1.0 + 1e-12).all()
    assert events.loc[pd.DatetimeIndex(month_ends.to_list())].all()
    return files, panels, targets, events


def modeled_slippage(orders: pd.DataFrame, panels: dict[str, pd.DataFrame]) -> float:
    total = 0.0
    for order in orders.itertuples(index=False):
        terminal = getattr(order, "terminal_liquidation", False)
        source = panels["close"] if pd.notna(terminal) and bool(terminal) else panels["open"]
        raw = source.loc[order.time, order.symbol]
        if pd.notna(raw):
            total += int(order.quantity) * abs(float(order.fill_price) - float(raw))
    return total


def main() -> None:
    files, panels, targets, events = build_portfolio()
    probe_time = pd.Timestamp("2024-01-02")
    probe_orders = pd.DataFrame([
        {"time": probe_time, "symbol": "TEST", "quantity": 2, "fill_price": 101.0, "terminal_liquidation": float("nan")},
        {"time": probe_time, "symbol": "TEST", "quantity": 3, "fill_price": 49.0, "terminal_liquidation": True},
    ])
    probe_panels = {"open": pd.DataFrame({"TEST": [100.0]}, index=[probe_time]),
                    "close": pd.DataFrame({"TEST": [50.0]}, index=[probe_time])}
    assert math.isclose(modeled_slippage(probe_orders, probe_panels), 5.0)
    OUT.mkdir(parents=True, exist_ok=True)
    config = {
        "strategy": "NIFTYBEES Donchian 55/20 + GOLDBEES 200DMA",
        "sleeve_weights": {"NIFTYBEES": 0.5, "GOLDBEES": 0.5},
        "rebalance": "signal changes and each month-end close; execute at next session open",
        "capital_inr": CAPITAL,
        "drawdown_limit_pct": 20,
        "slippage_bps_per_side": 10,
        "cash_return_pct": 0,
        "data_end": panels["close"].index[-1].date().isoformat(),
        "source_data": {name: str(frame.index[0].date()) + " to " + str(frame.index[-1].date()) for name, frame in files.items()},
    }
    (OUT / "strategy.json").write_text(json.dumps(config, indent=2), encoding="utf-8")
    splits = [
        ("2020_plus", date(2014, 1, 1), date(2017, 12, 31), date(2019, 12, 31)),
        ("recent", date(2014, 1, 1), date(2019, 12, 31), date(2022, 12, 31)),
    ]
    for name, train_start, train_end, validation_end in splits:
        screen, result, artifacts = q._walkforward(
            panels, targets, events, CAPITAL, train_start, train_end, validation_end,
            20, 10, "equity_delivery",
        )
        result["strategy"] = config["strategy"]
        result["symbols"] = ["GOLDBEES", "NIFTYBEES"]
        result["assumptions"] = config
        run = OUT / f"walkforward_{name}"
        run.mkdir(parents=True, exist_ok=True)
        screen.to_csv(run / "exposure_screen.csv", index=False)
        if artifacts:
            equity, orders = artifacts
            equity.to_csv(run / "test_equity.csv", index_label="time")
            orders.to_csv(run / "test_orders.csv", index=False)
            result["test_result"]["total_slippage_inr"] = modeled_slippage(orders, panels)
        (run / "summary.json").write_text(json.dumps(result, indent=2), encoding="utf-8")

    fixed_rows = []
    last_date = panels["close"].index[-1].date()
    for period, start in [("2020_plus", date(2020, 1, 1)), ("recent", date(2023, 1, 1))]:
        for exposure in (0.50, 0.75, 0.95):
            for slip in (10, 20, 50):
                equity, orders, stats = q._simulate(
                    panels, targets, events, CAPITAL, exposure, slip,
                    "equity_delivery", start, last_date, 20,
                )
                if exposure == 0.95 and slip == 50:
                    run = OUT / f"holdout_{period}_95cap_50bps"
                    run.mkdir(parents=True, exist_ok=True)
                    equity.to_csv(run / "equity.csv", index_label="time")
                    orders.to_csv(run / "orders.csv", index=False)
                    result = {
                        "strategy": config["strategy"], "period": period,
                        "training_cutoff": "2019-12-31" if period == "2020_plus" else "2022-12-31",
                        "exposure_cap_pct": 95, "slippage_bps_per_side": 50,
                        "total_slippage_inr": modeled_slippage(orders, panels), **stats,
                    }
                    (run / "summary.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
                    assert len(equity) > 0 and not orders.empty and equity.index.is_monotonic_increasing
                fixed_rows.append({
                    "period": period, "period_start": start.isoformat(), "period_end": last_date.isoformat(),
                    "exposure_cap_pct": exposure * 100, "slippage_bps_per_side": slip,
                    "total_slippage_inr": modeled_slippage(orders, panels), **stats,
                })
    pd.DataFrame(fixed_rows).to_csv(OUT / "fixed_exposure_cost_screen.csv", index=False)
    print(json.dumps({"output": str(OUT), "fixed_scenarios": len(fixed_rows), "month_end_rebalances": len(pd.Series(targets.index).groupby(targets.index.strftime("%Y-%m")).last())}, indent=2))


if __name__ == "__main__":
    main()
