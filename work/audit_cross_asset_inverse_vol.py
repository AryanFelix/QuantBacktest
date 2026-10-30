"""Compare monthly inverse-volatility sizing on the cross-asset ETF momentum ranks."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

import audit_cross_asset_momentum_ohlc as base
import upstox_quant as q


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs" / "cross_asset_inverse_vol_ohlc_frontier.csv"
SELECTION = ROOT / "outputs" / "cross_asset_inverse_vol_ohlc_selection.json"
RUNS = ROOT / "work" / "backtests" / "cross_asset_inverse_vol"
VOL_LOOKBACK = 63
SLIPPAGE_BPS = 50


def inverse_vol_targets(
    panels: dict[str, pd.DataFrame], equal_targets: pd.DataFrame, rebalance: pd.Series,
) -> pd.DataFrame:
    close = panels["close"]
    returns = close.pct_change(fill_method=None)
    volatility = returns.rolling(VOL_LOOKBACK, min_periods=VOL_LOOKBACK).std()
    targets = equal_targets.copy()
    current = pd.Series(0.0, index=close.columns)
    for i, timestamp in enumerate(close.index):
        if rebalance.iloc[i]:
            selected = equal_targets.iloc[i]
            selected = selected[selected > 0].index
            current[:] = 0.0
            if len(selected):
                sigma = volatility.loc[timestamp, selected]
                if not sigma.notna().all() or (sigma <= 0).any():
                    raise ValueError(f"Missing or invalid 63-session volatility at {timestamp.date()}")
                inverse = 1.0 / sigma
                current.loc[selected] = inverse / inverse.sum()
        targets.iloc[i] = current
    return targets


def main() -> None:
    q._self_check()
    specs = [f"{symbol}={base.DATA / filename}" for symbol, filename in base.ASSETS.items()]
    files, panels = q._read_prices(specs)
    equal_targets, events = q.make_targets(panels, "momentum12_1", top_n=3)
    targets = inverse_vol_targets(panels, equal_targets, events)
    base.ohlc.BARS["JUNIORBEES"] = (
        "work/data/etf_daily/NSE_EQ_INF732E01045-days-1-2014-01-01-2026-10-23.csv"
    )
    assert targets.index.equals(equal_targets.index) and targets.columns.equals(equal_targets.columns)
    assert (targets >= 0).all().all()
    assert ((targets.sum(axis=1) - equal_targets.sum(axis=1)).abs() < 1e-12).all()

    rows = []
    for period, (start, end) in base.PERIODS.items():
        run = RUNS / f"{period}__cap45"
        run.mkdir(parents=True, exist_ok=True)
        equity, orders, stats = q._simulate(
            panels, targets, events, base.CAPITAL, 0.45, SLIPPAGE_BPS,
            "equity_delivery", start, end, 20,
            cash_distributions=base.KNOWN_NIFTYBEES_DISTRIBUTIONS,
        )
        equity.reset_index().rename(columns={"index": "time"}).to_csv(run / "equity.csv", index=False)
        orders.to_csv(run / "orders.csv", index=False)
        risk = base.ohlc.run_case(
            f"inverse_vol_63d/{period}/cap45", run.relative_to(ROOT).as_posix(),
            slippage_bps=SLIPPAGE_BPS,
        )
        assert risk["max_close_replay_error_inr"] <= 0.03
        rows.append({
            "weighting": "inverse_volatility_63_sessions",
            "volatility_lookback_sessions": VOL_LOOKBACK,
            "slippage_bps_per_side": SLIPPAGE_BPS,
            "period": period,
            "period_start": start.isoformat(),
            "period_end": end.isoformat(),
            "gross_exposure_cap_pct": 45,
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
    assert len(table) == len(base.PERIODS) and not table["period"].duplicated().any()
    table.to_csv(OUT, index=False)
    development = table[table["period"].isin((
        "train_2014_2019", "validation_2020_2022", "train_plus_validation_2014_2022",
    ))]
    eligible = bool(development["within_20pct_ohlc"].all())
    holdout = table.loc[table["period"] == "pseudo_holdout_2023_plus"].iloc[0].to_dict()
    SELECTION.write_text(json.dumps({
        "strategy": "monthly top-three 12-1 momentum above 200-session SMA; inverse 63-session volatility weights",
        "capital_inr": base.CAPITAL,
        "gross_exposure_cap_pct": 45,
        "slippage_bps_per_side": SLIPPAGE_BPS,
        "development_ohlc_eligible": eligible,
        "development_windows": development[["period", "ohlc_drawdown_bound_pct", "within_20pct_ohlc"]].to_dict("records"),
        "pseudo_holdout": holdout,
        "limit": "The 45% cap was frozen from the equal-weight audit; this is a fixed-cap weighting comparison, not a reselected inverse-volatility frontier.",
    }, indent=2), encoding="utf-8")
    print(f"scenarios={len(table)} eligible={eligible} holdout_return={holdout['total_return_pct']:.2f}% OHLC={holdout['ohlc_drawdown_bound_pct']:.2f}%")


if __name__ == "__main__":
    main()
