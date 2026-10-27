"""Test sector rotation signals from official TRI while filling ETF market prices."""

from __future__ import annotations

import csv
import json
import sys
from datetime import date, datetime
from pathlib import Path

import pandas as pd

import audit_etf_intraday_drawdown as ohlc_audit
import replay_volatility_weighted_blend as blend
import sensitivity_sector_rotation as base
import upstox_quant as q


ROOT = Path(__file__).resolve().parents[1]
TRI_RAW = ROOT / "work" / "data" / "index_daily" / "sector_tri_raw_2014_2026.json"
OUT = ROOT / "work" / "backtests" / "sector_tri_signal_momentum"
SUMMARY = ROOT / "outputs" / "sector_tri_signal_momentum_sensitivity.csv"
OHLC = ROOT / "outputs" / "sector_tri_signal_momentum_ohlc_audit.csv"
SELECTION = ROOT / "outputs" / "sector_tri_signal_momentum_selection.json"
METHOD = ROOT / "outputs" / "sector_tri_signal_momentum_method.md"
CAPITAL = 1_000_000
DD_LIMIT = 20.0
EXPOSURES = (0.50, 0.75, 0.95, 1.00)
SLIPPAGE = (10, 50, 100)
INDEX_TO_ETF = {
    "Nifty Bank": "BANKBEES",
    "Nifty IT": "ITBEES",
    "Nifty Auto": "AUTOBEES",
    "Nifty Pharma": "PHARMABEES",
    "Nifty PSU Bank": "PSUBNKBEES",
}


def _read_tri(execution_index: pd.Index) -> tuple[pd.DataFrame, int]:
    raw = json.loads(TRI_RAW.read_text(encoding="utf-8"))
    assert raw["sourcePage"] == "https://www.niftyindices.com/reports/historical-data"
    assert raw["sourceRoute"] == "/BackPage/getTotalReturnIndexString"
    series: dict[str, dict[date, float]] = {etf: {} for etf in INDEX_TO_ETF.values()}
    for request in raw["requests"]:
        assert request["httpStatus"] == 200
        etf = INDEX_TO_ETF[request["index"]]
        for row in request["rows"]:
            assert row["Index Name"].strip().casefold() == request["index"].casefold()
            day = datetime.strptime(row["Date"], "%d %b %Y").date()
            value = float(row["TotalReturnsIndex"])
            assert value > 0 and day not in series[etf]
            series[etf][day] = value
    date_sets = [set(values) for values in series.values()]
    assert all(days == date_sets[0] for days in date_sets[1:])
    source_dates = date_sets[0]
    execution_dates = {timestamp.date() for timestamp in execution_index}
    assert execution_dates <= source_dates, "An ETF panel date lacks an official sector TRI close"
    frame = pd.DataFrame({
        etf: pd.Series(values, dtype=float)
        for etf, values in series.items()
    })
    frame.index = pd.to_datetime(frame.index)
    if execution_index.tz is not None:
        frame.index = frame.index.tz_localize(execution_index.tz)
    frame = frame.sort_index().reindex(execution_index)
    assert frame.notna().all().all()
    return frame, len(source_dates - execution_dates)


def _targets(signal_close: pd.DataFrame, execution_panels: dict[str, pd.DataFrame], top_n: int) -> tuple[pd.DataFrame, pd.Series]:
    targets, events = q.make_targets({"close": signal_close}, "momentum12_1", top_n=top_n)
    targets = targets.reindex(columns=execution_panels["close"].columns).fillna(0.0)
    assert targets.index.equals(execution_panels["close"].index)
    assert events.index.equals(execution_panels["close"].index)
    assert (targets >= 0).all().all() and (targets.sum(axis=1) <= 1.0 + 1e-12).all()
    return targets, events


def _run_label(strategy: str, period: str, exposure: float, slippage: int) -> str:
    return f"{strategy}__{period}__{int(exposure * 100)}cap__{slippage}bps"


