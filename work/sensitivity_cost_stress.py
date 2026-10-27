"""Stress candidate NIFTY/Gold rules at slippage above the base 50 bps case."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pandas as pd

import replay_volatility_weighted_blend as blend
import upstox_quant as q


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "work" / "backtests" / "cost_stress_sensitivity"
CAPITAL = 1_000_000
SLIPPAGE = (10, 50, 100, 150, 200)
CONFIGURATIONS = (
    ("solo65_no_throttle", 0.65, None),
    ("solo65_vol16", 0.65, 0.16),
    ("solo80_vol14", 0.80, 0.14),
    ("solo80_vol16", 0.80, 0.16),
    ("solo80_vol18", 0.80, 0.18),
)
PERIODS = (
    ("train_2014_2019", date(2014, 1, 1), date(2019, 12, 31)),
    ("validation_2020_2022", date(2020, 1, 1), date(2022, 12, 31)),
    ("holdout_2023_plus", date(2023, 1, 1), None),
    ("full_2020_plus", date(2020, 1, 1), None),
    ("full_2014_plus", date(2014, 1, 1), None),
)
METRICS = (
    "ending_balance_inr", "total_return_pct", "cagr_pct", "max_drawdown_pct",
    "total_fees_inr", "total_slippage_inr", "order_count",
)


def main() -> None:
    files, panels, portfolios, event_sets = blend.make_portfolios()
    events = event_sets["inverse_vol_63d_quarterly"]
    asset_returns = panels["close"].pct_change(fill_method=None).fillna(0.0)
    end = panels["close"].index[-1].date()
    rows = []
    for name, exposure, target in CONFIGURATIONS:
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
            finish = finish or end
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
                           f" scale at rebalance by min(1, {target:.0%} / trailing 63-session annualized "
                           "volatility of this unthrottled portfolio's lagged daily returns).")
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

    assert len(rows) == len(CONFIGURATIONS) * len(PERIODS) * len(SLIPPAGE) == 125
    OUT.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(OUT / "summary.csv", index=False)
    pd.DataFrame(rows).to_csv(ROOT / "outputs" / "cost_stress_sensitivity.csv", index=False)
    (OUT / "strategy.json").write_text(json.dumps({
        "capital_inr": CAPITAL,
        "rules": [
            {"name": name, "solo_sleeve_exposure_pct": exposure * 100,
             "volatility_target_pct": "" if target is None else target * 100}
            for name, exposure, target in CONFIGURATIONS
        ],
        "slippage_bps_per_side": list(SLIPPAGE),
        "execution": "signal and risk estimate use data through close; next-session-open fills",
        "fees": "current Upstox/NSE delivery schedule applied uniformly; cash yield and investor tax are zero/unmodeled",
        "data_end": end.isoformat(),
        "source_data": {name: f"{frame.index[0].date()} to {frame.index[-1].date()}" for name, frame in files.items()},
        "limits": ["This is a cost stress, not a spread forecast.", "All historical windows were previously inspected.", "Slippage above 50 bps is a stress case, not an estimate of expected ETF execution."],
    }, indent=2), encoding="utf-8")

    reference = pd.read_csv(ROOT / "outputs" / "joint_exposure_volatility_sensitivity.csv")
    reference_checks = 0
    for name, _, _ in CONFIGURATIONS:
        for period, _, _ in PERIODS:
            current = next(row for row in rows if row["strategy"] == name and row["period"] == period and row["slippage_bps_per_side"] == 50)
            previous = reference.loc[
                (reference["strategy"] == name)
                & (reference["period"] == period)
                & (reference["slippage_bps_per_side"] == 50)
            ]
            assert len(previous) == 1, (name, period)
            for metric in METRICS:
                assert abs(float(current[metric]) - float(previous.iloc[0][metric])) < 1e-7, (name, period, metric)
                reference_checks += 1
    assert reference_checks == len(CONFIGURATIONS) * len(PERIODS) * len(METRICS) == 175
    print(f"scenarios={len(rows)} reference_checks={reference_checks} output=outputs/cost_stress_sensitivity.csv")


if __name__ == "__main__":
    main()
