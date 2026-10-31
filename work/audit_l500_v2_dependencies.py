"""Measure L500-v2 candidate, order, action, and valuation dependencies without P&L."""

from __future__ import annotations

import argparse
import bisect
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow.dataset as ds

from audit_strategy_dependencies import atomic_csv, dependency_counts, dependency_source_key, resolution_attempt_for, score_at


ROOT = Path(__file__).resolve().parents[1]
PUBLIC = ROOT / "work" / "data" / "public_research"
RAW_DIR = PUBLIC / "tejhq" / "nse"
ADJ_DIR = PUBLIC / "tejhq" / "prices_adjusted"
ACTION_DIR = PUBLIC / "tejhq" / "actions"
BACKFILL = PUBLIC / "nse_calendar_backfill" / "nse_calendar_backfill.parquet"
ADJ_BACKFILL = PUBLIC / "nse_calendar_backfill" / "nse_calendar_backfill_adjusted.parquet"
REVIEWED_BRIDGES = PUBLIC / "isin_bridges" / "reviewed_identity_bridges.csv"
START, CUTOFF = pd.Timestamp("2018-01-01"), pd.Timestamp("2026-10-23")
RELEVANT_ACTIONS = {"split", "bonus", "dividend", "rights", "merger", "demerger", "spinoff"}


def atomic_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")
    temp.replace(path)


def load_frames() -> tuple[list[pd.Timestamp], pd.DataFrame, pd.DataFrame, dict[str, str], pd.DataFrame]:
    raw_files = sorted(RAW_DIR.glob("year=*/nse_*.parquet"))
    if len(raw_files) != 11:
        raise ValueError(f"expected 11 pinned raw NSE years, found {len(raw_files)}")
    raw_ds = ds.dataset([str(path) for path in raw_files], format="parquet")
    raw = raw_ds.to_table(columns=["date", "symbol", "series", "isin", "open", "high", "low", "close", "turnover"]).to_pandas()
    raw["source"] = "TejHQ public NSE EOD mirror"
    supplement = pd.read_parquet(BACKFILL, columns=["date", "symbol", "series", "isin", "open", "high", "low", "close", "turnover"])
    supplement["source"] = "NSE official EOD backfill"
    raw = pd.concat([raw, supplement[raw.columns]], ignore_index=True)
    raw["date"] = pd.to_datetime(raw["date"]).dt.normalize()
    raw["isin"] = raw["isin"].astype(str).str.upper()
    raw["symbol"] = raw["symbol"].astype(str).str.upper()
    raw["series"] = raw["series"].astype(str).str.upper()
    raw = raw[raw["series"].isin({"EQ", "BE"})]
    raw = raw.drop_duplicates(["date", "isin", "series"], keep="last")
    series_count = raw.groupby(["date", "isin"])["series"].nunique()
    ambiguous = set(series_count[series_count.gt(1)].index)

    adj_files = sorted(ADJ_DIR.glob("nse_*.parquet"))
    adj_ds = ds.dataset([str(path) for path in adj_files], format="parquet")
    adjusted = adj_ds.to_table(columns=["date", "isin", "series", "adj_close", "adj_factor_cumulative"]).to_pandas()
    adjusted["factor_status"] = ""
    adjusted = pd.concat([adjusted, pd.read_parquet(ADJ_BACKFILL,
                            columns=["date", "isin", "series", "adj_close", "adj_factor_cumulative", "factor_status"])],
                         ignore_index=True)
    adjusted["date"] = pd.to_datetime(adjusted["date"]).dt.normalize()
    adjusted["isin"] = adjusted["isin"].astype(str).str.upper()
    adjusted["series"] = adjusted["series"].astype(str).str.upper()
    adjusted = adjusted.drop_duplicates(["date", "isin", "series"], keep="last")
    data = raw.merge(adjusted, on=["date", "isin", "series"], how="left", validate="one_to_one")
    for field in ("open", "high", "low", "close", "turnover", "adj_close"):
        data[field] = pd.to_numeric(data[field], errors="coerce")
    data["ambiguous_series"] = [(date, isin) in ambiguous for date, isin in zip(data["date"], data["isin"])]

    sessions = sorted(set(raw["date"].dropna().map(pd.Timestamp))
                      | set(pd.to_datetime(supplement["date"]).dropna().map(pd.Timestamp)))
    sessions = [day.normalize() for day in sessions]
    history = pd.read_parquet(PUBLIC / "tejhq" / "symbol_history" / "nse.parquet")
    history["isin"] = history["isin"].astype(str).str.upper()
    history["symbol"] = history["symbol"].astype(str).str.upper()
    symbols = history.drop_duplicates("isin").set_index("isin")["symbol"].to_dict()

    action_frames = [pd.read_parquet(path) for path in sorted(ACTION_DIR.glob("nse_*.parquet"))]
    actions = pd.concat(action_frames, ignore_index=True)
    actions["ex_date"] = pd.to_datetime(actions["ex_date"], errors="coerce").dt.normalize()
    actions["symbol"] = actions["symbol"].astype(str).str.upper()
    actions["isin"] = actions["isin"].astype(str).str.upper()
    actions = actions.drop_duplicates(["symbol", "isin", "ex_date", "type", "ratio_num", "ratio_den", "cash_amount", "face_value_from", "face_value_to"])
    actions["term_variants"] = actions.groupby(["symbol", "isin", "ex_date", "type"], dropna=False)["type"].transform("size")
    return sessions, data, actions, symbols, history


