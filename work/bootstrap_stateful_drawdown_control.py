"""Stationary-bootstrap joint ETF OHLC paths and rerun the drawdown controls."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

import backtest_passive_mix_drawdown_control as control
import benchmark_nifty_gold_2020 as benchmark
import bootstrap_etf_drawdown_risk as bootstrap
import replay_volatility_weighted_blend as blend
import upstox_quant as q


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs" / "stateful_drawdown_control_bootstrap.csv"
START = date(2015, 1, 2)
END = date(2026, 10, 23)
CAPITAL = 1_000_000.0
SLIPPAGE_BPS = 50.0
N_PATHS = 5_000
HORIZON = 2_520
BLOCK_LENGTHS = (21, 63, 126)
SEED = 2_710_271
POLICIES = (
    ("fixed_45pct", 0.45, None),
    ("fixed_60pct", 0.60, None),
    ("dd_8pct_cut_60_to_30_recover_4pct", 0.60, 8.0),
    ("dd_10pct_cut_60_to_30_recover_5pct", 0.60, 10.0),
    ("dd_12pct_cut_60_to_30_recover_6pct", 0.60, 12.0),
)
ASSETS = ("NIFTYBEES", "GOLDBEES")
FEE_PRODUCTS = (q.FUND_FEE_PRODUCTS[ASSETS[0]], q.FUND_FEE_PRODUCTS[ASSETS[1]])


def fee_total(notional: np.ndarray, side: str, product: str) -> np.ndarray:
    amount = np.asarray(notional, dtype=float)
    active = amount > 0
    brokerage = np.where(active, 20.0, 0.0)
    exchange = amount * 0.0000307
    stt_rate = 0.00001 if product == "equity_fund_delivery" and side == "sell" else 0.0
    stt = amount * stt_rate
    stamp = amount * 0.00015 if side == "buy" else 0.0
    sebi = amount * 0.000001
    ipft = amount * 0.000000001
    dp = np.where(active & (side == "sell"), 20.0, 0.0)
    gst = 0.18 * (brokerage + exchange + sebi + ipft + dp)
    return brokerage + stt + exchange + stamp + sebi + ipft + dp + gst


def buy_capacity(cash: np.ndarray, fill: np.ndarray, product: str) -> np.ndarray:
    fixed = q._fee_breakdown(0.0, "buy", product)["total"]
    rate = (q._fee_breakdown(1_000_000.0, "buy", product)["total"] - fixed) / 1_000_000.0
    return np.floor(np.maximum(cash - fixed, 0.0) / (fill * (1.0 + rate))).astype(np.int64)


def load_source() -> tuple[dict[str, np.ndarray], np.ndarray, np.ndarray]:
    _, panels, _, _ = blend.make_portfolios()
    close = panels["close"].dropna(subset=list(ASSETS))
    dates = close.index[[timestamp.date() >= START for timestamp in close.index]]
    if dates.empty or dates[-1].date() != END:
        raise ValueError(f"Expected common ETF history through {END}; got {dates[-1].date() if len(dates) else 'none'}")
    all_close = close.loc[:, list(ASSETS)]
    previous_close = all_close.shift(1).loc[dates]
    current_close = all_close.loc[dates]
    opened = panels["open"].loc[dates, list(ASSETS)]
    high = panels["high"].loc[dates, list(ASSETS)]
    low = panels["low"].loc[dates, list(ASSETS)]
    if any(frame.isna().any().any() for frame in (previous_close, opened, high, low, current_close)):
        raise ValueError("Common-session OHLC inputs contain missing values")
    arrays = {
        "gap": (opened.to_numpy() / previous_close.to_numpy()),
        "high_open": (high.to_numpy() / opened.to_numpy()),
        "low_open": (low.to_numpy() / opened.to_numpy()),
        "close_open": (current_close.to_numpy() / opened.to_numpy()),
    }
    if any(not np.isfinite(values).all() or (values <= 0).any() for values in arrays.values()):
        raise ValueError("OHLC return factors must be finite and positive")
    if (arrays["high_open"] < 1).any() or (arrays["low_open"] > 1).any():
        raise ValueError("OHLC bars must contain their open prices")
    arrays["distribution"] = np.zeros(len(dates), dtype=float)
    date_values = np.array([timestamp.date() for timestamp in dates], dtype=object)
    for symbol, ex_date, amount in benchmark.NIFTYBEES_DISTRIBUTIONS:
        if symbol == ASSETS[0]:
            arrays["distribution"][date_values == ex_date] += amount
    previous_start = previous_close.iloc[0].to_numpy(dtype=float)
    return arrays, date_values, previous_start


def simulate(indices: np.ndarray, source: dict[str, np.ndarray], initial_prices: np.ndarray) -> dict[str, np.ndarray]:
    path_count, steps = indices.shape
    policy_count = len(POLICIES)
    shape = (path_count, policy_count)
    initials = np.array([policy[1] for policy in POLICIES], dtype=float)
    triggers = np.array([np.nan if policy[2] is None else policy[2] / 100.0 for policy in POLICIES])
    cash = np.full(shape, CAPITAL, dtype=float)
    qty_n = np.zeros(shape, dtype=np.int64)
    qty_g = np.zeros(shape, dtype=np.int64)
    current = np.broadcast_to(initials, shape).copy()
    pending = np.full(shape, np.nan)
    prior_nav = np.full(shape, CAPITAL, dtype=float)
    close_peak = np.full(shape, CAPITAL, dtype=float)
    ohlc_peak = np.full(shape, CAPITAL, dtype=float)
    worst_close = np.zeros(shape, dtype=float)
    worst_ohlc = np.zeros(shape, dtype=float)
    fees = np.zeros(shape, dtype=float)
    slippage = np.zeros(shape, dtype=float)
    order_count = np.zeros(shape, dtype=np.int32)
    trigger_count = np.zeros(shape, dtype=np.int32)
    recovery_count = np.zeros(shape, dtype=np.int32)
    prev_n = np.full(path_count, initial_prices[0], dtype=float)
    prev_g = np.full(path_count, initial_prices[1], dtype=float)
    slip = SLIPPAGE_BPS / 10_000.0

    for step in range(steps):
        sampled = indices[:, step]
        gap_n, gap_g = source["gap"][sampled].T
        high_n, high_g = source["high_open"][sampled].T
        low_n, low_g = source["low_open"][sampled].T
        close_n, close_g = source["close_open"][sampled].T
        open_n = prev_n * gap_n
        open_g = prev_g * gap_g

        distribution = source["distribution"][sampled]
        cash += qty_n * distribution[:, None]
        pretrade_open_nav = cash + qty_n * open_n[:, None] + qty_g * open_g[:, None]

        rebalance = np.ones(shape, dtype=bool) if step == 0 else np.isfinite(pending)
        target = np.where(step == 0, initials[None, :], np.where(rebalance, pending, current))
        desired_n = np.floor(prior_nav * target * 0.5 / prev_n[:, None]).astype(np.int64)
        desired_g = np.floor(prior_nav * target * 0.5 / prev_g[:, None]).astype(np.int64)
        desired_n = np.where(rebalance, desired_n, qty_n)
        desired_g = np.where(rebalance, desired_g, qty_g)

        sell_n = np.maximum(qty_n - desired_n, 0)
        fill_n = open_n[:, None] * (1.0 - slip)
        notional = sell_n * fill_n
        charges = fee_total(notional, "sell", FEE_PRODUCTS[0])
        cash += notional - charges
        qty_n -= sell_n
        fees += charges
        slippage += sell_n * open_n[:, None] * slip
        order_count += sell_n > 0

        sell_g = np.maximum(qty_g - desired_g, 0)
        fill_g = open_g[:, None] * (1.0 - slip)
        notional = sell_g * fill_g
        charges = fee_total(notional, "sell", FEE_PRODUCTS[1])
        cash += notional - charges
        qty_g -= sell_g
        fees += charges
        slippage += sell_g * open_g[:, None] * slip
        order_count += sell_g > 0

        buy_n = np.maximum(desired_n - qty_n, 0)
        fill_n = open_n[:, None] * (1.0 + slip)
        buy_n = np.minimum(buy_n, buy_capacity(cash, fill_n, FEE_PRODUCTS[0]))
        notional = buy_n * fill_n
        charges = fee_total(notional, "buy", FEE_PRODUCTS[0])
        over_cash = notional + charges > cash + 1e-8
        buy_n = np.maximum(buy_n - over_cash.astype(np.int64), 0)
        notional = buy_n * fill_n
        charges = fee_total(notional, "buy", FEE_PRODUCTS[0])
        cash -= notional + charges
        qty_n += buy_n
        fees += charges
        slippage += buy_n * open_n[:, None] * slip
        order_count += buy_n > 0

        buy_g = np.maximum(desired_g - qty_g, 0)
        fill_g = open_g[:, None] * (1.0 + slip)
        buy_g = np.minimum(buy_g, buy_capacity(cash, fill_g, FEE_PRODUCTS[1]))
        notional = buy_g * fill_g
        charges = fee_total(notional, "buy", FEE_PRODUCTS[1])
        over_cash = notional + charges > cash + 1e-8
        buy_g = np.maximum(buy_g - over_cash.astype(np.int64), 0)
        notional = buy_g * fill_g
        charges = fee_total(notional, "buy", FEE_PRODUCTS[1])
        cash -= notional + charges
        qty_g += buy_g
        fees += charges
        slippage += buy_g * open_g[:, None] * slip
        order_count += buy_g > 0

        current = np.where(rebalance, target, current)
        pending = np.where(rebalance, np.nan, pending)
        high_nav = np.maximum(
            pretrade_open_nav,
            cash + qty_n * (open_n * high_n)[:, None] + qty_g * (open_g * high_g)[:, None],
        )
        low_nav = np.minimum(
            pretrade_open_nav,
            cash + qty_n * (open_n * low_n)[:, None] + qty_g * (open_g * low_g)[:, None],
        )

        mark_n = open_n * close_n
        mark_g = open_g * close_g
        close_nav = cash + qty_n * mark_n[:, None] + qty_g * mark_g[:, None]

        if step == steps - 1:
            for qty, mark, product in (
                (qty_n, mark_n, FEE_PRODUCTS[0]),
                (qty_g, mark_g, FEE_PRODUCTS[1]),
            ):
                fill = mark[:, None] * (1.0 - slip)
                notional = qty * fill
                charges = fee_total(notional, "sell", product)
                cash += notional - charges
                fees += charges
                slippage += qty * mark[:, None] * slip
                order_count += qty > 0
                qty[:] = 0
            close_nav = cash.copy()
            high_nav = np.maximum(high_nav, close_nav)
            low_nav = np.minimum(low_nav, close_nav)

        close_peak = np.maximum(close_peak, close_nav)
        close_dd = close_nav / close_peak - 1.0
        worst_close = np.minimum(worst_close, close_dd)
        ohlc_peak = np.maximum(ohlc_peak, high_nav)
        ohlc_dd = low_nav / ohlc_peak - 1.0
        worst_ohlc = np.minimum(worst_ohlc, ohlc_dd)

        if step < steps - 1:
            cut = np.isfinite(triggers)[None, :] & (current >= 0.60 - 1e-12) & (close_dd <= -triggers[None, :])
            recover = np.isfinite(triggers)[None, :] & (current <= 0.30 + 1e-12) & (close_dd >= -triggers[None, :] / 2.0)
            pending = np.where(cut, 0.30, np.where(recover, 0.60, pending))
            trigger_count += cut
            recovery_count += recover

        prior_nav = close_nav
        prev_n, prev_g = mark_n, mark_g

    return {
        "ending_balance_inr": close_nav,
        "close_mdd_pct": worst_close * 100,
        "ohlc_bound_pct": worst_ohlc * 100,
        "total_fees_inr": fees,
        "total_slippage_inr": slippage,
        "order_count": order_count,
        "trigger_count": trigger_count,
        "recovery_count": recovery_count,
    }


def self_check(source: dict[str, np.ndarray], dates: np.ndarray, initial_prices: np.ndarray) -> None:
    control._self_check()
    bootstrap.check_sampler()
    for product in set(FEE_PRODUCTS):
        for side in ("buy", "sell"):
            for notional in (10_000.0, 250_000.0):
                expected = q._fee_breakdown(notional, side, product)["total"]
                actual = float(fee_total(np.array([notional]), side, product)[0])
                assert abs(actual - expected) < 1e-8, (product, side, notional, actual, expected)

    historical = np.arange(len(dates), dtype=np.int32)[None, :]
    replay = simulate(historical, source, initial_prices)
    _, panels, _, _ = blend.make_portfolios()
    for column, (name, exposure, trigger) in enumerate(POLICIES):
        _, _, stats = control.simulate(
            panels, name, exposure, trigger, SLIPPAGE_BPS, start=START, end=END,
        )
        saved = pd.read_csv(ROOT / "outputs" / "passive_drawdown_control_sensitivity.csv")
        row = saved.loc[(saved["strategy"] == name) & (saved["slippage_bps_per_side"] == SLIPPAGE_BPS)].iloc[0]
        assert abs(replay["ending_balance_inr"][0, column] - stats["ending_balance_inr"]) <= 0.03
        assert abs(replay["total_fees_inr"][0, column] - stats["total_fees_inr"]) <= 0.03
        assert abs(replay["total_slippage_inr"][0, column] - stats["total_slippage_inr"]) <= 0.03
        assert int(replay["order_count"][0, column]) == stats["order_count"]
        assert int(replay["trigger_count"][0, column]) == stats["trigger_count"]
        assert int(replay["recovery_count"][0, column]) == stats["recovery_count"]
        assert abs(replay["close_mdd_pct"][0, column] - stats["max_drawdown_pct"]) <= 1e-8
        assert abs(replay["ohlc_bound_pct"][0, column] - row["ohlc_drawdown_bound_pct"]) <= 0.01


def main() -> None:
    source, dates, initial_prices = load_source()
    self_check(source, dates, initial_prices)
    rows = []
    for block_number, mean_block in enumerate(BLOCK_LENGTHS):
        indices = bootstrap.stationary_indices(
            N_PATHS, HORIZON, len(dates), mean_block, SEED + block_number * 10_000,
        )
        result = simulate(indices, source, initial_prices)
        for column, (name, exposure, trigger) in enumerate(POLICIES):
            close_breach = result["close_mdd_pct"][:, column] <= -20.0
            ohlc_breach = result["ohlc_bound_pct"][:, column] <= -20.0
            terminal = result["ending_balance_inr"][:, column]
            p_close = float(close_breach.mean())
            p_ohlc = float(ohlc_breach.mean())
            rows.append({
                "method": "stateful_joint_ohlc_stationary_bootstrap",
                "strategy": name,
                "initial_exposure_pct": exposure * 100,
                "drawdown_trigger_pct": trigger if trigger is not None else "",
                "recovery_pct": trigger / 2 if trigger is not None else "",
                "slippage_bps_per_side": SLIPPAGE_BPS,
                "source_start": dates[0].isoformat(),
                "source_end": dates[-1].isoformat(),
                "source_sessions": len(dates),
                "horizon_sessions": HORIZON,
                "mean_block_sessions": mean_block,
                "simulations": N_PATHS,
                "close_mdd_breach_probability_pct": 100 * p_close,
                "close_breach_mcse_pp": 100 * np.sqrt(p_close * (1 - p_close) / N_PATHS),
                "ohlc_bound_breach_probability_pct": 100 * p_ohlc,
                "ohlc_breach_mcse_pp": 100 * np.sqrt(p_ohlc * (1 - p_ohlc) / N_PATHS),
                "median_close_mdd_pct": float(np.median(result["close_mdd_pct"][:, column])),
                "p05_ohlc_bound_pct": float(np.quantile(result["ohlc_bound_pct"][:, column], 0.05)),
                "median_cagr_pct": 100 * ((float(np.median(terminal)) / CAPITAL) ** (252 / HORIZON) - 1),
                "p10_cagr_pct": 100 * ((float(np.quantile(terminal, 0.10)) / CAPITAL) ** (252 / HORIZON) - 1),
                "median_ending_balance_inr": float(np.median(terminal)),
                "p10_ending_balance_inr": float(np.quantile(terminal, 0.10)),
                "median_triggers": float(np.median(result["trigger_count"][:, column])),
                "median_recoveries": float(np.median(result["recovery_count"][:, column])),
                "mean_fees_inr": float(result["total_fees_inr"][:, column].mean()),
                "mean_slippage_inr": float(result["total_slippage_inr"][:, column].mean()),
            })
        print(f"finished stateful {mean_block}-session blocks", flush=True)

    frame = pd.DataFrame(rows)
    assert len(frame) == len(BLOCK_LENGTHS) * len(POLICIES)
    assert frame["ohlc_bound_breach_probability_pct"].between(0, 100).all()
    assert frame["close_mdd_breach_probability_pct"].between(0, 100).all()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(OUT, index=False)
    print(f"wrote {len(frame)} stateful bootstrap rows to {OUT}")


if __name__ == "__main__":
    main()
