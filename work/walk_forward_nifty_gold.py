"""Expanding-window NIFTY/Gold rule selection with annual pseudo-out-of-sample folds."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pandas as pd

import audit_etf_intraday_drawdown as audit
import replay_volatility_weighted_blend as blend
import sensitivity_nifty_gold_parameters as sensitivity
import upstox_quant as q


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "work" / "backtests" / "nifty_gold_walk_forward"
SUMMARY = ROOT / "outputs" / "nifty_gold_walk_forward.csv"
CAPITAL = 1_000_000.0
EXPOSURE_CAP = 0.45
SLIPPAGE_BPS = 50.0
TRAIN_START = date(2014, 1, 1)
TEST_YEARS = range(2020, 2027)
BASELINE = "baseline_D55_20_SMA200"


def _save_run(path: Path, equity: pd.DataFrame, orders: pd.DataFrame) -> str:
    path.mkdir(parents=True, exist_ok=True)
    equity.to_csv(path / "equity.csv", index_label="time")
    orders.to_csv(path / "orders.csv", index=False)
    return str(path.relative_to(ROOT))


def _simulate(
    panels: dict[str, pd.DataFrame],
    targets: pd.DataFrame,
    events: pd.Series,
    start: date,
    end: date,
    path: Path,
    starting_balance: float = CAPITAL,
    prior_ohlc_peak_nav: float | None = None,
    prior_close_peak_nav: float | None = None,
    prior_ohlc_peak_date: str | None = None,
    prior_close_peak_date: str | None = None,
) -> tuple[pd.DataFrame, dict, dict]:
    equity, orders, stats = q._simulate(
        panels, targets, events, starting_balance, EXPOSURE_CAP, SLIPPAGE_BPS,
        "equity_delivery", start, end, 20.0,
    )
    stats["total_slippage_inr"] = blend.modeled_slippage(orders, panels)
    risk = audit.run_case(
        "walk_forward", _save_run(path, equity, orders), starting_balance,
        prior_ohlc_peak_nav, prior_close_peak_nav, prior_ohlc_peak_date, prior_close_peak_date,
    )
    assert risk["max_close_replay_error_inr"] <= 0.03
    return equity, stats, risk


def main() -> None:
    _, panels, _, _ = blend.make_portfolios()
    data_end = panels["close"].index[-1].date()
    targets_by_rule = {
        name: sensitivity._portfolio(panels, entry, exit_, trend)
        for name, entry, exit_, trend in sensitivity.VARIANTS
    }
    assert set(targets_by_rule) == {name for name, *_ in sensitivity.VARIANTS}

    rows: list[dict] = []
    sequence_state = {
        role: {
            "capital": CAPITAL,
            "ohlc_peak_nav": CAPITAL,
            "close_peak_nav": CAPITAL,
            "ohlc_peak_date": "starting_capital",
            "close_peak_date": "starting_capital",
            "worst_ohlc_pct": 0.0,
            "worst_close_pct": 0.0,
        }
        for role in ("walk_forward_selected", "fixed_D55_20_control")
    }
    for year in TEST_YEARS:
        train_end = date(year - 1, 12, 31)
        test_start = date(year, 1, 1)
        test_end = min(date(year, 12, 31), data_end)
        if test_start > data_end:
            break

        training: dict[str, tuple[dict, dict]] = {}
        for name, (targets, events) in targets_by_rule.items():
            _, stats, risk = _simulate(
                panels, targets, events, TRAIN_START, train_end,
                OUT / f"training_{year}" / name,
            )
            training[name] = (stats, risk)
        eligible = [
            name for name, (stats, risk) in training.items()
            if stats["within_drawdown_limit"] and risk["within_20pct_under_bound"]
        ]
        assert eligible, f"No training rule passed the 20% OHLC drawdown screen before {year}."
        selected_name = max(eligible, key=lambda name: training[name][0]["total_return_pct"])
        assert training[selected_name][1]["within_20pct_under_bound"]

        for role, name in (("walk_forward_selected", selected_name), ("fixed_D55_20_control", BASELINE)):
            targets, events = targets_by_rule[name]
            state = sequence_state[role]
            equity, stats, risk = _simulate(
                panels, targets, events, test_start, test_end,
                OUT / f"test_{year}" / role,
                state["capital"], state["ohlc_peak_nav"], state["close_peak_nav"],
                state["ohlc_peak_date"], state["close_peak_date"],
            )
            state["capital"] = stats["ending_balance_inr"]
            state["ohlc_peak_nav"] = risk["running_peak_nav_inr"]
            state["close_peak_nav"] = risk["running_close_peak_nav_inr"]
            state["ohlc_peak_date"] = risk["running_peak_date"]
            state["close_peak_date"] = risk["running_close_peak_date"]
            state["worst_ohlc_pct"] = min(state["worst_ohlc_pct"], risk["simultaneous_ohlc_drawdown_bound_pct"])
            state["worst_close_pct"] = min(state["worst_close_pct"], risk["close_drawdown_since_prior_peak_pct"])
            train_stats, train_risk = training[name]
            rows.append({
                "role": role,
                "test_year": year,
                "strategy": name,
                "selection_rule": "Highest net training return among seven rules passing 20% close and OHLC drawdown screens",
                "training_start": TRAIN_START.isoformat(),
                "training_end": train_end.isoformat(),
                "training_eligible_rules": len(eligible),
                "training_return_pct": train_stats["total_return_pct"],
                "training_close_mdd_pct": train_stats["max_drawdown_pct"],
                "training_ohlc_bound_pct": train_risk["simultaneous_ohlc_drawdown_bound_pct"],
                "test_start": stats["first_bar"][:10],
                "test_end": stats["last_bar"][:10],
                "sessions": len(equity),
                "starting_balance_inr": stats["starting_balance_inr"],
                "ending_balance_inr": stats["ending_balance_inr"],
                "total_return_pct": stats["total_return_pct"],
                "cagr_pct": stats["cagr_pct"],
                "close_mdd_pct": stats["max_drawdown_pct"],
                "annual_ohlc_bound_pct": risk["fold_ohlc_drawdown_bound_pct"],
                "ohlc_bound_pct": state["worst_ohlc_pct"],
                "stitched_close_mdd_pct": state["worst_close_pct"],
                "within_20pct_ohlc": state["worst_ohlc_pct"] >= -20.0,
                "total_fees_inr": stats["total_fees_inr"],
                "total_slippage_inr": stats["total_slippage_inr"],
                "order_count": stats["order_count"],
                "max_close_replay_error_inr": risk["max_close_replay_error_inr"],
                "gross_exposure_cap_pct": EXPOSURE_CAP * 100,
                "slippage_bps_per_side": SLIPPAGE_BPS,
            })

    result = pd.DataFrame(rows)
    assert len(result) == 14
    assert result.groupby("test_year")["role"].nunique().eq(2).all()
    assert result["max_close_replay_error_inr"].max() <= 0.03
    assert result["ohlc_bound_pct"].notna().all()
    result.to_csv(SUMMARY, index=False)

    print(json.dumps({
        "folds": result["test_year"].nunique(),
        "data_end": data_end.isoformat(),
        "selected_rules": result[result["role"].eq("walk_forward_selected")][["test_year", "strategy"]].to_dict("records"),
        "selected_ending_balance_inr": sequence_state["walk_forward_selected"]["capital"],
        "selected_compounded_return_pct": (sequence_state["walk_forward_selected"]["capital"] / CAPITAL - 1) * 100,
        "selected_stitched_close_mdd_pct": sequence_state["walk_forward_selected"]["worst_close_pct"],
        "selected_stitched_ohlc_bound_pct": sequence_state["walk_forward_selected"]["worst_ohlc_pct"],
        "selected_sequence_within_20pct": sequence_state["walk_forward_selected"]["worst_ohlc_pct"] >= -20.0,
        "baseline_ending_balance_inr": sequence_state["fixed_D55_20_control"]["capital"],
        "baseline_compounded_return_pct": (sequence_state["fixed_D55_20_control"]["capital"] / CAPITAL - 1) * 100,
        "baseline_stitched_close_mdd_pct": sequence_state["fixed_D55_20_control"]["worst_close_pct"],
        "baseline_stitched_ohlc_bound_pct": sequence_state["fixed_D55_20_control"]["worst_ohlc_pct"],
        "baseline_sequence_within_20pct": sequence_state["fixed_D55_20_control"]["worst_ohlc_pct"] >= -20.0,
        "summary": str(SUMMARY.relative_to(ROOT)),
    }, indent=2))


if __name__ == "__main__":
    main()
