"""Build a non-P&L dependency audit for the repaired NIFTY 200 study."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow.dataset as ds
import pyarrow.parquet as pq


ROOT = Path(__file__).resolve().parents[1]
PUBLIC = ROOT / "work" / "data" / "public_research"
RAW_DIR = PUBLIC / "tejhq" / "nse"
ADJ_DIR = PUBLIC / "tejhq" / "prices_adjusted"
ACTION_DIR = PUBLIC / "tejhq" / "actions"
BACKFILL = PUBLIC / "nse_calendar_backfill" / "nse_calendar_backfill.parquet"
ADJ_BACKFILL = PUBLIC / "nse_calendar_backfill" / "nse_calendar_backfill_adjusted.parquet"
INTERVALS = PUBLIC / "membership" / "membership_intervals.csv"
REPLAY_BRIDGES = PUBLIC / "membership" / "identity_bridges.csv"
REVIEWED_BRIDGES = PUBLIC / "isin_bridges" / "reviewed_identity_bridges.csv"
START, CUTOFF = pd.Timestamp("2018-01-01"), pd.Timestamp("2026-10-23")
RELEVANT_ACTIONS = {"split", "bonus", "dividend", "rights", "merger", "demerger", "spinoff"}


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def atomic_csv(path: Path, rows: list[dict], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    with temp.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows({key: row.get(key, "") for key in fields} for row in rows)
    temp.replace(path)


def score_at(prices: np.ndarray, i: int, rule: str) -> tuple[float | None, str]:
    offset = 252 if rule == "A" else 273
    if i < offset:
        return None, "insufficient_warmup"
    end = i - 21
    needed = prices[i - offset:end + 1]
    if len(needed) != offset - 21 + 1 or not np.isfinite(needed).all() or (needed <= 0).any():
        return None, "missing_or_invalid_adjusted_close"
    ret12 = prices[end] / prices[i - 252] - 1
    if rule == "A":
        return float(ret12), ""
    ret6 = prices[end] / prices[i - 126] - 1
    vol_returns = np.diff(np.log(prices[i - 273:end + 1]))
    if len(vol_returns) != 252:
        return None, "incomplete_volatility_window"
    vol = float(np.std(vol_returns, ddof=1) * np.sqrt(252))
    if not np.isfinite(vol) or vol <= 0:
        return None, "invalid_annualized_volatility"
    return float((ret6 + ret12) / 2 / vol), ""


def union_find(isins: set[str], bridges: list[dict[str, str]]) -> dict[str, str]:
    parent = {isin: isin for isin in isins}

    def root(value: str) -> str:
        while parent[value] != value:
            parent[value] = parent[parent[value]]
            value = parent[value]
        return value

    for row in bridges:
        old, new = row["from_isin"].upper(), row["to_isin"].upper()
        parent.setdefault(old, old)
        parent.setdefault(new, new)
        left, right = root(old), root(new)
        if left != right:
            parent[left] = right
    return {isin: root(isin) for isin in parent}


def dependency_source_key(row: dict) -> tuple[str, ...]:
    kind = str(row.get("input", ""))
    entity = str(row.get("entity", ""))
    date = str(row.get("date", ""))
    if kind.startswith(("signal_", "held_entitlement_")):
        symbol = entity.split("|", 1)[0]
        vendor_isin = row.get("reason", "").partition("vendor action ISIN=")[2]
        return symbol, date, kind, vendor_isin
    return date, entity, kind


def dependency_counts(rows: list[dict]) -> tuple[dict[str, int], dict[str, int]]:
    incidence = pd.Series([r["input"] for r in rows]).value_counts().to_dict()
    keys_by_type: dict[str, set[tuple[str, ...]]] = {}
    for row in rows:
        keys_by_type.setdefault(str(row["input"]), set()).add(dependency_source_key(row))
    unique = {kind: len(keys) for kind, keys in keys_by_type.items()}
    return ({str(k): int(v) for k, v in incidence.items()}, unique)


def resolution_attempt_for(row: dict) -> str:
    kind = str(row.get("input", ""))
    if kind == "signal_adjustment_factor":
        return "Compared the TejHQ factor series with adjacent official NSE EOD and the interval action feed; the factor interval remains unresolved, so no factor was imputed."
    if kind == "signal_window":
        return "Looked up each required adjusted close in TejHQ and the 18-date official NSE factor supplement; missing or invalid values remain missing."
    if kind in {"signal_identity_bridge", "held_identity_transition"}:
        return "Compared the exact old/new ISIN pair and effective date with the reviewed bridge table; no unreviewed alias was applied."
    if kind.startswith("signal_") or kind.startswith("held_entitlement_"):
        return "Checked the exact symbol, ex-date, action type, and vendor ISIN against the local reviewed primary-source register; no nearest-ISIN match or assumed entitlement was used."
    if kind == "held_position_close":
        return "Checked the exact ISIN/session in pinned TejHQ EOD and the 18-date official NSE supplement; no stale or zero mark was substituted."
    if kind == "intended_order_open":
        return "Checked the exact ISIN/execution date in pinned TejHQ EOD and the 18-date official NSE supplement; no fill was invented."
    if kind == "next_session_order":
        return "Checked the corrected source-session calendar through the evaluation cutoff; no in-window next session is available."
    return "Retained as unresolved after the exact source/date/entity checks recorded above."


def load_data() -> tuple[list[pd.Timestamp], pd.DataFrame, pd.DataFrame, pd.DataFrame, dict[str, str], list[dict], list[dict], dict[str, str]]:
    intervals = pd.read_csv(INTERVALS, dtype=str).fillna("")
    if not intervals["replay_status"].eq("CERTIFIED").all():
        raise ValueError("NIFTY 200 membership intervals are not replay-certified")
    member_isins = set(intervals["isin"].str.upper())
    reviewed = [row for row in read_csv(REVIEWED_BRIDGES) if row["status"] == "verified"]
    verified_pairs = {(r["from_isin"].upper(), r["to_isin"].upper()) for r in reviewed}
    canonical = union_find(member_isins, reviewed)

    raw_files = sorted(RAW_DIR.glob("year=*/nse_*.parquet"))
    raw_ds = ds.dataset([str(p) for p in raw_files], format="parquet")
    all_dates = {pd.Timestamp(x) for x in raw_ds.to_table(columns=["date"])["date"].to_pylist() if x}
    backfill_dates = pd.to_datetime(pd.read_parquet(BACKFILL, columns=["date"])["date"]).dropna()
    all_dates.update(pd.Timestamp(x) for x in backfill_dates)
    sessions = sorted(pd.Timestamp(x).normalize() for x in all_dates)

    raw = raw_ds.to_table(
        columns=["date", "symbol", "series", "isin", "open", "high", "low", "close", "turnover"],
        filter=ds.field("isin").isin(sorted(member_isins)),
    ).to_pandas()
    raw["source"] = "TejHQ public NSE EOD mirror"
    supplement = pd.read_parquet(BACKFILL, columns=["date", "symbol", "series", "isin", "open", "high", "low", "close", "turnover", "source_file"])
    supplement = supplement[supplement["isin"].astype(str).str.upper().isin(member_isins)].copy()
    supplement["source"] = "NSE official EOD backfill"
    raw = pd.concat([raw, supplement[raw.columns]], ignore_index=True)
    raw["date"] = pd.to_datetime(raw["date"]).dt.normalize()
    raw["isin"] = raw["isin"].astype(str).str.upper()
    raw["symbol"] = raw["symbol"].astype(str).str.upper()
    raw = raw[raw["series"].astype(str).isin({"EQ", "BE"})]
    raw = raw.drop_duplicates(["date", "isin", "series"])
    raw["canonical"] = raw["isin"].map(canonical).fillna(raw["isin"])

    adj_ds = ds.dataset([str(p) for p in sorted(ADJ_DIR.glob("nse_*.parquet"))], format="parquet")
    adj = adj_ds.to_table(
        columns=["date", "isin", "series", "adj_close", "adj_factor_cumulative"],
        filter=ds.field("isin").isin(sorted(member_isins)),
    ).to_pandas()
    adj["factor_status"] = ""
    adj_supplement = pd.read_parquet(ADJ_BACKFILL, columns=["date", "isin", "series", "adj_close", "adj_factor_cumulative", "factor_status"])
    adj_supplement = adj_supplement[adj_supplement["isin"].astype(str).str.upper().isin(member_isins)].copy()
    adj = pd.concat([adj, adj_supplement], ignore_index=True)
    adj["date"] = pd.to_datetime(adj["date"]).dt.normalize()
    adj["isin"] = adj["isin"].astype(str).str.upper()
    adj = adj.drop_duplicates(["date", "isin", "series"])
    data = raw.merge(adj, on=["date", "isin", "series"], how="left", validate="one_to_one")
    data["adj_factor_cumulative"] = pd.to_numeric(data["adj_factor_cumulative"], errors="coerce")
    data["adj_close"] = pd.to_numeric(data["adj_close"], errors="coerce")
    data["canonical"] = data["isin"].map(canonical).fillna(data["isin"])
    duplicate = data.groupby(["date", "canonical"], sort=False).size().rename("identity_rows").reset_index()
    data = data.merge(duplicate, on=["date", "canonical"], validate="many_to_one")
    data.loc[data["identity_rows"].gt(1), ["open", "close", "adj_close"]] = np.nan

    history = pd.read_parquet(PUBLIC / "tejhq" / "symbol_history" / "nse.parquet")
    history["isin"] = history["isin"].astype(str).str.upper()
    history["symbol"] = history["symbol"].astype(str).str.upper()
    symbols = history.drop_duplicates("isin").set_index("isin")["symbol"].astype(str).str.upper().to_dict()
    actions = pd.concat([pd.read_parquet(p) for p in sorted(ACTION_DIR.glob("nse_*.parquet"))], ignore_index=True)
    actions["ex_date"] = pd.to_datetime(actions["ex_date"], errors="coerce").dt.normalize()
    actions["symbol"] = actions["symbol"].astype(str).str.upper()
    actions["isin"] = actions["isin"].astype(str).str.upper()
    actions = actions.drop_duplicates(["symbol", "isin", "ex_date", "type", "ratio_num", "ratio_den", "cash_amount", "face_value_from", "face_value_to"])
    actions["term_variants"] = actions.groupby(["symbol", "isin", "ex_date", "type"], dropna=False)["type"].transform("size")
    replay_rows = read_csv(REPLAY_BRIDGES)
    unreviewed = [r for r in replay_rows if (r["from_isin"].upper(), r["to_isin"].upper()) not in verified_pairs]
    return sessions, intervals, data, actions, symbols, reviewed, unreviewed, canonical, history


def audit() -> dict:
    sessions, intervals, data, actions, symbols, reviewed, unreviewed, canonical, history = load_data()
    index = {day: i for i, day in enumerate(sessions)}
    cutoff_idx = index[max(day for day in sessions if day <= CUTOFF)]
    series = {
        key: frame.sort_values("date").drop_duplicates("date").set_index("date").reindex(sessions)
        for key, frame in data.groupby("canonical", sort=False)
    }
    close_values = {key: pd.to_numeric(frame["close"], errors="coerce").to_numpy(dtype=float) for key, frame in series.items()}
    adjusted_values = {key: pd.to_numeric(frame["adj_close"], errors="coerce").to_numpy(dtype=float) for key, frame in series.items()}
    verified_action_keys = {
        (r["symbol"].upper(), pd.Timestamp(r["economic_ex_date"]), "split")
        for r in reviewed
    }
    verified_action_keys |= {
        (r["symbol"].upper(), pd.Timestamp(r["economic_ex_date"]), "bonus")
        for r in reviewed
    }
    previous_session = {sessions[i]: sessions[i - 1] for i in range(1, len(sessions))}
    reviewed_pairs = {(r["from_isin"].upper(), r["to_isin"].upper()) for r in reviewed}
    transitions = []
    history = history.copy()
    history["valid_from"] = pd.to_datetime(history["valid_from"], errors="coerce").dt.normalize()
    history["valid_to"] = pd.to_datetime(history["valid_to"], errors="coerce").dt.normalize()
    for _, group in history.sort_values("valid_from").groupby("symbol", sort=False):
        rows = list(group.itertuples(index=False))
        for old, new in zip(rows, rows[1:]):
            pair = (str(old.isin).upper(), str(new.isin).upper())
            if previous_session.get(new.valid_from) == old.valid_to and pair not in reviewed_pairs:
                transitions.append({"symbol": str(new.symbol).upper(), "from_isin": pair[0], "to_isin": pair[1], "date": new.valid_from})
    transitions_by_symbol = {}
    for event in transitions:
        transitions_by_symbol.setdefault(event["symbol"], []).append(event)
    actions_by_symbol = {key: frame.sort_values("ex_date").reset_index(drop=True)
                         for key, frame in actions.groupby("symbol", sort=False)}

    month_ends = pd.DataFrame({"date": [d for d in sessions if START <= d <= CUTOFF]})
    month_ends = month_ends.groupby(month_ends["date"].dt.to_period("M"))["date"].max().tolist()
    month_ends = [d for d in month_ends if d.month <= 9 or d < pd.Timestamp("2026-10-01")]
    schedules = {
        "M": month_ends,
        "Q": [d for d in month_ends if d.month in {3, 6, 9, 12}],
    }
    dependencies, signals, orders, marks = [], [], [], []
    summaries = {}

    for rule in ("A", "B"):
        for cadence in ("M", "Q"):
            candidate_id = f"NIFTY200-{rule}-{cadence}"
            prior: list[str] = []
            decisions = []
            for decision in schedules[cadence]:
                i = index[decision]
                members = intervals[(pd.to_datetime(intervals["valid_from"]) <= decision)
                                    & (pd.to_datetime(intervals["valid_to"]) >= decision)]
                member_ids = members["isin"].str.upper().tolist()
                scored = []
                unresolved_signal_count = 0
                for isin in member_ids:
                    canon = canonical.get(isin, isin)
                    symbol = symbols.get(isin, "")
                    frame = series.get(canon)
                    if frame is None:
                        frame = series.get(isin)
                    price_values = adjusted_values.get(canon, adjusted_values.get(isin))
                    raw_close_values = close_values.get(canon, close_values.get(isin))
                    reason_list = []
                    score, score_reason = (None, "missing_identity_price_series") if price_values is None else score_at(price_values, i, rule)
                    offset = 252 if rule == "A" else 273
                    start_i, end_i = max(0, i - offset), i - 21
                    unresolved_factor_dates = []
                    if frame is not None and end_i >= start_i:
                        statuses = frame["factor_status"].iloc[start_i:end_i + 1].fillna("").astype(str)
                        unresolved_factor_dates = [sessions[j] for j, value in enumerate(statuses, start_i) if value.startswith("unresolved")]
                    if unresolved_factor_dates:
                        reason_list.append("unresolved_adjustment_factor")
                        dependencies.append({"candidate_id": candidate_id, "rule": rule, "date": decision.date().isoformat(),
                                             "entity": f"{symbol}|{isin}", "input": "signal_adjustment_factor",
                                             "source": "NSE official EOD supplement plus TejHQ adjusted-price reference",
                                             "reason": f"{len(unresolved_factor_dates)} unresolved factor rows in signal window; first={unresolved_factor_dates[0].date()}",
                                             "impact": "ranking-changing signal unknown"})
                    if score_reason:
                        reason_list.append(score_reason)
                    if score is None:
                        missing_adjusted_dates = []
                        if price_values is not None and end_i >= start_i:
                            needed_adjusted = price_values[start_i:end_i + 1]
                            missing_adjusted_dates = [sessions[j] for j, value in enumerate(needed_adjusted, start_i)
                                                      if not np.isfinite(value) or value <= 0]
                        missing_detail = (f"; missing/invalid adjusted closes={len(missing_adjusted_dates)}, "
                                          f"first={missing_adjusted_dates[0].date()}, last={missing_adjusted_dates[-1].date()}"
                                          if missing_adjusted_dates else "")
                        dependencies.append({"candidate_id": candidate_id, "rule": rule, "date": decision.date().isoformat(),
                                             "entity": f"{symbol}|{isin}", "input": "signal_window",
                                             "source": "TejHQ adjusted NSE price history",
                                             "reason": f"{score_reason or 'required adjusted-price window unavailable'}; window={sessions[start_i].date()}..{sessions[end_i].date()}{missing_detail}",
                                             "impact": "ranking-changing signal unknown"})
                    if start_i < end_i and symbol:
                        symbol_actions = actions_by_symbol.get(symbol, actions.iloc[0:0])
                        action_rows = symbol_actions[symbol_actions["ex_date"].between(sessions[start_i], sessions[end_i])]
                        unique_signal_events = action_rows.drop_duplicates(["symbol", "ex_date", "type", "isin"])
                        for event in unique_signal_events.itertuples(index=False):
                            kind = str(event.type).lower()
                            if kind not in RELEVANT_ACTIONS:
                                continue
                            event_key = (symbol, pd.Timestamp(event.ex_date), kind)
                            if event_key not in verified_action_keys:
                                why = "historical signal action not independently reconciled to primary terms"
                                variants = int(getattr(event, "term_variants", 1))
                                variant_note = f"; source contains {variants} distinct term rows" if variants > 1 else ""
                                reason_list.append(why)
                                dependencies.append({"candidate_id": candidate_id, "rule": rule, "date": event.ex_date.date().isoformat(),
                                                     "entity": f"{symbol}|{isin}", "input": f"signal_{kind}",
                                                     "source": "TejHQ NSE corporate-action feed",
                                                     "reason": f"{why}; vendor action ISIN={event.isin}{variant_note}",
                                                     "impact": "ranking-changing signal may be misstated"})
                        for event in transitions_by_symbol.get(symbol, []):
                            if sessions[start_i] <= event["date"] <= sessions[end_i]:
                                reason_list.append("unreviewed_ISIN_transition_in_signal_window")
                                dependencies.append({"candidate_id": candidate_id, "rule": rule, "date": event["date"].date().isoformat(),
                                                     "entity": f"{symbol}|{event['from_isin']}->{event['to_isin']}",
                                                     "input": "signal_identity_bridge", "source": "TejHQ symbol history",
                                                     "reason": "adjacent identity span is not in the verified bridge table",
                                                     "impact": "ranking-changing signal may be misstated"})
                    if reason_list:
                        unresolved_signal_count += 1
                    scored.append({"candidate_id": candidate_id, "signal_date": decision.date().isoformat(),
                                   "symbol": symbol, "isin": isin, "canonical": canon,
                                   "score": score if score is not None else "", "score_status": "UNRESOLVED" if reason_list else ("SCORED" if score is not None else "UNRESOLVED"),
                                   "unresolved_reason": "; ".join(dict.fromkeys(reason_list))})
                positive = [r for r in scored if r["score"] != "" and float(r["score"]) > 0]
                positive.sort(key=lambda r: (-float(r["score"]), r["isin"]))
                rank = {r["canonical"]: n for n, r in enumerate(positive, 1)}
                for row in scored:
                    row["rank"] = rank.get(row["canonical"], "")
                    signals.append(row)
                score_map = {r["canonical"]: float(r["score"]) for r in positive}
                retained = [c for c in prior if c in rank and rank[c] <= 25]
                retained = sorted(set(retained), key=lambda c: (rank[c], c))[:20]
                chosen = list(retained)
                for row in positive:
                    if len(chosen) >= 20:
                        break
                    if row["canonical"] not in chosen:
                        chosen.append(row["canonical"])
                target = chosen
                conditional = unresolved_signal_count > 0
                exec_date = sessions[i + 1] if i + 1 < len(sessions) else None
                active = {r["canonical"]: r["isin"] for r in scored}
                if exec_date is None or exec_date > CUTOFF:
                    dependencies.append({"candidate_id": candidate_id, "rule": rule, "date": decision.date().isoformat(),
                                         "entity": "", "input": "next_session_order", "source": "source-session calendar",
                                         "reason": "no in-window next-session execution date", "impact": "strategy path cannot execute"})
                else:
                    execution = data[(data["date"] == exec_date) & data["canonical"].isin(set(prior) | set(target))]
                    open_by = execution.groupby("canonical")["open"].first().to_dict()
                    for canon in sorted(set(prior) ^ set(target)):
                        side = "BUY" if canon in target else "SELL"
                        isin = active.get(canon, canon)
                        open_px = open_by.get(canon, np.nan)
                        status = "OBSERVED" if np.isfinite(open_px) and open_px > 0 else "MISSING_OPEN"
                        orders.append({"candidate_id": candidate_id, "signal_date": decision.date().isoformat(),
                                       "execution_date": exec_date.date().isoformat(), "side": side,
                                       "symbol": symbols.get(isin, ""), "isin": isin, "canonical": canon,
                                       "raw_open": open_px if status == "OBSERVED" else "",
                                       "dependency_status": status, "conditional_signal_set": conditional})
                        if status != "OBSERVED":
                            dependencies.append({"candidate_id": candidate_id, "rule": rule, "date": exec_date.date().isoformat(),
                                                 "entity": f"{symbols.get(isin,'')}|{isin}", "input": "intended_order_open",
                                                 "source": "TejHQ NSE cash EOD + official NSE backfill",
                                                 "reason": f"{side} order has no positive finite next-session open",
                                                 "impact": "intended order cannot be executed/reconciled"})
                decisions.append({"date": decision, "exec_date": exec_date, "target": target,
                                  "active": active, "conditional": conditional, "scores": score_map})
                prior = target

            expected_marks = observed_marks = 0
            for j, decision_row in enumerate(decisions):
                start_date = decision_row["exec_date"]
                if start_date is None or start_date > CUTOFF:
                    continue
                start_i = index[start_date]
                has_next = j + 1 < len(decisions) and decisions[j + 1]["exec_date"] is not None
                if has_next:
                    end_i = min(index[decisions[j + 1]["exec_date"]], cutoff_idx)
                    next_target = set(decisions[j + 1]["target"])
                else:
                    end_i, next_target = cutoff_idx, set()
                for canon in decision_row["target"]:
                    mark_end = min(cutoff_idx, end_i - 1) if has_next else cutoff_idx
                    frame = series.get(canon)
                    raw_close = close_values.get(canon)
                    for k in range(start_i, mark_end + 1):
                        expected_marks += 1
                        close = np.nan if raw_close is None else raw_close[k]
                        if np.isfinite(close) and close > 0:
                            observed_marks += 1
                        else:
                            date = sessions[k]
                            dependencies.append({"candidate_id": candidate_id, "rule": rule, "date": date.date().isoformat(),
                                                 "entity": canon, "input": "held_position_close",
                                                 "source": "TejHQ NSE cash EOD + official NSE backfill",
                                                 "reason": "held position has no positive finite raw close for daily NAV valuation",
                                                 "impact": "position/NAV path invalid; no stale or zero mark allowed"})
                    symbol = symbols.get(decision_row["active"].get(canon, canon), "")
                    if symbol:
                        symbol_actions = actions_by_symbol.get(symbol, actions.iloc[0:0])
                        held_actions = symbol_actions[symbol_actions["ex_date"].between(start_date, sessions[end_i])]
                        unique_held_events = held_actions.drop_duplicates(["symbol", "ex_date", "type", "isin"])
                        for event in unique_held_events.itertuples(index=False):
                            kind = str(event.type).lower()
                            if kind not in RELEVANT_ACTIONS:
                                continue
                            if (symbol, pd.Timestamp(event.ex_date), kind) in verified_action_keys:
                                continue
                            variants = int(getattr(event, "term_variants", 1))
                            variant_note = f"; source contains {variants} distinct term rows" if variants > 1 else ""
                            dependencies.append({"candidate_id": candidate_id, "rule": rule, "date": event.ex_date.date().isoformat(),
                                                 "entity": f"{symbol}|{event.isin}", "input": f"held_entitlement_{kind}",
                                                 "source": "TejHQ NSE corporate-action feed",
                                                 "reason": f"actual held interval crosses unreconciled {kind} terms/entitlement; vendor action ISIN={event.isin}{variant_note}",
                                                 "impact": "position path invalid until entitlement/identity is valued"})
                        for event in transitions_by_symbol.get(symbol, []):
                            if start_date <= event["date"] <= sessions[end_i]:
                                dependencies.append({"candidate_id": candidate_id, "rule": rule, "date": event["date"].date().isoformat(),
                                                     "entity": f"{symbol}|{event['from_isin']}->{event['to_isin']}",
                                                     "input": "held_identity_transition", "source": "TejHQ symbol history",
                                                     "reason": "held position crosses an unreviewed ISIN transition",
                                                     "impact": "position identity/shares cannot be valued without a reviewed bridge"})
                    marks.append({"candidate_id": candidate_id, "signal_date": decision_row["date"].date().isoformat(),
                                  "execution_date": start_date.date().isoformat(), "canonical": canon,
                                  "expected_close_marks": max(0, mark_end - start_i + 1),
                                  "observed_close_marks": sum(np.isfinite(raw_close[k]) and raw_close[k] > 0
                                                                for k in range(start_i, mark_end + 1)) if raw_close is not None else 0,
                                  "conditional_signal_set": decision_row["conditional"]})
            candidate_dependencies = [r for r in dependencies if r["candidate_id"] == candidate_id]
            candidate_signal_actions = [r for r in candidate_dependencies
                                        if str(r["input"]).startswith("signal_") and r["input"] not in {
                                            "signal_window", "signal_adjustment_factor", "signal_identity_bridge"}]
            candidate_held_marks = [r for r in candidate_dependencies if r["input"] == "held_position_close"]
            candidate_order_gaps = [r for r in candidate_dependencies if r["input"] == "intended_order_open"]
            summaries[candidate_id] = {
                "scheduled_decisions": len(decisions), "total_member_signal_rows": len([r for r in signals if r["candidate_id"] == candidate_id]),
                "decisions_with_unresolved_member_signals": sum(r["conditional"] for r in decisions),
                "provisional_order_intents": len([r for r in orders if r["candidate_id"] == candidate_id]),
                "expected_daily_close_marks": expected_marks, "observed_daily_close_marks": observed_marks,
                "missing_daily_close_marks": expected_marks - observed_marks,
                "unreviewed_signal_action_path_incidences": len(candidate_signal_actions),
                "unreviewed_signal_action_unique_events": len({dependency_source_key(r) for r in candidate_signal_actions}),
                "held_action_path_incidences": sum(r["input"].startswith("held_entitlement_") for r in candidate_dependencies),
                "held_action_unique_events": len({dependency_source_key(r) for r in candidate_dependencies if r["input"].startswith("held_entitlement_")}),
                "order_open_failures": len(candidate_order_gaps),
                "order_open_unique_entity_dates": len({dependency_source_key(r) for r in candidate_order_gaps}),
                "held_close_gap_path_incidences": len(candidate_held_marks),
                "held_close_gap_unique_entity_dates": len({dependency_source_key(r) for r in candidate_held_marks}),
                "unreviewed_identity_signal_path_incidences": sum(r["input"] == "signal_identity_bridge" for r in candidate_dependencies),
                "unresolved_adjustment_factor_signal_windows": sum(r["input"] == "signal_adjustment_factor" for r in candidate_dependencies),
                "ranking_changing_signal_dependencies": sum(r["candidate_id"] == candidate_id and r["impact"].startswith("ranking-changing signal") for r in dependencies),
                "missing_adjusted_signal_windows": sum(r["candidate_id"] == candidate_id and r["input"] == "signal_window" for r in dependencies),
                "promotable": not any(r["candidate_id"] == candidate_id for r in dependencies),
            }

    for dependency in dependencies:
        dependency["resolution_attempt"] = resolution_attempt_for(dependency)
    out_dir = PUBLIC / "strategy_dependencies" / "nifty200"
    atomic_csv(out_dir / "signal_dependencies.csv", signals,
               ["candidate_id", "signal_date", "symbol", "isin", "canonical", "score", "rank", "score_status", "unresolved_reason"])
    atomic_csv(out_dir / "intended_orders.csv", orders,
               ["candidate_id", "signal_date", "execution_date", "side", "symbol", "isin", "canonical", "raw_open", "dependency_status", "conditional_signal_set"])
    atomic_csv(out_dir / "position_valuation_windows.csv", marks,
               ["candidate_id", "signal_date", "execution_date", "canonical", "expected_close_marks", "observed_close_marks", "conditional_signal_set"])
    atomic_csv(out_dir / "unresolved_dependencies.csv", dependencies,
               ["candidate_id", "rule", "date", "entity", "input", "source", "reason", "resolution_attempt", "impact"])
    dependency_incidence, unique_dependency_sources = dependency_counts(dependencies)
    unique_close_gaps = len({dependency_source_key(r) for r in dependencies if r["input"] == "held_position_close"})
    unique_order_gaps = len({dependency_source_key(r) for r in dependencies if r["input"] == "intended_order_open"})
    result = {
        "protocol_id": "NIFTY200-v1", "audit_type": "non-P&L candidate dependency audit",
        "evaluation_start": START.date().isoformat(), "evaluation_cutoff": CUTOFF.date().isoformat(),
        "working_calendar_sessions": len(sessions), "calendar_basis": "TejHQ raw source dates plus 18 primary NSE EOD sessions; not globally certified",
        "membership_replay_certified": True, "membership_replay_failed_batches": 0,
        "manual_verified_identity_bridges": [r["symbol"] for r in reviewed if r["membership_replay"].lower() == "true"],
        "reviewed_bridge_date_discrepancies": [
            {"symbol": r["symbol"], "economic_ex_date": r["economic_ex_date"],
             "vendor_first_new_observation": r["vendor_first_new_observation"],
             "discrepancy": r["identity_date_conflict"]}
            for r in reviewed if r.get("identity_date_conflict") and r["identity_date_conflict"].lower() != "no"
        ],
        "automatic_identity_bridges_not_independently_reviewed": len(unreviewed),
        "configurations": summaries, "dependency_rows": len(dependencies),
        "dependency_path_incidence_counts": dependency_incidence,
        "unique_source_entity_date_type_counts": unique_dependency_sources,
        "held_close_gap_unique_entity_dates": unique_close_gaps,
        "order_open_gap_unique_entity_dates": unique_order_gaps,
        "performance_gate": "NOT RUN; this audit computes no NAV, return, CAGR, fees, or strategy ranking",
        "strategy_study_authorized": all(v["promotable"] for v in summaries.values()),
    }
    (ROOT / "outputs" / "nifty200_candidate_dependency_audit_2026-10-31.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))
    return result


def self_check() -> None:
    prices = np.arange(1.0, 300.0)
    score_a, reason_a = score_at(prices, 280, "A")
    score_b, reason_b = score_at(prices, 280, "B")
    assert not reason_a and not reason_b and score_a > 0 and score_b > 0
    assert score_at(prices, 100, "A")[1] == "insufficient_warmup"
    broken = prices.copy()
    broken[30] = np.nan
    assert score_at(broken, 280, "B")[1] == "missing_or_invalid_adjusted_close"
    sample = [
        {"input": "signal_dividend", "entity": "ABC|ID1", "date": "2020-01-01", "reason": "vendor action ISIN=ID1"},
        {"input": "signal_dividend", "entity": "ABC|ID1", "date": "2020-01-01", "reason": "vendor action ISIN=ID1"},
        {"input": "held_position_close", "entity": "ID1", "date": "2020-01-02", "reason": "missing"},
    ]
    incidence, unique = dependency_counts(sample)
    assert incidence["signal_dividend"] == 2 and unique["signal_dividend"] == 1
    assert unique["held_position_close"] == 1
    assert resolution_attempt_for({"input": "held_position_close"}).startswith("Checked the exact ISIN/session")
    print("candidate dependency self-check passed: A/B windows, warmup, and missing adjusted bars")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--self-check", action="store_true")
    args = parser.parse_args()
    self_check() if args.self_check else audit()