def main() -> None:
    q._self_check()
    files, panels = q._read_prices([f"{name}={base.DATA / path}" for name, path in base.ASSETS.items()])
    assert set(files) == set(base.ASSETS)
    signal_close, unmapped_index_sessions = _read_tri(panels["close"].index)
    assert panels["close"].index.min().date() == date(2014, 1, 1)
    assert panels["close"].index.max().date() == date(2026, 10, 23)

    result_rows = []
    risk_rows = []
    for top_n in (1, 2, 3):
        strategy = f"sector_tri_momentum12_1_top{top_n}"
        targets, events = _targets(signal_close, panels, top_n)
        active = targets[list(INDEX_TO_ETF.values())].sum(axis=1).gt(0)
        first_active = active[active].index[0].date().isoformat() if active.any() else ""
        for period, start, end in base.PERIODS:
            for exposure in EXPOSURES:
                for slippage in SLIPPAGE:
                    equity, orders, stats = q._simulate(
                        panels, targets, events, CAPITAL, exposure, slippage,
                        "equity_delivery", start, end, DD_LIMIT,
                    )
                    stats["total_slippage_inr"] = blend.modeled_slippage(orders, panels)
                    label = _run_label(strategy, period, exposure, slippage)
                    run = OUT / label
                    run.mkdir(parents=True, exist_ok=True)
                    equity.reset_index(names="time").to_csv(run / "equity.csv", index=False)
                    orders.to_csv(run / "orders.csv", index=False)
                    summary = {
                        "strategy": strategy,
                        "signal_source": "official Nifty sector gross TRI",
                        "top_n": top_n,
                        "period": period,
                        "period_start": start.isoformat(),
                        "period_end": end.isoformat(),
                        "exposure_cap_pct": exposure * 100,
                        "slippage_bps_per_side": slippage,
                        "first_active_date": first_active,
                        "cash_distributions_credited": False,
                        **stats,
                    }
                    (run / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
                    result_rows.append({
                        "strategy": strategy,
                        "signal_source": "official Nifty sector gross TRI",
                        "top_n": top_n,
                        "period": period,
                        "period_start": start.isoformat(),
                        "period_end": end.isoformat(),
                        "first_active_date": first_active,
                        "exposure_cap_pct": exposure * 100,
                        "slippage_bps_per_side": slippage,
                        "starting_balance_inr": stats["starting_balance_inr"],
                        "ending_balance_inr": stats["ending_balance_inr"],
                        "total_return_pct": stats["total_return_pct"],
                        "cagr_pct": stats["cagr_pct"],
                        "max_drawdown_pct": stats["max_drawdown_pct"],
                        "sharpe_zero_rf": stats["sharpe_zero_rf"],
                        "average_gross_exposure_pct": stats["average_gross_exposure_pct"],
                        "order_count": stats["order_count"],
                        "fees_inr": stats["total_fees_inr"],
                        "slippage_cost_inr": stats["total_slippage_inr"],
                        "within_20pct_close": stats["within_drawdown_limit"],
                        "source_artifact": f"{run.relative_to(ROOT).as_posix()}/summary.json",
                    })
                    if slippage == 50:
                        risk = ohlc_audit.run_case(label, run.relative_to(ROOT).as_posix())
                        assert risk["max_close_replay_error_inr"] <= 0.03
                        risk_rows.append({
                            "strategy": strategy,
                            "period": period,
                            "exposure_cap_pct": exposure * 100,
                            "slippage_bps_per_side": slippage,
                            "close_max_drawdown_pct": risk["close_max_drawdown_pct"],
                            "simultaneous_ohlc_drawdown_bound_pct": risk["simultaneous_ohlc_drawdown_bound_pct"],
                            "bound_peak_date": risk["bound_peak_date"],
                            "bound_trough_date": risk["bound_trough_date"],
                            "within_20pct_under_bound": risk["within_20pct_under_bound"],
                            "max_close_replay_error_inr": risk["max_close_replay_error_inr"],
                            "source_artifact": f"{run.relative_to(ROOT).as_posix()}/equity.csv;{run.relative_to(ROOT).as_posix()}/orders.csv",
                        })

    assert len(result_rows) == 3 * len(base.PERIODS) * len(EXPOSURES) * len(SLIPPAGE) == 144
    assert len(risk_rows) == 3 * len(base.PERIODS) * len(EXPOSURES) == 48
    result = pd.DataFrame(result_rows)
    risk = pd.DataFrame(risk_rows)
    assert not result.duplicated(["strategy", "period", "exposure_cap_pct", "slippage_bps_per_side"]).any()
    assert not risk.duplicated(["strategy", "period", "exposure_cap_pct", "slippage_bps_per_side"]).any()
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    result.to_csv(SUMMARY, index=False)
    risk.to_csv(OHLC, index=False)

    train = result[(result["period"] == "train_2022_2023") & (result["slippage_bps_per_side"] == 50)]
    risk_for_selection = risk.rename(columns={"source_artifact": "risk_source_artifact"})
    train = train.merge(risk_for_selection[risk_for_selection["period"] == "train_2022_2023"], on=["strategy", "period", "exposure_cap_pct", "slippage_bps_per_side"])
    feasible = train[train["within_20pct_under_bound"]]
    selected = feasible.sort_values("cagr_pct", ascending=False).iloc[0] if not feasible.empty else None
    if selected is None:
        selection = {
            "selected_strategy": None,
            "training_period": "train_2022_2023",
            "selection_cost_bps_per_side": 50,
            "criterion": "highest net CAGR among candidates passing the conservative daily OHLC drawdown screen",
            "feasible_candidates": 0,
            "note": "No TRI-signal candidate in the predeclared grid passed the training OHLC screen.",
        }
        selection_text = "No candidate in the predeclared grid passed the training OHLC screen."
    else:
        chosen = result[
            (result["strategy"] == selected["strategy"])
            & (result["exposure_cap_pct"] == selected["exposure_cap_pct"])
            & (result["slippage_bps_per_side"] == 50)
        ].merge(
            risk_for_selection,
            on=["strategy", "period", "exposure_cap_pct", "slippage_bps_per_side"],
        )
        selection = {
            "selected_strategy": str(selected["strategy"]),
            "selected_top_n": int(selected["top_n"]),
            "selected_exposure_cap_pct": float(selected["exposure_cap_pct"]),
            "training_period": "train_2022_2023",
            "selection_cost_bps_per_side": 50,
            "criterion": "highest net CAGR among candidates passing the conservative daily OHLC drawdown screen",
            "training_result": selected.to_dict(),
            "same_rule_validation_holdout_full": chosen[chosen["period"].isin(["validation_2024", "holdout_2025_plus", "continuous_2022_plus"])].to_dict("records"),
            "caveat": "The broader history and later periods were previously inspected; this is not a pristine lockbox or live-performance evidence.",
        }
        selection_text = (
            f"Selected {selected['strategy']} at {selected['exposure_cap_pct']:.0f}% exposure. "
            f"Training return was {selected['total_return_pct']:+.2f}% and its conservative OHLC bound was "
            f"{selected['simultaneous_ohlc_drawdown_bound_pct']:.2f}%."
        )
    SELECTION.write_text(json.dumps(selection, indent=2, default=str), encoding="utf-8")

    excluded_dates = unmapped_index_sessions
    METHOD.write_text(
        "# Sector momentum with official TRI signals\n\n"
        f"**Run date:** {date.today().isoformat()}\n"
        "**Execution data:** Upstox daily ETF OHLC through 2026-10-23\n"
        "**Signal data:** NSE Indices gross sector TRI, 2014-01-01 through 2026-10-23\n"
        "**Capital / risk screen:** ₹10 lakh; 20% maximum drawdown\n\n"
        "## Rule and implementation\n\n"
        "For BANKBEES, ITBEES, AUTOBEES, PHARMABEES, and PSUBNKBEES, rank the corresponding official Nifty sector gross TRI series by 12–1 momentum (252-session return ending 21 sessions before month-end). Hold only positive-score indices above their own 200-session TRI average, equally weight the top 1/2/3, and rebalance at month-end signals for next-session ETF opens. ETF market prices determine quantities, fills, NAV, fees, and slippage; TRI is signal data only. Four official special-session dates in 2015–2018 have no common Upstox execution-panel date and are omitted from the aligned signal grid. The price-signal baseline is the matching row in `outputs/sector_rotation_sensitivity.csv`.\n\n"
        "Costs use current modeled equity-fund delivery charges uniformly across historical trades and 10/50/100 bps adverse slippage per side. Base results credit no ETF cash distributions because the sector ETF event ledger is incomplete; the disputed 2026 AUTOBEES/PHARMABEES claims remain a separate source-only lead. The official TRI is not an ETF fill price and does not supply ETF market impact or distribution dates.\n\n"
        "## Walk-forward-style selection result\n\n"
        f"{selection_text} The selected rule, its 2024 validation, 2025+ holdout, continuous replay, and OHLC bounds are in `outputs/sector_tri_signal_momentum_selection.json`; all 144 strategy/cost/period rows are in `outputs/sector_tri_signal_momentum_sensitivity.csv`. The 48 50-bps paths have conservative same-day high-before-low replays in `outputs/sector_tri_signal_momentum_ohlc_audit.csv`; every order ledger reconciled to saved close NAV within ₹0.03.\n\n"
        "## Limits\n\n"
        "This is a signal-source challenger, not a cash-distribution-adjusted ETF total-return backtest. The five-ETF universe has unequal inception dates and survivor bias; although index TRI supplies pre-launch signal warm-up, ETF P&L begins only when traded ETF bars exist. The 2025+ and full histories were inspected repeatedly and are not untouched holdouts. The OHLC envelope assumes held positions hit daily highs before lows; it is conservative but is not an enforceable future loss limit. A passing historical bound does not guarantee future drawdown stays below 20%.\n\n"
        "The source capture script is `work/capture_sector_tri_signal_history.py`; raw rows are in `work/data/index_daily/sector_tri_raw_2014_2026.json`. NSE Indices describes TRI as price performance plus dividends indexed on ex-date and reinvested; its historical-data page's POST route was observed in official page JavaScript and is not a documented public API. See [NSE TRI methodology](https://www.niftyindices.com/resources/index-concepts/total-return-index) and [historical-data report](https://www.niftyindices.com/reports/historical-data).\n",
        encoding="utf-8",
    )
    print(f"cases={len(result)} ohlc_cases={len(risk)} unmapped_official_sessions={excluded_dates} selected={selection.get('selected_strategy')}")


if __name__ == "__main__":
    main()
