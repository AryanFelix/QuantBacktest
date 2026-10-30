"""Re-run the cross-asset ETF momentum cap grid with corrected fees and OHLC risk."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pandas as pd

import audit_etf_intraday_drawdown as ohlc
import upstox_quant as q


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "work" / "data" / "etf_daily"
ASSETS = {
    "NIFTYBEES": "NSE_EQ_INF204KB14I2-days-1-2014-01-01-2026-10-23.csv",
    "BANKBEES": "NSE_EQ_INF204KB15I9-days-1-2014-01-01-2026-10-23.csv",
    "ITBEES": "NSE_EQ_INF204KB15V2-days-1-2014-01-01-2026-10-23.csv",
    "AUTOBEES": "NSE_EQ_INF204KC1337-days-1-2014-01-01-2026-10-23.csv",
    "PHARMABEES": "NSE_EQ_INF204KC1089-days-1-2014-01-01-2026-10-23.csv",
    "PSUBNKBEES": "NSE_EQ_INF204KB16I7-days-1-2014-01-01-2026-10-23.csv",
    "JUNIORBEES": "NSE_EQ_INF732E01045-days-1-2014-01-01-2026-10-23.csv",
    "GOLDBEES": "GOLDBEES-days-1-2014-01-01-2026-10-23.csv",
}
PERIODS = {
    "train_2014_2019": (date(2014, 1, 1), date(2019, 12, 31)),
    "validation_2020_2022": (date(2020, 1, 1), date(2022, 12, 31)),
    "train_plus_validation_2014_2022": (date(2014, 1, 1), date(2022, 12, 31)),
    "pseudo_holdout_2023_plus": (date(2023, 1, 1), date(2026, 10, 23)),
    "full_2014_2026": (date(2014, 1, 1), date(2026, 10, 23)),
}
CAPITAL = 1_000_000
EXPOSURES = tuple(value / 100 for value in range(25, 100, 5))
SLIPPAGE_BPS = (10, 50)
KNOWN_NIFTYBEES_DISTRIBUTIONS = [
    ("NIFTYBEES", date(2014, 3, 11), 0.70),
    ("NIFTYBEES", date(2015, 2, 20), 0.80),
]
OUT = ROOT / "outputs" / "cross_asset_momentum_ohlc_risk_frontier.csv"
SELECTION = ROOT / "outputs" / "cross_asset_momentum_ohlc_selection.json"
RUNS = ROOT / "work" / "backtests" / "cross_asset_momentum_risk_frontier"


def main() -> None:
    q._self_check()
    specifications = [f"{symbol}={DATA / filename}" for symbol, filename in ASSETS.items()]
    files, panels = q._read_prices(specifications)
    targets, events = q.make_targets(panels, "momentum12_1", top_n=3)
    ohlc.BARS["JUNIORBEES"] = "work/data/etf_daily/NSE_EQ_INF732E01045-days-1-2014-01-01-2026-10-23.csv"
    assert set(ASSETS) == set(targets.columns)
    assert all(frame.index.is_unique and frame.index.is_monotonic_increasing for frame in panels.values())

    rows = []
    for slippage in SLIPPAGE_BPS:
        for period, (start, end) in PERIODS.items():
            for exposure in EXPOSURES:
                label = f"{slippage}bps/{period}/cap{int(exposure * 100)}"
                run = RUNS / f"{slippage}bps" / f"{period}__cap{int(exposure * 100):02d}"
                run.mkdir(parents=True, exist_ok=True)
                equity, orders, stats = q._simulate(
                    panels, targets, events, CAPITAL, exposure, slippage,
                    "equity_delivery", start, end, 20,
                    cash_distributions=KNOWN_NIFTYBEES_DISTRIBUTIONS,
                )
                equity.reset_index().rename(columns={"index": "time"}).to_csv(run / "equity.csv", index=False)
                orders.to_csv(run / "orders.csv", index=False)
                risk = ohlc.run_case(label, run.relative_to(ROOT).as_posix(), slippage_bps=slippage)
                assert risk["max_close_replay_error_inr"] <= 0.03
                rows.append({
                    "slippage_bps_per_side": slippage,
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
                    "ohlc_headroom_to_20pct_pp": risk["headroom_to_20pct_bound_pp"],
                    "within_20pct_ohlc": risk["within_20pct_under_bound"],
                    "total_fees_inr": stats["total_fees_inr"],
                    "cash_distributions_inr": stats["cash_distributions_inr"],
                    "order_count": stats["order_count"],
                    "turnover_inr": stats["turnover_inr"],
                    "max_close_replay_error_inr": risk["max_close_replay_error_inr"],
                    "ohlc_peak_date": risk["bound_peak_date"],
                    "ohlc_trough_date": risk["bound_trough_date"],
                    "run_artifact": run.relative_to(ROOT).as_posix(),
                })

    table = pd.DataFrame(rows)
    expected = len(SLIPPAGE_BPS) * len(PERIODS) * len(EXPOSURES)
    assert len(table) == expected and not table.duplicated(["slippage_bps_per_side", "period", "gross_exposure_cap_pct"]).any()
    table.to_csv(OUT, index=False)

    selection = {}
    for slippage in SLIPPAGE_BPS:
        cost_rows = table[table["slippage_bps_per_side"] == slippage]
        candidates = []
        for exposure in EXPOSURES:
            by_period = cost_rows[cost_rows["gross_exposure_cap_pct"] == exposure * 100].set_index("period")
            required = by_period.loc[["train_2014_2019", "validation_2020_2022", "train_plus_validation_2014_2022"]]
            if required["within_20pct_ohlc"].all():
                candidates.append({
                    "exposure_pct": exposure * 100,
                    "validation_cagr_pct": float(by_period.loc["validation_2020_2022", "cagr_pct"]),
                    "worst_development_ohlc_pct": float(required["ohlc_drawdown_bound_pct"].min()),
                })
        chosen = max(candidates, key=lambda x: (x["validation_cagr_pct"], x["worst_development_ohlc_pct"], -x["exposure_pct"])) if candidates else None
        selection[str(slippage)] = {
            "selection_rule": "highest validation CAGR among caps passing 20% OHLC in training, validation, and continuous train-plus-validation; ties prefer more OHLC headroom then lower exposure",
            "eligible_caps": candidates,
            "selected": chosen,
            "pseudo_holdout": None if chosen is None else json.loads(cost_rows[
                (cost_rows["period"] == "pseudo_holdout_2023_plus")
                & (cost_rows["gross_exposure_cap_pct"] == chosen["exposure_pct"])
            ].iloc[0].to_json()),
        }
    SELECTION.write_text(json.dumps({
        "strategy": "monthly top-three 12-1 momentum among eight ETFs above their 200-session SMA",
        "capital_inr": CAPITAL,
        "data_end": str(max(frame.index[-1].date() for frame in files.values())),
        "exposure_grid_pct": [value * 100 for value in EXPOSURES],
        "slippage_bps_per_side": list(SLIPPAGE_BPS),
        "selection_by_cost": selection,
        "limits": [
            "All historical windows have been inspected; the 2023+ segment is a retrospective pseudo-holdout.",
            "GoldBeES and sector ETF cash distributions are not completely reconciled; only verified NIFTYBEES payouts are credited.",
            "OHLC bounds assume same-day held-asset highs precede lows; fees are current modeled charges and slippage is assumed, not observed.",
            "The historical screen is not a future loss limit or an executable stop guarantee.",
        ],
    }, indent=2), encoding="utf-8")

    for slippage in SLIPPAGE_BPS:
        chosen = selection[str(slippage)]["selected"]
        if chosen:
            result = selection[str(slippage)]["pseudo_holdout"]
            print(f"{slippage}bps selected={chosen['exposure_pct']:.0f}% holdout_return={result['total_return_pct']:.2f}% close_dd={result['close_max_drawdown_pct']:.2f}% OHLC={result['ohlc_drawdown_bound_pct']:.2f}%")
        else:
            print(f"{slippage}bps no cap passed the training/validation OHLC selection gates")
    print(f"scenarios={len(table)} output={OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
