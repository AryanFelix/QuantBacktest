"""Measure local parameter stability of the fixed NIFTY/Gold ETF trend mix."""

from __future__ import annotations

import math
from datetime import date
from pathlib import Path

import pandas as pd

import replay_volatility_weighted_blend as blend
import upstox_quant as q


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "work" / "backtests" / "etf_parameter_sensitivity"
SUMMARY = ROOT / "outputs" / "etf_parameter_sensitivity.csv"
CAPITAL = 1_000_000
SLIPPAGE = (10, 20, 50)
VARIANTS = (
    ("baseline_D55_20_SMA200", 55, 20, 200),
    ("channel_entry_D40_20_SMA200", 40, 20, 200),
    ("channel_entry_D75_20_SMA200", 75, 20, 200),
    ("channel_exit_D55_10_SMA200", 55, 10, 200),
    ("channel_exit_D55_30_SMA200", 55, 30, 200),
    ("gold_trend_D55_20_SMA150", 55, 20, 150),
    ("gold_trend_D55_20_SMA250", 55, 20, 250),
)


def _channel_target(panels: dict[str, pd.DataFrame], entry_n: int, exit_n: int) -> tuple[pd.Series, pd.Series]:
    close = panels["close"]["NIFTYBEES"]
    high = panels["high"]["NIFTYBEES"]
    low = panels["low"]["NIFTYBEES"]
    entry = close > high.shift(1).rolling(entry_n, min_periods=entry_n).max()
    exit_ = close < low.shift(1).rolling(exit_n, min_periods=exit_n).min()
    target = pd.Series(0.0, index=close.index, name="NIFTYBEES")
    events = pd.Series(False, index=close.index)
    state = False
    for i in range(len(close)):
        new_state = state
        if pd.notna(entry.iloc[i]) and bool(entry.iloc[i]):
            new_state = True
        elif pd.notna(exit_.iloc[i]) and bool(exit_.iloc[i]):
            new_state = False
        if new_state != state:
            state = new_state
            events.iloc[i] = True
        target.iloc[i] = float(state)
    return target, events


def _trend_target(panels: dict[str, pd.DataFrame], window: int) -> tuple[pd.Series, pd.Series]:
    close = panels["close"]["GOLDBEES"]
    trend = close > close.rolling(window, min_periods=window).mean()
    target = pd.Series(0.0, index=close.index, name="GOLDBEES")
    events = pd.Series(False, index=close.index)
    state = False
    for i, value in enumerate(trend):
        new_state = bool(value) if pd.notna(value) else False
        if new_state != state:
            state = new_state
            events.iloc[i] = True
        target.iloc[i] = float(state)
    return target, events


def _portfolio(panels: dict[str, pd.DataFrame], channel_n: int, exit_n: int, trend_n: int):
    nifty, nifty_events = _channel_target(panels, channel_n, exit_n)
    gold, gold_events = _trend_target(panels, trend_n)
    active = pd.concat([nifty, gold], axis=1).reindex(columns=["NIFTYBEES", "GOLDBEES"])
    targets = active * 0.5
    events = nifty_events | gold_events
    month_ends = pd.Series(active.index, index=active.index).groupby(active.index.strftime("%Y-%m")).last()
    events.loc[pd.DatetimeIndex(month_ends.to_list())] = True
    assert targets.columns.tolist() == ["NIFTYBEES", "GOLDBEES"]
    assert ((targets == 0.0) | (targets == 0.5)).all().all()
    assert (targets.sum(axis=1) <= 1.0 + 1e-12).all()
    assert events.loc[pd.DatetimeIndex(month_ends.to_list())].all()
    return targets, events


def main() -> None:
    files, panels, canonical, canonical_events = blend.make_portfolios()
    end = panels["close"].index[-1].date()
    periods = (
        ("train_2014_2019", date(2014, 1, 1), date(2019, 12, 31), "train_2014_2019"),
        ("validation_2020_2022", date(2020, 1, 1), date(2022, 12, 31), "validation_2020_2022"),
        ("recent_2023_plus", date(2023, 1, 1), end, "holdout_2023_plus"),
        ("full_2020_plus", date(2020, 1, 1), end, "full_2020_plus"),
        ("full_2014_plus", date(2014, 1, 1), end, "full_2014_plus"),
    )
    reference = pd.read_csv(OUT / ".." / "volatility_weighted_blend" / "summary.csv")
    rows = []
    OUT.mkdir(parents=True, exist_ok=True)
    for name, entry_n, exit_n, trend_n in VARIANTS:
        targets, events = _portfolio(panels, entry_n, exit_n, trend_n)
        if name == "baseline_D55_20_SMA200":
            assert targets.equals(canonical["fixed_50_50"])
            assert events.equals(canonical_events["fixed_50_50"])
        for period, start, finish, reference_period in periods:
            for slip in SLIPPAGE:
                equity, orders, stats = q._simulate(
                    panels, targets, events, CAPITAL, 1.0, slip,
                    "equity_delivery", start, finish, 20,
                )
                stats["total_slippage_inr"] = blend.modeled_slippage(orders, panels)
                row = {
                    "variant": name,
                    "nifty_donchian_entry_sessions": entry_n,
                    "nifty_donchian_exit_sessions": exit_n,
                    "gold_sma_sessions": trend_n,
                    "period": period,
                    "reference_period": reference_period,
                    "slippage_bps_per_side": slip,
                    "exposure_cap_pct": 100,
                    **stats,
                }
                rows.append(row)
                run = OUT / f"{name}__{period}__{slip}bps"
                run.mkdir(exist_ok=True)
                equity.to_csv(run / "equity.csv", index_label="time")
                orders.to_csv(run / "orders.csv", index=False)

                if name == "baseline_D55_20_SMA200" and slip in (10, 50):
                    expected = reference[
                        reference["portfolio"].eq("fixed_50_50")
                        & reference["period"].eq(reference_period)
                        & reference["slippage_bps_per_side"].eq(slip)
                    ]
                    assert len(expected) == 1
                    for key in ("ending_balance_inr", "max_drawdown_pct", "total_fees_inr", "order_count"):
                        actual_value = float(stats[key])
                        expected_value = float(expected.iloc[0][key])
                        assert math.isclose(actual_value, expected_value, rel_tol=0, abs_tol=1e-7), (key, actual_value, expected_value)
    result = pd.DataFrame(rows)
    assert len(result) == len(VARIANTS) * len(periods) * len(SLIPPAGE)
    result.to_csv(SUMMARY, index=False)
    print(f"wrote {len(result)} sensitivity cases; data end {end}; caches: {len(files)}")


if __name__ == "__main__":
    main()
