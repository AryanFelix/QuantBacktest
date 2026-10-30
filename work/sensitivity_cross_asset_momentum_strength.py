"""Test strength-weighted sizing on the cross-asset monthly top-three momentum rule."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

import audit_cross_asset_momentum_ohlc as base
import upstox_quant as q


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs" / "cross_asset_momentum_strength_ohlc_frontier.csv"
SELECTION = ROOT / "outputs" / "cross_asset_momentum_strength_ohlc_selection.json"
RUNS = ROOT / "work" / "backtests" / "cross_asset_momentum_strength_weighted"
SLIPPAGE_BPS = 50
EXPOSURES = tuple(value / 100 for value in range(25, 100, 5))


def strength_weight_targets(
    panels: dict[str, pd.DataFrame], equal_targets: pd.DataFrame, rebalance: pd.Series,
) -> pd.DataFrame:
    close = panels["close"]
    scores = close.shift(21) / close.shift(252) - 1.0
    targets = equal_targets.copy()
    current = pd.Series(0.0, index=close.columns)
    for i, timestamp in enumerate(close.index):
        if rebalance.iloc[i]:
            selected = equal_targets.iloc[i]
            selected = selected[selected > 0].index
            current[:] = 0.0
            if len(selected):
                momentum = scores.loc[timestamp, selected]
                if not momentum.notna().all() or (momentum <= 0).any():
                    raise ValueError(f"Missing or non-positive selected momentum at {timestamp.date()}")
                current.loc[selected] = momentum / momentum.sum()
        targets.iloc[i] = current
    return targets


def main() -> None:
    q._self_check()
    specs = [f"{symbol}={base.DATA / filename}" for symbol, filename in base.ASSETS.items()]
    _, panels = q._read_prices(specs)
    equal_targets, events = q.make_targets(panels, "momentum12_1", top_n=3)
    targets = strength_weight_targets(panels, equal_targets, events)
    base.ohlc.BARS["JUNIORBEES"] = (
        "work/data/etf_daily/NSE_EQ_INF732E01045-days-1-2014-01-01-2026-10-23.csv"
    )
    assert targets.index.equals(equal_targets.index) and targets.columns.equals(equal_targets.columns)
    assert (targets >= 0).all().all()
    assert ((targets.sum(axis=1) - equal_targets.sum(axis=1)).abs() < 1e-12).all()

    rows = []
    for period, (start, end) in base.PERIODS.items():
        for exposure in EXPOSURES:
            run = RUNS / f"{period}__cap{int(exposure * 100):02d}"
            run.mkdir(parents=True, exist_ok=True)
            equity, orders, stats = q._simulate(
                panels, targets, events, base.CAPITAL, exposure, SLIPPAGE_BPS,
                "equity_delivery", start, end, 20,
                cash_distributions=base.KNOWN_NIFTYBEES_DISTRIBUTIONS,
            )
            equity.reset_index().rename(columns={"index": "time"}).to_csv(run / "equity.csv", index=False)
            orders.to_csv(run / "orders.csv", index=False)
            risk = base.ohlc.run_case(
                f"strength_weighted/{period}/cap{int(exposure * 100)}",
                run.relative_to(ROOT).as_posix(), slippage_bps=SLIPPAGE_BPS,
            )
            assert risk["max_close_replay_error_inr"] <= 0.03
            rows.append({
                "weighting": "12_1_momentum_strength_weighted",
                "slippage_bps_per_side": SLIPPAGE_BPS,
                "period": period,
                "period_start": start.isoformat(),
                "period_end": end.isoformat(),
                "gross_exposure_cap_pct": exposure * 100,
                "starting_balance_inr": stats["starting_balance_inr"],
                "ending_balance_inr": stats["ending_balance_inr"],
                "total_return_pct": stats["total_return_pct"],
                "cagr_pct": stats["cagr_pct"],
                "close_max_drawdown_pct": risk["close_max_drawdown_pct"],
                "ohlc_drawdown_bound_pct": risk["simultaneous_ohlc_drawdown_bound_pct"],
                "within_20pct_ohlc": risk["within_20pct_under_bound"],
                "total_fees_inr": stats["total_fees_inr"],
                "cash_distributions_inr": stats["cash_distributions_inr"],
                "order_count": stats["order_count"],
                "max_close_replay_error_inr": risk["max_close_replay_error_inr"],
                "run_artifact": run.relative_to(ROOT).as_posix(),
            })

    table = pd.DataFrame(rows)
    expected = len(base.PERIODS) * len(EXPOSURES)
    assert len(table) == expected and not table.duplicated(["period", "gross_exposure_cap_pct"]).any()
    table.to_csv(OUT, index=False)
    candidates = []
    for exposure in EXPOSURES:
        by_period = table[table["gross_exposure_cap_pct"] == exposure * 100].set_index("period")
        development = by_period.loc[[
            "train_2014_2019", "validation_2020_2022", "train_plus_validation_2014_2022",
        ]]
        if development["within_20pct_ohlc"].all():
            candidates.append({
                "exposure_pct": exposure * 100,
                "validation_cagr_pct": float(by_period.loc["validation_2020_2022", "cagr_pct"]),
                "worst_development_ohlc_pct": float(development["ohlc_drawdown_bound_pct"].min()),
            })
    chosen = max(candidates, key=lambda x: (
        x["validation_cagr_pct"], x["worst_development_ohlc_pct"], -x["exposure_pct"],
    )) if candidates else None
    holdout = None if chosen is None else table[
        (table["period"] == "pseudo_holdout_2023_plus")
        & (table["gross_exposure_cap_pct"] == chosen["exposure_pct"])
    ].iloc[0].to_dict()
    SELECTION.write_text(json.dumps({
        "strategy": "monthly top-three 12-1 momentum above 200-session SMA; selected weights proportional to positive 12-1 scores",
        "capital_inr": base.CAPITAL,
        "slippage_bps_per_side": SLIPPAGE_BPS,
        "exposure_grid_pct": [value * 100 for value in EXPOSURES],
        "selection_rule": "Highest validation CAGR among caps passing the 20% OHLC bound in training, validation, and continuous development; ties prefer more risk headroom then lower exposure.",
        "eligible_caps": candidates,
        "selected": chosen,
        "pseudo_holdout": holdout,
        "limits": [
            "All windows have been inspected; 2023+ is a retrospective pseudo-holdout.",
            "The price-signal ETF universe has unequal inception histories and no point-in-time constituent archive.",
            "Gold and sector ETF distributions are incomplete; only verified NIFTYBEES payouts are credited.",
            "OHLC envelope assumes same-day held-asset highs precede lows and is not a future loss limit.",
        ],
    }, indent=2), encoding="utf-8")
    if chosen:
        print(f"selected={chosen['exposure_pct']:.0f}% eligible={len(candidates)} holdout={holdout['total_return_pct']:.2f}% OHLC={holdout['ohlc_drawdown_bound_pct']:.2f}%")
    else:
        print("no exposure cap passed all development OHLC gates")
    print(f"scenarios={len(table)} output={OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
