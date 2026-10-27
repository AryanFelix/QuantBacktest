"""Select passive NIFTY/Gold initial exposure on a training window, then carry it forward."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pandas as pd

import benchmark_nifty_gold_2020 as benchmark
import replay_volatility_weighted_blend as blend


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs" / "passive_mix_exposure_sensitivity.csv"
RUNS = ROOT / "work" / "backtests" / "passive_mix_exposure"
START = date(2015, 1, 2)
TRAIN_END = date(2019, 12, 31)
EXPOSURE_PCTS = tuple(range(30, 101, 5))


def nav_at_or_before(path: Path, cutoff: date) -> float:
    equity = pd.read_csv(path)
    dates = pd.to_datetime(equity["time"]).dt.date
    eligible = equity.loc[dates <= cutoff]
    if eligible.empty:
        raise ValueError(f"No equity observation on or before {cutoff}: {path}")
    return float(eligible["nav"].iloc[-1])


def main() -> None:
    _, panels, _, _ = blend.make_portfolios()
    full_end = panels["close"].index[-1].date()
    common = panels["close"].dropna(subset=["NIFTYBEES", "GOLDBEES"]).index
    assert any(timestamp.date() == START for timestamp in common) and TRAIN_END < full_end
    targets, events = benchmark._passive_targets(
        panels, {"NIFTYBEES": 0.5, "GOLDBEES": 0.5},
    )

    train_results = {}
    full_results = {}
    for exposure_pct in EXPOSURE_PCTS:
        label = f"passive_equal_{exposure_pct:03d}"
        train_results[exposure_pct] = benchmark._run(
            f"{label}_train_2015_2019", targets, events, panels, TRAIN_END,
            start=START,
            run_dir=RUNS / "train_2015_2019",
            cash_distributions=benchmark.NIFTYBEES_DISTRIBUTIONS,
            exposure_cap=exposure_pct / 100,
        )
        full_results[exposure_pct] = benchmark._run(
            f"{label}_continuous_2015_plus", targets, events, panels, full_end,
            start=START,
            run_dir=RUNS / "continuous_2015_plus",
            cash_distributions=benchmark.NIFTYBEES_DISTRIBUTIONS,
            exposure_cap=exposure_pct / 100,
        )

    eligible = [
        result for result in train_results.values()
        if result["within_20pct_ohlc"]
    ]
    assert eligible, "No training exposure passes the conservative OHLC screen"
    selected_pct = int(max(eligible, key=lambda row: row["total_return_pct"])["gross_exposure_cap_pct"])
    output_rows = []
    for exposure_pct in EXPOSURE_PCTS:
        train = train_results[exposure_pct]
        output_rows.append({
            "period": "train_2015_2019",
            "tested_initial_exposure_pct": exposure_pct,
            "strategy": train["strategy"],
            **train,
            "post_2019_oos_return_pct": "",
            "training_selected": exposure_pct == selected_pct,
        })
        continuous = full_results[exposure_pct]
        full_path = RUNS / "continuous_2015_plus" / f"passive_equal_{exposure_pct:03d}_continuous_2015_plus" / "equity.csv"
        train_end_nav = nav_at_or_before(full_path, TRAIN_END)
        continuous["post_2019_oos_start_nav_inr"] = train_end_nav
        continuous["post_2019_oos_return_pct"] = (
            continuous["ending_balance_inr"] / train_end_nav - 1
        ) * 100
        output_rows.append({
            "period": "continuous_2015_plus",
            "tested_initial_exposure_pct": exposure_pct,
            "strategy": continuous["strategy"],
            **continuous,
            "training_selected": exposure_pct == selected_pct,
        })

    result = pd.DataFrame(output_rows)
    assert len(result) == 2 * len(EXPOSURE_PCTS)
    assert result["strategy"].is_unique
    assert result.loc[result["period"].eq("train_2015_2019"), "training_selected"].sum() == 1
    assert result.loc[result["period"].eq("continuous_2015_plus"), "post_2019_oos_return_pct"].notna().all()
    result.to_csv(OUT, index=False)
    print(f"wrote {len(result)} exposure-period rows; training selected {selected_pct}% initial exposure")


if __name__ == "__main__":
    main()
