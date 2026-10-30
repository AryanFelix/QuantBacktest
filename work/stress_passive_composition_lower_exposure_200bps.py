"""Compare low initial NIFTY/Gold mix exposures under 200-bps friction."""

from datetime import date
from pathlib import Path

import pandas as pd

import benchmark_nifty_gold_2020 as benchmark
import replay_volatility_weighted_blend as blend
import select_passive_drawdown_control_walkforward as walkforward


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs" / "passive_mix_composition_lower_exposure_200bps.csv"
RUNS = ROOT / "work" / "backtests" / "passive_mix_composition_lower_exposure_200bps"
EXPOSURES = (0.25, 0.30)
NIFTY_SHARES = (30, 50, 70)
SLIPPAGE_BPS = 200.0


def main() -> None:
    _, panels, _, _ = blend.make_portfolios()
    data_end = panels["close"].dropna(subset=["NIFTYBEES", "GOLDBEES"]).index[-1].date()
    periods = (
        ("continuous_2015_2026", date(2015, 1, 2), data_end),
        *walkforward.PERIODS,
    )
    rows = []
    for exposure in EXPOSURES:
        for nifty_pct in NIFTY_SHARES:
            gold_pct = 100 - nifty_pct
            targets, events = benchmark._passive_targets(panels, {
                "NIFTYBEES": nifty_pct / 100,
                "GOLDBEES": gold_pct / 100,
            })
            name = f"initial_{int(exposure * 100)}pct_nifty_{nifty_pct:02d}_gold_{gold_pct:02d}"
            for period, start, end in periods:
                result = benchmark._run(
                    f"{name}_{period}_{int(SLIPPAGE_BPS)}bps", targets, events,
                    panels, end, start=start,
                    run_dir=RUNS / period,
                    cash_distributions=benchmark.NIFTYBEES_DISTRIBUTIONS,
                    exposure_cap=exposure, slippage_bps=SLIPPAGE_BPS,
                )
                rows.append({
                    **result,
                    "period": period,
                    "initial_exposure_pct": exposure * 100,
                    "nifty_share_of_risky_sleeve_pct": nifty_pct,
                    "gold_share_of_risky_sleeve_pct": gold_pct,
                })
    table = pd.DataFrame(rows)
    assert len(table) == len(EXPOSURES) * len(NIFTY_SHARES) * len(periods) == 24
    assert not table.duplicated(["initial_exposure_pct", "nifty_share_of_risky_sleeve_pct", "period"]).any()
    assert table["slippage_bps_per_side"].eq(SLIPPAGE_BPS).all()
    assert table["max_close_replay_error_inr"].max() <= 0.03
    table.to_csv(OUT, index=False)
    print(f"wrote {len(table)} lower-exposure composition rows through {data_end}")


if __name__ == "__main__":
    main()
