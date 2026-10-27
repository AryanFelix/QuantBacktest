"""Stress the fixed-45% passive NIFTY/Gold composition frontier across execution costs."""

from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "work"))

import backtest_stock_momentum as stock
import benchmark_nifty_gold_2020 as benchmark
import replay_volatility_weighted_blend as blend
import sensitivity_passive_mix_composition as composition

COSTS = (10, 50, 100, 200)
RUNS = ROOT / "work" / "backtests" / "passive_mix_composition_cost"
RESULTS = ROOT / "outputs" / "passive_mix_composition_cost_sensitivity.csv"
SELECTION = ROOT / "outputs" / "passive_mix_composition_cost_selection.json"
SIM_TYPE = "passive_nifty_gold_composition_cost_sensitivity"
METHOD = "outputs/passive_mix_composition_cost_method.md"


def main() -> None:
    _, panels, _, _ = blend.make_portfolios()
    common = panels["close"].dropna(subset=["NIFTYBEES", "GOLDBEES"]).index
    end = common[-1].date()
    assert any(ts.date() == composition.START for ts in common) and composition.TRAIN_END < end
    rows = []

    for slippage in COSTS:
        for nifty_pct in composition.NIFTY_SHARES:
            name = f"passive_45pct_nifty_{nifty_pct:03d}_gold_{100-nifty_pct:03d}"
            targets, events = benchmark._passive_targets(panels, {
                "NIFTYBEES": nifty_pct / 100,
                "GOLDBEES": (100 - nifty_pct) / 100,
            })
            for period, period_end in (("train_2015_2019", composition.TRAIN_END), ("continuous_2015_plus", end)):
                result = benchmark._run(
                    f"{name}_{period}_{slippage}bps", targets, events, panels, period_end,
                    start=composition.START, run_dir=RUNS / f"{slippage}bps" / period,
                    cash_distributions=benchmark.NIFTYBEES_DISTRIBUTIONS,
                    exposure_cap=composition.INITIAL_EXPOSURE, slippage_bps=slippage,
                )
                rows.append({
                    **result,
                    "period": period,
                    "initial_exposure_pct": composition.INITIAL_EXPOSURE * 100,
                    "nifty_share_of_risky_sleeve_pct": nifty_pct,
                    "gold_share_of_risky_sleeve_pct": 100 - nifty_pct,
                    "nifty_initial_capital_pct": composition.INITIAL_EXPOSURE * nifty_pct,
                    "gold_initial_capital_pct": composition.INITIAL_EXPOSURE * (100 - nifty_pct),
                    "training_selected": False,
                })

    selection_by_cost = {}
    for slippage in COSTS:
        training = [row for row in rows if row["period"] == "train_2015_2019" and row["slippage_bps_per_side"] == slippage]
        eligible = [row for row in training if row["within_20pct_ohlc"]]
        selected = max(eligible, key=lambda row: (
            row["total_return_pct"], row["ohlc_drawdown_bound_pct"],
            -abs(row["nifty_share_of_risky_sleeve_pct"] - 50),
        )) if eligible else None
        if selected:
            selected["training_selected"] = True
            continuous = next(
                row for row in rows
                if row["period"] == "continuous_2015_plus"
                and row["slippage_bps_per_side"] == slippage
                and row["nifty_share_of_risky_sleeve_pct"] == selected["nifty_share_of_risky_sleeve_pct"]
            )
            continuous["training_selected"] = True
        else:
            continuous = None
        full_pass = [
            row for row in rows
            if row["period"] == "continuous_2015_plus"
            and row["slippage_bps_per_side"] == slippage
            and row["within_20pct_ohlc"]
        ]
        frontier = max(full_pass, key=lambda row: row["total_return_pct"]) if full_pass else None
        selection_by_cost[str(slippage)] = {
            "training_selected_nifty_share_pct": selected["nifty_share_of_risky_sleeve_pct"] if selected else None,
            "training_row": selected,
            "continuous_selected_row": continuous,
            "highest_full_history_return_passing_20pct": frontier,
            "no_training_candidate_passes": selected is None,
        }

    assert len(rows) == len(COSTS) * len(composition.NIFTY_SHARES) * 2
    baseline = {
        (row["period"], float(row["nifty_share_of_risky_sleeve_pct"])): row
        for row in stock.read_csv(ROOT / "outputs" / "passive_mix_composition_sensitivity.csv")
    }
    for row in rows:
        if row["slippage_bps_per_side"] != 50:
            continue
        reference = baseline[(row["period"], float(row["nifty_share_of_risky_sleeve_pct"]))]
        for key in ("ending_balance_inr", "total_return_pct", "close_mdd_pct", "ohlc_drawdown_bound_pct", "total_fees_inr", "total_slippage_inr", "order_count"):
            assert abs(float(row[key]) - float(reference[key])) <= 0.03, (key, row[key], reference[key])

    pd.DataFrame(rows).to_csv(RESULTS, index=False)
    SELECTION.write_text(json.dumps({
        "initial_exposure_pct": composition.INITIAL_EXPOSURE * 100,
        "training_period": [composition.START.isoformat(), composition.TRAIN_END.isoformat()],
        "continuous_period_end": end.isoformat(),
        "tested_costs_bps_per_side": list(COSTS),
        "training_rule": "At each cost, select the highest net-return NIFTY/Gold composition passing the -20% training OHLC envelope; ties prefer more headroom and then proximity to equal sleeves.",
        "all_dates_previously_inspected": True,
        "selection_by_cost": selection_by_cost,
        "interpretation": "The continuous full-history frontier is post-hoc. Cost levels are sensitivities, not measured spreads; no allocation is independently validated.",
    }, indent=2), encoding="utf-8")

    ledger = stock.read_csv(ROOT / "outputs" / "backtest_summary.csv")
    fields = list(ledger[0])
    ledger = [row for row in ledger if row["simulation_type"] != SIM_TYPE]
    for row in rows:
        record = {field: "" for field in fields}
        record.update({
            "simulation_type": SIM_TYPE,
            "strategy": row["strategy"],
            "universe": "NIFTYBEES + GOLDBEES",
            "period": row["period"],
            "period_start": row["period_start"],
            "period_end": row["period_end"],
            "starting_balance_inr": row["starting_balance_inr"],
            "ending_balance_inr": row["ending_balance_inr"],
            "total_return_pct": row["total_return_pct"],
            "cagr_pct": row["cagr_pct"],
            "max_drawdown_pct": row["close_mdd_pct"],
            "gross_exposure_cap_pct": row["initial_exposure_pct"],
            "slippage_bps_per_side": row["slippage_bps_per_side"],
            "fees_inr": row["total_fees_inr"],
            "slippage_cost_inr": row["total_slippage_inr"],
            "order_count": row["order_count"],
            "within_20pct": row["within_20pct_ohlc"],
            "selection_or_sizing": f"Initial 45% gross allocation; NIFTY {row['nifty_share_of_risky_sleeve_pct']:.0f}% / Gold {row['gold_share_of_risky_sleeve_pct']:.0f}% within sleeve; no rebalancing",
            "source_artifact": f"outputs/passive_mix_composition_cost_sensitivity.csv;outputs/passive_mix_composition_cost_selection.json;{METHOD};work/sensitivity_passive_mix_composition_cost.py",
            "notes": f"OHLC envelope {row['ohlc_drawdown_bound_pct']:.4f}%; current modeled fees; {row['slippage_bps_per_side']} bps/side sensitivity; all dates inspected.",
        })
        ledger.append(record)
    stock.atomic_csv(ROOT / "outputs" / "backtest_summary.csv", ledger, fields)

    manifest_path = ROOT / "outputs" / "data_manifest.csv"
    manifest = stock.read_csv(manifest_path)
    manifest_fields = list(manifest[0])
    manifest = [row for row in manifest if row["dataset"] != "Passive NIFTY/Gold composition cost sensitivity"]
    manifest.append({
        "dataset": "Passive NIFTY/Gold composition cost sensitivity",
        "ticker": "NIFTYBEES; GOLDBEES",
        "instrument_key": "NSE_EQ|INF204KB14I2; NSE_EQ|INF204KB17I5",
        "bar_interval": "daily candles; single initial purchase; terminal liquidation",
        "first_bar": composition.START.isoformat(),
        "last_bar": end.isoformat(),
        "bar_count": f"{len(rows)} metric rows; {len(COSTS)} costs x {len(composition.NIFTY_SHARES)} ratios x 2 windows",
        "file_count": "88 exact-fee replays + CSV + selection JSON + method + runner",
        "empty_files": "0",
        "cache_paths": "work/sensitivity_passive_mix_composition_cost.py;outputs/passive_mix_composition_cost_sensitivity.csv;outputs/passive_mix_composition_cost_selection.json;outputs/passive_mix_composition_cost_method.md;work/backtests/passive_mix_composition_cost/",
        "purpose": "Stress the fixed-45%-initial passive NIFTY/Gold composition frontier under current modeled fees and 10/50/100/200 bps per-side slippage",
        "notes": "All eleven ratios are independently replayed at each cost with integer units and known NIFTYBEES payouts. The 50 bps runs reconcile to the base composition study within ₹0.03; all later periods are retrospective and assumed slippage is not a measured spread.",
    })
    for row in manifest:
        if row["dataset"] == "Consolidated backtest metric ledger":
            row["bar_count"] = str(len(ledger))
            phrase = "Eighty-eight passive NIFTY/Gold composition cost-stress rows added."
            if phrase not in row["notes"]:
                row["notes"] = row["notes"].rstrip() + " " + phrase
    stock.atomic_csv(manifest_path, manifest, manifest_fields)

    print(json.dumps({
        "rows": len(rows),
        "costs_bps_per_side": list(COSTS),
        "training_selected_ratios_by_cost": {
            cost: values["training_selected_nifty_share_pct"]
            for cost, values in selection_by_cost.items()
        },
        "fifty_bps_reconciled_to_base": True,
        "end_date": end.isoformat(),
    }, indent=2))


if __name__ == "__main__":
    main()
