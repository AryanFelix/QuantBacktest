"""Stress the passive 45% reference and 8%/10% NIFTY/Gold controls at 200 bps."""

from datetime import date
from pathlib import Path

import pandas as pd

import select_passive_drawdown_control_walkforward as walkforward


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs" / "passive_drawdown_control_200bps_stress.csv"
POLICIES = (
    ("fixed_45pct", 0.45, None, "passive_reference"),
    ("dd_8pct_cut_60_to_30_recover_4pct", 0.60, 8.0, "selected_rule_cost_stress"),
    ("dd_10pct_cut_60_to_30_recover_5pct", 0.60, 10.0, "training_tie_sensitivity"),
)


def main() -> None:
    walkforward.control._self_check()
    _, panels, _, _ = walkforward.blend.make_portfolios()
    periods = (("continuous_2015_2026", date(2015, 1, 2), date(2026, 10, 23)), *walkforward.PERIODS[1:])
    rows = [walkforward.run_case(
        panels, period, start, end, name, exposure, trigger, 200.0, role,
    ) for name, exposure, trigger, role in POLICIES for period, start, end in periods]
    table = pd.DataFrame(rows)
    assert len(table) == 9 and table["max_close_replay_error_inr"].max() <= 0.03
    assert table["slippage_bps_per_side"].eq(200).all()
    table.to_csv(OUT, index=False)
    print(f"wrote {len(table)} 200-bps stress rows to {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
