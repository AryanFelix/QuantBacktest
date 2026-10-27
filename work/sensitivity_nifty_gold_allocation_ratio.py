"""Train-select NIFTY/Gold active-sleeve ratios under an OHLC drawdown screen."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pandas as pd

import audit_etf_intraday_drawdown as ohlc_audit
import replay_volatility_weighted_blend as blend
import upstox_quant as q


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "work" / "backtests" / "nifty_gold_allocation_ratio"
GRID = ROOT / "outputs" / "nifty_gold_allocation_ratio_sensitivity.csv"
TRAIN_RISK = ROOT / "outputs" / "nifty_gold_allocation_ratio_training_ohlc.csv"
OOS_RISK = ROOT / "outputs" / "nifty_gold_allocation_ratio_oos_ohlc.csv"
COSTS = ROOT / "outputs" / "nifty_gold_allocation_ratio_cost_sensitivity.csv"
SELECTION = ROOT / "outputs" / "nifty_gold_allocation_ratio_selection.json"
CAPITAL = 1_000_000
DD_LIMIT = 20.0
PRIMARY_SLIPPAGE = 50
RATIOS = tuple(i / 10 for i in range(11))
CAPS = (0.30, 0.40, 0.45, 0.50, 0.60, 0.70, 0.80, 0.90, 1.00)
SLIPPAGE = (10, 50, 100)
PERIODS = (
    ("train_2015_2019", date(2015, 1, 2), date(2019, 12, 31)),
    ("validation_2020_2022", date(2020, 1, 1), date(2022, 12, 30)),
    ("holdout_2023_plus", date(2023, 1, 1), date(2026, 10, 23)),
    ("test_2020_plus", date(2020, 1, 1), date(2026, 10, 23)),
    ("continuous_2015_plus", date(2015, 1, 2), date(2026, 10, 23)),
)
TEST_PERIODS = {"validation_2020_2022", "holdout_2023_plus", "test_2020_plus", "continuous_2015_plus"}
ohlc_audit.BARS = {name: ohlc_audit.BARS[name] for name in ("NIFTYBEES", "GOLDBEES")}


def _rule_id(frequency: str, nifty_share: float, cap: float) -> str:
    return f"{frequency}__nifty{int(round(nifty_share * 100)):03d}__cap{int(round(cap * 100)):03d}"


def _targets(active: pd.DataFrame, nifty_share: float) -> pd.DataFrame:
    target = pd.DataFrame(0.0, index=active.index, columns=active.columns)
    target["NIFTYBEES"] = active["NIFTYBEES"].gt(0).astype(float) * nifty_share
    target["GOLDBEES"] = active["GOLDBEES"].gt(0).astype(float) * (1.0 - nifty_share)
    assert (target >= 0).all().all() and (target.sum(axis=1) <= 1.0 + 1e-12).all()
    return target


def _measure(panels: dict, targets: pd.DataFrame, events: pd.Series, cap: float,
             start: date, end: date, slippage: int) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    equity, orders, stats = q._simulate(
        panels, targets, events, CAPITAL, cap, slippage,
        "equity_delivery", start, end, DD_LIMIT,
    )
    stats["total_slippage_inr"] = blend.modeled_slippage(orders, panels)
    return equity, orders, stats


def _save_run(run_id: str, equity: pd.DataFrame, orders: pd.DataFrame, summary: dict) -> str:
    run = OUT / run_id
    run.mkdir(parents=True, exist_ok=True)
    equity.reset_index(names="time").to_csv(run / "equity.csv", index=False)
    orders.to_csv(run / "orders.csv", index=False)
    (run / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return run.relative_to(ROOT).as_posix()


def _selection_key(row: dict) -> tuple:
    return (
        -float(row["total_return_pct"]),
        -float(row["simultaneous_ohlc_drawdown_bound_pct"]),
        float(row["gross_exposure_cap_pct"]),
        abs(float(row["nifty_share_pct"]) - 50.0),
        0 if row["rebalance_frequency"] == "quarterly" else 1,
    )


def main() -> None:
    q._self_check()
    _, panels, portfolios, portfolio_events = blend.make_portfolios()
    active = portfolios["fixed_50_50"].gt(0).astype(float)
    assert list(active.columns) == ["NIFTYBEES", "GOLDBEES"]
    assert active.index.equals(panels["close"].index)

    reference = portfolios["fixed_50_50"]
    equal_monthly = _targets(active, 0.50)
    assert equal_monthly.equals(reference)
    assert not portfolio_events["fixed_50_50"].equals(portfolio_events["fixed_50_50_quarterly"])
    reference_cap = 0.45

    records = []
    training_risk_rows = []
    trained_runs: dict[str, dict] = {}
    for frequency in ("monthly", "quarterly"):
        events = portfolio_events["fixed_50_50" if frequency == "monthly" else "fixed_50_50_quarterly"]
        for ratio in RATIOS:
            targets = _targets(active, ratio)
            for cap in CAPS:
                rule_id = _rule_id(frequency, ratio, cap)
                for period, start, end in PERIODS:
                    equity, orders, stats = _measure(panels, targets, events, cap, start, end, PRIMARY_SLIPPAGE)
                    risk = None
                    run_path = ""
                    if period == "train_2015_2019":
                        run_path = _save_run(
                            f"training/{rule_id}__{period}__{PRIMARY_SLIPPAGE}bps",
                            equity, orders, {"rule_id": rule_id, "period": period, "nifty_share_pct": ratio * 100,
                                            "gross_exposure_cap_pct": cap * 100, **stats},
                        )
                        risk = ohlc_audit.run_case(
                            rule_id, run_path, CAPITAL,
                        )
                        assert risk["max_close_replay_error_inr"] <= 0.03
                        training_risk_rows.append({
                            "rule_id": rule_id,
                            "rebalance_frequency": frequency,
                            "nifty_share_pct": ratio * 100,
                            "gold_share_pct": (1.0 - ratio) * 100,
                            "gross_exposure_cap_pct": cap * 100,
                            **risk,
                        })
                        trained_runs[rule_id] = {
                            "equity": equity, "orders": orders, "stats": stats,
                            "targets": targets, "events": events, "frequency": frequency,
                            "ratio": ratio, "cap": cap,
                        }
                    records.append({
                        "rule_id": rule_id,
                        "rebalance_frequency": frequency,
                        "nifty_share_pct": ratio * 100,
                        "gold_share_pct": (1.0 - ratio) * 100,
                        "gross_exposure_cap_pct": cap * 100,
                        "period": period,
                        "period_start": start.isoformat(),
                        "period_end": end.isoformat(),
                        "starting_balance_inr": stats["starting_balance_inr"],
                        "ending_balance_inr": stats["ending_balance_inr"],
                        "total_return_pct": stats["total_return_pct"],
                        "cagr_pct": stats["cagr_pct"],
                        "max_drawdown_pct": stats["max_drawdown_pct"],
                        "sharpe_zero_rf": stats["sharpe_zero_rf"],
                        "average_gross_exposure_pct": stats["average_gross_exposure_pct"],
                        "order_count": stats["order_count"],
                        "fees_inr": stats["total_fees_inr"],
                        "slippage_cost_inr": stats["total_slippage_inr"],
                        "slippage_bps_per_side": PRIMARY_SLIPPAGE,
                        "within_20pct_close": stats["within_drawdown_limit"],
                        "source_artifact": f"{run_path + '/summary.json;' if run_path else ''}outputs/nifty_gold_allocation_ratio_method.md;work/sensitivity_nifty_gold_allocation_ratio.py",
                    })

    grid = pd.DataFrame(records)
    training_risk = pd.DataFrame(training_risk_rows)
    assert len(grid) == len(RATIOS) * len(CAPS) * 2 * len(PERIODS) == 990
    assert len(training_risk) == len(RATIOS) * len(CAPS) * 2 == 198
    assert not grid.duplicated(["rule_id", "period"]).any()
    grid = grid.merge(training_risk[["rule_id", "simultaneous_ohlc_drawdown_bound_pct", "within_20pct_under_bound"]],
                      on="rule_id", how="left", validate="many_to_one")
    grid["training_ohlc_bound_pct"] = grid["simultaneous_ohlc_drawdown_bound_pct"]
    grid["training_pass_20pct_ohlc"] = grid["within_20pct_under_bound"]
    grid = grid.drop(columns=["simultaneous_ohlc_drawdown_bound_pct", "within_20pct_under_bound"])
    grid.to_csv(GRID, index=False)
    training_risk.to_csv(TRAIN_RISK, index=False)

    candidates = [
        {**row, **trained_runs[row["rule_id"]]["stats"]}
        for row in training_risk.to_dict(orient="records") if row["within_20pct_under_bound"]
    ]
    candidates.sort(key=_selection_key)
    selected = candidates[0] if candidates else None
    oos_risk_rows, oos_risk_entries = [], []
    cost_rows = []
    oos_metrics: dict[str, dict] = {}

    equal_rule = _rule_id("monthly", 0.50, reference_cap)
    evaluations = []
    if selected:
        evaluations.append(("train_selected", selected["rule_id"], trained_runs[selected["rule_id"]]))
    evaluations.append(("fixed_50_50_45pct_reference", equal_rule, {
        "targets": equal_monthly, "events": portfolio_events["fixed_50_50"],
        "frequency": "monthly", "ratio": 0.50, "cap": reference_cap,
    }))

    unique_evaluations = {}
    for role, rule_id, spec in evaluations:
        unique_evaluations.setdefault(rule_id, (role, spec))
    for rule_id, (role, spec) in unique_evaluations.items():
        for period, start, end in PERIODS:
            if period == "train_2015_2019":
                continue
            equity, orders, stats = _measure(panels, spec["targets"], spec["events"], spec["cap"],
                                             start, end, PRIMARY_SLIPPAGE)
            run_path = _save_run(f"{role}/{rule_id}__{period}__50bps", equity, orders,
                                 {"role": role, "rule_id": rule_id, "period": period, **stats})
            risk = ohlc_audit.run_case(rule_id, run_path, CAPITAL)
            assert risk["max_close_replay_error_inr"] <= 0.03
            oos_risk_rows.append({"role": role, "rule_id": rule_id, "period": period, **risk})
            oos_risk_entries.append({"role": role, "rule_id": rule_id, "period": period, "risk": risk})
            oos_metrics[f"{rule_id}|{period}"] = {
                "return_pct": stats["total_return_pct"],
                "close_mdd_pct": stats["max_drawdown_pct"],
                "ohlc_bound_pct": risk["simultaneous_ohlc_drawdown_bound_pct"],
                "within_20pct_ohlc": risk["within_20pct_under_bound"],
            }

        for period, start, end in PERIODS:
            if period not in {"test_2020_plus", "holdout_2023_plus", "continuous_2015_plus"}:
                continue
            for slip in SLIPPAGE:
                equity, orders, stats = _measure(panels, spec["targets"], spec["events"], spec["cap"],
                                                 start, end, slip)
                if slip == PRIMARY_SLIPPAGE:
                    assert abs(stats["total_return_pct"] - oos_metrics[f"{rule_id}|{period}"]["return_pct"]) < 1e-8
                cost_rows.append({
                    "role": role,
                    "rule_id": rule_id,
                    "rebalance_frequency": spec["frequency"],
                    "nifty_share_pct": spec["ratio"] * 100,
                    "gross_exposure_cap_pct": spec["cap"] * 100,
                    "period": period,
                    "period_start": start.isoformat(),
                    "period_end": end.isoformat(),
                    "slippage_bps_per_side": slip,
                    "total_return_pct": stats["total_return_pct"],
                    "max_drawdown_pct": stats["max_drawdown_pct"],
                    "fees_inr": stats["total_fees_inr"],
                    "slippage_cost_inr": stats["total_slippage_inr"],
                    "order_count": stats["order_count"],
                    "source_artifact": "outputs/nifty_gold_allocation_ratio_cost_sensitivity.csv;work/sensitivity_nifty_gold_allocation_ratio.py",
                })

    pd.DataFrame(oos_risk_rows).to_csv(OOS_RISK, index=False)
    pd.DataFrame(cost_rows).to_csv(COSTS, index=False)
    chosen = None if selected is None else {
        "rule_id": selected["rule_id"],
        "rebalance_frequency": selected["rebalance_frequency"],
        "nifty_share_pct": selected["nifty_share_pct"],
        "gold_share_pct": selected["gold_share_pct"],
        "gross_exposure_cap_pct": selected["gross_exposure_cap_pct"],
        "training_return_pct": selected["total_return_pct"],
        "training_close_mdd_pct": selected["max_drawdown_pct"],
        "training_ohlc_bound_pct": selected["simultaneous_ohlc_drawdown_bound_pct"],
        "training_ohlc_pass": selected["within_20pct_under_bound"],
        "oos_results": {
            period: oos_metrics[f"{selected['rule_id']}|{period}"]
            for period, _, _ in PERIODS if period in TEST_PERIODS
        },
    }
    selection = {
        "as_of": "2026-10-27",
        "primary_slippage_bps_per_side": PRIMARY_SLIPPAGE,
        "capital_inr": CAPITAL,
        "training_period": "2015-01-02 through 2019-12-31",
        "candidate_count": len(training_risk),
        "eligible_training_candidates": len(candidates),
        "selection_rule": "Among training rules passing the -20% order-ledger OHLC bound, maximize net return; tie-break by shallower OHLC bound, lower cap, allocation closest to 50/50, then quarterly schedule.",
        "selected": chosen,
        "fixed_50_50_monthly_45pct_reference": {
            "rule_id": equal_rule,
            "oos_results": {
                period: oos_metrics[f"{equal_rule}|{period}"]
                for period, _, _ in PERIODS if period in TEST_PERIODS
            },
        },
        "top_10_training_candidates": [
            {key: row[key] for key in ("rule_id", "rebalance_frequency", "nifty_share_pct", "gross_exposure_cap_pct", "total_return_pct", "max_drawdown_pct", "simultaneous_ohlc_drawdown_bound_pct")}
            for row in candidates[:10]
        ],
        "oos_ohlc_audits": oos_risk_entries,
        "limitations": [
            "All inspected historical windows were previously viewed; chronological tests are not a fresh lockbox.",
            "ETF cash distributions, Gold ETF event completeness, tax, cash yield, live spread, and market impact remain unresolved.",
            "The daily OHLC bound is conservative by construction but does not guarantee a future 20% maximum drawdown.",
        ],
    }
    SELECTION.write_text(json.dumps(selection, indent=2), encoding="utf-8")
    assert len(oos_risk_rows) == len(unique_evaluations) * 4
    assert len(cost_rows) == len(unique_evaluations) * 3 * len(SLIPPAGE)
    print(f"grid={len(grid)} training_ohlc={len(training_risk)} eligible={len(candidates)} selected={chosen['rule_id'] if chosen else 'none'} oos_ohlc={len(oos_risk_rows)} cost_rows={len(cost_rows)}")


if __name__ == "__main__":
    main()
