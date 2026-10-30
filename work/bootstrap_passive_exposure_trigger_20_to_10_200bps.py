"""Statefully bootstrap the 20%-to-10% passive drawdown throttle."""

from pathlib import Path

import numpy as np
import pandas as pd

import backtest_passive_mix_drawdown_control as control
import benchmark_nifty_gold_2020 as benchmark
import bootstrap_etf_drawdown_risk as bootstrap
import bootstrap_stateful_drawdown_control as stateful
import replay_volatility_weighted_blend as blend


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs" / "passive_exposure_trigger_20_to_10_200bps_bootstrap.csv"
STRESS = ROOT / "outputs" / "passive_exposure_trigger_20_to_10_200bps.csv"
SLIPPAGE_BPS = 200.0
NAME = "dd_8pct_cut_20_to_10_recover_4pct_30_70"
EXPOSURE = 0.20
LOWER_EXPOSURE = 0.10
TRIGGER = 8.0
POLICIES = ((NAME, EXPOSURE, TRIGGER),)


def main() -> None:
    stateful.SLIPPAGE_BPS = SLIPPAGE_BPS
    stateful.POLICIES = POLICIES
    stateful.NIFTY_SLEEVE_WEIGHT_BY_POLICY = {NAME: 0.30}
    stateful.EXPOSURE_BANDS_BY_POLICY = {NAME: (EXPOSURE, LOWER_EXPOSURE)}
    source, dates, initial_prices = stateful.load_source()
    bootstrap.check_sampler()
    _, panels, _, _ = blend.make_portfolios()
    targets, events = benchmark._passive_targets(
        panels, {"NIFTYBEES": 0.30, "GOLDBEES": 0.70},
    )
    historical = np.arange(len(dates), dtype=np.int32)[None, :]
    replay = stateful.simulate(historical, source, initial_prices)
    _, _, canonical = control.simulate(
        panels, NAME, EXPOSURE, TRIGGER, SLIPPAGE_BPS,
        start=stateful.START, end=stateful.END,
        base_targets=targets, rebalance_events=events,
        lower_exposure=LOWER_EXPOSURE,
    )
    expected = pd.read_csv(STRESS).query("period == 'continuous_2015_2026'").iloc[0]
    assert abs(replay["ending_balance_inr"][0, 0] - canonical["ending_balance_inr"]) <= 0.03
    assert abs(replay["total_fees_inr"][0, 0] - canonical["total_fees_inr"]) <= 0.03
    assert abs(replay["total_slippage_inr"][0, 0] - canonical["total_slippage_inr"]) <= 0.03
    assert int(replay["order_count"][0, 0]) == canonical["order_count"]
    assert int(replay["trigger_count"][0, 0]) == canonical["trigger_count"]
    assert int(replay["recovery_count"][0, 0]) == canonical["recovery_count"]
    assert abs(replay["close_mdd_pct"][0, 0] - canonical["max_drawdown_pct"]) <= 1e-8
    assert abs(replay["ohlc_bound_pct"][0, 0] - expected["ohlc_drawdown_bound_pct"]) <= 0.01

    rows = []
    for block_number, mean_block in enumerate(stateful.BLOCK_LENGTHS):
        indices = bootstrap.stationary_indices(
            stateful.N_PATHS, stateful.HORIZON, len(dates), mean_block,
            stateful.SEED + 2_000_000 + block_number * 10_000,
        )
        result = stateful.simulate(indices, source, initial_prices)
        close_dd = result["close_mdd_pct"][:, 0]
        ohlc_dd = result["ohlc_bound_pct"][:, 0]
        terminal = result["ending_balance_inr"][:, 0]
        probability = float((ohlc_dd <= -20.0).mean())
        rows.append({
            "strategy": NAME,
            "initial_exposure_pct": EXPOSURE * 100,
            "reduced_exposure_pct": LOWER_EXPOSURE * 100,
            "drawdown_trigger_pct": TRIGGER,
            "recovery_pct": TRIGGER / 2,
            "nifty_sleeve_pct": 30.0,
            "gold_sleeve_pct": 70.0,
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
            "mean_triggers": float(result["trigger_count"][:, 0].mean()),
            "mean_recoveries": float(result["recovery_count"][:, 0].mean()),
            "mean_fees_inr": float(result["total_fees_inr"][:, 0].mean()),
            "mean_slippage_inr": float(result["total_slippage_inr"][:, 0].mean()),
        })
        print(f"finished 20%-to-10% stateful {mean_block}-session blocks", flush=True)

    table = pd.DataFrame(rows)
    assert len(table) == len(stateful.BLOCK_LENGTHS) == 3
    assert table["ohlc_bound_breach_probability_pct"].between(0, 100).all()
    table.to_csv(OUT, index=False)
    print(f"wrote {len(table)} 20%-to-10% drawdown-control summaries")


if __name__ == "__main__":
    main()
