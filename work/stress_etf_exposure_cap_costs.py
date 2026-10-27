"""Freeze training-selected NIFTY/Gold exposure caps across slippage stresses."""

from __future__ import annotations

import csv
import json
import os
import tempfile
from pathlib import Path

import pandas as pd

import replay_volatility_weighted_blend as blend
from select_etf_exposure_cap_oos import (
    CAPITAL, CAPS, TEST_END, TEST_START, TRAIN_END, TRAIN_START,
    run_case, select_cap,
)


ROOT = Path(__file__).resolve().parents[1]
RUNS = ROOT / "work" / "backtests" / "etf_exposure_cap_cost_stress"
RESULTS = ROOT / "outputs" / "etf_exposure_cap_cost_stress.csv"
TRAINING_GRID = ROOT / "outputs" / "etf_exposure_cap_cost_stress_training_grid.csv"
SELECTION_REFERENCE = ROOT / "outputs" / "etf_exposure_cap_oos_selection.json"
SUMMARY = ROOT / "outputs" / "backtest_summary.csv"
MANIFEST = ROOT / "outputs" / "data_manifest.csv"
SLIPPAGE_LEVELS = (10, 50, 100, 200)
RISK_LIMITS = (20, 15)
SIMULATION_TYPE = "etf_exposure_cap_cost_stress"
RESULT_FIELDS = (
    "risk_limit_pct", "slippage_bps_per_side", "selected_cap_pct", "selection_status",
    "training_starting_balance_inr", "training_ending_balance_inr", "training_return_pct",
    "training_cagr_pct", "training_close_max_drawdown_pct", "training_ohlc_drawdown_bound_pct",
    "training_fees_inr", "training_slippage_inr", "training_order_count",
    "training_average_gross_exposure_pct", "holdout_starting_balance_inr", "holdout_ending_balance_inr",
    "holdout_return_pct", "holdout_cagr_pct", "holdout_close_max_drawdown_pct",
    "holdout_ohlc_drawdown_bound_pct", "holdout_headroom_to_20pct_pp", "holdout_fees_inr",
    "holdout_slippage_inr", "holdout_order_count", "holdout_average_gross_exposure_pct",
    "holdout_max_close_replay_error_inr", "training_artifact", "holdout_artifact",
)


def write_csv(path: Path, rows: list[dict], fields: list[str]) -> None:
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", newline="", delete=False, dir=path.parent, suffix=".tmp") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
        temporary = Path(handle.name)
    os.replace(temporary, path)


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def selected_row(stress: int, risk_limit: int, cap: int, training: dict, holdout: dict) -> dict:
    return {
        "risk_limit_pct": risk_limit,
        "slippage_bps_per_side": stress,
        "selected_cap_pct": cap,
        "selection_status": "selected",
        "training_starting_balance_inr": training["starting_balance_inr"],
        "training_ending_balance_inr": training["ending_balance_inr"],
        "training_return_pct": training["total_return_pct"],
        "training_cagr_pct": training["cagr_pct"],
        "training_close_max_drawdown_pct": training["close_max_drawdown_pct"],
        "training_ohlc_drawdown_bound_pct": training["simultaneous_ohlc_drawdown_bound_pct"],
        "training_fees_inr": training["total_fees_inr"],
        "training_slippage_inr": training["total_slippage_inr"],
        "training_order_count": training["order_count"],
        "training_average_gross_exposure_pct": training["average_gross_exposure_pct"],
        "holdout_starting_balance_inr": holdout["starting_balance_inr"],
        "holdout_ending_balance_inr": holdout["ending_balance_inr"],
        "holdout_return_pct": holdout["total_return_pct"],
        "holdout_cagr_pct": holdout["cagr_pct"],
        "holdout_close_max_drawdown_pct": holdout["close_max_drawdown_pct"],
        "holdout_ohlc_drawdown_bound_pct": holdout["simultaneous_ohlc_drawdown_bound_pct"],
        "holdout_headroom_to_20pct_pp": holdout["headroom_to_20pct_bound_pp"],
        "holdout_fees_inr": holdout["total_fees_inr"],
        "holdout_slippage_inr": holdout["total_slippage_inr"],
        "holdout_order_count": holdout["order_count"],
        "holdout_average_gross_exposure_pct": holdout["average_gross_exposure_pct"],
        "holdout_max_close_replay_error_inr": holdout["max_close_replay_error_inr"],
        "training_artifact": training["run_artifact"],
        "holdout_artifact": holdout["run_artifact"],
    }


