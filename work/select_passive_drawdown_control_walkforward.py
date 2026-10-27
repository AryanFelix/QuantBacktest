"""Select among the frozen passive drawdown triggers on training data only."""

from __future__ import annotations

import csv
import json
import os
import tempfile
from datetime import date
from pathlib import Path

import pandas as pd

import audit_etf_intraday_drawdown as audit
import backtest_passive_mix_drawdown_control as control
import replay_volatility_weighted_blend as blend


ROOT = Path(__file__).resolve().parents[1]
RUNS = ROOT / "work" / "backtests" / "passive_drawdown_control_walkforward"
RESULTS = ROOT / "outputs" / "passive_drawdown_control_walkforward.csv"
SELECTION = ROOT / "outputs" / "passive_drawdown_control_walkforward_selection.json"
SUMMARY = ROOT / "outputs" / "backtest_summary.csv"
MANIFEST = ROOT / "outputs" / "data_manifest.csv"
CAPITAL = 1_000_000.0
TRIGGERS = (8.0, 10.0, 12.0)
TRAIN_COST = 50.0
TEST_COST_STRESS = (10.0, 100.0)
PERIODS = (
    ("training", date(2015, 1, 2), date(2019, 12, 31)),
    ("validation", date(2020, 1, 1), date(2022, 12, 30)),
    ("pseudo_holdout", date(2023, 1, 1), date(2026, 10, 23)),
)
SIMULATION_TYPE = "passive_drawdown_control_walkforward"


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


def run_case(panels, period: str, start: date, end: date, name: str, exposure: float,
             trigger: float | None, slippage: float, role: str) -> dict:
    equity, orders, stats = control.simulate(
        panels, name, exposure, trigger, slippage, start=start, end=end,
    )
    run = RUNS / f"{period}_{name}_{int(slippage)}bps"
    run.mkdir(parents=True, exist_ok=True)
    equity.to_csv(run / "equity.csv", index_label="time")
    orders.to_csv(run / "orders.csv", index=False)
    risk = audit.run_case(
        f"{period}; {name}; {slippage:g} bps/side",
        run.relative_to(ROOT).as_posix(),
        starting_balance=CAPITAL,
        slippage_bps=slippage,
    )
    return {
        **stats,
        "period": period,
        "period_start": start.isoformat(),
        "period_end": end.isoformat(),
        "role": role,
        "trigger_pct": trigger if trigger is not None else "",
        "ohlc_drawdown_bound_pct": risk["simultaneous_ohlc_drawdown_bound_pct"],
        "within_20pct_ohlc": risk["within_20pct_under_bound"],
        "max_close_replay_error_inr": risk["max_close_replay_error_inr"],
        "run_artifact": run.relative_to(ROOT).as_posix(),
    }


def update_summary(rows: list[dict]) -> None:
    summary = [row for row in read_csv(SUMMARY) if row["simulation_type"] != SIMULATION_TYPE]
    fields = list(summary[0])
    for result in rows:
        summary.append({field: {
            "simulation_type": SIMULATION_TYPE,
            "strategy": result["strategy"],
            "universe": "NIFTYBEES; GOLDBEES",
            "period": result["period"],
            "period_start": result["period_start"],
            "period_end": result["period_end"],
            "starting_balance_inr": result["starting_balance_inr"],
            "ending_balance_inr": result["ending_balance_inr"],
            "total_return_pct": result["total_return_pct"],
            "cagr_pct": result["cagr_pct"],
            "max_drawdown_pct": result["max_drawdown_pct"],
            "gross_exposure_cap_pct": result["initial_exposure_pct"],
            "slippage_bps_per_side": result["slippage_bps_per_side"],
            "fees_inr": result["total_fees_inr"],
            "slippage_cost_inr": result["total_slippage_inr"],
            "order_count": result["order_count"],
            "within_20pct": result["within_20pct_ohlc"],
            "selection_or_sizing": (
                f"60% start, cut to 30% at {result['trigger_pct']}% drawdown; role={result['role']}"
                if result["trigger_pct"] != ""
                else f"{result['initial_exposure_pct']:.0f}% fixed exposure; role={result['role']}"
            ),
            "source_artifact": "outputs/passive_drawdown_control_walkforward.csv",
            "notes": (
                f"OHLC bound {result['ohlc_drawdown_bound_pct']:.3f}%; independent segment start; "
                "GoldBeES distributions incomplete; later windows previously inspected."
            ),
        }.get(field, "") for field in fields})
    write_csv(SUMMARY, summary, fields)


