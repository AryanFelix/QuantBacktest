"""Run first-signal conditional order diagnostics through the shared cash engine."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "work"))
import audit_strategy_dependencies as audit
import upstox_quant as cash_engine

CAPITAL = 1_000_000.0
START = pd.Timestamp("2018-01-01")
OUT = ROOT / "outputs" / "nifty200_cash_prefix_traces_2026-11-01.json"
DETAIL_DIR = audit.PUBLIC / "strategy_dependencies" / "nifty200"


def first_diagnostic_target(signals: pd.DataFrame, candidate: str) -> tuple[pd.Timestamp, list[str], int, int]:
    rows = signals.loc[signals["candidate_id"].eq(candidate)].copy()
    signal_date = pd.Timestamp(rows["signal_date"].min())
    first = rows.loc[rows["signal_date"].eq(signal_date.date().isoformat())].copy()
    first["score"] = pd.to_numeric(first["score"], errors="coerce")
    unknown = int(first["score_status"].eq("UNRESOLVED").sum())
    usable = first.loc[first["score_status"].eq("SCORED") & first["score"].gt(0)]
    usable = usable.sort_values(["score", "isin"], ascending=[False, True]).drop_duplicates("canonical")
    return signal_date, usable["canonical"].astype(str).head(20).tolist(), unknown, len(usable)


def blockers_for(dependencies: pd.DataFrame, candidate: str, signal_date: pd.Timestamp) -> list[dict]:
    rows = dependencies.loc[
        dependencies["candidate_id"].eq(candidate)
        & dependencies["signal_date"].eq(signal_date.date().isoformat())
        & dependencies["input"].str.startswith("signal_")
    ].copy()
    rows = rows.drop_duplicates(["date", "entity", "input", "reason"]).sort_values(["date", "input", "entity"])
    fields = ["date", "entity", "input", "source", "reason", "resolution_attempt", "impact"]
    return rows[fields].head(12).to_dict(orient="records")


def run() -> dict:
    sessions, intervals, data, actions, symbols, reviewed, unreviewed, canonical, history = audit.load_data()
    signals = pd.read_csv(DETAIL_DIR / "signal_dependencies.csv", dtype=str).fillna("")
    dependencies = pd.read_csv(DETAIL_DIR / "unresolved_dependencies.csv", dtype=str).fillna("")
    all_sessions = pd.DatetimeIndex(sessions)
    traces, equity_rows, order_frames = [], [], []

    for candidate in ("NIFTY200-A-M", "NIFTY200-A-Q", "NIFTY200-B-M", "NIFTY200-B-Q"):
        signal_date, target_names, unknown_scores, positive_scored = first_diagnostic_target(signals, candidate)
        signal_rows = signals.loc[
            signals["candidate_id"].eq(candidate) & signals["signal_date"].eq(signal_date.date().isoformat())
        ]
        unresolved = signal_rows.loc[signal_rows["score_status"].eq("UNRESOLVED"),
                                     ["symbol", "isin", "membership_interval_isin", "identity_resolution_method", "unresolved_reason"]]
        signal_index = all_sessions.get_loc(signal_date)
        if signal_index + 1 >= len(all_sessions):
            raise ValueError(f"No next-session execution date for {candidate} at {signal_date.date()}")
        execution_date = all_sessions[signal_index + 1]

        source = data.loc[data["canonical"].astype(str).isin(target_names)]
        opens = source.pivot_table(index="date", columns="canonical", values="open", aggfunc="first").reindex(
            index=all_sessions, columns=target_names
        )
        closes = source.pivot_table(index="date", columns="canonical", values="close", aggfunc="first").reindex(
            index=all_sessions, columns=target_names
        )
        quote_issues = []
        for name in target_names:
            for day, field, panel in ((signal_date, "signal_close", closes),
                                      (execution_date, "next_session_open", opens),
                                      (execution_date, "next_session_close", closes)):
                value = panel.at[day, name] if day in panel.index and name in panel.columns else np.nan
                if not np.isfinite(value) or value <= 0:
                    quote_issues.append({"date": day.date().isoformat(), "entity": name, "input": field,
                                         "reason": "no positive finite raw NSE cash quote"})

        engine_orders = pd.DataFrame()
        equity = pd.DataFrame()
        stats = {}
        if not quote_issues:
            targets = pd.DataFrame(0.0, index=all_sessions, columns=target_names)
            for name in target_names:
                targets.loc[signal_date, name] = 1.0 / 20.0
            rebalance = pd.Series(False, index=all_sessions)
            rebalance.loc[signal_date] = True
            equity, engine_orders, stats = cash_engine._simulate(
                {"open": opens, "close": closes}, targets, rebalance,
                starting_balance=CAPITAL, max_exposure=1.0, slippage_bps=50.0,
                start=START.date(), end=execution_date.date(), drawdown_limit_pct=100.0,
                cash_yield_series=None, liquidate_terminal=False,
            )
            if engine_orders.get("terminal_liquidation", pd.Series(dtype=bool)).fillna(False).any():
                raise AssertionError("Diagnostic account must remain invested through its observed close mark")
            reconciliation = (equity["nav"] - equity["cash_inr"] - equity["invested_inr"]).abs()
            if not np.isfinite(reconciliation).all() or reconciliation.max() > 0.05:
                raise AssertionError(f"Order-to-NAV cash reconciliation failed for {candidate}")
            if len(engine_orders) != len(target_names) or not engine_orders["side"].eq("buy").all():
                raise AssertionError(f"Conditional first rebalance did not fill every diagnostic target for {candidate}")
            engine_orders["reference_open_raw"] = [opens.at[row.time, row.symbol] for row in engine_orders.itertuples()]
            engine_orders["slippage_cost_inr"] = engine_orders["quantity"] * (
                engine_orders["fill_price"] - engine_orders["reference_open_raw"]
            ).abs()
            engine_orders = engine_orders.assign(candidate_id=candidate, diagnostic_only=True)
            order_frames.append(engine_orders)
            for day, row in equity.iterrows():
                equity_rows.append({"candidate_id": candidate, "date": day.date().isoformat(),
                                    "cash_inr": float(row["cash_inr"]), "invested_inr": float(row["invested_inr"]),
                                    "nav_inr": float(row["nav"]), "conditional_orders_to_date": int(
                                        engine_orders["time"].le(day).sum())})
        else:
            reconciliation = pd.Series(dtype=float)

        traces.append({
            "candidate_id": candidate,
            "first_signal_date": signal_date.date().isoformat(),
            "first_execution_date": execution_date.date().isoformat(),
            "signal_members": int(len(signal_rows)),
            "unresolved_member_signals": unknown_scores,
            "positive_fully_scored_members": positive_scored,
            "conditional_names_simulated": len(target_names),
            "unfilled_slots_left_as_cash": max(0, 20 - len(target_names)),
            "first_signal_blocks_valid_target": bool(unknown_scores),
            "valid_strategy_orders_before_stop": 0 if unknown_scores or quote_issues else int(len(engine_orders)),
            "valid_strategy_cash_at_stop_inr": CAPITAL if unknown_scores else float(stats.get("ending_cash_inr", CAPITAL)),
            "first_signal_unresolved_examples": unresolved.head(8).to_dict(orient="records"),
            "first_signal_dependency_examples": blockers_for(dependencies, candidate, signal_date),
            "diagnostic_quote_issues": quote_issues,
            "diagnostic_engine_ran": not quote_issues,
            "diagnostic_only_orders": int(len(engine_orders)),
            "diagnostic_fees_inr": float(stats.get("total_fees_inr", 0.0)),
            "diagnostic_slippage_cost_inr": float(engine_orders["slippage_cost_inr"].sum()) if len(engine_orders) else 0.0,
            "diagnostic_total_fees_plus_slippage_inr": float(stats.get("total_fees_inr", 0.0)
                                                                + (engine_orders["slippage_cost_inr"].sum() if len(engine_orders) else 0.0)),
            "diagnostic_turnover_inr": float(stats.get("turnover_inr", 0.0)),
            "diagnostic_ending_cash_inr": float(stats.get("ending_cash_inr", CAPITAL)),
            "diagnostic_ending_invested_inr": float(stats.get("ending_invested_inr", 0.0)),
            "diagnostic_ending_nav_inr": float(stats.get("ending_balance_inr", CAPITAL)),
            "max_cash_plus_position_nav_residual_inr": float(reconciliation.max()) if len(reconciliation) else None,
            "strategy_pnl": "NOT CALCULATED; unresolved signals may change the target",
            "valid_strategy_prefix": f"cash-only through {signal_date.date()}; stops before {execution_date.date()} order",
        })

    if order_frames:
        pd.concat(order_frames, ignore_index=True).to_csv(DETAIL_DIR / "conditional_first_rebalance_orders.csv", index=False)
    pd.DataFrame(equity_rows).to_csv(DETAIL_DIR / "conditional_first_rebalance_equity.csv", index=False)
    result = {
        "protocol_id": "NIFTY200-v1.3-diagnostic",
        "study_selection": "Original NIFTY200 A-M/A-Q/B-M/B-Q fixed before any new P&L",
        "starting_capital_inr": CAPITAL,
        "evaluation": {"start": "2018-01-01", "cutoff": "2026-10-23"},
        "execution": "Shared cash engine; next-session raw open; integer shares; 50 bps per-side slippage; current NSE fee model; zero cash yield; no terminal liquidation in the diagnostic window",
        "conditional_order_policy": "Only positive, fully SCORED members receive a provisional 5% weight; unknown scores remain unknown and their weight stays cash. These orders discover execution dependencies and are not strategy P&L or a valid target ranking.",
        "configurations": traces,
        "performance_gate": "NOT RUN; no configuration has a fully resolved first-signal ranking",
        "strategy_study_authorized": False,
    }
    OUT.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))
    return result


if __name__ == "__main__":
    run()
