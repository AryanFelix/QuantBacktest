"""Stress exact stock/ETF sleeve allocations under adverse per-side slippage."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "work"))

import sensitivity_stock_nifty_gold_sleeve_split as base

COSTS = (10, 50, 100, 200)
RESULTS = ROOT / "outputs" / "stock_nifty_gold_sleeve_split_cost.csv"
SELECTION = ROOT / "outputs" / "stock_nifty_gold_sleeve_split_cost_selection.json"


def main() -> None:
    context = base.load_context()
    all_rows = []
    selections = {}
    baseline = base.stock.read_csv(ROOT / "outputs" / "stock_nifty_gold_blend.csv")
    baseline = next(row for row in baseline if row["period"] == "full_2021_2026")

    for cost in COSTS:
        runs = [base.run_weight(weight, context, cost) for weight in base.WEIGHTS]
        rows = [row for run in runs for row in run["rows"]]
        training = [row for row in rows if row["period"] == "train_2021_2023" and row["within_20pct_ohlc"]]
        if not training:
            selections[str(cost)] = {"selected_stock_pct": None, "reason": "No tested weight passed the training OHLC screen."}
            for row in rows:
                row["selected_on_training_only"] = False
                all_rows.append(row)
            continue
        selected = max(training, key=lambda row: (
            float(row["total_return_pct"]), float(row["ohlc_drawdown_bound_pct"]),
            -abs(float(row["stock_initial_capital_pct"]) - 50),
        ))
        selected_pct = float(selected["stock_initial_capital_pct"])
        for row in rows:
            row["selected_on_training_only"] = row["stock_initial_capital_pct"] == selected_pct
            row["selection_rule"] = "Highest net 2021-2023 return among exact 10-point splits passing the -20% combined OHLC bound at this slippage; ties prefer more drawdown headroom, then proximity to 50/50."
            all_rows.append(row)
        chosen_run = next(run for run in runs if run["stock_weight"] * 100 == selected_pct)
        selections[str(cost)] = {
            "selected_stock_pct": selected_pct,
            "selected_etf_pct": 100 - selected_pct,
            "training": selected,
            "validation_2024": next(row for row in chosen_run["rows"] if row["period"] == "validation_2024"),
            "holdout_2025_plus": next(row for row in chosen_run["rows"] if row["period"] == "holdout_2025_plus"),
            "full_2021_2026": next(row for row in chosen_run["rows"] if row["period"] == "full_2021_2026"),
        }
        if cost == 50:
            half = next(row for row in rows if row["stock_initial_capital_pct"] == 50 and row["period"] == "full_2021_2026")
            for row_key in ("ending_balance_inr", "total_return_pct", "ohlc_drawdown_bound_pct", "fees_inr", "slippage_cost_inr", "order_count"):
                assert np.isclose(float(half[row_key]), float(baseline[row_key]), rtol=0, atol=1e-6), (row_key, half[row_key], baseline[row_key])

    pd.DataFrame(all_rows).to_csv(RESULTS, index=False)
    selection = {
        "costs_bps_per_side": list(COSTS),
        "selection_rule": "At each cost, select the highest-return 2021-2023 exact split passing the -20% training OHLC bound; the stock/ETF rule itself is unchanged.",
        "all_dates_previously_inspected": True,
        "selections_by_cost": selections,
        "baseline_50bps_reconciled": True,
        "interpretation": "Cost stress is retrospective and cannot establish a live spread or a validated winner.",
    }
    SELECTION.write_text(json.dumps(selection, indent=2), encoding="utf-8")

    summary_path = ROOT / "outputs" / "backtest_summary.csv"
    ledger = base.stock.read_csv(summary_path)
    fields = list(ledger[0])
    ledger = [row for row in ledger if row["simulation_type"] != "stock_nifty_gold_split_cost_sensitivity"]
    for row in all_rows:
        record = {field: "" for field in fields}
        record.update({
            "simulation_type": "stock_nifty_gold_split_cost_sensitivity",
            "strategy": f"Stock/ETF exact split at {row['slippage_bps_per_side']} bps",
            "universe": "Restored-provisional NIFTY 50 stocks; NIFTYBEES; GOLDBEES",
            "period": row["period"], "period_start": row["period_start"], "period_end": row["period_end"],
            "starting_balance_inr": row["starting_balance_inr"], "ending_balance_inr": row["ending_balance_inr"],
            "total_return_pct": row["total_return_pct"], "cagr_pct": row["cagr_pct"],
            "max_drawdown_pct": row["close_max_drawdown_pct"],
            "gross_exposure_cap_pct": row["initial_gross_target_pct"],
            "slippage_bps_per_side": row["slippage_bps_per_side"],
            "fees_inr": row["fees_inr"], "slippage_cost_inr": row["slippage_cost_inr"],
            "order_count": row["order_count"], "within_20pct": row["within_20pct_ohlc"],
            "selection_or_sizing": f"Exact {row['stock_initial_capital_pct']:.0f}% stock / {row['etf_initial_capital_pct']:.0f}% ETF initial capital; selected on training only={row['selected_on_training_only']}",
            "source_artifact": "outputs/stock_nifty_gold_sleeve_split_cost.csv;outputs/stock_nifty_gold_sleeve_split_cost_selection.json;outputs/stock_nifty_gold_sleeve_split_cost_method.md;work/sensitivity_stock_nifty_gold_split_cost.py",
            "notes": f"Combined OHLC bound {row['ohlc_drawdown_bound_pct']:.4f}%; {row['slippage_bps_per_side']} bps/side; current modeled fees; 0% cash yield. All dates inspected; cost sensitivity, not a validated allocation.",
        })
        ledger.append(record)
    base.stock.atomic_csv(summary_path, ledger, fields)

    manifest_path = ROOT / "outputs" / "data_manifest.csv"
    manifest = base.stock.read_csv(manifest_path)
    manifest_fields = list(manifest[0])
    dataset = "Stock + NIFTY/Gold exact split execution-cost sensitivity"
    manifest = [row for row in manifest if row["dataset"] != dataset]
    manifest.append({
        "dataset": dataset, "ticker": "Restored-universe NIFTY 50 stocks; NIFTYBEES; GOLDBEES",
        "instrument_key": "", "bar_interval": "daily marks; monthly and quarterly trades",
        "first_bar": base.START.date().isoformat(), "last_bar": base.END.date().isoformat(),
        "bar_count": "1420", "file_count": "44 exact allocations per cost x 4 slippage levels",
        "empty_files": "0",
        "cache_paths": "work/sensitivity_stock_nifty_gold_split_cost.py;outputs/stock_nifty_gold_sleeve_split_cost.csv;outputs/stock_nifty_gold_sleeve_split_cost_selection.json;outputs/stock_nifty_gold_sleeve_split_cost_method.md",
        "purpose": "Stress exact ₹10 lakh stock/ETF allocations under adverse execution costs and the 20% historical drawdown screen",
        "notes": "10/50/100/200 bps per side; cost levels are sensitivities, not observed spreads; all dates inspected.",
    })
    for row in manifest:
        if row["dataset"] == "Consolidated backtest metric ledger":
            row["bar_count"] = str(len(ledger))
            phrase = "One hundred seventy-six stock/NIFTY/Gold exact-split cost-stress rows added."
            if phrase not in row["notes"]:
                row["notes"] = row["notes"].rstrip() + " " + phrase
    base.stock.atomic_csv(manifest_path, manifest, manifest_fields)

    print(json.dumps({
        "slippage_bps_per_side": list(COSTS),
        "metric_rows": len(all_rows),
        "selected_stock_pct_by_cost": {cost: result.get("selected_stock_pct") for cost, result in selections.items()},
        "baseline_50bps_reconciled": True,
    }, indent=2))


if __name__ == "__main__":
    main()
