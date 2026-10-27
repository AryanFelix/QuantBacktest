"""Test a causal high-water drawdown throttle on a passive NIFTY/Gold sleeve."""

from __future__ import annotations

import math
from collections import defaultdict
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

import audit_etf_intraday_drawdown as audit
import benchmark_nifty_gold_2020 as benchmark
import replay_volatility_weighted_blend as blend
import upstox_quant as q


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs" / "passive_drawdown_control_sensitivity.csv"
RUNS = ROOT / "work" / "backtests" / "passive_drawdown_control"
START = date(2015, 1, 2)
CAPITAL = 1_000_000.0
FIXED_EXPOSURES = (0.45, 0.60)
TRIGGERS_PCT = (8.0, 10.0, 12.0)
SLIPPAGE_BPS = (10.0, 50.0, 100.0)
LOW_EXPOSURE = 0.30
HIGH_EXPOSURE = 0.60


def next_exposure(
    current: float, drawdown: float, trigger_pct: float | None,
    high_exposure: float = HIGH_EXPOSURE, low_exposure: float = LOW_EXPOSURE,
) -> float:
    if trigger_pct is None:
        return current
    trigger = trigger_pct / 100
    if math.isclose(current, high_exposure) and drawdown <= -trigger:
        return low_exposure
    if math.isclose(current, low_exposure) and drawdown >= -trigger / 2:
        return high_exposure
    return current


def _self_check() -> None:
    assert next_exposure(0.60, -0.08, 8.0) == 0.30
    assert next_exposure(0.60, -0.079, 8.0) == 0.60
    assert next_exposure(0.30, -0.051, 10.0) == 0.30
    assert next_exposure(0.30, -0.049, 10.0) == 0.60
    assert next_exposure(0.60, -0.20, None) == 0.60
    assert next_exposure(0.70, -0.08, 8.0, 0.70, 0.35) == 0.35
    assert next_exposure(0.35, -0.039, 8.0, 0.70, 0.35) == 0.70


