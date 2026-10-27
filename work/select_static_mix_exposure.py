"""Select a quarterly NIFTY/Gold mix exposure on 2015–2019, then freeze it for 2020+."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pandas as pd

import benchmark_nifty_gold_2020 as benchmark
import replay_volatility_weighted_blend as blend


ROOT = Path(__file__).resolve().parents[1]
TRAINING_OUT = ROOT / "work" / "backtests" / "static_mix_exposure_training"
TEST_OUT = ROOT / "work" / "backtests" / "static_mix_exposure_test"
TRAINING_SUMMARY = ROOT / "outputs" / "static_mix_exposure_training.csv"
SELECTION = ROOT / "outputs" / "static_mix_training_selection.json"
TEST_SUMMARY = ROOT / "outputs" / "static_mix_exposure_oos_test.csv"
TRAIN_START = date(2015, 1, 2)
TRAIN_END = date(2019, 12, 31)
TEST_START = date(2020, 1, 1)
CAP_GRID = [cap / 100 for cap in range(10, 101, 5)]


def main() -> None:
    _, panels, _, _ = blend.make_portfolios()
    data_end = panels["close"].index[-1].date()
    assert panels["close"].index[0].date() == date(2014, 1, 1)
    assert TRAIN_START < TRAIN_END < TEST_START <= data_end
    targets, events = benchmark._quarterly_static_targets(panels)
    training_rows = [
        benchmark._run(
            f"static_mix_{int(cap * 100):03d}pct",
            targets,
            events,
            panels,
            TRAIN_END,
            start=TRAIN_START,
            run_dir=TRAINING_OUT,
            cash_distributions=benchmark.NIFTYBEES_DISTRIBUTIONS,
            exposure_cap=cap,
        )
        for cap in CAP_GRID
    ]
    training = pd.DataFrame(training_rows)
    assert len(training) == len(CAP_GRID) == training["strategy"].nunique()
    assert training["period_start"].eq(TRAIN_START.isoformat()).all()
    assert training["period_end"].eq(TRAIN_END.isoformat()).all()
    eligible = training.loc[training["within_20pct_ohlc"]].sort_values(
        ["total_return_pct", "gross_exposure_cap_pct"], ascending=[False, True]
    )
    assert not eligible.empty, "No training exposure passes the 20% OHLC drawdown screen"
    selected = eligible.iloc[0]
    selected_cap = float(selected["gross_exposure_cap_pct"]) / 100
    TRAINING_SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    training.to_csv(TRAINING_SUMMARY, index=False)
    test_rows = [
        benchmark._run(
            f"static_mix_oos_{int(cap * 100):03d}pct",
            targets,
            events,
            panels,
            data_end,
            start=TEST_START,
            run_dir=TEST_OUT,
            cash_distributions=benchmark.NIFTYBEES_DISTRIBUTIONS,
            exposure_cap=cap,
        )
        for cap in CAP_GRID
    ]
    test = pd.DataFrame(test_rows)
    test["selected_by_training_rule"] = test["gross_exposure_cap_pct"].eq(selected_cap * 100)
    assert len(test) == len(CAP_GRID) == test["strategy"].nunique()
    assert test["period_start"].eq(TEST_START.isoformat()).all()
    assert test["period_end"].eq(data_end.isoformat()).all()
    assert test["max_close_replay_error_inr"].max() <= 0.03
    test.to_csv(TEST_SUMMARY, index=False)
    selected_test = test.loc[test["selected_by_training_rule"]].iloc[0]
    test_passers = test.loc[test["within_20pct_ohlc"]].sort_values(
        ["total_return_pct", "gross_exposure_cap_pct"], ascending=[False, True]
    )
    assert len(test_passers) > 0 and bool(selected_test["selected_by_training_rule"])
    SELECTION.write_text(json.dumps({
        "training_period": [TRAIN_START.isoformat(), TRAIN_END.isoformat()],
        "candidate_gross_exposure_caps_pct": [cap * 100 for cap in CAP_GRID],
        "selection_rule": "Highest net training return among candidates with conservative same-day OHLC drawdown bound no worse than -20%",
        "selected_cap_pct": selected_cap * 100,
        "selected_training_return_pct": float(selected["total_return_pct"]),
        "selected_training_ohlc_bound_pct": float(selected["ohlc_drawdown_bound_pct"]),
        "training_candidates": len(training),
        "cash_distributions_inr": float(selected["cash_distributions_inr"]),
        "test_period": [TEST_START.isoformat(), data_end.isoformat()],
        "test_was_inspected_before_selection": True,
        "selected_cap_test_return_pct": float(selected_test["total_return_pct"]),
        "selected_cap_test_ohlc_bound_pct": float(selected_test["ohlc_drawdown_bound_pct"]),
        "selected_cap_test_passed_20pct": bool(selected_test["within_20pct_ohlc"]),
        "highest_return_test_candidate_passing_screen_pct": float(test_passers.iloc[0]["gross_exposure_cap_pct"]),
        "test_sensitivity_is_post_hoc": True,
        "status": "historical pseudo-out-of-sample; not an untouched holdout",
        "artifacts": {
            "training_summary": str(TRAINING_SUMMARY.relative_to(ROOT)),
            "training_runs": str(TRAINING_OUT.relative_to(ROOT)),
            "test_summary": str(TEST_SUMMARY.relative_to(ROOT)),
            "test_runs": str(TEST_OUT.relative_to(ROOT)),
        },
    }, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "selected_cap_pct": selected_cap * 100,
        "training": training[["strategy", "total_return_pct", "ohlc_drawdown_bound_pct", "within_20pct_ohlc"]].to_dict("records"),
        "test": test[["strategy", "total_return_pct", "ohlc_drawdown_bound_pct", "within_20pct_ohlc"]].to_dict("records"),
        "highest_test_cap_passing_20pct_screen": float(test_passers.iloc[0]["gross_exposure_cap_pct"]),
        "training_summary": str(TRAINING_SUMMARY.relative_to(ROOT)),
        "selection": str(SELECTION.relative_to(ROOT)),
        "test_summary": str(TEST_SUMMARY.relative_to(ROOT)),
    }, indent=2))


if __name__ == "__main__":
    main()