def update_manifest() -> None:
    manifest = read_csv(MANIFEST)
    fields = list(manifest[0])
    dataset = "Passive NIFTY/Gold drawdown trigger walk-forward"
    manifest = [row for row in manifest if row["dataset"] != dataset]
    manifest.append({
        "dataset": dataset,
        "ticker": "NIFTYBEES; GOLDBEES",
        "instrument_key": "NSE_EQ|INF204KB14I2; NSE_EQ|INF204KB17I5",
        "bar_interval": "daily closes; next-open fills",
        "first_bar": "2015-01-02",
        "last_bar": "2026-10-23",
        "bar_count": "3 trigger candidates; 3 periods; 50-bps primary plus selected-rule 10/100-bps stresses",
        "file_count": "CSV + selection JSON + method + runner + equity/order ledgers",
        "empty_files": 0,
        "cache_paths": "outputs/passive_drawdown_control_walkforward.csv;outputs/passive_drawdown_control_walkforward_selection.json;outputs/passive_drawdown_control_walkforward_method.md;work/select_passive_drawdown_control_walkforward.py;work/backtests/passive_drawdown_control_walkforward/",
        "purpose": "Select the existing 8/10/12% passive drawdown trigger on 2015-2019 and freeze it on later periods",
        "notes": "Current modeled delivery fees, known NIFTYBEES distributions, 0% cash yield, and modeled slippage; 2020+ is not an untouched lockbox.",
    })
    write_csv(MANIFEST, manifest, fields)


def main() -> None:
    control._self_check()
    _, panels, _, _ = blend.make_portfolios()
    common = panels["close"].dropna(subset=["NIFTYBEES", "GOLDBEES"]).index
    assert common[0].date() <= PERIODS[0][1] and common[-1].date() == PERIODS[-1][2]
    RUNS.mkdir(parents=True, exist_ok=True)

    rows = []
    training = []
    for period, start, end in PERIODS:
        for trigger in TRIGGERS:
            row = run_case(
                panels, period, start, end,
                f"dd_{int(trigger)}pct_cut_60_to_30_recover_{int(trigger / 2)}pct",
                0.60, trigger, TRAIN_COST,
                "training_candidate" if period == "training" else "fixed_candidate_comparison",
            )
            rows.append(row)
            if period == "training":
                training.append(row)
        for exposure in (0.45, 0.60):
            rows.append(run_case(
                panels, period, start, end, f"fixed_{int(exposure * 100)}pct",
                exposure, None, TRAIN_COST, "passive_reference",
            ))

    eligible = [row for row in training if row["ohlc_drawdown_bound_pct"] >= -20.0]
    chosen = max(eligible, key=lambda row: (row["total_return_pct"], -float(row["trigger_pct"]))) if eligible else None
    selected_trigger = float(chosen["trigger_pct"]) if chosen else None
    if chosen:
        for period, start, end in PERIODS[1:]:
            name = f"dd_{int(selected_trigger)}pct_cut_60_to_30_recover_{int(selected_trigger / 2)}pct"
            for slippage in TEST_COST_STRESS:
                rows.append(run_case(
                    panels, period, start, end, name, 0.60, selected_trigger, slippage,
                    "selected_rule_cost_stress",
                ))
    assert len(rows) == (len(PERIODS) * (len(TRIGGERS) + 2) + (len(PERIODS) - 1) * len(TEST_COST_STRESS) if chosen else len(PERIODS) * (len(TRIGGERS) + 2))
    assert all(row["max_close_replay_error_inr"] <= 0.03 for row in rows)
    assert len({(row["period"], row["strategy"], row["slippage_bps_per_side"]) for row in rows}) == len(rows)

    RESULTS.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(RESULTS, index=False)
    selection = {
        "capital_inr": CAPITAL,
        "selection_cost_bps_per_side": TRAIN_COST,
        "training_period": [PERIODS[0][1].isoformat(), PERIODS[0][2].isoformat()],
        "validation_period": [PERIODS[1][1].isoformat(), PERIODS[1][2].isoformat()],
        "pseudo_holdout_period": [PERIODS[2][1].isoformat(), PERIODS[2][2].isoformat()],
        "candidate_triggers_pct": list(TRIGGERS),
        "risk_limit_ohlc_pct": -20.0,
        "selection_rule": "Highest training net return among 8/10/12% triggers passing -20% OHLC bound; ties prefer lower trigger.",
        "selected_trigger_pct": selected_trigger,
        "selected_training_case": chosen,
        "training_candidates": training,
        "later_periods_previously_inspected": True,
        "result_csv": "outputs/passive_drawdown_control_walkforward.csv",
    }
    SELECTION.write_text(json.dumps(selection, indent=2), encoding="utf-8")
    update_summary(rows)
    update_manifest()
    print(f"Selected {selected_trigger}% trigger on training at 50 bps; wrote {len(rows)} period/cost cases.")


if __name__ == "__main__":
    main()
