"""Screen higher capital deployment when one NIFTY/Gold trend sleeve is active."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pandas as pd

import upstox_quant as q
import replay_volatility_weighted_blend as blend


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "work" / "backtests" / "single_sleeve_deployment"
CAPITAL = 1_000_000
SLIPPAGE = (10, 50)
SINGLE_EXPOSURES = (0.50, 0.55, 0.60, 0.65, 0.70, 0.75, 1.00)
PERIODS = [
    ("train_2014_2019", date(2014, 1, 1), date(2019, 12, 31)),
    ("validation_2020_2022", date(2020, 1, 1), date(2022, 12, 31)),
    ("holdout_2023_plus", date(2023, 1, 1), date(2026, 10, 23)),
    ("full_2020_plus", date(2020, 1, 1), date(2026, 10, 23)),
    ("full_2014_plus", date(2014, 1, 1), date(2026, 10, 23)),
]
BASELINES = {
    "inverse_vol_63d": "monthly",
    "inverse_vol_63d_quarterly": "quarterly",
}
METRICS = (
    "ending_balance_inr", "total_return_pct", "cagr_pct", "max_drawdown_pct",
    "total_fees_inr", "order_count", "total_slippage_inr",
)


def main() -> None:
    files, panels, portfolios, portfolio_events = blend.make_portfolios()
    reference = pd.read_csv(ROOT / "outputs" / "volatility_weighted_blend_screen.csv")
    OUT.mkdir(parents=True, exist_ok=True)
    rows = []
    baseline_checks = 0
    for base_name, frequency in BASELINES.items():
        base_targets = portfolios[base_name]
        events = portfolio_events[base_name]
        one_active = base_targets.sum(axis=1).between(0.5 - 1e-12, 0.5 + 1e-12)
        two_active = base_targets.sum(axis=1) > 0.99
        for single_exposure in SINGLE_EXPOSURES:
            targets = blend.single_sleeve_weight_targets(base_targets, single_exposure)
            assert (targets.loc[one_active].sum(axis=1) - single_exposure).abs().lt(1e-12).all()
            assert (targets.sum(axis=1) <= 1.0 + 1e-12).all()
            assert (targets.loc[two_active].sub(base_targets.loc[two_active]).abs().to_numpy() < 1e-12).all()
            portfolio = f"inverse_vol_{frequency}_single_{int(single_exposure * 100)}"

            for period, start, finish in PERIODS:
                for slip in SLIPPAGE:
                    equity, orders, stats = q._simulate(
                        panels, targets, events, CAPITAL, 1.0, slip,
                        "equity_delivery", start, finish, 20,
                    )
                    stats["total_slippage_inr"] = blend.modeled_slippage(orders, panels)
                    if single_exposure == 0.50:
                        baseline = reference.loc[
                            (reference["portfolio"] == base_name)
                            & (reference["period"] == period)
                            & (reference["slippage_bps_per_side"] == slip)
                        ]
                        assert len(baseline) == 1, (base_name, period, slip)
                        for metric in METRICS:
                            assert abs(float(stats[metric]) - float(baseline.iloc[0][metric])) < 1e-7, (base_name, period, slip, metric)
                        baseline_checks += 1

                    key = f"{portfolio}__{period}__{slip}bps"
                    run = OUT / key
                    run.mkdir(exist_ok=True)
                    equity.to_csv(run / "equity.csv", index_label="time")
                    orders.to_csv(run / "orders.csv", index=False)
                    rows.append({
                        "portfolio": portfolio,
                        "schedule": frequency,
                        "single_sleeve_exposure_pct": single_exposure * 100,
                        "period": period,
                        "period_start": start.isoformat(),
                        "period_end": finish.isoformat(),
                        "slippage_bps_per_side": slip,
                        "exposure_cap_pct": 100,
                        **stats,
                    })

    assert len(rows) == 140, len(rows)
    assert baseline_checks == 20, baseline_checks
    result = pd.DataFrame(rows)
    result.to_csv(OUT / "summary.csv", index=False)
    result.to_csv(ROOT / "outputs" / "single_sleeve_deployment_sensitivity.csv", index=False)
    (OUT / "strategy.json").write_text(json.dumps({
        "capital_inr": CAPITAL,
        "base_rule": "63-session inverse-volatility allocation when both Donchian 55/20 NIFTYBEES and 200DMA GOLDBEES sleeves are active",
        "screen": "when exactly one trend sleeve is active, set gross exposure to 50%, 75%, or 100%; when neither is active, hold cash",
        "rebalances": "same immediate signal changes and monthly or quarterly calendar schedule as the reference strategy; signal-close weights execute next session open",
        "slippage_bps_per_side": list(SLIPPAGE),
        "current_fee_schedule_applied_uniformly": True,
        "cash_return_pct": 0,
        "data_end": "2026-10-23",
        "source_data": {name: f"{frame.index[0].date()} to {frame.index[-1].date()}" for name, frame in files.items()},
        "reference_reproduction_checks": baseline_checks,
        "scenario_count": len(rows),
    }, indent=2), encoding="utf-8")
    print(json.dumps({"output": str(OUT), "scenarios": len(rows), "baseline_checks": baseline_checks}, indent=2))


if __name__ == "__main__":
    main()
