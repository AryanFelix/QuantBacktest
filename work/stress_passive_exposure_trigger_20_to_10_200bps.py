"""Replay a frozen 20%-to-10% passive drawdown throttle at 200 bps."""

from datetime import date
from pathlib import Path

import pandas as pd

import audit_etf_intraday_drawdown as audit
import backtest_passive_mix_drawdown_control as control
import benchmark_nifty_gold_2020 as benchmark
import replay_volatility_weighted_blend as blend
import select_passive_drawdown_control_walkforward as walkforward


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs" / "passive_exposure_trigger_20_to_10_200bps.csv"
RUNS = ROOT / "work" / "backtests" / "passive_exposure_trigger_20_to_10_200bps"
NAME = "dd_8pct_cut_20_to_10_recover_4pct_30_70"
EXPOSURE = 0.20
LOWER_EXPOSURE = 0.10
TRIGGER = 8.0
SLIPPAGE_BPS = 200.0
PERIODS = (
    ("continuous_2015_2026", date(2015, 1, 2), date(2026, 10, 23)),
    *walkforward.PERIODS,
)


def main() -> None:
    control._self_check()
    _, panels, _, _ = blend.make_portfolios()
    targets, events = benchmark._passive_targets(
        panels, {"NIFTYBEES": 0.30, "GOLDBEES": 0.70},
    )
    rows = []
    for period, start, end in PERIODS:
        equity, orders, stats = control.simulate(
            panels, NAME, EXPOSURE, TRIGGER, SLIPPAGE_BPS,
            start=start, end=end,
            base_targets=targets,
            rebalance_events=events,
            lower_exposure=LOWER_EXPOSURE,
        )
        run = RUNS / period
        run.mkdir(parents=True, exist_ok=True)
        equity.to_csv(run / "equity.csv", index_label="time")
        orders.to_csv(run / "orders.csv", index=False)
        audit.SLIPPAGE_BPS = SLIPPAGE_BPS
        risk = audit.run_case(
            f"{period}; {NAME}; {SLIPPAGE_BPS:g} bps/side",
            run.relative_to(ROOT).as_posix(),
            starting_balance=control.CAPITAL,
            slippage_bps=SLIPPAGE_BPS,
        )
        rows.append({
            **stats,
            "strategy": NAME,
            "period": period,
            "period_start": start.isoformat(),
            "period_end": end.isoformat(),
            "ohlc_drawdown_bound_pct": risk["simultaneous_ohlc_drawdown_bound_pct"],
            "within_20pct_ohlc": risk["within_20pct_under_bound"],
            "max_close_replay_error_inr": risk["max_close_replay_error_inr"],
            "max_gross_exposure_pct": 100 * equity["gross_exposure"].max(),
            "slippage_bps_per_side": SLIPPAGE_BPS,
        })

    table = pd.DataFrame(rows)
    assert len(table) == 4 and table["max_close_replay_error_inr"].max() <= 0.03
    assert table["slippage_bps_per_side"].eq(SLIPPAGE_BPS).all()
    table.to_csv(OUT, index=False)
    print(f"wrote {len(table)} 20%-to-10% drawdown-control replays")


if __name__ == "__main__":
    main()
