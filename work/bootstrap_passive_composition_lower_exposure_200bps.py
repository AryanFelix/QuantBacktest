"""Bootstrap low-exposure and 45% NIFTY/Gold mixes at 200 bps."""

from pathlib import Path

import numpy as np
import pandas as pd

import backtest_passive_mix_drawdown_control as control
import benchmark_nifty_gold_2020 as benchmark
import bootstrap_etf_drawdown_risk as bootstrap
import bootstrap_stateful_drawdown_control as stateful
import replay_volatility_weighted_blend as blend


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs" / "passive_mix_composition_lower_exposure_200bps_bootstrap.csv"
STRESS = ROOT / "outputs" / "passive_mix_composition_lower_exposure_200bps.csv"
SLIPPAGE_BPS = 200.0
EXPOSURES = (0.10, 0.15, 0.20, 0.25, 0.30, 0.45)
LOW_EXPOSURE_POLICIES = tuple(
    (f"initial_{int(exposure * 100)}pct_nifty_30_gold_70", exposure, None)
    for exposure in EXPOSURES
) + (
    ("initial_20pct_nifty_50_gold_50", 0.20, None),
    ("initial_20pct_nifty_70_gold_30", 0.20, None),
)
COMPOSITION_CHALLENGERS = (
    ("initial_30pct_nifty_40_gold_60", 0.30, None),
    ("initial_30pct_nifty_50_gold_50", 0.30, None),
    ("initial_30pct_nifty_70_gold_30", 0.30, None),
    ("initial_45pct_nifty_40_gold_60", 0.45, None),
    ("initial_45pct_nifty_50_gold_50", 0.45, None),
    ("initial_45pct_nifty_70_gold_30", 0.45, None),
)
POLICIES = LOW_EXPOSURE_POLICIES + COMPOSITION_CHALLENGERS
NIFTY_SHARE_BY_POLICY = {
    **{name: 0.30 for name, _, _ in LOW_EXPOSURE_POLICIES[:len(EXPOSURES)]},
    "initial_20pct_nifty_50_gold_50": 0.50,
    "initial_20pct_nifty_70_gold_30": 0.70,
    "initial_30pct_nifty_40_gold_60": 0.40,
    "initial_30pct_nifty_50_gold_50": 0.50,
    "initial_30pct_nifty_70_gold_30": 0.70,
    "initial_45pct_nifty_40_gold_60": 0.40,
    "initial_45pct_nifty_50_gold_50": 0.50,
    "initial_45pct_nifty_70_gold_30": 0.70,
}


def main() -> None:
    stateful.SLIPPAGE_BPS = SLIPPAGE_BPS
    stateful.POLICIES = POLICIES
    stateful.NIFTY_SLEEVE_WEIGHT_BY_POLICY = NIFTY_SHARE_BY_POLICY
    source, dates, initial_prices = stateful.load_source()
    bootstrap.check_sampler()
    _, panels, _, _ = blend.make_portfolios()
    historical = np.arange(len(dates), dtype=np.int32)[None, :]
    replay = stateful.simulate(historical, source, initial_prices)
    stress = pd.read_csv(STRESS)
    for column, (name, exposure, trigger) in enumerate(POLICIES):
        nifty_share = NIFTY_SHARE_BY_POLICY[name]
        targets, events = benchmark._passive_targets(panels, {
            "NIFTYBEES": nifty_share,
            "GOLDBEES": 1.0 - nifty_share,
        })
        _, _, canonical = control.simulate(
            panels, name, exposure, trigger, SLIPPAGE_BPS,
            start=stateful.START, end=stateful.END,
            base_targets=targets, rebalance_events=events,
        )
        expected = stress.loc[
            (stress["strategy"] == f"{name}_continuous_2015_2026_{int(SLIPPAGE_BPS)}bps")
            & (stress["period"] == "continuous_2015_2026")
        ].iloc[0]
        assert abs(replay["ending_balance_inr"][0, column] - canonical["ending_balance_inr"]) <= 0.03
        assert abs(replay["total_fees_inr"][0, column] - canonical["total_fees_inr"]) <= 0.03
        assert abs(replay["total_slippage_inr"][0, column] - canonical["total_slippage_inr"]) <= 0.03
        assert int(replay["order_count"][0, column]) == canonical["order_count"]
        assert abs(replay["close_mdd_pct"][0, column] - canonical["max_drawdown_pct"]) <= 1e-8
        assert abs(replay["ohlc_bound_pct"][0, column] - expected["ohlc_drawdown_bound_pct"]) <= 0.01

    rows = []
    for block_number, mean_block in enumerate(stateful.BLOCK_LENGTHS):
        indices = bootstrap.stationary_indices(
            stateful.N_PATHS, stateful.HORIZON, len(dates), mean_block,
            stateful.SEED + 2_000_000 + block_number * 10_000,
        )
        result = stateful.simulate(indices, source, initial_prices)
        for column, (name, exposure, _) in enumerate(POLICIES):
            nifty_share = NIFTY_SHARE_BY_POLICY[name]
            close_dd = result["close_mdd_pct"][:, column]
            ohlc_dd = result["ohlc_bound_pct"][:, column]
            terminal = result["ending_balance_inr"][:, column]
            breached = ohlc_dd <= -20.0
            probability = float(breached.mean())
            rows.append({
                "strategy": name,
                "initial_exposure_pct": exposure * 100,
                "nifty_sleeve_pct": nifty_share * 100,
                "gold_sleeve_pct": (1.0 - nifty_share) * 100,
                "slippage_bps_per_side": SLIPPAGE_BPS,
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
            })
        print(f"finished 200-bps composition stateful {mean_block}-session blocks", flush=True)

    table = pd.DataFrame(rows)
    assert len(table) == len(POLICIES) * len(stateful.BLOCK_LENGTHS) == 42
    assert table["ohlc_bound_breach_probability_pct"].between(0, 100).all()
    table.to_csv(OUT, index=False)
    print(f"wrote {len(table)} composition bootstrap summaries")


if __name__ == "__main__":
    main()
