"""Bootstrap 30% initial NIFTY/Gold mixes at 50 and 200 bps."""

from pathlib import Path
import sys

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "work"))

import backtest_passive_mix_drawdown_control as control
import benchmark_nifty_gold_2020 as benchmark
import bootstrap_etf_drawdown_risk as bootstrap
import bootstrap_stateful_drawdown_control as stateful
import replay_volatility_weighted_blend as blend

OUT = ROOT / "outputs" / "passive_mix_30pct_composition_cost_bootstrap.csv"
BASELINE = ROOT / "outputs" / "passive_mix_composition_lower_exposure_200bps_bootstrap.csv"
STRESS = ROOT / "outputs" / "passive_mix_composition_lower_exposure_200bps.csv"
COSTS = (50.0, 200.0)
POLICIES = (
    ("initial_30pct_nifty_30_gold_70", 0.30, None),
    ("initial_30pct_nifty_40_gold_60", 0.30, None),
    ("initial_30pct_nifty_50_gold_50", 0.30, None),
    ("initial_30pct_nifty_70_gold_30", 0.30, None),
)
NIFTY_SHARES = {
    "initial_30pct_nifty_30_gold_70": 0.30,
    "initial_30pct_nifty_40_gold_60": 0.40,
    "initial_30pct_nifty_50_gold_50": 0.50,
    "initial_30pct_nifty_70_gold_30": 0.70,
}


def main() -> None:
    stateful.POLICIES = POLICIES
    stateful.NIFTY_SLEEVE_WEIGHT_BY_POLICY = NIFTY_SHARES
    source, dates, initial_prices = stateful.load_source()
    bootstrap.check_sampler()
    _, panels, _, _ = blend.make_portfolios()
    historical = np.arange(len(dates), dtype=np.int32)[None, :]
    stress = pd.read_csv(STRESS)
    cost_ledger = pd.read_csv(ROOT / "outputs" / "passive_mix_30pct_composition_cost.csv")
    rows = []

    for cost in COSTS:
        stateful.SLIPPAGE_BPS = cost
        replay = stateful.simulate(historical, source, initial_prices)
        for column, (name, exposure, trigger) in enumerate(POLICIES):
            nifty_share = NIFTY_SHARES[name]
            targets, events = benchmark._passive_targets(panels, {
                "NIFTYBEES": nifty_share,
                "GOLDBEES": 1.0 - nifty_share,
            })
            _, _, canonical = control.simulate(
                panels, name, exposure, trigger, cost,
                start=stateful.START, end=stateful.END,
                base_targets=targets, rebalance_events=events,
            )
            assert abs(replay["ending_balance_inr"][0, column] - canonical["ending_balance_inr"]) <= 0.03
            assert abs(replay["total_fees_inr"][0, column] - canonical["total_fees_inr"]) <= 0.03
            assert abs(replay["total_slippage_inr"][0, column] - canonical["total_slippage_inr"]) <= 0.03
            assert int(replay["order_count"][0, column]) == canonical["order_count"]
            assert abs(replay["close_mdd_pct"][0, column] - canonical["max_drawdown_pct"]) <= 1e-8
            if cost == 200.0:
                expected = stress.loc[
                    stress["strategy"].eq(f"{name}_continuous_2015_2026_200bps")
                    & stress["period"].eq("continuous_2015_2026")
                ].iloc[0]
                assert abs(replay["ending_balance_inr"][0, column] - expected["ending_balance_inr"]) <= 0.03
                assert abs(replay["ohlc_bound_pct"][0, column] - expected["ohlc_drawdown_bound_pct"]) <= 0.01
            else:
                expected = cost_ledger.loc[
                    cost_ledger["strategy"].eq(f"{name}_continuous_2015_2026_50bps")
                    & cost_ledger["period"].eq("continuous_2015_2026")
                ].iloc[0]
                assert abs(replay["ohlc_bound_pct"][0, column] - expected["ohlc_drawdown_bound_pct"]) <= 0.01

    baseline = pd.read_csv(BASELINE)
    for block_number, mean_block in enumerate(stateful.BLOCK_LENGTHS):
        indices = bootstrap.stationary_indices(
            stateful.N_PATHS, stateful.HORIZON, len(dates), mean_block,
            stateful.SEED + 2_000_000 + block_number * 10_000,
        )
        for cost in COSTS:
            stateful.SLIPPAGE_BPS = cost
            result = stateful.simulate(indices, source, initial_prices)
            for column, (name, exposure, _) in enumerate(POLICIES):
                close_dd = result["close_mdd_pct"][:, column]
                ohlc_dd = result["ohlc_bound_pct"][:, column]
                terminal = result["ending_balance_inr"][:, column]
                breached = ohlc_dd <= -20.0
                probability = float(breached.mean())
                row = {
                    "strategy": name,
                    "initial_exposure_pct": exposure * 100,
                    "nifty_sleeve_pct": NIFTY_SHARES[name] * 100,
                    "gold_sleeve_pct": (1.0 - NIFTY_SHARES[name]) * 100,
                    "slippage_bps_per_side": cost,
                    "source_start": dates[0].isoformat(),
                    "source_end": dates[-1].isoformat(),
                    "source_sessions": len(dates),
                    "horizon_sessions": stateful.HORIZON,
                    "mean_block_sessions": mean_block,
                    "simulations": stateful.N_PATHS,
                    "ohlc_bound_breach_probability_pct": 100 * probability,
                    "ohlc_breach_mcse_pp": 100 * np.sqrt(probability * (1 - probability) / stateful.N_PATHS),
                    "median_close_mdd_pct": float(np.median(close_dd)),
                    "p05_ohlc_bound_pct": float(np.quantile(ohlc_dd, 0.05)),
                    "median_cagr_pct": 100 * ((float(np.median(terminal)) / stateful.CAPITAL) ** (252 / stateful.HORIZON) - 1),
                    "p10_cagr_pct": 100 * ((float(np.quantile(terminal, 0.10)) / stateful.CAPITAL) ** (252 / stateful.HORIZON) - 1),
                    "median_ending_balance_inr": float(np.median(terminal)),
                    "p10_ending_balance_inr": float(np.quantile(terminal, 0.10)),
                    "mean_fees_inr": float(result["total_fees_inr"][:, column].mean()),
                    "mean_slippage_inr": float(result["total_slippage_inr"][:, column].mean()),
                }
                if cost == 200.0:
                    prior = baseline.loc[
                        baseline["strategy"].eq(name)
                        & baseline["mean_block_sessions"].eq(mean_block)
                    ].iloc[0]
                    for key in (
                        "ohlc_bound_breach_probability_pct",
                        "p05_ohlc_bound_pct",
                        "median_cagr_pct",
                        "p10_cagr_pct",
                    ):
                        assert abs(float(row[key]) - float(prior[key])) <= 1e-8, (key, row[key], prior[key])
                rows.append(row)

    table = pd.DataFrame(rows)
    assert len(table) == len(POLICIES) * len(COSTS) * len(stateful.BLOCK_LENGTHS) == 24
    assert table["ohlc_bound_breach_probability_pct"].between(0, 100).all()
    assert not table.duplicated(["strategy", "slippage_bps_per_side", "mean_block_sessions"]).any()
    table.to_csv(OUT, index=False)
    print(f"wrote {len(table)} paired-cost bootstrap summaries")


if __name__ == "__main__":
    main()
