"""Select a NIFTY/Gold exposure cap on prior OHLC risk, then freeze it for a later test."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pandas as pd

import audit_etf_intraday_drawdown as audit
import replay_volatility_weighted_blend as blend
import upstox_quant as q


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "work" / "backtests" / "etf_exposure_cap_oos"
RESULTS = ROOT / "outputs" / "etf_exposure_cap_oos.csv"
SELECTION = ROOT / "outputs" / "etf_exposure_cap_oos_selection.json"
CAPITAL = 1_000_000.0
SLIPPAGE_BPS = 50.0
CAPS = tuple(range(25, 101, 5))
TRAIN_START, TRAIN_END = date(2014, 1, 1), date(2022, 12, 30)
TEST_START, TEST_END = date(2023, 1, 1), date(2026, 10, 23)


def select_cap(rows: pd.DataFrame, risk_limit_pct: float) -> int:
    eligible = rows[rows["simultaneous_ohlc_drawdown_bound_pct"] >= -risk_limit_pct]
    if eligible.empty:
        raise ValueError(f"no training cap passed the {risk_limit_pct:g}% OHLC screen")
    winner = eligible.sort_values(
        ["total_return_pct", "gross_exposure_cap_pct"],
        ascending=[False, True],
        kind="stable",
    ).iloc[0]
    return int(winner["gross_exposure_cap_pct"])


def run_case(
    panels, targets, events, segment: str, cap: int, start: date, end: date,
    slippage_bps: float = SLIPPAGE_BPS, run_root: Path | None = None,
) -> dict:
    equity, orders, stats = q._simulate(
        panels, targets, events, CAPITAL, cap / 100, slippage_bps,
        "equity_delivery", start, end, 20,
    )
    run = (run_root or OUT) / f"{segment}_cap_{cap:02d}"
    run.mkdir(parents=True, exist_ok=True)
    equity.to_csv(run / "equity.csv", index_label="time")
    orders.to_csv(run / "orders.csv", index=False)
    risk = audit.run_case(
        f"Quarterly fixed 50/50 trend; {cap}% exposure cap; {segment}",
        str(run.relative_to(ROOT)),
        slippage_bps=slippage_bps,
    )
    return {
        "segment": segment,
        "period_start": start.isoformat(),
        "period_end": end.isoformat(),
        "slippage_bps_per_side": slippage_bps,
        "gross_exposure_cap_pct": cap,
        "starting_balance_inr": stats["starting_balance_inr"],
        "ending_balance_inr": stats["ending_balance_inr"],
        "total_return_pct": stats["total_return_pct"],
        "cagr_pct": stats["cagr_pct"],
        "annualized_volatility_pct": stats["annualized_volatility_pct"],
        "sharpe_zero_rf": stats["sharpe_zero_rf"],
        "close_max_drawdown_pct": risk["close_max_drawdown_pct"],
        "simultaneous_ohlc_drawdown_bound_pct": risk["simultaneous_ohlc_drawdown_bound_pct"],
        "bound_peak_date": risk["bound_peak_date"],
        "bound_trough_date": risk["bound_trough_date"],
        "headroom_to_20pct_bound_pp": risk["headroom_to_20pct_bound_pp"],
        "within_20pct_under_bound": risk["within_20pct_under_bound"],
        "total_fees_inr": stats["total_fees_inr"],
        "total_slippage_inr": blend.modeled_slippage(orders, panels),
        "order_count": stats["order_count"],
        "average_gross_exposure_pct": stats["average_gross_exposure_pct"],
        "cash_distributions_inr": stats["cash_distributions_inr"],
        "max_close_replay_error_inr": risk["max_close_replay_error_inr"],
        "run_artifact": str(run.relative_to(ROOT)).replace("\\", "/"),
    }


def main() -> None:
    _, panels, portfolios, event_sets = blend.make_portfolios()
    assert panels["close"].index.is_unique
    targets = portfolios["fixed_50_50_quarterly"]
    events = event_sets["fixed_50_50_quarterly"]
    OUT.mkdir(parents=True, exist_ok=True)

    training = [
        run_case(panels, targets, events, "training", cap, TRAIN_START, TRAIN_END)
        for cap in CAPS
    ]
    training_frame = pd.DataFrame(training)
    selected_20 = select_cap(training_frame, 20)
    selected_15 = select_cap(training_frame, 15)
    assert len(training_frame) == len(CAPS)
    assert training_frame["within_20pct_under_bound"].eq(
        training_frame["simultaneous_ohlc_drawdown_bound_pct"].ge(-20)
    ).all()

    oos_caps = sorted({selected_20, selected_15, 45, 50})
    oos = [
        run_case(panels, targets, events, "holdout", cap, TEST_START, TEST_END)
        for cap in oos_caps
    ]
    oos_frame = pd.DataFrame(oos)
    selected_oos = oos_frame.loc[oos_frame["gross_exposure_cap_pct"].eq(selected_20)].iloc[0]
    assert bool(selected_oos["within_20pct_under_bound"])
    assert (training_frame["max_close_replay_error_inr"] < 0.01).all()
    assert (oos_frame["max_close_replay_error_inr"] < 0.01).all()

    result = pd.concat([training_frame, oos_frame], ignore_index=True)
    result.insert(0, "selection_role", "training_grid")
    result.loc[result["segment"].eq("holdout"), "selection_role"] = "frozen_oos_comparison"
    result.loc[
        result["segment"].eq("training") & result["gross_exposure_cap_pct"].eq(selected_20),
        "selection_role",
    ] = "selected_at_20pct_training_screen"
    result.loc[
        result["segment"].eq("training") & result["gross_exposure_cap_pct"].eq(selected_15),
        "selection_role",
    ] = "selected_at_15pct_buffer_screen"
    result.loc[
        result["segment"].eq("holdout") & result["gross_exposure_cap_pct"].eq(selected_20),
        "selection_role",
    ] = "primary_frozen_oos"
    result.loc[
        result["segment"].eq("holdout") & result["gross_exposure_cap_pct"].eq(selected_15),
        "selection_role",
    ] = "15pct_buffer_frozen_oos"
    result.to_csv(RESULTS, index=False)

    selection = {
        "strategy": "Quarterly fixed 50/50 NIFTYBEES Donchian 55/20 and GOLDBEES SMA200",
        "capital_inr": CAPITAL,
        "slippage_bps_per_side": SLIPPAGE_BPS,
        "training_period": [TRAIN_START.isoformat(), TRAIN_END.isoformat()],
        "holdout_period": [TEST_START.isoformat(), TEST_END.isoformat()],
        "candidate_caps_pct": list(CAPS),
        "selection_rule": "Highest training net total return among caps whose simultaneous daily OHLC drawdown bound passes the stated threshold; ties prefer lower cap.",
        "selected_cap_at_20pct_limit": selected_20,
        "selected_cap_at_15pct_safety_buffer": selected_15,
        "selected_20pct_cap_training": next(r for r in training if r["gross_exposure_cap_pct"] == selected_20),
        "selected_20pct_cap_holdout": next(r for r in oos if r["gross_exposure_cap_pct"] == selected_20),
        "selected_15pct_cap_training": next(r for r in training if r["gross_exposure_cap_pct"] == selected_15),
        "selected_15pct_cap_holdout": next(r for r in oos if r["gross_exposure_cap_pct"] == selected_15),
        "limitations": [
            "Later ETF history and strategy families have already been inspected; the 2023+ window is chronological pseudo-out-of-sample, not an untouched lockbox.",
            "OHLC drawdown assumes every held high precedes every held low on each date; it is a conservative envelope, not an observed path or future loss cap.",
            "Current fees are applied uniformly over history, 50 bps per-side slippage is modeled, cash earns 0%, and investor tax and market impact are excluded.",
            "ETF price histories are used; GoldBeES distribution completeness is unresolved.",
        ],
        "results_csv": str(RESULTS.relative_to(ROOT)).replace("\\", "/"),
    }
    SELECTION.write_text(json.dumps(selection, indent=2), encoding="utf-8")
    print(
        f"Selected {selected_20}% cap at the 20% training screen and {selected_15}% at the 15% buffer; "
        f"frozen 2023+ OHLC bound {selected_oos['simultaneous_ohlc_drawdown_bound_pct']:.2f}%.",
        flush=True,
    )


if __name__ == "__main__":
    main()
