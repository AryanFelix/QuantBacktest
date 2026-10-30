"""Compare zero-yield cash with a synthetic RBI 91-day T-bill cash return."""

from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "work"))

import benchmark_nifty_gold_2020 as benchmark
import bootstrap_etf_drawdown_risk as bootstrap
import replay_volatility_weighted_blend as blend
import select_passive_drawdown_control_walkforward as walkforward
import upstox_quant as q

RATES = ROOT / "outputs" / "rbi_91d_tbill_yields_2015_2026.csv"
ZERO_YIELD_REPLAYS = ROOT / "outputs" / "quarterly_static_mix_cost_sensitivity.csv"
OUT = ROOT / "outputs" / "quarterly_static_mix_cash_yield_sensitivity.csv"
BOOT_OUT = ROOT / "outputs" / "quarterly_static_mix_cash_yield_bootstrap.csv"
RUNS = ROOT / "work" / "backtests" / "quarterly_static_mix_cash_yield"
CAPITAL = 1_000_000.0
MIXES_55 = tuple((nifty, 100 - nifty) for nifty in range(0, 101, 10))
MIXES_60 = ((20, 80), (30, 70), (40, 60), (50, 50))


def _cash_rates_on_sessions(index: pd.DatetimeIndex) -> pd.Series:
    rates = pd.read_csv(RATES, parse_dates=["auction_date", "issue_date"])
    rates["cutoff_yield_pct"] = pd.to_numeric(rates["cutoff_yield_pct"], errors="coerce").ffill()
    if rates["issue_date"].duplicated().any() or rates["cutoff_yield_pct"].isna().any():
        raise ValueError("T-bill issue dates must be unique and have a known carried yield")
    rates = rates.sort_values("issue_date")
    session_dates = index.tz_localize(None) if index.tz is not None else index
    session_dates = session_dates.normalize()
    sessions = pd.DataFrame({"session_date": session_dates, "timestamp": index})
    aligned = pd.merge_asof(
        sessions.sort_values("session_date"),
        rates[["issue_date", "cutoff_yield_pct"]].sort_values("issue_date"),
        left_on="session_date", right_on="issue_date", direction="backward",
    )
    in_scope = aligned["session_date"] >= pd.Timestamp("2015-01-02")
    if aligned.loc[in_scope, "cutoff_yield_pct"].isna().any():
        raise ValueError("T-bill yield history does not cover every research-period session")
    return pd.Series(aligned["cutoff_yield_pct"].to_numpy(dtype=float), index=index)


def self_check_cash_yield() -> None:
    index = pd.date_range("2025-01-01", periods=2, tz="Asia/Kolkata")
    prices = pd.DataFrame({"CASH": [100.0, 100.0]}, index=index)
    targets = pd.DataFrame({"CASH": [0.0, 0.0]}, index=index)
    events = pd.Series(False, index=index)
    yields = pd.Series([5.0, 5.0], index=index)
    equity, _, stats = q._simulate(
        {"open": prices, "close": prices}, targets, events, 1_000_000.0,
        0.55, 0, start=date(2025, 1, 1), end=date(2025, 1, 2),
        cash_yield_series=yields,
    )
    expected_interest = 1_000_000.0 * 0.05 / 365
    assert abs(equity["cash_yield_inr"].sum() - expected_interest) < 1e-8
    assert abs(equity["nav"].iloc[-1] - (1_000_000.0 + expected_interest)) < 1e-8
    assert abs(stats["cash_yield_inr"] - expected_interest) < 1e-8