def update_backtest_summary(results: list[dict]) -> None:
    rows = [row for row in read_csv(SUMMARY) if row["simulation_type"] != SIMULATION_TYPE]
    fields = list(rows[0])
    for result in results:
        if result["selection_status"] != "selected":
            continue
        for segment in ("training", "holdout"):
            prefix = "training_" if segment == "training" else "holdout_"
            summary = {
                "simulation_type": SIMULATION_TYPE,
                "strategy": "Quarterly 50/50 NIFTYBEES Donchian 55/20 + GOLDBEES SMA200",
                "universe": "NIFTYBEES; GOLDBEES",
                "period": f"{segment}_risk{result['risk_limit_pct']}",
                "period_start": TRAIN_START.isoformat() if segment == "training" else TEST_START.isoformat(),
                "period_end": TRAIN_END.isoformat() if segment == "training" else TEST_END.isoformat(),
                "starting_balance_inr": CAPITAL,
                "ending_balance_inr": result[f"{prefix}ending_balance_inr"],
                "total_return_pct": result[f"{prefix}return_pct"],
                "cagr_pct": result[f"{prefix}cagr_pct"],
                "max_drawdown_pct": result[f"{prefix}ohlc_drawdown_bound_pct"],
                "gross_exposure_cap_pct": result["selected_cap_pct"],
                "slippage_bps_per_side": result["slippage_bps_per_side"],
                "fees_inr": result[f"{prefix}fees_inr"],
                "slippage_cost_inr": result[f"{prefix}slippage_inr"],
                "order_count": result[f"{prefix}order_count"],
                "within_20pct": result[f"{prefix}ohlc_drawdown_bound_pct"] >= -20,
                "selection_or_sizing": f"Cap selected on training OHLC screen <= -{result['risk_limit_pct']}%; per-side slippage stress",
                "source_artifact": "outputs/etf_exposure_cap_cost_stress.csv",
                "notes": "2023+ is pseudo-OOS; price-only GOLDBEES history has incomplete distribution coverage.",
            }
            rows.append({field: summary.get(field, "") for field in fields})
    write_csv(SUMMARY, rows, fields)


def update_manifest() -> None:
    rows = read_csv(MANIFEST)
    fields = list(rows[0])
    dataset = "NIFTY/Gold exposure-cap transaction-cost stress"
    rows = [row for row in rows if row["dataset"] != dataset]
    rows.append({
        "dataset": dataset,
        "ticker": "NIFTYBEES; GOLDBEES",
        "instrument_key": "NSE_EQ|INF204KB14I2; NSE_EQ|INF204KB17I5",
        "bar_interval": "daily OHLC; quarterly target rebalance",
        "first_bar": TRAIN_START.isoformat(),
        "last_bar": TEST_END.isoformat(),
        "bar_count": "64 training cap cases + frozen selections at 4 slippage levels",
        "file_count": "2 cost stress CSVs, equity/order ledgers, method, runner",
        "empty_files": 0,
        "cache_paths": "outputs/etf_exposure_cap_cost_stress.csv;outputs/etf_exposure_cap_cost_stress_training_grid.csv;outputs/etf_exposure_cap_cost_stress_method.md;work/stress_etf_exposure_cap_costs.py;work/audit_etf_intraday_drawdown.py;work/backtests/etf_exposure_cap_cost_stress/",
        "purpose": "Retest training-selected gross exposure caps at 10/50/100/200 bps per-side slippage and freeze each choice on 2023+",
        "notes": "Modeled current delivery fees plus slippage; GoldBeES distributions, tax, cash yield, market impact, and future drawdown remain unresolved.",
    })
    write_csv(MANIFEST, rows, fields)


