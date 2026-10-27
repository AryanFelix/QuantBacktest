"""Screen trailing-volatility throttles on the quarterly NIFTY/Gold blend."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pandas as pd

import replay_volatility_weighted_blend as blend
import upstox_quant as q


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "work" / "backtests" / "volatility_target_sensitivity"
CAPITAL = 1_000_000
VOL_TARGETS = (0.08, 0.10, 0.12, 0.14, 0.16)
SLIPPAGE = (10, 50)


def main() -> None:
    files, panels, portfolios, event_sets = blend.make_portfolios()
    base = blend.single_sleeve_weight_targets(portfolios["inverse_vol_63d_quarterly"], 0.65)
    events = event_sets["inverse_vol_63d_quarterly"]
    asset_returns = panels["close"].pct_change(fill_method=None).fillna(0.0)
    base_returns = (asset_returns * base.shift(1).fillna(0.0)).sum(axis=1)
    end = panels["close"].index[-1].date()
    periods = (
        ("train_2014_2019", date(2014, 1, 1), date(2019, 12, 31)),
        ("validation_2020_2022", date(2020, 1, 1), date(2022, 12, 31)),
        ("holdout_2023_plus", date(2023, 1, 1), end),
        ("full_2020_plus", date(2020, 1, 1), end),
        ("full_2014_plus", date(2014, 1, 1), end),
    )
    configurations = [("no_throttle", None)] + [(f"vol_{int(v * 100)}pct", v) for v in VOL_TARGETS]
    rows = []
    for name, target in configurations:
        targets = base if target is None else blend.trailing_volatility_throttle_targets(
            base, events, base_returns, target,
        )
        for period, start, finish in periods:
            for slip in SLIPPAGE:
                equity, orders, stats = q._simulate(
                    panels, targets, events, CAPITAL, 1.0, slip,
                    "equity_delivery", start, finish, 20,
                )
                row = {
                    "strategy": name,
                    "volatility_target_pct": "" if target is None else target * 100,
                    "period": period,
                    "period_start": start.isoformat(),
                    "period_end": finish.isoformat(),
                    "starting_balance_inr": CAPITAL,
                    "exposure_cap_pct": 100,
                    "slippage_bps_per_side": slip,
                    "total_slippage_inr": blend.modeled_slippage(orders, panels),
                    "selection_or_sizing": "Quarterly 63-session inverse-vol split when both trend sleeves are active; 65% gross when one is active; at rebalance events scale by min(1, target volatility / trailing 63-session realized portfolio volatility); no leverage.",
                    "first_bar": str(equity.index[0]),
                    "last_bar": str(equity.index[-1]),
                    **stats,
                }
                rows.append(row)
                key = f"{name}__{period}__{slip}bps"
                run = OUT / key
                run.mkdir(parents=True, exist_ok=True)
                equity.to_csv(run / "equity.csv", index_label="time")
                orders.to_csv(run / "orders.csv", index=False)
    assert len(rows) == len(configurations) * len(periods) * len(SLIPPAGE) == 60
    OUT.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(OUT / "summary.csv", index=False)
    pd.DataFrame(rows).to_csv(ROOT / "outputs" / "volatility_target_sensitivity.csv", index=False)
    (OUT / "strategy.json").write_text(json.dumps({
        "capital_inr": CAPITAL,
        "base_rule": "NIFTYBEES Donchian 55/20 and GOLDBEES 200-session SMA; 63-session inverse-vol weights when both sleeves are active, 65% gross when one is active.",
        "throttle": "At each existing signal-change or quarter-end rebalance, scale base weights by min(1, target annualized volatility / trailing 63-session realized volatility of lagged base portfolio returns); hold scale until the next rebalance.",
        "annualized_volatility_targets_pct": [v * 100 for v in VOL_TARGETS],
        "execution": "Signal and risk estimate use data through the rebalance close; trades fill at the next session open.",
        "slippage_bps_per_side": list(SLIPPAGE),
        "data_end": end.isoformat(),
        "source_data": {name: f"{frame.index[0].date()} to {frame.index[-1].date()}" for name, frame in files.items()},
        "limits": ["All time slices were inspected during prior research; this is retrospective sensitivity, not independent validation.", "The target is an exposure throttle, not a guaranteed volatility or drawdown bound.", "Cash yield is zero; current delivery charges are applied uniformly; slippage is modeled."],
    }, indent=2), encoding="utf-8")

    baseline = next(r for r in rows if r["strategy"] == "no_throttle" and r["period"] == "full_2014_plus" and r["slippage_bps_per_side"] == 50)
    established = next(r for r in csv_rows(ROOT / "outputs" / "single_sleeve_deployment_sensitivity.csv") if r["portfolio"] == "inverse_vol_quarterly_single_65" and r["period"] == "full_2014_plus" and int(r["slippage_bps_per_side"]) == 50)
    for field in ("ending_balance_inr", "total_return_pct", "cagr_pct", "max_drawdown_pct", "total_fees_inr", "total_slippage_inr", "order_count"):
        assert abs(float(baseline[field]) - float(established[field])) < 1e-8, f"Baseline mismatch for {field}"
    print(f"scenarios={len(rows)} baseline_checks=7 output=outputs/volatility_target_sensitivity.csv")


def csv_rows(path: Path) -> list[dict[str, str]]:
    import csv
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


if __name__ == "__main__":
    main()