def main() -> None:
    self_check_cash_yield()
    _, panels, _, _ = blend.make_portfolios()
    cash_yields = _cash_rates_on_sessions(panels["close"].index)
    base_targets, events = benchmark._quarterly_static_targets(panels)
    data_end = panels["close"].index[-1].date()
    periods = (
        ("continuous_2015_2026", date(2015, 1, 2), data_end),
        *walkforward.PERIODS,
    )
    baselines = pd.read_csv(ZERO_YIELD_REPLAYS)
    cases = [
        (55, nifty, gold, 200, period, start, end)
        for nifty, gold in MIXES_55 for period, start, end in periods
    ]
    cases.extend((55, 40, 60, 50, period, start, end) for period, start, end in periods)
    cases.extend(
        (60, nifty, gold, 200, period, start, end)
        for nifty, gold in MIXES_60 for period, start, end in periods
    )
    results = []
    targets_by_mix = {}
    for cap, nifty, gold, cost, period, start, end in cases:
        mix = (nifty, gold)
        if mix not in targets_by_mix:
            targets_by_mix[mix] = base_targets.copy()
            targets_by_mix[mix]["NIFTYBEES"] = nifty / 100
            targets_by_mix[mix]["GOLDBEES"] = gold / 100
            assert (targets_by_mix[mix].sum(axis=1) == 1.0).all()
        baseline = baselines[
            ((baselines["gross_exposure_cap_pct"] - cap).abs() < 1e-6)
            & (baselines["nifty_sleeve_pct"] == nifty)
            & (baselines["gold_sleeve_pct"] == gold)
            & (baselines["slippage_bps_per_side"] == cost)
            & (baselines["period"] == period)
        ]
        if len(baseline) == 0:
            assert (cap, mix, cost) == (60, (20, 80), 200)
            zero_name = f"quarterly_static_{nifty:02d}_{gold:02d}_{cap}pct_{period}_{cost}bps_zero_yield"
            zero = benchmark._run(
                zero_name, targets_by_mix[mix], events, panels, end, start=start,
                run_dir=RUNS / "zero_yield" / period,
                cash_distributions=benchmark.NIFTYBEES_DISTRIBUTIONS,
                exposure_cap=cap / 100, slippage_bps=cost,
            )
            baseline_end = zero["ending_balance_inr"]
            baseline_return = zero["total_return_pct"]
        else:
            assert len(baseline) == 1, f"Duplicate zero-yield control for {period}/{cost}/{mix}"
            baseline_end = float(baseline.iloc[0]["ending_balance_inr"])
            baseline_return = float(baseline.iloc[0]["total_return_pct"])
        name = f"quarterly_static_{nifty:02d}_{gold:02d}_{cap}pct_{period}_{cost}bps_cash_yield"
        row = benchmark._run(
            name, targets_by_mix[mix], events, panels, end, start=start,
            run_dir=RUNS / f"{cost}bps" / period,
            cash_distributions=benchmark.NIFTYBEES_DISTRIBUTIONS,
            exposure_cap=cap / 100, slippage_bps=cost,
            cash_yield_series=cash_yields,
        )
        row.update({
            "period": period,
            "slippage_bps_per_side": cost,
            "gross_exposure_cap_pct": cap,
            "nifty_sleeve_pct": nifty,
            "gold_sleeve_pct": gold,
            "zero_yield_ending_balance_inr": baseline_end,
            "zero_yield_total_return_pct": baseline_return,
            "cash_yield_increment_inr": row["ending_balance_inr"] - baseline_end,
        })
        assert row["cash_yield_inr"] > 0 and row["max_close_replay_error_inr"] <= 0.03
        results.append(row)
    result_frame = pd.DataFrame(results)
    assert len(result_frame) == len(cases) == 64
    result_frame.to_csv(OUT, index=False)

    bootstrap_rows = []
    bootstrap_cases = (
        [(55, *mix) for mix in MIXES_55]
        + [(60, *mix) for mix in MIXES_60]
    )
    for case_number, (cap, nifty, gold) in enumerate(bootstrap_cases):
        full_run = RUNS / "200bps" / periods[0][0] / (
            f"quarterly_static_{nifty:02d}_{gold:02d}_{cap}pct_"
            "continuous_2015_2026_200bps_cash_yield/equity.csv"
        )
        returns, start_date = bootstrap.load_returns(full_run)
        for block_number, mean_block in enumerate(bootstrap.BLOCK_LENGTHS):
            seed = bootstrap.SEED + 8_000_000 + case_number * 100_000 + block_number * 10_000
            for horizon, metrics in bootstrap.simulate(returns, seed, mean_block).items():
                bootstrap_rows.append({
                    "strategy": f"Quarterly static {cap}% cap; {nifty}/{gold} NIFTY/Gold; RBI 91-day cash proxy",
                    "slippage_bps_per_side": 200,
                    "gross_exposure_cap_pct": cap,
                    "nifty_sleeve_pct": nifty,
                    "gold_sleeve_pct": gold,
                    "bootstrap_start": start_date,
                    "history_observations": len(returns),
                    "mean_block_sessions": mean_block,
                    "simulations": 5000,
                    "horizon": horizon,
                    **metrics,
                    "source_equity": str(full_run.relative_to(ROOT)),
                })
    assert len(bootstrap_rows) == len(bootstrap_cases) * len(bootstrap.BLOCK_LENGTHS) * len(bootstrap.HORIZONS) == 180
    pd.DataFrame(bootstrap_rows).to_csv(BOOT_OUT, index=False)
    print(f"Wrote {len(results)} cash-yield/control replays and {len(bootstrap_rows)} cash-yield bootstrap summaries.")


if __name__ == "__main__":
    main()
