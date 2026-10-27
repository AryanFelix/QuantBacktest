"""Screen solo-sleeve exposure together with the quarterly volatility throttle."""

from __future__ import annotations

import csv
import json
from datetime import date
from pathlib import Path

import pandas as pd

import replay_volatility_weighted_blend as blend
import upstox_quant as q


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "work" / "backtests" / "joint_exposure_volatility_sensitivity"
CAPITAL = 1_000_000
SOLO_EXPOSURES = (0.65, 0.70, 0.75, 0.80)
VOL_TARGETS = (0.14, 0.16, 0.18)
SLIPPAGE = (10, 50)
PERIODS = (
    ("train_2014_2019", date(2014, 1, 1), date(2019, 12, 31)),
    ("validation_2020_2022", date(2020, 1, 1), date(2022, 12, 31)),
    ("holdout_2023_plus", date(2023, 1, 1), date(2026, 10, 23)),
    ("full_2020_plus", date(2020, 1, 1), date(2026, 10, 23)),
    ("full_2014_plus", date(2014, 1, 1), date(2026, 10, 23)),
)
METRICS = (
    "ending_balance_inr", "total_return_pct", "cagr_pct", "max_drawdown_pct",
    "total_fees_inr", "total_slippage_inr", "order_count",
)


def main() -> None:
    files, panels, portfolios, event_sets = blend.make_portfolios()
    events = event_sets["inverse_vol_63d_quarterly"]
    asset_returns = panels["close"].pct_change(fill_method=None).fillna(0.0)
    configurations = [("solo65_no_throttle", 0.65, None)]
    configurations += [
        (f"solo{int(exposure * 100)}_vol{int(target * 100)}", exposure, target)
        for exposure in SOLO_EXPOSURES for target in VOL_TARGETS
    ]
    rows = []
    for name, exposure, target in configurations:
        base = blend.single_sleeve_weight_targets(
            portfolios["inverse_vol_63d_quarterly"], exposure,
        )
        if target is None:
            targets = base
        else:
            base_returns = (asset_returns * base.shift(1).fillna(0.0)).sum(axis=1)
            targets = blend.trailing_volatility_throttle_targets(
                base, events, base_returns, target,
            )
            assert (targets.sum(axis=1) <= base.sum(axis=1) + 1e-12).all()
        for period, start, finish in PERIODS:
            for slip in SLIPPAGE:
                equity, orders, stats = q._simulate(
                    panels, targets, events, CAPITAL, 1.0, slip,
                    "equity_delivery", start, finish, 20,
                )
                stats["total_slippage_inr"] = blend.modeled_slippage(orders, panels)
                row = {
                    "strategy": name,
                    "solo_sleeve_exposure_pct": exposure * 100,
                    "volatility_target_pct": "" if target is None else target * 100,
                    "period": period,
                    "period_start": start.isoformat(),
                    "period_end": finish.isoformat(),
                    "starting_balance_inr": CAPITAL,
                    "exposure_cap_pct": 100,
                    "slippage_bps_per_side": slip,
                    "total_slippage_inr": stats["total_slippage_inr"],
                    "selection_or_sizing": (
                        f"Quarterly 63-session inverse-vol split when both sleeves are active; "
                        f"{exposure:.0%} gross when one is active; "
                        + ("no volatility throttle." if target is None else
                           f" at each rebalance scale by min(1, {target:.0%} / trailing 63-session annualized volatility "
                           "of this unthrottled portfolio's lagged daily returns).")
                    ),
                    "first_bar": str(equity.index[0]),
                    "last_bar": str(equity.index[-1]),
                    **stats,
                }
                rows.append(row)
                run = OUT / f"{name}__{period}__{slip}bps"
                run.mkdir(parents=True, exist_ok=True)
                equity.to_csv(run / "equity.csv", index_label="time")
                orders.to_csv(run / "orders.csv", index=False)

    assert len(rows) == len(configurations) * len(PERIODS) * len(SLIPPAGE) == 130
    OUT.mkdir(parents=True, exist_ok=True)
    result = pd.DataFrame(rows)
    result.to_csv(OUT / "summary.csv", index=False)
    result.to_csv(ROOT / "outputs" / "joint_exposure_volatility_sensitivity.csv", index=False)
    (OUT / "strategy.json").write_text(json.dumps({
        "capital_inr": CAPITAL,
        "base_rule": "NIFTYBEES Donchian 55/20 and GOLDBEES 200-session SMA; quarterly 63-session inverse-vol split when both active.",
        "screen": "65%, 70%, 75%, or 80% gross when one sleeve is active; at rebalance events optionally scale by min(1, target volatility / trailing 63-session realized volatility of that unthrottled exposure rule).",
        "targets_pct": [target * 100 for target in VOL_TARGETS],
        "execution": "signal and risk estimate use data through close; orders fill at next session open",
        "slippage_bps_per_side": list(SLIPPAGE),
        "current_fee_schedule_applied_uniformly": True,
        "cash_return_pct": 0,
        "data_end": panels["close"].index[-1].date().isoformat(),
        "source_data": {name: f"{frame.index[0].date()} to {frame.index[-1].date()}" for name, frame in files.items()},
        "limits": ["All windows were inspected in prior research; later slices are not independent holdouts.", "Volatility scaling is not a future drawdown guarantee.", "Cash earns zero; investor tax and live spreads are not modeled."],
    }, indent=2), encoding="utf-8")

    baseline = next(row for row in rows if row["strategy"] == "solo65_no_throttle" and row["period"] == "full_2014_plus" and row["slippage_bps_per_side"] == 50)
    with (ROOT / "outputs" / "single_sleeve_deployment_sensitivity.csv").open(encoding="utf-8-sig", newline="") as handle:
        established = next(row for row in csv.DictReader(handle) if row["portfolio"] == "inverse_vol_quarterly_single_65" and row["period"] == "full_2014_plus" and int(row["slippage_bps_per_side"]) == 50)
    for field in METRICS:
        assert abs(float(baseline[field]) - float(established[field])) < 1e-8, f"Baseline mismatch for {field}"
    print(f"scenarios={len(rows)} baseline_checks={len(METRICS)} output=outputs/joint_exposure_volatility_sensitivity.csv")


if __name__ == "__main__":
    main()
