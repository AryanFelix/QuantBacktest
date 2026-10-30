"""Screen two 65% cap challengers against the zero-yield and T-bill controls."""

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
from stress_quarterly_static_mix_cash_yield import _cash_rates_on_sessions, self_check_cash_yield

OUT = ROOT / "outputs" / "quarterly_static_mix_cash_yield_65pct_challengers.csv"
BOOT_OUT = ROOT / "outputs" / "quarterly_static_mix_cash_yield_65pct_bootstrap.csv"
RUNS = ROOT / "work" / "backtests" / "quarterly_static_mix_cash_yield_65pct"
CAP = 0.65
MIXES = ((20, 80), (30, 70))
SLIPPAGE = 200


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
    replay_rows = []
    equity_paths = []
    for nifty, gold in MIXES:
        targets = base_targets.copy()
        targets["NIFTYBEES"], targets["GOLDBEES"] = nifty / 100, gold / 100
        assert (targets.sum(axis=1) == 1.0).all()
        for period, start, end in periods:
            base_name = f"quarterly_static_{nifty:02d}_{gold:02d}_65pct_{period}_200bps_zero_yield"
            base = benchmark._run(
                base_name, targets, events, panels, end, start=start,
                run_dir=RUNS / "zero_yield" / period,
                cash_distributions=benchmark.NIFTYBEES_DISTRIBUTIONS,
                exposure_cap=CAP, slippage_bps=SLIPPAGE,
            )
            cash_name = f"quarterly_static_{nifty:02d}_{gold:02d}_65pct_{period}_200bps_cash_yield"
            cash = benchmark._run(
                cash_name, targets, events, panels, end, start=start,
                run_dir=RUNS / "tbill_proxy" / period,
                cash_distributions=benchmark.NIFTYBEES_DISTRIBUTIONS,
                exposure_cap=CAP, slippage_bps=SLIPPAGE,
                cash_yield_series=cash_yields,
            )
            assert cash["cash_yield_inr"] > 0 and cash["max_close_replay_error_inr"] <= 0.03
            replay_rows.append({
                "period": period,
                "gross_exposure_cap_pct": 65,
                "nifty_sleeve_pct": nifty,
                "gold_sleeve_pct": gold,
                "slippage_bps_per_side": SLIPPAGE,
                **{f"zero_yield_{key}": value for key, value in base.items()},
                **{f"tbill_proxy_{key}": value for key, value in cash.items()},
            })
            for mode, name in (("zero_yield", base_name), ("tbill_proxy", cash_name)):
                equity_paths.append((nifty, gold, mode, RUNS / mode / period / name / "equity.csv"))
    assert len(replay_rows) == len(MIXES) * len(periods) == 8
    pd.DataFrame(replay_rows).to_csv(OUT, index=False)

    bootstrap_rows = []
    full_history_paths = [case for case in equity_paths if "continuous_2015_2026" in str(case[3])]
    assert len(full_history_paths) == len(MIXES) * 2
    for case_number, (nifty, gold, mode, path) in enumerate(full_history_paths):
        for block_number, mean_block in enumerate(bootstrap.BLOCK_LENGTHS):
            returns, start_date = bootstrap.load_returns(path)
            seed = bootstrap.SEED + 9_000_000 + case_number * 100_000 + block_number * 10_000
            for horizon, metrics in bootstrap.simulate(returns, seed, mean_block).items():
                bootstrap_rows.append({
                    "strategy": f"65% cap; {nifty}/{gold} NIFTY/Gold; {mode}",
                    "cash_yield_mode": mode,
                    "slippage_bps_per_side": SLIPPAGE,
                    "gross_exposure_cap_pct": 65,
                    "nifty_sleeve_pct": nifty,
                    "gold_sleeve_pct": gold,
                    "bootstrap_start": start_date,
                    "history_observations": len(returns),
                    "mean_block_sessions": mean_block,
                    "simulations": 5000,
                    "horizon": horizon,
                    **metrics,
                    "source_equity": str(path.relative_to(ROOT)),
                })
    assert len(bootstrap_rows) == 48
    pd.DataFrame(bootstrap_rows).to_csv(BOOT_OUT, index=False)
    print(f"Wrote {len(replay_rows)} 65% challenger replay pairs and {len(bootstrap_rows)} bootstrap summaries.")


if __name__ == "__main__":
    main()
