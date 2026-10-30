"""Check neighboring high-exposure NIFTY/Gold mixes with and without T-bill proxy yield."""

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

OUT = ROOT / "outputs" / "quarterly_static_cash_yield_neighbor_screen.csv"
BOOT_OUT = ROOT / "outputs" / "quarterly_static_cash_yield_neighbor_bootstrap.csv"
RUNS = ROOT / "work" / "backtests" / "quarterly_static_cash_yield_neighbors"
CASES = ((60, 10, 90), (65, 10, 90), (65, 40, 60), (70, 40, 60), (70, 50, 50))
SLIPPAGE = 200


def main() -> None:
    self_check_cash_yield()
    _, panels, _, _ = blend.make_portfolios()
    rates = _cash_rates_on_sessions(panels["close"].index)
    base_targets, events = benchmark._quarterly_static_targets(panels)
    end = panels["close"].index[-1].date()
    periods = (("continuous_2015_2026", date(2015, 1, 2), end), *walkforward.PERIODS)
    replay_rows = []
    bootstrap_cases = []

    for cap, nifty, gold in CASES:
        targets = base_targets.copy()
        targets["NIFTYBEES"], targets["GOLDBEES"] = nifty / 100, gold / 100
        assert (targets.sum(axis=1) == 1.0).all()
        for period, start, period_end in periods:
            values = {}
            for mode, cash_rates in (("zero_yield", None), ("tbill_proxy", rates)):
                name = f"quarterly_static_{nifty:02d}_{gold:02d}_{cap}pct_{period}_200bps_{mode}"
                values[mode] = benchmark._run(
                    name, targets, events, panels, period_end, start=start,
                    run_dir=RUNS / mode / period,
                    cash_distributions=benchmark.NIFTYBEES_DISTRIBUTIONS,
                    exposure_cap=cap / 100, slippage_bps=SLIPPAGE,
                    cash_yield_series=cash_rates,
                )
            assert values["tbill_proxy"]["cash_yield_inr"] > 0
            assert values["zero_yield"]["max_close_replay_error_inr"] <= 0.03
            assert values["tbill_proxy"]["max_close_replay_error_inr"] <= 0.03
            replay_rows.append({
                "period": period,
                "gross_exposure_cap_pct": cap,
                "nifty_sleeve_pct": nifty,
                "gold_sleeve_pct": gold,
                "slippage_bps_per_side": SLIPPAGE,
                **{f"zero_yield_{key}": value for key, value in values["zero_yield"].items()},
                **{f"tbill_proxy_{key}": value for key, value in values["tbill_proxy"].items()},
            })
            if period == "continuous_2015_2026":
                for mode in ("zero_yield", "tbill_proxy"):
                    name = f"quarterly_static_{nifty:02d}_{gold:02d}_{cap}pct_{period}_200bps_{mode}"
                    bootstrap_cases.append((cap, nifty, gold, mode, RUNS / mode / period / name / "equity.csv"))

    assert len(replay_rows) == len(CASES) * len(periods) == 20
    pd.DataFrame(replay_rows).to_csv(OUT, index=False)
    bootstrap_rows = []
    for case_number, (cap, nifty, gold, mode, path) in enumerate(bootstrap_cases):
        returns, start_date = bootstrap.load_returns(path)
        for block_number, mean_block in enumerate(bootstrap.BLOCK_LENGTHS):
            seed = bootstrap.SEED + 10_000_000 + case_number * 100_000 + block_number * 10_000
            for horizon, metrics in bootstrap.simulate(returns, seed, mean_block).items():
                bootstrap_rows.append({
                    "strategy": f"Quarterly static {cap}% cap; {nifty}/{gold} NIFTY/Gold; {mode}",
                    "cash_yield_mode": mode,
                    "slippage_bps_per_side": SLIPPAGE,
                    "gross_exposure_cap_pct": cap,
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
    assert len(bootstrap_rows) == len(CASES) * 2 * len(bootstrap.BLOCK_LENGTHS) * len(bootstrap.HORIZONS) == 120
    pd.DataFrame(bootstrap_rows).to_csv(BOOT_OUT, index=False)
    print(f"Wrote {len(replay_rows)} neighboring replay pairs and {len(bootstrap_rows)} bootstrap summaries.")


if __name__ == "__main__":
    main()
