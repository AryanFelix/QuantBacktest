"""Statefully bootstrap passive ETF exposures and controls at 200 bps."""

from pathlib import Path

import numpy as np
import pandas as pd

import bootstrap_etf_drawdown_risk as bootstrap
import bootstrap_stateful_drawdown_control as stateful


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs" / "stateful_drawdown_control_200bps_bootstrap.csv"
SLIPPAGE_BPS = 200.0
POLICIES = tuple(
    (f"fixed_{int(exposure * 100)}pct", exposure, None)
    for exposure in (0.20, 0.25, 0.30, 0.35, 0.40, 0.45)
) + stateful.POLICIES[2:4]


def main() -> None:
    stateful.SLIPPAGE_BPS = SLIPPAGE_BPS
    stateful.POLICIES = POLICIES
    source, dates, initial_prices = stateful.load_source()
    stateful.control._self_check()
    bootstrap.check_sampler()
    _, panels, _, _ = stateful.blend.make_portfolios()

    historical = np.arange(len(dates), dtype=np.int32)[None, :]
    replay = stateful.simulate(historical, source, initial_prices)
    stress = pd.read_csv(ROOT / "outputs" / "passive_drawdown_control_200bps_stress.csv")
    for column, (name, exposure, trigger) in enumerate(POLICIES):
        _, _, stats = stateful.control.simulate(
            panels, name, exposure, trigger, SLIPPAGE_BPS,
            start=stateful.START, end=stateful.END,
        )
        expected = stress.loc[
            (stress["strategy"] == name) & (stress["period"] == "continuous_2015_2026")
        ].iloc[0]
        assert abs(replay["ending_balance_inr"][0, column] - stats["ending_balance_inr"]) <= 0.03
        assert abs(replay["total_fees_inr"][0, column] - stats["total_fees_inr"]) <= 0.03
        assert abs(replay["total_slippage_inr"][0, column] - stats["total_slippage_inr"]) <= 0.03
        assert int(replay["order_count"][0, column]) == stats["order_count"]
        assert int(replay["trigger_count"][0, column]) == stats["trigger_count"]
        assert int(replay["recovery_count"][0, column]) == stats["recovery_count"]
        assert abs(replay["close_mdd_pct"][0, column] - stats["max_drawdown_pct"]) <= 1e-8
        assert abs(replay["ohlc_bound_pct"][0, column] - expected["ohlc_drawdown_bound_pct"]) <= 0.01

    rows = []
    for block_number, mean_block in enumerate(stateful.BLOCK_LENGTHS):
        indices = bootstrap.stationary_indices(
            stateful.N_PATHS, stateful.HORIZON, len(dates), mean_block,
            stateful.SEED + 1_000_000 + block_number * 10_000,
        )
        result = stateful.simulate(indices, source, initial_prices)
        for column, (name, exposure, trigger) in enumerate(POLICIES):
            close_dd = result["close_mdd_pct"][:, column]
            ohlc_dd = result["ohlc_bound_pct"][:, column]
            terminal = result["ending_balance_inr"][:, column]
            close_breach = close_dd <= -20.0
            ohlc_breach = ohlc_dd <= -20.0
            p_ohlc = float(ohlc_breach.mean())
            rows.append({
                "strategy": name,
                "initial_exposure_pct": exposure * 100,
                "drawdown_trigger_pct": trigger if trigger is not None else "",
                "recovery_pct": trigger / 2 if trigger is not None else "",
                "slippage_bps_per_side": SLIPPAGE_BPS,
                "source_start": dates[0].isoformat(),
                "source_end": dates[-1].isoformat(),
                "source_sessions": len(dates),
                "horizon_sessions": stateful.HORIZON,
                "mean_block_sessions": mean_block,
                "simulations": stateful.N_PATHS,
                "close_mdd_breach_probability_pct": 100 * close_breach.mean(),
                "ohlc_bound_breach_probability_pct": 100 * p_ohlc,
                "ohlc_breach_mcse_pp": 100 * np.sqrt(p_ohlc * (1 - p_ohlc) / stateful.N_PATHS),
                "median_close_mdd_pct": float(np.median(close_dd)),
                "p05_ohlc_bound_pct": float(np.quantile(ohlc_dd, 0.05)),
                "median_cagr_pct": 100 * ((float(np.median(terminal)) / stateful.CAPITAL) ** (252 / stateful.HORIZON) - 1),
                "p10_cagr_pct": 100 * ((float(np.quantile(terminal, 0.10)) / stateful.CAPITAL) ** (252 / stateful.HORIZON) - 1),
                "median_ending_balance_inr": float(np.median(terminal)),
                "p10_ending_balance_inr": float(np.quantile(terminal, 0.10)),
                "median_triggers": float(np.median(result["trigger_count"][:, column])),
                "median_recoveries": float(np.median(result["recovery_count"][:, column])),
                "mean_fees_inr": float(result["total_fees_inr"][:, column].mean()),
                "mean_slippage_inr": float(result["total_slippage_inr"][:, column].mean()),
            })
        print(f"finished 200-bps stateful {mean_block}-session blocks", flush=True)

    table = pd.DataFrame(rows)
    assert len(table) == len(POLICIES) * len(stateful.BLOCK_LENGTHS) == 24
    assert table["ohlc_bound_breach_probability_pct"].between(0, 100).all()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    table.to_csv(OUT, index=False)
    print(f"wrote {len(table)} bootstrap summaries to {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