def main() -> None:
    _, panels, portfolios, event_sets = blend.make_portfolios()
    assert panels["close"].index.is_unique
    targets = portfolios["fixed_50_50_quarterly"]
    events = event_sets["fixed_50_50_quarterly"]
    RUNS.mkdir(parents=True, exist_ok=True)

    grid_rows = []
    selection_rows = []
    by_cost_cap: dict[tuple[int, int], dict] = {}
    for slippage in SLIPPAGE_LEVELS:
        training = [
            run_case(
                panels, targets, events, "training", cap, TRAIN_START, TRAIN_END,
                slippage_bps=slippage, run_root=RUNS / f"{slippage}bps",
            )
            for cap in CAPS
        ]
        grid = pd.DataFrame(training)
        chosen = {
            limit: select_cap(grid, limit)
            if grid["simultaneous_ohlc_drawdown_bound_pct"].ge(-limit).any()
            else None
            for limit in RISK_LIMITS
        }
        for row in training:
            row = dict(row)
            row["selected_at_20pct"] = chosen[20] is not None and row["gross_exposure_cap_pct"] == chosen[20]
            row["selected_at_15pct"] = chosen[15] is not None and row["gross_exposure_cap_pct"] == chosen[15]
            grid_rows.append(row)
        print(f"{slippage} bps/side: selected caps at 20%/15% screens = {chosen[20]}/{chosen[15]}", flush=True)
        for cap in {value for value in chosen.values() if value is not None}:
            by_cost_cap[(slippage, cap)] = run_case(
                panels, targets, events, "holdout", cap, TEST_START, TEST_END,
                slippage_bps=slippage, run_root=RUNS / f"{slippage}bps",
            )
        for limit, cap in chosen.items():
            if cap is None:
                result = dict.fromkeys(RESULT_FIELDS, "")
                result.update({
                    "risk_limit_pct": limit,
                    "slippage_bps_per_side": slippage,
                    "selection_status": "no_training_candidate_passed",
                })
                selection_rows.append(result)
                continue
            train_row = next(row for row in training if row["gross_exposure_cap_pct"] == cap)
            test_row = by_cost_cap[(slippage, cap)]
            selection_rows.append(selected_row(slippage, limit, cap, train_row, test_row))

    reference = json.loads(SELECTION_REFERENCE.read_text(encoding="utf-8"))
    base20 = next(row for row in selection_rows if row["slippage_bps_per_side"] == 50 and row["risk_limit_pct"] == 20)
    base15 = next(row for row in selection_rows if row["slippage_bps_per_side"] == 50 and row["risk_limit_pct"] == 15)
    assert base20["selected_cap_pct"] == reference["selected_cap_at_20pct_limit"] == 70
    assert base15["selected_cap_pct"] == reference["selected_cap_at_15pct_safety_buffer"] == 40
    assert abs(base20["holdout_return_pct"] - reference["selected_20pct_cap_holdout"]["total_return_pct"]) < 1e-7
    assert abs(base20["holdout_ohlc_drawdown_bound_pct"] - reference["selected_20pct_cap_holdout"]["simultaneous_ohlc_drawdown_bound_pct"]) < 1e-7
    assert abs(base15["holdout_return_pct"] - reference["selected_15pct_cap_holdout"]["total_return_pct"]) < 1e-7

    grid_fields = list(grid_rows[0])
    write_csv(TRAINING_GRID, grid_rows, grid_fields)
    write_csv(RESULTS, selection_rows, list(RESULT_FIELDS))
    update_backtest_summary(selection_rows)
    update_manifest()
    print(pd.DataFrame(selection_rows)[[
        "risk_limit_pct", "slippage_bps_per_side", "selected_cap_pct",
        "training_return_pct", "training_ohlc_drawdown_bound_pct",
        "holdout_return_pct", "holdout_ohlc_drawdown_bound_pct",
    ]].to_string(index=False))


if __name__ == "__main__":
    main()