def valid_ohlc(frame: pd.DataFrame) -> np.ndarray:
    o, h, low, close, turnover = (frame[key].to_numpy(dtype=float) for key in ("open", "high", "low", "close", "turnover"))
    finite_positive = np.isfinite(o) & np.isfinite(h) & np.isfinite(low) & np.isfinite(close) & np.isfinite(turnover)
    finite_positive &= (o > 0) & (h > 0) & (low > 0) & (close > 0) & (turnover > 0)
    return finite_positive & (h >= np.maximum.reduce([o, close, low])) & (low <= np.minimum.reduce([o, close, h]))


def window_complete(prefix: np.ndarray, start: int, end: int) -> bool:
    return start >= 0 and end >= start and (prefix[end] - prefix[start]) == 0


def audit() -> dict:
    sessions, data, actions, symbols, history = load_frames()
    index = {day: i for i, day in enumerate(sessions)}
    cutoff_idx = index[max(day for day in sessions if day <= CUTOFF)]
    entity_data = {}
    for isin, group in data.groupby("isin", sort=False):
        frame = group.sort_values("date").drop_duplicates("date").set_index("date").reindex(sessions)
        frame["ambiguous_series"] = frame["ambiguous_series"].eq(True)
        raw_ok = valid_ohlc(frame) & ~frame["ambiguous_series"].to_numpy(dtype=bool)
        adj = pd.to_numeric(frame["adj_close"], errors="coerce").to_numpy(dtype=float)
        adj_ok = np.isfinite(adj) & (adj > 0)
        bad_raw_prefix = np.r_[0, np.cumsum(~raw_ok)]
        bad_adj_prefix = np.r_[0, np.cumsum(~adj_ok)]
        ambiguous = frame["ambiguous_series"].to_numpy(dtype=bool)
        ambiguous_prefix = np.r_[0, np.cumsum(ambiguous)]
        entity_data[isin] = {
            "raw_ok": raw_ok, "adj": adj,
            "open": pd.to_numeric(frame["open"], errors="coerce").to_numpy(dtype=float),
            "close": pd.to_numeric(frame["close"], errors="coerce").to_numpy(dtype=float),
            "turnover": pd.to_numeric(frame["turnover"], errors="coerce").to_numpy(dtype=float),
            "bad_raw_prefix": bad_raw_prefix, "bad_adj_prefix": bad_adj_prefix,
            "ambiguous_prefix": ambiguous_prefix,
            "factor_status": frame["factor_status"].fillna("").astype(str).to_numpy(),
            "dates": frame.index.to_list(),
        }

    actions_by_symbol = {key: frame.sort_values("ex_date").reset_index(drop=True)
                         for key, frame in actions.groupby("symbol", sort=False)}
    reviewed = pd.read_csv(REVIEWED_BRIDGES, dtype=str).fillna("")
    verified_action_keys = {(r.symbol.upper(), pd.Timestamp(r.economic_ex_date), "split")
                            for r in reviewed.itertuples(index=False) if r.status == "verified"}
    history = history.copy()
    history["valid_from"] = pd.to_datetime(history["valid_from"], errors="coerce").dt.normalize()
    history["valid_to"] = pd.to_datetime(history["valid_to"], errors="coerce").dt.normalize()
    previous_session = {sessions[i]: sessions[i - 1] for i in range(1, len(sessions))}
    transitions_by_symbol = {}
    for symbol, group in history.sort_values("valid_from").groupby("symbol", sort=False):
        rows = list(group.itertuples(index=False))
        for old, new in zip(rows, rows[1:]):
            if previous_session.get(new.valid_from) == old.valid_to:
                transitions_by_symbol.setdefault(str(symbol).upper(), []).append({
                    "date": new.valid_from, "from_isin": str(old.isin).upper(), "to_isin": str(new.isin).upper()})

    dates = [day for day in sessions if START <= day <= CUTOFF]
    date_frame = pd.DataFrame({"date": dates})
    month_ends = date_frame.groupby(date_frame["date"].dt.to_period("M"))["date"].max().tolist()
    month_ends = [day for day in month_ends if day.month <= 9 or day < pd.Timestamp("2026-10-01")]
    schedules = {"M": month_ends, "Q": [day for day in month_ends if day.month in {3, 6, 9, 12}]}
    dependencies, signals, orders, marks, eligibility = [], [], [], [], []
    summaries = {}

    for rule in ("A", "B"):
        offset = 252 if rule == "A" else 273
        for cadence in ("M", "Q"):
            candidate_id = f"L500v2-{rule}-{cadence}"
            prior: list[str] = []
            decisions = []
            for decision in schedules[cadence]:
                i = index[decision]
                eligible, liquidity_fail, window_fail, ambiguous_fail = [], 0, 0, 0
                signal_start, signal_end = i - offset, i - 21
                for isin, entity in entity_data.items():
                    if signal_start < 0 or i < 63:
                        continue
                    liquidity_ok = window_complete(entity["bad_raw_prefix"], i - 63, i)
                    if not liquidity_ok:
                        liquidity_fail += 1
                        ambiguous_fail += int(entity["ambiguous_prefix"][i] - entity["ambiguous_prefix"][i - 63] > 0)
                        continue
                    if not window_complete(entity["bad_raw_prefix"], signal_start, signal_end + 1):
                        window_fail += 1
                        ambiguous_fail += int(entity["ambiguous_prefix"][signal_end + 1] - entity["ambiguous_prefix"][signal_start] > 0)
                        continue
                    if not window_complete(entity["bad_adj_prefix"], signal_start, signal_end + 1):
                        window_fail += 1
                        continue
                    score, reason = score_at(entity["adj"], i, rule)
                    if reason:
                        window_fail += 1
                        continue
                    mean_turnover = float(np.mean(entity["turnover"][i - 63:i]))
                    if not np.isfinite(mean_turnover) or mean_turnover <= 0:
                        liquidity_fail += 1
                        continue
                    eligible.append((isin, mean_turnover, score))
                eligible.sort(key=lambda row: (-row[1], row[0]))
                selected = eligible[:500]
                eligibility.append({"candidate_id": candidate_id, "signal_date": decision.date().isoformat(),
                                    "eligible_before_top500": len(eligible), "selected_up_to_500": len(selected),
                                    "incomplete_liquidity_windows": liquidity_fail,
                                    "incomplete_signal_windows": window_fail, "ambiguous_series_dates": ambiguous_fail})
                scored = []
                for isin, mean_turnover, score in selected:
                    symbol = symbols.get(isin, "")
                    entity = entity_data[isin]
                    reason_list = []
                    if signal_start < 0 or i < 63:
                        reason_list.append("insufficient_warmup")
                    unresolved_factors = [sessions[j] for j in range(signal_start, signal_end + 1)
                                          if entity["factor_status"][j].startswith("unresolved")]
                    if unresolved_factors:
                        reason_list.append("unresolved_adjustment_factor")
                        dependencies.append({"candidate_id": candidate_id, "rule": rule, "date": decision.date().isoformat(),
                                             "entity": f"{symbol}|{isin}", "input": "signal_adjustment_factor",
                                             "source": "NSE official EOD supplement plus TejHQ adjusted-price reference",
                                             "reason": f"{len(unresolved_factors)} unresolved factor rows in fixed signal window; first={unresolved_factors[0].date()}",
                                             "impact": "ranking-changing signal unknown"})
                    action_frame = actions_by_symbol.get(symbol, actions.iloc[0:0])
                    event_rows = action_frame[action_frame["ex_date"].between(sessions[signal_start], sessions[signal_end])]
                    for event in event_rows.drop_duplicates(["symbol", "ex_date", "type", "isin"]).itertuples(index=False):
                        kind = str(event.type).lower()
                        if kind not in RELEVANT_ACTIONS or (symbol, pd.Timestamp(event.ex_date), kind) in verified_action_keys:
                            continue
                        variants = int(getattr(event, "term_variants", 1))
                        variant_note = f"; source contains {variants} distinct term rows" if variants > 1 else ""
                        reason_list.append("unreconciled_primary_action_terms_in_signal_window")
                        dependencies.append({"candidate_id": candidate_id, "rule": rule, "date": event.ex_date.date().isoformat(),
                                             "entity": f"{symbol}|{isin}", "input": f"signal_{kind}",
                                             "source": "TejHQ NSE corporate-action feed",
                                             "reason": f"signal window uses an adjusted price across unverified action terms; vendor action ISIN={event.isin}{variant_note}",
                                             "impact": "ranking-changing signal may be misstated"})
                    scored.append({"candidate_id": candidate_id, "signal_date": decision.date().isoformat(),
                                   "symbol": symbol, "isin": isin, "mean_turnover_63": mean_turnover,
                                   "score": score, "score_status": "CONDITIONAL" if reason_list else "SCORED"})
                positive = [row for row in scored if row["score"] > 0]
                positive.sort(key=lambda row: (-row["score"], row["isin"]))
                rank = {row["isin"]: n for n, row in enumerate(positive, 1)}
                for row in scored:
                    row["rank"] = rank.get(row["isin"], "")
                    signals.append(row)
                retained = [isin for isin in prior if isin in rank and rank[isin] <= 25]
                retained = sorted(set(retained), key=lambda isin: (rank[isin], isin))[:20]
                target = list(retained)
                for row in positive:
                    if len(target) >= 20:
                        break
                    if row["isin"] not in target:
                        target.append(row["isin"])
                conditional = any(row["score_status"] == "CONDITIONAL" for row in scored)
                exec_date = sessions[i + 1] if i + 1 < len(sessions) else None
                if exec_date is None or exec_date > CUTOFF:
                    dependencies.append({"candidate_id": candidate_id, "rule": rule, "date": decision.date().isoformat(),
                                         "entity": "", "input": "next_session_order", "source": "source-session calendar",
                                         "reason": "no in-window next-session execution date", "impact": "strategy path cannot execute"})
                else:
                    execution_i = index[exec_date]
                    for isin in sorted(set(prior) ^ set(target)):
                        side = "BUY" if isin in target else "SELL"
                        symbol = symbols.get(isin, "")
                        open_px = entity_data.get(isin, {}).get("open", np.full(len(sessions), np.nan))[execution_i]
                        status = "OBSERVED" if np.isfinite(open_px) and open_px > 0 else "MISSING_OPEN"
                        orders.append({"candidate_id": candidate_id, "signal_date": decision.date().isoformat(),
                                       "execution_date": exec_date.date().isoformat(), "side": side,
                                       "symbol": symbol, "isin": isin, "raw_open": open_px if status == "OBSERVED" else "",
                                       "dependency_status": status, "conditional_signal_set": conditional})
                        if status != "OBSERVED":
                            dependencies.append({"candidate_id": candidate_id, "rule": rule, "date": exec_date.date().isoformat(),
                                                 "entity": f"{symbol}|{isin}", "input": "intended_order_open",
                                                 "source": "TejHQ NSE cash EOD + official NSE backfill",
                                                 "reason": f"{side} order has no positive finite next-session open",
                                                 "impact": "intended order cannot be executed/reconciled"})
                decisions.append({"date": decision, "exec_date": exec_date, "target": target,
                                  "conditional": conditional})
                prior = target

            expected_marks = observed_marks = 0
            for j, decision_row in enumerate(decisions):
                start_date = decision_row["exec_date"]
                if start_date is None or start_date > CUTOFF:
                    continue
                start_i = index[start_date]
                has_next = j + 1 < len(decisions) and decisions[j + 1]["exec_date"] is not None
                end_i = min(index[decisions[j + 1]["exec_date"]], cutoff_idx) if has_next else cutoff_idx
                mark_end = min(cutoff_idx, end_i - 1) if has_next else cutoff_idx
                for isin in decision_row["target"]:
                    entity = entity_data[isin]
                    for k in range(start_i, mark_end + 1):
                        expected_marks += 1
                        close = entity["close"][k]
                        if np.isfinite(close) and close > 0:
                            observed_marks += 1
                        else:
                            dependencies.append({"candidate_id": candidate_id, "rule": rule, "date": sessions[k].date().isoformat(),
                                                 "entity": f"{symbols.get(isin,'')}|{isin}", "input": "held_position_close",
                                                 "source": "TejHQ NSE cash EOD + official NSE backfill",
                                                 "reason": "held position has no positive finite raw close for daily NAV valuation",
                                                 "impact": "position/NAV path invalid; no stale or zero mark allowed"})
                    symbol = symbols.get(isin, "")
                    if symbol:
                        action_frame = actions_by_symbol.get(symbol, actions.iloc[0:0])
                        held_events = action_frame[action_frame["ex_date"].between(start_date, sessions[end_i])]
                        for event in held_events.drop_duplicates(["symbol", "ex_date", "type", "isin"]).itertuples(index=False):
                            kind = str(event.type).lower()
                            if kind not in RELEVANT_ACTIONS or (symbol, pd.Timestamp(event.ex_date), kind) in verified_action_keys:
                                continue
                            variants = int(getattr(event, "term_variants", 1))
                            variant_note = f"; source contains {variants} distinct term rows" if variants > 1 else ""
                            dependencies.append({"candidate_id": candidate_id, "rule": rule, "date": event.ex_date.date().isoformat(),
                                                 "entity": f"{symbol}|{event.isin}", "input": f"held_entitlement_{kind}",
                                                 "source": "TejHQ NSE corporate-action feed",
                                                 "reason": f"held ISIN {isin} crosses unreconciled {kind} terms/entitlement; vendor action ISIN={event.isin}{variant_note}",
                                                 "impact": "position path invalid until entitlement/identity is valued"})
                        for event in transitions_by_symbol.get(symbol, []):
                            if start_date <= event["date"] <= sessions[end_i] and event["from_isin"] == isin:
                                dependencies.append({"candidate_id": candidate_id, "rule": rule, "date": event["date"].date().isoformat(),
                                                     "entity": f"{symbol}|{event['from_isin']}->{event['to_isin']}",
                                                     "input": "held_identity_transition", "source": "TejHQ symbol history",
                                                     "reason": "held position crosses an unreviewed ISIN transition; no automatic alias used",
                                                     "impact": "position identity/shares cannot be valued without a reviewed bridge"})
                    marks.append({"candidate_id": candidate_id, "signal_date": decision_row["date"].date().isoformat(),
                                  "execution_date": start_date.date().isoformat(), "isin": isin,
                                  "expected_close_marks": max(0, mark_end - start_i + 1),
                                  "observed_close_marks": sum(np.isfinite(entity["close"][k]) and entity["close"][k] > 0
                                                                for k in range(start_i, mark_end + 1)),
                                  "conditional_signal_set": decision_row["conditional"]})
            candidate_rows = [row for row in signals if row["candidate_id"] == candidate_id]
            config_deps = [row for row in dependencies if row["candidate_id"] == candidate_id]
            eligible_counts = [row["eligible_before_top500"] for row in eligibility if row["candidate_id"] == candidate_id]
            summaries[candidate_id] = {
                "scheduled_decisions": len(decisions), "eligible_candidates_min": min(eligible_counts, default=0),
                "eligible_candidates_median": float(np.median(eligible_counts)) if eligible_counts else 0,
                "eligible_candidates_max": max(eligible_counts, default=0),
                "decisions_with_fewer_than_20_eligible_candidates": sum(value < 20 for value in eligible_counts),
                "selected_signal_rows": len(candidate_rows),
                "decisions_with_conditional_signal_set": sum(row["conditional"] for row in decisions),
                "provisional_order_intents": sum(row["candidate_id"] == candidate_id for row in orders),
                "expected_daily_close_marks": expected_marks, "observed_daily_close_marks": observed_marks,
                "missing_daily_close_marks": expected_marks - observed_marks,
                "order_open_failures": sum(row["candidate_id"] == candidate_id and row["input"] == "intended_order_open" for row in config_deps),
                "material_dependencies": len(config_deps), "promotable": not config_deps,
            }

    for dependency in dependencies:
        dependency["resolution_attempt"] = resolution_attempt_for(dependency)
    out_dir = PUBLIC / "strategy_dependencies" / "l500_v2"
    atomic_csv(out_dir / "eligibility_by_decision.csv", eligibility,
               ["candidate_id", "signal_date", "eligible_before_top500", "selected_up_to_500", "incomplete_liquidity_windows", "incomplete_signal_windows", "ambiguous_series_dates"])
    atomic_csv(out_dir / "signal_dependencies.csv", signals,
               ["candidate_id", "signal_date", "symbol", "isin", "mean_turnover_63", "score", "rank", "score_status"])
    atomic_csv(out_dir / "intended_orders.csv", orders,
               ["candidate_id", "signal_date", "execution_date", "side", "symbol", "isin", "raw_open", "dependency_status", "conditional_signal_set"])
    atomic_csv(out_dir / "position_valuation_windows.csv", marks,
               ["candidate_id", "signal_date", "execution_date", "isin", "expected_close_marks", "observed_close_marks", "conditional_signal_set"])
    atomic_csv(out_dir / "unresolved_dependencies.csv", dependencies,
               ["candidate_id", "rule", "date", "entity", "input", "source", "reason", "resolution_attempt", "impact"])
    incidence, unique = dependency_counts(dependencies)
    result = {
        "protocol_id": "L500-v2", "audit_type": "non-P&L candidate dependency audit",
        "evaluation_start": START.date().isoformat(), "evaluation_cutoff": CUTOFF.date().isoformat(),
        "working_calendar_sessions": len(sessions),
        "calendar_basis": "TejHQ raw source dates plus 18 primary-NSE EOD sessions; finite corrections applied, not a claim of global archive completeness",
        "sessions_added_from_verified_primary_sources": 18,
        "security_series": len(entity_data), "eligibility_rule": "positive, finite, valid observed EQ/BE OHLC and turnover for prior 63 completed sessions and the full applicable signal window; no ISIN stitching",
        "configurations": summaries, "dependency_rows": len(dependencies),
        "dependency_path_incidence_counts": incidence, "unique_source_entity_date_type_counts": unique,
        "performance_gate": "NOT RUN; no NAV, return, CAGR, fee attribution, or strategy ranking was calculated",
        "strategy_study_authorized": all(summary["promotable"] for summary in summaries.values()),
    }
    atomic_json(ROOT / "outputs" / "l500_data_gate_2026-10-31.json", result)
    print(json.dumps(result, indent=2))
    return result


def self_check() -> None:
    sessions = list(pd.date_range("2020-01-01", periods=5, freq="B"))
    values = np.r_[0, 0, 1, 0, 0]
    prefix = np.r_[0, np.cumsum(values)]
    assert window_complete(prefix, 3, 4)
    assert not window_complete(prefix, 2, 3)
    raw = pd.DataFrame({"open": [10.0], "high": [11.0], "low": [9.0], "close": [10.5], "turnover": [100.0]})
    assert valid_ohlc(raw).tolist() == [True]
    raw.loc[0, "high"] = 10.0
    assert valid_ohlc(raw).tolist() == [False]
    assert sessions[-1] > sessions[0]
    assert resolution_attempt_for({"input": "intended_order_open"}).startswith("Checked the exact ISIN/execution date")
    print("L500-v2 dependency self-check passed: complete windows, OHLC validation, and source session ordering")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--self-check", action="store_true")
    args = parser.parse_args()
    self_check() if args.self_check else audit()
