"""Block-bootstrap drawdown risk for the frozen NIFTY/Gold ETF candidates."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs" / "etf_drawdown_bootstrap.csv"
BLOCK_LENGTHS = (21, 63, 126)
SIMULATIONS = 5_000
HORIZONS = {"1y": 252, "3y": 756, "5y": 1_260, "10y": 2_520}
CAPITAL = 1_000_000
SEED = 2_610_270
CASES = [
    ("Quarterly fixed 50/50 control", 50, "work/backtests/volatility_weighted_blend/fixed_50_50_quarterly__full_2014_plus__50bps/equity.csv"),
    ("Quarterly fixed control; 45% gross cap", 50, "work/backtests/intraday_ohlc_exposure/gross_cap_45pct__50bps/equity.csv"),
    ("Quarterly fixed control; 70% gross cap", 50, "work/backtests/intraday_ohlc_exposure/gross_cap_70pct__50bps/equity.csv"),
    ("Quarterly inverse-vol; 65% solo; 16% throttle", 50, "work/backtests/cost_stress_sensitivity/solo65_vol16__full_2014_plus__50bps/equity.csv"),
    ("Quarterly inverse-vol; 80% solo; 16% throttle", 50, "work/backtests/cost_stress_sensitivity/solo80_vol16__full_2014_plus__50bps/equity.csv"),
    ("Quarterly inverse-vol; 65% solo; 16% throttle", 100, "work/backtests/cost_stress_sensitivity/solo65_vol16__full_2014_plus__100bps/equity.csv"),
    ("Quarterly inverse-vol; 80% solo; 16% throttle", 100, "work/backtests/cost_stress_sensitivity/solo80_vol16__full_2014_plus__100bps/equity.csv"),
    ("Quarterly inverse-vol; 50/50 active sleeves", 50, "work/backtests/volatility_weighted_blend/inverse_vol_63d_quarterly__full_2014_plus__50bps/equity.csv"),
    ("Passive NIFTY/Gold; 22.5% each initial", 50, "work/backtests/nifty_gold_full_history_benchmarks/passive_NIFTY_Gold_22_5pct_each/equity.csv"),
    ("Passive NIFTY/Gold; 55% initial", 50, "work/backtests/passive_mix_exposure/continuous_2015_plus/passive_equal_055_continuous_2015_plus/equity.csv"),
    ("Passive NIFTY/Gold; 60% initial", 50, "work/backtests/passive_mix_exposure/continuous_2015_plus/passive_equal_060_continuous_2015_plus/equity.csv"),
    ("Passive NIFTY/Gold; 45% initial; 2015 common", 50, "work/backtests/passive_mix_exposure/continuous_2015_plus/passive_equal_045_continuous_2015_plus/equity.csv"),
    ("Passive NIFTY/Gold; 50% initial; 2015 common", 50, "work/backtests/passive_mix_exposure/continuous_2015_plus/passive_equal_050_continuous_2015_plus/equity.csv"),
    ("Passive NIFTY/Gold; DD8% cut 60 to 30; 2015 common", 50, "work/backtests/passive_drawdown_control/dd_8pct_cut_60_to_30_recover_4pct__50bps/equity.csv"),
    ("Passive NIFTY/Gold; DD10% cut 60 to 30; 2015 common", 50, "work/backtests/passive_drawdown_control/dd_10pct_cut_60_to_30_recover_5pct__50bps/equity.csv"),
    ("Passive NIFTY/Gold; DD12% cut 60 to 30; 2015 common", 50, "work/backtests/passive_drawdown_control/dd_12pct_cut_60_to_30_recover_6pct__50bps/equity.csv"),
]


def stationary_indices(n_paths: int, n_days: int, n_observations: int, mean_block: int, seed: int) -> np.ndarray:
    rng = np.random.default_rng(seed)
    indices = np.empty((n_paths, n_days), dtype=np.int32)
    indices[:, 0] = rng.integers(n_observations, size=n_paths)
    for day in range(1, n_days):
        restart = rng.random(n_paths) < 1 / mean_block
        fresh = rng.integers(n_observations, size=n_paths)
        indices[:, day] = np.where(restart, fresh, (indices[:, day - 1] + 1) % n_observations)
    return indices


def check_sampler() -> None:
    indices = stationary_indices(32, 100, 7, 5, SEED)
    assert indices.shape == (32, 100)
    assert indices.min() >= 0 and indices.max() < 7


def load_returns(relative_path: str) -> tuple[np.ndarray, str]:
    equity = pd.read_csv(ROOT / relative_path, parse_dates=["time"])
    active = equity.loc[equity["gross_exposure"] > 0, "time"]
    if active.empty:
        raise ValueError(f"No active exposure in {relative_path}")
    start = active.iloc[0]
    returns = equity.loc[equity["time"] >= start, "nav"].pct_change(fill_method=None).dropna().to_numpy(dtype=float)
    if len(returns) < HORIZONS["10y"] or np.any(returns <= -1) or not np.isfinite(returns).all():
        raise ValueError(f"Invalid or too-short return history in {relative_path}")
    return returns, start.date().isoformat()


def simulate(returns: np.ndarray, seed: int, mean_block: int) -> dict[str, dict[str, float]]:
    count = SIMULATIONS
    max_days = HORIZONS["10y"]
    batch_size = 500
    terminal = {name: np.empty(count) for name in HORIZONS}
    drawdowns = {name: np.empty(count) for name in HORIZONS}
    for first in range(0, count, batch_size):
        batch = min(batch_size, count - first)
        indices = stationary_indices(batch, max_days, len(returns), mean_block, seed + first)
        wealth = np.cumprod(1 + returns[indices], axis=1)
        peak = np.maximum.accumulate(np.maximum(wealth, 1.0), axis=1)
        dd = wealth / peak - 1.0
        for name, days in HORIZONS.items():
            terminal[name][first:first + batch] = wealth[:, days - 1]
            drawdowns[name][first:first + batch] = dd[:, :days].min(axis=1)

    result = {}
    for name, days in HORIZONS.items():
        nav = terminal[name]
        mdd = drawdowns[name]
        breach = mdd <= -0.20
        probability = breach.mean()
        result[name] = {
            "sessions": days,
            "probability_drawdown_below_20pct": 100 * probability,
            "breach_probability_mcse_pp": 100 * np.sqrt(probability * (1 - probability) / count),
            "median_max_drawdown_pct": 100 * np.median(mdd),
            "p05_max_drawdown_pct": 100 * np.quantile(mdd, 0.05),
            "median_cagr_pct": 100 * (np.median(nav) ** (252 / days) - 1),
            "p10_cagr_pct": 100 * (np.quantile(nav, 0.10) ** (252 / days) - 1),
            "median_ending_balance_inr": CAPITAL * np.median(nav),
            "p10_ending_balance_inr": CAPITAL * np.quantile(nav, 0.10),
        }
    return result


def main() -> None:
    check_sampler()
    rows = []
    for number, (strategy, slippage, path) in enumerate(CASES):
        returns, start = load_returns(path)
        for block_number, mean_block in enumerate(BLOCK_LENGTHS):
            result = simulate(returns, SEED + number * 100_000 + block_number * 10_000, mean_block)
            for horizon, metrics in result.items():
                rows.append({
                    "strategy": strategy,
                    "slippage_bps_per_side": slippage,
                    "bootstrap_start": start,
                    "history_observations": len(returns),
                    "mean_block_sessions": mean_block,
                    "simulations": SIMULATIONS,
                    "horizon": horizon,
                    **metrics,
                    "source_equity": path,
                })
    OUT.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(OUT, index=False)
    print(f"wrote {len(rows)} bootstrap summaries to {OUT}")


if __name__ == "__main__":
    main()
