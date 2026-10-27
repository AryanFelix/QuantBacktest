"""Train-select the NIFTY/Gold composition at a fixed passive initial allocation."""

from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "work"))

import backtest_stock_momentum as stock
import benchmark_nifty_gold_2020 as benchmark
import replay_volatility_weighted_blend as blend

START = date(2015, 1, 2)
TRAIN_END = date(2019, 12, 31)
INITIAL_EXPOSURE = 0.45
SLIPPAGE_BPS = 50.0
NIFTY_SHARES = tuple(range(0, 101, 10))
RUNS = ROOT / "work" / "backtests" / "passive_mix_composition"
RESULTS = ROOT / "outputs" / "passive_mix_composition_sensitivity.csv"
SELECTION = ROOT / "outputs" / "passive_mix_composition_selection.json"


def nav_at_or_before(path: Path, cutoff: date) -> float:
    equity = pd.read_csv(path)
    dates = pd.to_datetime(equity["time"]).dt.date
    eligible = equity.loc[dates <= cutoff]
    if eligible.empty:
        raise ValueError(f"No equity observation on or before {cutoff}: {path}")
    return float(eligible["nav"].iloc[-1])


def main() -> None:
    _, panels, _, _ = blend.make_portfolios()
    common = panels["close"].dropna(subset=["NIFTYBEES", "GOLDBEES"]).index
    end = common[-1].date()
    assert any(ts.date() == START for ts in common) and TRAIN_END < end
    rows = []

    for nifty_pct in NIFTY_SHARES:
        weights = {"NIFTYBEES": nifty_pct / 100, "GOLDBEES": (100 - nifty_pct) / 100}
        name = f"passive_45pct_nifty_{nifty_pct:03d}_gold_{100-nifty_pct:03d}"
        targets, events = benchmark._passive_targets(panels, weights)
        train = benchmark._run(
            f"{name}_train_2015_2019", targets, events, panels, TRAIN_END,
            start=START, run_dir=RUNS / "train_2015_2019",
            cash_distributions=benchmark.NIFTYBEES_DISTRIBUTIONS,
            exposure_cap=INITIAL_EXPOSURE,
        )
        continuous = benchmark._run(
            f"{name}_continuous_2015_plus", targets, events, panels, end,
            start=START, run_dir=RUNS / "continuous_2015_plus",
            cash_distributions=benchmark.NIFTYBEES_DISTRIBUTIONS,
            exposure_cap=INITIAL_EXPOSURE,
        )
        full_equity = RUNS / "continuous_2015_plus" / f"{name}_continuous_2015_plus" / "equity.csv"
        train_nav = nav_at_or_before(full_equity, TRAIN_END)
        for period, result in (("train_2015_2019", train), ("continuous_2015_plus", continuous)):
            row = {
                **result,
                "period": period,
                "initial_exposure_pct": INITIAL_EXPOSURE * 100,
                "nifty_share_of_risky_sleeve_pct": nifty_pct,
                "gold_share_of_risky_sleeve_pct": 100 - nifty_pct,
                "nifty_initial_capital_pct": INITIAL_EXPOSURE * nifty_pct,
                "gold_initial_capital_pct": INITIAL_EXPOSURE * (100 - nifty_pct),
                "post_2019_return_on_carried_nav_pct": (continuous["ending_balance_inr"] / train_nav - 1) * 100 if period == "continuous_2015_plus" else "",
                "training_selected": False,
            }
            rows.append(row)

    eligible = [row for row in rows if row["period"] == "train_2015_2019" and row["within_20pct_ohlc"]]
    if not eligible:
        raise AssertionError("No passive NIFTY/Gold composition passed the training OHLC screen")
    selected = max(eligible, key=lambda row: (
        float(row["total_return_pct"]), float(row["ohlc_drawdown_bound_pct"]),
        -float(row["initial_exposure_pct"]), -abs(float(row["nifty_share_of_risky_sleeve_pct"]) - 50),
    ))
    for row in rows:
        row["training_selected"] = row["strategy"].startswith(selected["strategy"].removesuffix("_train_2015_2019"))
    assert len(rows) == len(NIFTY_SHARES) * 2
    assert len({(row["period"], row["strategy"]) for row in rows}) == len(rows)

    baseline = next(
        row for row in stock.read_csv(ROOT / "outputs" / "passive_mix_exposure_sensitivity.csv")
        if row["period"] == "continuous_2015_plus" and float(row["tested_initial_exposure_pct"]) == 45
    )
    half = next(row for row in rows if row["period"] == "continuous_2015_plus" and row["nifty_share_of_risky_sleeve_pct"] == 50)
    for key in ("ending_balance_inr", "total_return_pct", "close_mdd_pct", "ohlc_drawdown_bound_pct", "total_fees_inr", "total_slippage_inr", "order_count"):
        assert np.isclose(float(half[key]), float(baseline[key]), rtol=0, atol=0.03), (key, half[key], baseline[key])

    result = pd.DataFrame(rows)
    result.to_csv(RESULTS, index=False)
    full_rows = [row for row in rows if row["period"] == "continuous_2015_plus"]
    full_pass = [row for row in full_rows if row["within_20pct_ohlc"]]
    full_leader = max(full_pass, key=lambda row: float(row["total_return_pct"])) if full_pass else None
    chosen_full = next(row for row in full_rows if row["strategy"].startswith(selected["strategy"].removesuffix("_train_2015_2019")))
    selection = {
        "initial_exposure_pct": INITIAL_EXPOSURE * 100,
        "slippage_bps_per_side": SLIPPAGE_BPS,
        "training_selection_rule": "Highest net return on 2015-2019 among the 11 fixed-total-exposure NIFTY/Gold ratios passing the -20% conservative OHLC screen; ties prefer more headroom, then proximity to equal sleeves.",
        "training_selected_ratio": {
            "nifty_share_pct": selected["nifty_share_of_risky_sleeve_pct"],
            "gold_share_pct": selected["gold_share_of_risky_sleeve_pct"],
            "training_row": selected,
            "continuous_2015_plus_row": chosen_full,
        },
        "highest_full_history_return_passing_20pct": full_leader,
        "full_history_frontier_is_post_hoc": True,
        "all_dates_previously_inspected": True,
        "interpretation": "The continuous and post-2019 slices are retrospective; they are not independent validation.",
    }
    SELECTION.write_text(json.dumps(selection, indent=2), encoding="utf-8")

    summary_path = ROOT / "outputs" / "backtest_summary.csv"
    ledger = stock.read_csv(summary_path)
    fields = list(ledger[0])
    sim_type = "passive_nifty_gold_composition_sensitivity"
    ledger = [item for item in ledger if item["simulation_type"] != sim_type]
    for row in rows:
        record = {field: "" for field in fields}
        record.update({
            "simulation_type": sim_type, "strategy": row["strategy"],
            "universe": "NIFTYBEES + GOLDBEES",
            "period": row["period"], "period_start": row["period_start"], "period_end": row["period_end"],
            "starting_balance_inr": row["starting_balance_inr"], "ending_balance_inr": row["ending_balance_inr"],
            "total_return_pct": row["total_return_pct"], "cagr_pct": row["cagr_pct"],
            "max_drawdown_pct": row["close_mdd_pct"], "gross_exposure_cap_pct": row["initial_exposure_pct"],
            "slippage_bps_per_side": SLIPPAGE_BPS, "fees_inr": row["total_fees_inr"],
            "slippage_cost_inr": row["total_slippage_inr"], "order_count": row["order_count"],
            "within_20pct": row["within_20pct_ohlc"],
            "selection_or_sizing": f"Initial 45% gross allocation; NIFTY {row['nifty_share_of_risky_sleeve_pct']:.0f}% / Gold {row['gold_share_of_risky_sleeve_pct']:.0f}% within sleeve; no rebalancing",
            "source_artifact": "outputs/passive_mix_composition_sensitivity.csv;outputs/passive_mix_composition_selection.json;outputs/passive_mix_composition_method.md;work/sensitivity_passive_mix_composition.py",
            "notes": f"OHLC envelope {row['ohlc_drawdown_bound_pct']:.4f}%; known NIFTYBEES distributions credited, Gold distributions incomplete; 50 bps/side; all dates inspected.",
        })
        ledger.append(record)
    stock.atomic_csv(summary_path, ledger, fields)

    manifest_path = ROOT / "outputs" / "data_manifest.csv"
    manifest = stock.read_csv(manifest_path)
    manifest_fields = list(manifest[0])
    dataset = "Passive NIFTY/Gold initial composition sensitivity"
    manifest = [item for item in manifest if item["dataset"] != dataset]
    manifest.append({
        "dataset": dataset, "ticker": "NIFTYBEES; GOLDBEES",
        "instrument_key": "NSE_EQ|INF204KB14I2; NSE_EQ|INF204KB17I5",
        "bar_interval": "daily candles; single initial purchase",
        "first_bar": START.isoformat(), "last_bar": end.isoformat(), "bar_count": str(len(common)),
        "file_count": "11 compositions x training and continuous replays", "empty_files": "0",
        "cache_paths": "work/sensitivity_passive_mix_composition.py;outputs/passive_mix_composition_sensitivity.csv;outputs/passive_mix_composition_selection.json;outputs/passive_mix_composition_method.md;work/backtests/passive_mix_composition/",
        "purpose": "Select NIFTY/Gold passive initial composition under the 20% historical OHLC drawdown screen at fixed 45% initial gross exposure",
        "notes": "50 bps/side; current modeled fees; known NIFTYBEES distributions credited; GOLDBEES distributions not verified; no rebalancing; all dates inspected.",
    })
    for item in manifest:
        if item["dataset"] == "Consolidated backtest metric ledger":
            item["bar_count"] = str(len(ledger))
            phrase = "Twenty-two passive NIFTY/Gold composition training/continuous rows added."
            if phrase not in item["notes"]:
                item["notes"] = item["notes"].rstrip() + " " + phrase
    stock.atomic_csv(manifest_path, manifest, manifest_fields)

    print(json.dumps({
        "ratio_cases": len(NIFTY_SHARES), "period_rows": len(rows),
        "training_selected_nifty_share_pct": selected["nifty_share_of_risky_sleeve_pct"],
        "training_return_pct": selected["total_return_pct"],
        "training_ohlc_bound_pct": selected["ohlc_drawdown_bound_pct"],
        "selected_continuous_return_pct": chosen_full["total_return_pct"],
        "selected_post_2019_return_pct": chosen_full["post_2019_return_on_carried_nav_pct"],
        "selected_continuous_ohlc_bound_pct": chosen_full["ohlc_drawdown_bound_pct"],
        "full_window_best_passing_nifty_share_pct": full_leader["nifty_share_of_risky_sleeve_pct"] if full_leader else None,
        "baseline_45pct_equal_mix_reconciled": True,
    }, indent=2))


if __name__ == "__main__":
    main()
