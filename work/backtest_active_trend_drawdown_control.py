"""Select a close-drawdown throttle for the quarterly NIFTY/Gold trend blend."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

import audit_etf_intraday_drawdown as audit
import backtest_passive_mix_drawdown_control as throttle
import benchmark_nifty_gold_2020 as benchmark
import replay_volatility_weighted_blend as blend
import upstox_quant as q


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs" / "active_trend_drawdown_control.csv"
SELECTION = ROOT / "outputs" / "active_trend_drawdown_selection.json"
RUNS = ROOT / "work" / "backtests" / "active_trend_drawdown"
TRAIN_START = date(2014, 1, 2)
TRAIN_END = date(2022, 12, 30)
HOLDOUT_START = date(2023, 1, 1)
CAPITAL = 1_000_000.0
SLIPPAGE_BPS = 50.0
HIGH_CAP = 0.70
LOW_CAP = 0.35
TRIGGERS = (8.0, 10.0, 12.0)


def _self_check() -> None:
    assert throttle.next_exposure(0.70, -0.08, 8.0, HIGH_CAP, LOW_CAP) == LOW_CAP
    assert throttle.next_exposure(0.35, -0.04, 8.0, HIGH_CAP, LOW_CAP) == HIGH_CAP


def assert_matches_shared_simulator(
    panels: dict[str, pd.DataFrame], targets: pd.DataFrame, events: pd.Series,
    cap: float, start: date, end: date,
) -> None:
    reference, reference_orders, reference_stats = q._simulate(
        panels, targets, events, CAPITAL, cap, SLIPPAGE_BPS, "equity_delivery", start, end,
        cash_distributions=benchmark.NIFTYBEES_DISTRIBUTIONS,
    )
    equity, orders, stats = throttle.simulate(
        panels, f"fixed_{int(cap * 100)}", cap, None, SLIPPAGE_BPS, start, end,
        targets, events,
    )
    assert np.allclose(equity["nav"].to_numpy(), reference["nav"].to_numpy(), atol=0.03, rtol=0)
    assert len(orders) == len(reference_orders)
    assert abs(stats["total_fees_inr"] - reference_stats["total_fees_inr"]) <= 0.03


def run_case(
    panels: dict[str, pd.DataFrame], targets: pd.DataFrame, events: pd.Series,
    candidate: dict, segment: str, start: date, end: date,
) -> dict:
    name = candidate["name"]
    equity, orders, stats = throttle.simulate(
        panels, name, candidate["high_cap"], candidate["trigger_pct"], SLIPPAGE_BPS,
        start, end, targets, events,
        LOW_CAP if candidate["trigger_pct"] is not None else None,
    )
    run_dir = RUNS / f"{segment}_{name}"
    run_dir.mkdir(parents=True, exist_ok=True)
    equity.to_csv(run_dir / "equity.csv", index_label="time")
    orders.to_csv(run_dir / "orders.csv", index=False)
    relative = run_dir.relative_to(ROOT).as_posix()
    audit.SLIPPAGE_BPS = SLIPPAGE_BPS
    risk = audit.run_case(name, relative, starting_balance=CAPITAL)
    assert risk["max_close_replay_error_inr"] <= 0.03
    returns = equity["nav"].pct_change().replace([np.inf, -np.inf], np.nan).dropna()
    sharpe = float(returns.mean() / returns.std(ddof=1) * np.sqrt(252)) if len(returns) > 1 and returns.std(ddof=1) else 0.0
    return {
        **stats,
        "candidate": name,
        "segment": segment,
        "close_mdd_pct": risk["close_drawdown_since_prior_peak_pct"],
        "ohlc_drawdown_bound_pct": risk["simultaneous_ohlc_drawdown_bound_pct"],
        "within_20pct_ohlc": risk["within_20pct_under_bound"],
        "sharpe_zero_rf": sharpe,
        "max_close_replay_error_inr": risk["max_close_replay_error_inr"],
        "source_equity": f"{relative}/equity.csv",
        "source_orders": f"{relative}/orders.csv",
    }


def main() -> None:
    _self_check()
    _, panels, portfolios, portfolio_events = blend.make_portfolios()
    throttle._self_check()
    for exposure in (0.45, 0.60):
        throttle.assert_matches_shared_simulator(panels, exposure)
    targets = portfolios["fixed_50_50_quarterly"]
    events = portfolio_events["fixed_50_50_quarterly"]
    common_end = panels["close"].dropna(subset=["NIFTYBEES", "GOLDBEES"]).index[-1].date()
    assert common_end == date(2026, 10, 23), "Keep this frozen experiment on the documented history cutoff"

    candidates = [
        {"name": "fixed_70pct", "high_cap": HIGH_CAP, "trigger_pct": None},
        {"name": "fixed_40pct", "high_cap": 0.40, "trigger_pct": None},
        *[
            {
                "name": f"dd_{int(trigger)}pct_cut_70_to_35_recover_{int(trigger / 2)}pct",
                "high_cap": HIGH_CAP,
                "trigger_pct": trigger,
            }
            for trigger in TRIGGERS
        ],
    ]
    assert_matches_shared_simulator(panels, targets, events, HIGH_CAP, TRAIN_START, TRAIN_END)
    assert_matches_shared_simulator(panels, targets, events, 0.40, TRAIN_START, TRAIN_END)

    results = []
    for segment, start, end in (
        ("training", TRAIN_START, TRAIN_END),
        ("holdout", HOLDOUT_START, common_end),
    ):
        results.extend(run_case(panels, targets, events, candidate, segment, start, end) for candidate in candidates)
    result = pd.DataFrame(results)
    training = result.loc[result["segment"] == "training"]
    passing = training.loc[training["ohlc_drawdown_bound_pct"] >= -20.0]
    if passing.empty:
        raise AssertionError("No candidate passed the pre-registered training OHLC drawdown screen")
    selected = passing.sort_values(["total_return_pct", "candidate"], ascending=[False, True]).iloc[0]
    selected_holdout = result.loc[
        (result["segment"] == "holdout") & (result["candidate"] == selected["candidate"])
    ].iloc[0]
    selection = {
        "strategy_family": "quarterly fixed 50/50 NIFTYBEES Donchian 55/20 and GOLDBEES SMA200",
        "capital_inr": CAPITAL,
        "slippage_bps_per_side": SLIPPAGE_BPS,
        "fees": "Current modeled Upstox/NSE equity delivery charges; 0% cash yield",
        "training_period": [TRAIN_START.isoformat(), TRAIN_END.isoformat()],
        "holdout_period": [HOLDOUT_START.isoformat(), common_end.isoformat()],
        "candidate_rules": candidates,
        "selection_rule": "Highest net training return among fixed-70%, fixed-40%, and 70%-to-35% throttle candidates whose simultaneous daily OHLC drawdown bound is no worse than -20%; selected rule is frozen before evaluating the fresh-account 2023+ segment.",
        "selected_candidate": str(selected["candidate"]),
        "selected_training": selected.to_dict(),
        "selected_holdout": selected_holdout.to_dict(),
        "all_candidates_passed_holdout_20pct": bool(
            result.loc[result["segment"] == "holdout", "within_20pct_ohlc"].all()
        ),
        "caveat": "The later period and candidate family were already inspected in broader research; this is retrospective pseudo-out-of-sample evidence, not a pristine lockbox or future loss limit.",
    }
    assert len(result) == len(candidates) * 2
    assert not result.duplicated(["segment", "candidate"]).any()
    assert result["max_close_replay_error_inr"].max() <= 0.03
    OUT.parent.mkdir(parents=True, exist_ok=True)
    result.to_csv(OUT, index=False)
    SELECTION.write_text(json.dumps(selection, indent=2, default=str) + "\n", encoding="utf-8")
    print(f"Selected {selected['candidate']} on training OHLC screen; replayed {len(result)} candidate-segment cases through {common_end}; no broker orders placed")


if __name__ == "__main__":
    main()