def simulate(
    panels: dict[str, pd.DataFrame],
    name: str,
    initial_exposure: float,
    trigger_pct: float | None,
    slippage_bps: float,
    start: date = START,
    end: date | None = None,
    base_targets: pd.DataFrame | None = None,
    rebalance_events: pd.Series | None = None,
    lower_exposure: float | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    if not 0 < initial_exposure <= 1 or slippage_bps < 0:
        raise ValueError("exposure must be in (0, 1] and slippage must be non-negative")
    if trigger_pct is not None and not 0 < trigger_pct < 100:
        raise ValueError("drawdown trigger must be between 0 and 100 percent")
    if lower_exposure is not None and not 0 < lower_exposure <= initial_exposure:
        raise ValueError("lower exposure must be positive and no greater than the initial cap")
    if (base_targets is None) != (rebalance_events is None):
        raise ValueError("active target weights and their rebalance events must be supplied together")

    opens, closes = panels["open"], panels["close"]
    symbols = ["NIFTYBEES", "GOLDBEES"]
    if base_targets is not None:
        if not base_targets.index.is_unique or not rebalance_events.index.is_unique:
            raise ValueError("active targets and rebalance events need unique session indexes")
        if set(base_targets.columns) != set(symbols):
            raise ValueError("active targets must contain NIFTYBEES and GOLDBEES weights")
        active_weights = base_targets.reindex(index=closes.index, columns=symbols).fillna(0.0)
        if not np.isfinite(active_weights.to_numpy(dtype=float)).all() or (active_weights < 0).any().any():
            raise ValueError("active target weights must be finite and non-negative")
        active_events = rebalance_events.reindex(closes.index).fillna(False).astype(bool)
    else:
        active_weights = active_events = None
    low_cap = LOW_EXPOSURE if lower_exposure is None else lower_exposure
    dates = closes.index[[
        timestamp.date() >= start and (end is None or timestamp.date() <= end)
        for timestamp in closes.index
    ]]
    if dates.empty or dates[0].date() < start:
        raise ValueError("common ETF history does not include the requested paper/backtest window")
    end_date = dates[-1].date()
    open_marks = opens.where(opens.notna(), closes.ffill().shift(1))
    close_marks = closes.ffill()
    quantity = {"NIFTYBEES": 0, "GOLDBEES": 0}
    fee_products = {symbol: q.FUND_FEE_PRODUCTS[symbol] for symbol in quantity}
    distributions = defaultdict(list)
    for symbol, ex_date, amount in benchmark.NIFTYBEES_DISTRIBUTIONS:
        if ex_date in {timestamp.date() for timestamp in dates}:
            distributions[ex_date].append((symbol, amount))

    cash = CAPITAL
    prior_close_nav = CAPITAL
    high_water = CAPITAL
    current_exposure = initial_exposure
    pending_exposure: float | None = None
    pending_reason = ""
    slip = slippage_bps / 10_000
    orders: list[dict] = []
    equity_rows: list[dict] = []
    total_slippage = 0.0
    trigger_count = recovery_count = 0

    for step, timestamp in enumerate(dates):
        source_i = closes.index.get_loc(timestamp)
        signal_i = source_i - 1
        if signal_i < 0:
            raise ValueError("a prior close is required for next-open sizing")
        distribution_cash = sum(
            quantity[symbol] * amount for symbol, amount in distributions.get(timestamp.date(), [])
        )
        cash += distribution_cash

        rebalance = step == 0 or pending_exposure is not None
        if active_events is not None and signal_i >= 0:
            rebalance = rebalance or bool(active_events.iloc[signal_i])
        if rebalance:
            target_exposure = initial_exposure if step == 0 else (
                float(pending_exposure) if pending_exposure is not None else current_exposure
            )
            reason = "initial_entry" if step == 0 else (pending_reason or "scheduled_rebalance")
            reference_prices = close_marks.iloc[signal_i]
            if active_weights is None:
                desired = {
                    symbol: int(math.floor(
                        prior_close_nav * target_exposure * 0.5 / float(reference_prices[symbol])
                    ))
                    for symbol in quantity
                }
            else:
                weights = active_weights.iloc[signal_i].copy()
                total_weight = float(weights.sum())
                if total_weight > target_exposure:
                    weights *= target_exposure / total_weight
                desired = {
                    symbol: int(math.floor(prior_close_nav * float(weights[symbol]) / float(reference_prices[symbol])))
                    if pd.notna(reference_prices[symbol]) and float(reference_prices[symbol]) > 0 else 0
                    for symbol in quantity
                }
            executable = opens.loc[timestamp]
            marked_open = open_marks.loc[timestamp]

            for symbol in quantity:
                if pd.isna(executable[symbol]):
                    continue
                amount = quantity[symbol] - desired[symbol]
                if amount <= 0:
                    continue
                raw_fill = float(marked_open[symbol])
                fill = raw_fill * (1 - slip)
                notional = amount * fill
                charges = q._fee_breakdown(notional, "sell", fee_products[symbol])
                cash += notional - charges["total"]
                quantity[symbol] -= amount
                total_slippage += amount * abs(fill - raw_fill)
                orders.append({
                    "time": timestamp, "symbol": symbol, "side": "sell", "quantity": amount,
                    "fill_price": fill, "notional": notional, "reason": reason, **charges,
                })

            for symbol in quantity:
                if pd.isna(executable[symbol]):
                    continue
                amount = desired[symbol] - quantity[symbol]
                if amount <= 0:
                    continue
                raw_fill = float(marked_open[symbol])
                fill = raw_fill * (1 + slip)
                lo, hi = 0, amount
                while lo < hi:
                    mid = (lo + hi + 1) // 2
                    charges = q._fee_breakdown(mid * fill, "buy", fee_products[symbol])
                    if mid * fill + charges["total"] <= cash:
                        lo = mid
                    else:
                        hi = mid - 1
                amount = lo
                if not amount:
                    continue
                notional = amount * fill
                charges = q._fee_breakdown(notional, "buy", fee_products[symbol])
                cash -= notional + charges["total"]
                quantity[symbol] += amount
                total_slippage += amount * abs(fill - raw_fill)
                orders.append({
                    "time": timestamp, "symbol": symbol, "side": "buy", "quantity": amount,
                    "fill_price": fill, "notional": notional, "reason": reason, **charges,
                })
            current_exposure = target_exposure
            pending_exposure = None
            pending_reason = ""

        close_prices = close_marks.loc[timestamp]
        nav = cash + sum(
            quantity[symbol] * float(close_prices[symbol])
            for symbol in quantity if quantity[symbol] and pd.notna(close_prices[symbol])
        )
        high_water = max(high_water, nav)
        drawdown = nav / high_water - 1
        exposure = sum(
            quantity[symbol] * float(close_prices[symbol])
            for symbol in quantity if quantity[symbol] and pd.notna(close_prices[symbol])
        ) / nav
        equity_rows.append({
            "time": timestamp, "nav": nav, "risky_exposure": exposure, "gross_exposure": exposure,
            "cash_distribution_inr": distribution_cash,
            "close_drawdown_pct": drawdown * 100,
            "target_exposure_after_close_pct": current_exposure * 100,
        })
        high_cap = initial_exposure if active_weights is not None else HIGH_EXPOSURE
        next_target = next_exposure(current_exposure, drawdown, trigger_pct, high_cap, low_cap)
        if next_target != current_exposure:
            pending_exposure = next_target
            pending_reason = "drawdown_cut" if next_target < current_exposure else "drawdown_recovery"
            if pending_reason == "drawdown_cut":
                trigger_count += 1
            else:
                recovery_count += 1
            equity_rows[-1]["target_exposure_after_close_pct"] = next_target * 100
        prior_close_nav = nav

    last_timestamp = dates[-1]
    for symbol, amount in quantity.items():
        if amount <= 0:
            continue
        raw_fill = float(close_marks.loc[last_timestamp, symbol])
        fill = raw_fill * (1 - slip)
        notional = amount * fill
        charges = q._fee_breakdown(notional, "sell", fee_products[symbol])
        cash += notional - charges["total"]
        total_slippage += amount * abs(fill - raw_fill)
        orders.append({
            "time": last_timestamp, "symbol": symbol, "side": "sell", "quantity": amount,
            "fill_price": fill, "notional": notional, "reason": "terminal_liquidation",
            "terminal_liquidation": True, **charges,
        })
    equity_rows[-1]["nav"] = cash
    equity = pd.DataFrame(equity_rows).set_index("time")
    order_frame = pd.DataFrame(orders)
    full_nav = np.r_[CAPITAL, equity["nav"].to_numpy(dtype=float)]
    max_drawdown = float((full_nav / np.maximum.accumulate(full_nav) - 1).min() * 100)
    stats = {
        "strategy": name,
        "period_start": dates[0].date().isoformat(),
        "period_end": end_date.isoformat(),
        "sessions": len(dates),
        "starting_balance_inr": CAPITAL,
        "ending_balance_inr": cash,
        "total_return_pct": (cash / CAPITAL - 1) * 100,
        "cagr_pct": ((cash / CAPITAL) ** (252 / len(dates)) - 1) * 100,
        "total_fees_inr": float(order_frame["total"].sum()),
        "total_slippage_inr": total_slippage,
        "order_count": len(order_frame),
        "trigger_count": trigger_count,
        "recovery_count": recovery_count,
        "average_exposure_pct": float(equity["risky_exposure"].mean() * 100),
        "average_gross_exposure_pct": float(equity["gross_exposure"].mean() * 100),
        "max_drawdown_pct": max_drawdown,
        "within_drawdown_limit": max_drawdown >= -20.0,
        "slippage_bps_per_side": slippage_bps,
        "initial_exposure_pct": initial_exposure * 100,
        "drawdown_trigger_pct": trigger_pct if trigger_pct is not None else "",
    }
    return equity, order_frame, stats


def assert_matches_shared_simulator(panels: dict[str, pd.DataFrame], exposure: float) -> None:
    targets, events = benchmark._passive_targets(
        panels, {"NIFTYBEES": 0.5, "GOLDBEES": 0.5},
    )
    reference, reference_orders, reference_stats = q._simulate(
        panels, targets, events, CAPITAL, exposure, 50.0, "equity_delivery", START,
        panels["close"].dropna(subset=["NIFTYBEES", "GOLDBEES"]).index[-1].date(),
        cash_distributions=benchmark.NIFTYBEES_DISTRIBUTIONS,
    )
    equity, orders, stats = simulate(
        panels, f"fixed_{int(exposure * 100)}", exposure, None, 50.0,
    )
    assert np.allclose(equity["nav"].to_numpy(), reference["nav"].to_numpy(), atol=0.03, rtol=0)
    assert len(orders) == len(reference_orders)
    assert abs(stats["total_fees_inr"] - reference_stats["total_fees_inr"]) <= 0.03


def run_case(
    panels: dict[str, pd.DataFrame], name: str, exposure: float,
    trigger_pct: float | None, slippage_bps: float,
) -> dict:
    equity, orders, stats = simulate(panels, name, exposure, trigger_pct, slippage_bps)
    run_dir = RUNS / f"{name}__{int(slippage_bps)}bps"
    run_dir.mkdir(parents=True, exist_ok=True)
    equity.to_csv(run_dir / "equity.csv", index_label="time")
    orders.to_csv(run_dir / "orders.csv", index=False)
    relative = str(run_dir.relative_to(ROOT))
    audit.SLIPPAGE_BPS = slippage_bps
    risk = audit.run_case(name, relative, starting_balance=CAPITAL)
    assert risk["max_close_replay_error_inr"] <= 0.03
    return {
        **stats,
        "close_mdd_pct": risk["close_max_drawdown_pct"],
        "ohlc_drawdown_bound_pct": risk["simultaneous_ohlc_drawdown_bound_pct"],
        "within_20pct_ohlc": risk["within_20pct_under_bound"],
        "max_close_replay_error_inr": risk["max_close_replay_error_inr"],
        "source_equity": f"{relative}/equity.csv",
        "source_orders": f"{relative}/orders.csv",
    }


def main() -> None:
    _self_check()
    _, panels, _, _ = blend.make_portfolios()
    common = panels["close"].dropna(subset=["NIFTYBEES", "GOLDBEES"]).index
    assert common[0].date() <= START < common[-1].date()
    assert common[-1].date() == date(2026, 10, 23), "Keep this frozen experiment on the documented history cutoff"
    for exposure in FIXED_EXPOSURES:
        assert_matches_shared_simulator(panels, exposure)

    results = []
    for slip in SLIPPAGE_BPS:
        for exposure in FIXED_EXPOSURES:
            name = f"fixed_{int(exposure * 100)}pct"
            results.append(run_case(panels, name, exposure, None, slip))
        for trigger in TRIGGERS_PCT:
            name = f"dd_{int(trigger)}pct_cut_60_to_30_recover_{int(trigger / 2)}pct"
            results.append(run_case(panels, name, HIGH_EXPOSURE, trigger, slip))

    result = pd.DataFrame(results)
    assert len(result) == len(SLIPPAGE_BPS) * (len(FIXED_EXPOSURES) + len(TRIGGERS_PCT))
    assert result["strategy"].notna().all()
    assert not result.duplicated(["strategy", "slippage_bps_per_side"]).any()
    assert result["max_close_replay_error_inr"].max() <= 0.03
    OUT.parent.mkdir(parents=True, exist_ok=True)
    result.to_csv(OUT, index=False)
    print(f"wrote {len(result)} drawdown-control cases through {common[-1].date()}; no broker orders placed")


if __name__ == "__main__":
    main()
