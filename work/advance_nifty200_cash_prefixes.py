"""Correct the first source-backed signals and run their actual cash-account prefixes."""

from __future__ import annotations

import json
import hashlib
import sys
import tempfile
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow.dataset as ds

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "work"))
import audit_strategy_dependencies as audit
import upstox_quant as cash_engine

DETAIL = audit.PUBLIC / "strategy_dependencies" / "nifty200"
OUT = ROOT / "outputs" / "nifty200_sequential_account_cycle2_2026-11-02.json"
LOCAL = DETAIL / "sequential_cash_prefixes_cycle2_2026-11-02"
CAPITAL = 1_000_000.0
SLIPPAGE_BPS = 50.0
AGEL_ISIN = "INE364U01010"
AGEL_RATIO = Decimal("761") / Decimal("1000")
DIVIDEND_DELAY_DAYS = 30

# Ratios and full subscription prices come from the registered source protocol.
RIGHTS = {
    ("CANBK", "2017-02-17"): [(1 / 10, 207.0)],
    ("INDHOTEL", "2017-10-04"): [(1 / 5, 75.0)],
    ("KARURVYSYA", "2017-10-12"): [(1 / 6, 76.0)],
    ("TATASTEEL", "2018-01-31"): [(4 / 25, 510.0), (2 / 25, 615.0)],
    ("PEL", "2018-01-31"): [(1 / 23, 2380.0)],
}
DIVIDENDS = {
    ("COLPAL", "2017-12-18"): 4.0,
    ("ENGINERSIN", "2017-09-11"): 0.50,
}
IDFC_INFERENCE = {
    "vendor_symbol": "IDFCBANK", "vendor_isin": "INE092T01019",
    "debt_isin": "INE092T08352", "classification": "supported_debt_event_inference",
}
CONFIGURATIONS = ("NIFTY200-A-M", "NIFTY200-A-Q", "NIFTY200-B-M", "NIFTY200-B-Q")


def source_child_series() -> pd.Series:
    history = pd.read_parquet(audit.PUBLIC / "tejhq" / "symbol_history" / "nse.parquet")
    isins = history.loc[history["symbol"].astype(str).str.upper().eq("RHFL"), "isin"].dropna().astype(str).unique()
    if len(isins) != 1:
        raise ValueError(f"RHFL needs one dated identity; found {isins.tolist()}")
    files = sorted(audit.RAW_DIR.glob("year=*/nse_*.parquet"))
    raw = ds.dataset([str(path) for path in files], format="parquet").to_table(
        columns=["date", "isin", "series", "close"], filter=ds.field("isin").isin(isins.tolist())
    ).to_pandas()
    raw["date"] = pd.to_datetime(raw["date"]).dt.normalize()
    raw = raw.loc[raw["series"].isin({"EQ", "BE"})].drop_duplicates("date")
    return pd.to_numeric(raw.set_index("date")["close"], errors="coerce").sort_index()


def setup():
    cache_manifest = audit.verify_signal_cache()
    sessions, intervals, data, actions, symbols, reviewed, unreviewed, canonical, history = audit.load_data()
    signals = pd.read_csv(DETAIL / "signal_dependencies.csv", dtype=str).fillna("")
    signals["score"] = pd.to_numeric(signals["score"], errors="coerce")
    signals["rank"] = pd.to_numeric(signals["rank"], errors="coerce")
    signals["unresolved_dependency_keys"] = signals["unresolved_dependency_keys"].map(json.loads)
    dependency_rows = pd.read_csv(DETAIL / "unresolved_dependencies.csv", dtype=str).fillna("")
    dependency_records = {row["dependency_key"]: row.to_dict() for _, row in dependency_rows.iterrows()}
    if not all(audit.dependency_key(row) == key for key, row in dependency_records.items()):
        raise ValueError("unresolved dependency key does not match its pinned source record")
    index = {day: i for i, day in enumerate(sessions)}
    by_canonical = {}
    for name, group in data.groupby("canonical", sort=False):
        frame = group[["date", "close", "adj_close", "adj_factor_cumulative"]]
        frame = frame.sort_values("date").drop_duplicates("date").set_index("date").reindex(sessions)
        by_canonical[name] = frame
    account_data = data[["date", "isin", "symbol", "canonical", "open", "close"]].copy()
    return sessions, account_data, actions, signals, index, by_canonical, source_child_series(), dependency_records, cache_manifest


def interval_return(parent: pd.DataFrame, child: pd.Series, start: pd.Timestamp,
                    end: pd.Timestamp) -> float:
    demerger = pd.Timestamp("2017-09-05")
    dividend_date = pd.Timestamp("2017-09-21")
    if start not in parent.index or end not in parent.index:
        raise ValueError("RELCAPITAL endpoint missing from the source-session calendar")
    p0, p1 = float(parent.at[start, "close"]), float(parent.at[end, "close"])
    if not np.isfinite([p0, p1]).all() or min(p0, p1) <= 0:
        raise ValueError("RELCAPITAL endpoint close missing or invalid")
    initial = p0
    q_child = 0.0
    if start < demerger <= end:
        q_child = 1.0
    q_parent = 1.0
    if start < dividend_date <= end:
        ex_close = parent.at[dividend_date, "close"]
        if not np.isfinite(ex_close) or ex_close <= 0:
            raise ValueError("RELCAPITAL dividend ex-date close missing")
        q_parent += 10.50 / float(ex_close)
    final = q_parent * p1
    if q_child:
        child_close = child.get(end, np.nan)
        if not np.isfinite(child_close) or child_close <= 0:
            raise ValueError(f"RHFL endpoint mark missing on {end.date()}")
        final += float(child_close)
    return final / initial - 1.0


def score_with_corrections(candidate: str, day: pd.Timestamp, row: pd.Series,
                           sessions: list[pd.Timestamp], index: dict, series_by_canonical: dict,
                           raw_child: pd.Series, event_log: list[dict],
                           free_right: tuple[str, str] | None = None) -> tuple[float | None, dict]:
    symbol, canon = str(row["symbol"]).upper(), str(row["canonical"])
    if symbol == "RELCAPITAL":
        parent = series_by_canonical[canon]
        i = index[day]
        end = sessions[i - 21]
        start12 = sessions[i - 252]
        ret12 = interval_return(parent, raw_child, start12, end)
        if candidate.endswith("-Q") or candidate.endswith("-M"):
            if candidate.split("-")[1] == "A":
                return ret12, {"method": "source_total_wealth_parent_plus_1_RHFL_and_reinvested_10_50_dividend",
                               "ret12": ret12, "score_status": "VALID_SCORE"}
            start6 = sessions[i - 126]
            ret6 = interval_return(parent, raw_child, start6, end)
            numerator = (ret6 + ret12) / 2
            return None, {"method": "B_volatility_not_calculated_missing_RHFL_prelisting_daily_marks",
                          "ret6": ret6, "ret12": ret12, "return_numerator": numerator,
                          "selection_bound": "NONPOSITIVE" if numerator <= 0 else "MATERIAL_UNKNOWN",
                          "score_status": "UNKNOWN_DATA"}

    frame = series_by_canonical[canon]
    prices = pd.to_numeric(frame["adj_close"], errors="coerce").to_numpy(dtype=float).copy()
    raw_close = pd.to_numeric(frame["close"], errors="coerce").to_numpy(dtype=float)
    factors = pd.to_numeric(frame["adj_factor_cumulative"], errors="coerce").to_numpy(dtype=float)
    i = index[day]
    offset = 252 if candidate.split("-")[1] == "A" else 273
    first, last = i - offset, i - 21
    corrections = []
    for (event_symbol, date_text), tranches in RIGHTS.items():
        if symbol != event_symbol:
            continue
        ex = pd.Timestamp(date_text)
        ex_i = index.get(ex)
        if ex_i is None or not first <= ex_i <= last:
            continue
        if not np.isfinite(raw_close[ex_i - 1]) or not np.isfinite(factors[[ex_i - 1, ex_i]]).all():
            raise ValueError(f"{symbol} rights source rows missing at {ex.date()}")
        ratio = sum(r for r, _ in tranches)
        cash = sum(r * (0.0 if free_right == (symbol, date_text) else issue) for r, issue in tranches)
        prior = raw_close[ex_i - 1]
        terp = (prior + cash) / (1 + ratio)
        expected = prior / terp
        observed = factors[ex_i] / factors[ex_i - 1]
        adjustment = expected / observed
        prices[ex_i:] *= adjustment
        event = {"candidate_id": candidate, "signal_date": day.date().isoformat(), "symbol": symbol,
                 "ex_date": date_text, "event": "rights", "prior_raw_close_inr": prior,
                 "ratio_new_per_old": ratio, "full_subscription_cash_per_old_share_inr": cash,
                 "terp_inr": terp, "provider_factor_multiplier": observed,
                 "source_factor_multiplier": expected, "applied_signal_multiplier": adjustment}
        corrections.append(event)
    for (event_symbol, date_text), amount in DIVIDENDS.items():
        if symbol != event_symbol:
            continue
        ex = pd.Timestamp(date_text)
        ex_i = index.get(ex)
        if ex_i is None or not first <= ex_i <= last:
            continue
        if not np.isfinite(raw_close[ex_i - 1]) or not np.isfinite(factors[[ex_i - 1, ex_i]]).all():
            raise ValueError(f"{symbol} dividend source rows missing at {ex.date()}")
        prior = raw_close[ex_i - 1]
        expected = prior / (prior - amount)
        observed = factors[ex_i] / factors[ex_i - 1]
        adjustment = expected / observed
        prices[ex_i:] *= adjustment
        corrections.append({"candidate_id": candidate, "signal_date": day.date().isoformat(), "symbol": symbol,
                            "ex_date": date_text, "event": "dividend", "prior_raw_close_inr": prior,
                            "cash_per_share_inr": amount, "provider_factor_multiplier": observed,
                            "source_factor_multiplier": expected, "applied_signal_multiplier": adjustment})
    rule = candidate.split("-")[1]
    baseline_prices = pd.to_numeric(frame["adj_close"], errors="coerce").to_numpy(dtype=float)
    baseline, baseline_reason = audit.score_at(baseline_prices, i, rule)
    if baseline_reason or not np.isclose(baseline, float(row["score"]), rtol=1e-8, atol=1e-10):
        raise AssertionError(f"source score does not reproduce for {candidate} {symbol} {day.date()}")
    value, reason = audit.score_at(prices, i, rule)
    if reason:
        return None, {"method": reason, "score_status": "UNKNOWN_DATA"}
    event_log.extend(corrections)
    end = i - 21
    base_vol = corrected_vol = None
    if rule == "B":
        base_returns = np.diff(np.log(baseline_prices[i - 273:end + 1]))
        corrected_returns = np.diff(np.log(prices[i - 273:end + 1]))
        base_vol = float(np.std(base_returns, ddof=1) * np.sqrt(252) * 100)
        corrected_vol = float(np.std(corrected_returns, ddof=1) * np.sqrt(252) * 100)
    free_value = None
    free_vol = None
    if free_right is None:
        event_rights = next(((sym, day_text) for (sym, day_text) in RIGHTS
                             if sym == symbol and index.get(pd.Timestamp(day_text), -1) in range(first, last + 1)), None)
        if event_rights:
            free_value, free_details = score_with_corrections(candidate, day, row, sessions, index,
                                                              series_by_canonical, raw_child, [],
                                                              free_right=event_rights)
            free_vol = free_details.get("annualized_volatility_pct")
    return value, {"method": "registered_source_TER P_and_dividend_factor", "corrections": corrections,
                   "score_status": "VALID_SCORE", "free_right_score_sensitivity": free_value,
                   "annualized_volatility_pct": corrected_vol,
                   "baseline_annualized_volatility_pct": base_vol,
                   "corrected_annualized_volatility_pct": corrected_vol,
                   "free_right_annualized_volatility_pct": free_vol,
                   "volatility_delta_pct": corrected_vol - base_vol if base_vol is not None else None}


def exact_dependency_resolutions(candidate: str, row: pd.Series, details: dict,
                                 dependency_records: dict[str, dict]) -> tuple[list[str], list[dict]]:
    resolved = []
    unmatched = []
    corrections = details.get("corrections", [])
    for key in row.get("unresolved_dependency_keys", []):
        dependency = dependency_records.get(key)
        if dependency is None:
            unmatched.append({"key": key, "reason": "dependency key missing from pinned dependency ledger"})
            continue
        symbol = str(dependency.get("entity", "")).split("|", 1)[0].upper()
        kind = str(dependency.get("input", ""))
        event_date = str(dependency.get("date", ""))
        correction_match = any(
            str(item.get("symbol", "")).upper() == symbol
            and str(item.get("ex_date", "")) == event_date
            and (kind == f"signal_{item.get('event', '')}"
                 or (kind == "signal_adjustment_factor" and item.get("event") in {"rights", "dividend"}))
            for item in corrections
        )
        relcapital_match = (
            symbol == "RELCAPITAL" and kind == "signal_other" and event_date == "2017-09-05"
            and (details.get("method", "").startswith("source_total_wealth_parent_plus_1_RHFL")
                 or (details.get("selection_bound") == "NONPOSITIVE"
                     and details.get("method", "").startswith("B_volatility_not_calculated_missing_RHFL")))
        )
        idfc_match = (
            symbol == IDFC_INFERENCE["vendor_symbol"] and kind == "signal_other"
            and event_date == "2017-12-14" and "INE092T01019" in str(dependency.get("entity", ""))
        )
        if correction_match or relcapital_match or idfc_match:
            resolved.append(key)
        else:
            unmatched.append({"key": key, "input": kind, "date": event_date,
                              "entity": dependency.get("entity", ""),
                              "reason": dependency.get("reason", "unresolved source dependency")})
    return resolved, unmatched


def choose_target(candidate: str, day: pd.Timestamp, prior: list[str], sessions: list[pd.Timestamp], signals: pd.DataFrame,
                  index: dict, series_by_canonical: dict, child: pd.Series,
                  correction_log: list[dict], dependency_records: dict[str, dict] | None = None) -> dict:
    dependency_records = dependency_records or {}
    rows = signals.loc[signals["candidate_id"].eq(candidate)
                       & signals["signal_date"].eq(day.date().isoformat())].copy()
    entries, unresolved, selection_bounds = [], [], []
    for _, row in rows.iterrows():
        status = row["score_status"]
        score = row["score"]
        details = {}
        if status == "VALID_SCORE":
            score = float(score)
        elif status == "RULE_INELIGIBLE":
            continue
        elif np.isfinite(score):
            score, details = score_with_corrections(candidate, day, row, sessions, index, series_by_canonical,
                                                    child, correction_log)
            resolved_keys, unmatched_keys = exact_dependency_resolutions(candidate, row, details, dependency_records)
            if details.get("selection_bound") == "NONPOSITIVE" and score is None:
                if resolved_keys and not unmatched_keys:
                    selection_bounds.append({"symbol": row["symbol"], "reason": details["method"],
                                             "return_numerator": details["return_numerator"],
                                             "selection_bound": "NONPOSITIVE; cannot displace a positive target",
                                             "resolved_dependency_keys": resolved_keys})
                    continue
                unresolved.append({"symbol": row["symbol"], "reason": row["unresolved_reason"],
                                   "unmatched_dependency_keys": unmatched_keys, **details})
                continue
            if details.get("score_status") == "UNKNOWN_DATA" or unmatched_keys or not resolved_keys:
                unresolved.append({"symbol": row["symbol"], "reason": row["unresolved_reason"],
                                   "unmatched_dependency_keys": unmatched_keys, **details})
                continue
            details["resolved_dependency_keys"] = resolved_keys
        else:
            unresolved.append({"symbol": row["symbol"], "reason": row["unresolved_reason"],
                               "unmatched_dependency_keys": [
                                   {"key": key, **dependency_records.get(key, {"reason": "dependency key missing"})}
                                   for key in row.get("unresolved_dependency_keys", [])]})
            continue
        if row["symbol"] == "IDFCBANK" and status == "UNKNOWN_DATA":
            details["classification"] = IDFC_INFERENCE
            details["classification_caveat"] = "exact original vendor event notice not located; event/debt match remains an inference"
        if status == "UNKNOWN_DATA" and np.isfinite(row["score"]):
            details["vendor_score"] = float(row["score"])
            details["corrected_score"] = float(score)
            details["score_delta"] = float(score) - float(row["score"])
            for event in details.get("corrections", []):
                event["vendor_score"] = float(row["score"])
                event["corrected_score"] = float(score)
                event["score_delta"] = float(score) - float(row["score"])
                event["free_right_score_sensitivity"] = details.get("free_right_score_sensitivity")
        entries.append({"canonical": row["canonical"], "symbol": row["symbol"], "isin": row["isin"],
                        "score": float(score), "status": status, **details})
    positive = sorted((r for r in entries if r["score"] > 0), key=lambda r: (-r["score"], r["isin"]))
    rank = {r["canonical"]: n for n, r in enumerate(positive, 1)}
    retained = sorted({name for name in prior if name in rank and rank[name] <= 25},
                      key=lambda name: (rank[name], name))[:20]
    target = list(retained)
    for row in positive:
        if len(target) == 20:
            break
        if row["canonical"] not in target:
            target.append(row["canonical"])
    if len(target) != 20:
        unresolved.append({"reason": f"only {len(target)} source-supported positive slots"})
    cutoff = positive[19]["score"] if len(positive) >= 20 else None
    certified = not unresolved and len(target) == 20
    source_exceptions = [{"symbol": r["symbol"], "vendor_score": r.get("vendor_score"),
                          "corrected_score": r.get("corrected_score", r["score"]),
                          "score_delta": r.get("score_delta", 0.0),
                          "free_right_score_sensitivity": r.get("free_right_score_sensitivity"),
                          "baseline_annualized_volatility_pct": r.get("baseline_annualized_volatility_pct"),
                          "corrected_annualized_volatility_pct": r.get("corrected_annualized_volatility_pct"),
                          "free_right_annualized_volatility_pct": r.get("free_right_annualized_volatility_pct"),
                          "volatility_delta_pct": r.get("volatility_delta_pct"),
                          "free_right_sensitivity_crosses_cutoff": bool(
                              cutoff is not None and r.get("free_right_score_sensitivity") is not None
                              and r["free_right_score_sensitivity"] >= cutoff),
                          "classification": r.get("classification"),
                          "classification_caveat": r.get("classification_caveat"),
                          "resolved_dependency_keys": r.get("resolved_dependency_keys", []),
                          "corrections": [{k: v for k, v in event.items() if k not in {"candidate_id", "signal_date"}}
                                          for event in r.get("corrections", [])]}
                         for r in entries if r["status"] == "UNKNOWN_DATA"]
    ineligible = rows.loc[rows["score_status"].eq("RULE_INELIGIBLE"),
                          ["symbol", "isin", "unresolved_reason"]].to_dict(orient="records")
    return {"candidate_id": candidate, "signal_date": day.date().isoformat(),
            "target_status": "CERTIFIED_UNDER_REGISTERED_SOURCE_CORRECTIONS" if certified else "BLOCKED",
            "signal_rows": int(len(rows)), "rule_ineligible_count": int(rows["score_status"].eq("RULE_INELIGIBLE").sum()),
            "resolved_source_exception_count": sum(r["status"] == "UNKNOWN_DATA" for r in entries),
            "twentieth_positive_score": cutoff, "positive_known_scores": len(positive),
            "ineligible": ineligible, "source_resolved_exceptions": source_exceptions,
            "retained_from_prior": [next(r["symbol"] for r in entries if r["canonical"] == name) for name in retained],
            "selected": [{"symbol": next(r["symbol"] for r in entries if r["canonical"] == name),
                          "canonical": name, "score": next(r["score"] for r in entries if r["canonical"] == name)}
                         for name in target],
            "selection_bounds": selection_bounds, "unresolved": unresolved,
            "ranking_policy": "positive score descending; ISIN ascending tie-break; retain prior names ranked 1-25 then fill to 20"}


def action_gate(candidate: str, targets_by_signal: dict, actions: pd.DataFrame,
                data: pd.DataFrame, sessions: list[pd.Timestamp], start: date, end: date,
                claim_scenario: str = "base"):
    wanted = set().union(*(set(items) for items in targets_by_signal.values()))
    action_rows = actions.loc[actions["ex_date"].between(pd.Timestamp(start), pd.Timestamp(end))].copy()
    distributions, payment_dates, claim_events, blockers = [], {}, [], []
    active_targets = []
    for signal_text, target in targets_by_signal.items():
        signal_index = sessions.index(pd.Timestamp(signal_text))
        if signal_index + 1 < len(sessions):
            active_targets.append((sessions[signal_index + 1], set(target)))
    for _, event in action_rows.iterrows():
        kind = str(event["type"]).lower()
        if kind in {"agm", "meeting"}:
            continue
        event_date = pd.Timestamp(event["ex_date"]).normalize()
        # The schedule limits identity checks; _simulate reads the actual shares before ex-date orders.
        active = [(execution, target) for execution, target in active_targets if execution < event_date]
        if not active:
            continue
        held_before_open = max(active, key=lambda item: item[0])[1]
        symbol = str(event.get("resolved_symbol", "")).upper()
        vendor_symbol = str(event.get("symbol", "")).upper()
        event_isin = str(event.get("isin", "")).upper()
        by_symbol = set(data.loc[data["symbol"].eq(symbol or vendor_symbol), "canonical"].dropna())
        by_isin = set(data.loc[data["isin"].eq(event_isin), "canonical"].dropna())
        identities = (by_symbol | by_isin) & held_before_open
        if not identities:
            continue
        if len(identities) != 1 or (symbol and by_symbol and by_isin and by_symbol.isdisjoint(by_isin)):
            blockers.append({"date": event_date.date().isoformat(), "symbol": vendor_symbol or symbol,
                             "event": kind, "entity": event_isin,
                             "reason": "relevant corporate-action identity is ambiguous against the pre-open held position",
                             "held_candidates": sorted(identities), "input": "action_identity"})
            continue
        canon = next(iter(identities))
        if not symbol and len(by_isin) != 1:
            blockers.append({"date": event_date.date().isoformat(), "symbol": vendor_symbol,
                             "canonical": canon, "event": kind, "entity": event_isin,
                             "reason": "relevant action has no verified date-valid identity",
                             "input": "action_identity"})
            continue
        if kind == "dividend":
            amount = pd.to_numeric(pd.Series([event.get("cash_amount")]), errors="coerce").iloc[0]
            if not np.isfinite(amount) or amount < 0:
                blockers.append({"date": event_date.date().isoformat(), "symbol": vendor_symbol,
                                 "canonical": canon, "event": kind, "entity": event_isin,
                                 "reason": "held dividend has no source-supported non-negative amount",
                                 "input": "dividend_entitlement"})
                continue
            distribution = (canon, event_date.date(), float(amount))
            distributions.append(distribution)
            payment_dates[distribution[:2]] = event_date.date() + timedelta(days=DIVIDEND_DELAY_DAYS)
            continue
        if (vendor_symbol == "ADANIENT" and event_date == pd.Timestamp("2018-04-05")
                and "scheme of arrangement" in str(event.get("raw_subject", "")).lower()):
            parent_rows = data.loc[data["canonical"].eq(canon)].drop_duplicates("date").set_index("date")
            prior_days = [day for day in sessions if day < event_date]
            cum_date = prior_days[-1]
            cum_close = pd.to_numeric(pd.Series([parent_rows["close"].get(cum_date, np.nan)]), errors="coerce").iloc[0]
            ex_close = pd.to_numeric(pd.Series([parent_rows["close"].get(event_date, np.nan)]), errors="coerce").iloc[0]
            if not np.isfinite([cum_close, ex_close]).all() or min(cum_close, ex_close) <= 0:
                blockers.append({"date": event_date.date().isoformat(), "symbol": vendor_symbol,
                                 "canonical": canon, "event": kind, "entity": event_isin,
                                 "reason": "AGEL detached claim needs observed AEL raw closes on 2018-04-04 and 2018-04-05",
                                 "input": "claim_mark"})
                continue
            child_name = "INE364U01010"
            child_rows = data.loc[data["isin"].eq(AGEL_ISIN)]
            child_names = child_rows["canonical"].dropna().astype(str).unique()
            listing_date = pd.Timestamp("2018-06-18")
            listing_close = child_rows.loc[child_rows["date"].eq(listing_date), "close"].dropna()
            if len(child_names) != 1 or listing_close.empty:
                blockers.append({"date": listing_date.date().isoformat(), "symbol": "ADANIGREEN",
                                 "canonical": AGEL_ISIN, "event": "detached_claim_listing_mark",
                                 "reason": "AGEL listing-session raw close or exact ISIN identity is missing",
                                 "input": "claim_mark"})
                continue
            child_name = child_names[0]
            later_sessions = [day for day in sessions if day > listing_date]
            if not later_sessions:
                blockers.append({"date": listing_date.date().isoformat(), "symbol": "ADANIGREEN",
                                 "canonical": child_name, "event": "detached_claim_disposal",
                                 "reason": "no next source session after AGEL listing",
                                 "input": "claim_disposal"})
                continue
            sale_date = later_sessions[0]
            child_open = child_rows.loc[child_rows["date"].eq(sale_date), "open"].dropna()
            if child_open.empty:
                blockers.append({"date": sale_date.date().isoformat(), "symbol": "ADANIGREEN",
                                 "canonical": child_name, "event": "detached_claim_disposal",
                                 "reason": "first post-listing raw regular-session open is missing",
                                 "input": "claim_disposal"})
                continue
            detached_mark = (float(cum_close) - float(ex_close)) / float(AGEL_RATIO)
            if detached_mark < 0:
                blockers.append({"date": event_date.date().isoformat(), "symbol": vendor_symbol,
                                 "canonical": canon, "event": "detached_claim_mark",
                                 "reason": "parent cum/ex price difference implies a negative detached mark",
                                 "input": "claim_mark", "cum_close": float(cum_close), "ex_close": float(ex_close)})
                continue
            claim_events.append({"parent_symbol": canon, "child_symbol": child_name,
                                 "ex_date": event_date.date(), "listing_date": listing_date.date(),
                                 "sale_date": sale_date.date(), "ratio": str(AGEL_RATIO),
                                 "detached_unit_mark": detached_mark if claim_scenario == "base" else 0.0,
                                 "base_detached_unit_mark": detached_mark,
                                 "scenario": claim_scenario, "event_isin": event_isin,
                                 "cum_date": cum_date.date().isoformat(),
                                 "cum_close_raw": float(cum_close), "ex_close_raw": float(ex_close),
                                 "listing_close_raw": float(listing_close.iloc[0]),
                                 "disposal_open_raw": float(child_open.iloc[0])})
            continue
        blockers.append({"date": event_date.date().isoformat(), "symbol": vendor_symbol or symbol,
                         "canonical": canon, "event": kind, "entity": event_isin,
                         "reason": "held-position entitlement or share conversion is not modeled by the cash engine",
                         "source_subject": str(event.get("raw_subject", "")), "input": "held_entitlement"})
    blockers.sort(key=lambda row: (row["date"], row.get("symbol", "")))
    return distributions, payment_dates, claim_events, blockers


def run_account(candidate: str, signals: pd.DataFrame, schedules: list[dict],
                data: pd.DataFrame, actions: pd.DataFrame, sessions: list[pd.Timestamp],
                end_day: str, valuation_scenario: str = "base", slippage_bps: float = SLIPPAGE_BPS,
                signal_blocker: dict | None = None) -> dict:
    if not schedules:
        ending_day = pd.Timestamp(end_day).date().isoformat()
        return {"candidate_id": candidate, "status": "NO_EXECUTION_UNRESOLVED_FIRST_TARGET",
                "actual_order_count": 0, "first_material_blocker": signal_blocker,
                "valuation_scenario": valuation_scenario, "slippage_bps_per_side": slippage_bps,
                "valid_through": ending_day, "starting_capital_inr": CAPITAL,
                "ending_nav_inr": CAPITAL, "ending_cash_inr": CAPITAL, "ending_invested_inr": 0.0,
                "ending_cash_receivable_inr": 0.0, "ending_locked_claim_inr": 0.0,
                "max_drawdown_pct": 0.0, "turnover_inr": 0.0, "fees_inr": 0.0,
                "cagr": "NOT REPORTED: no certified order; cash waiting path only"}
    targets_by_signal = {item["signal_date"]: [r["canonical"] for r in item["selected"]] for item in schedules}
    first_signal_index = sessions.index(pd.Timestamp(schedules[0]["signal_date"]))
    first_fill_index = first_signal_index + 1
    if first_fill_index >= len(sessions):
        return {"candidate_id": candidate, "status": "BLOCKED_BEFORE_FIRST_FILL", "actual_order_count": 0,
                "first_material_blocker": {"date": schedules[0]["signal_date"], "input": "next_session_order",
                                           "reason": "no source-session execution date follows the first signal"},
                "valuation_scenario": valuation_scenario, "slippage_bps_per_side": slippage_bps,
                "valid_through": pd.Timestamp(end_day).date().isoformat(), "starting_capital_inr": CAPITAL,
                "ending_nav_inr": CAPITAL, "ending_cash_inr": CAPITAL, "ending_invested_inr": 0.0,
                "ending_cash_receivable_inr": 0.0, "ending_locked_claim_inr": 0.0,
                "max_drawdown_pct": 0.0, "turnover_inr": 0.0, "fees_inr": 0.0}
    first_fill = sessions[first_fill_index].date()
    distributions, payment_dates, claim_events, blockers = action_gate(
        candidate, targets_by_signal, actions, data, sessions, first_fill,
        pd.Timestamp(end_day).date(), valuation_scenario,
    )
    effective_end = pd.Timestamp(end_day)
    if blockers:
        blocker_date = pd.Timestamp(blockers[0]["date"])
        stop_index = sessions.index(blocker_date)
        effective_end = min(effective_end, sessions[stop_index - 1])
    wanted = set().union(*map(set, targets_by_signal.values())) | {event["child_symbol"] for event in claim_events}
    wanted = sorted(wanted)
    quote_window = data["date"].between(pd.Timestamp("2018-01-01"), effective_end)
    quotes = data.loc[quote_window & data["canonical"].isin(wanted),
                      ["date", "canonical", "open", "close"]]
    opens = quotes.pivot_table(index="date", columns="canonical", values="open", aggfunc="first").reindex(
        index=sessions, columns=wanted)
    closes = quotes.pivot_table(index="date", columns="canonical", values="close", aggfunc="first").reindex(
        index=sessions, columns=wanted)
    del quotes, quote_window
    rebalance = pd.Series(False, index=sessions)
    targets = pd.DataFrame(0.0, index=sessions, columns=wanted)
    for item in schedules:
        signal = pd.Timestamp(item["signal_date"])
        rebalance.loc[signal] = True
        targets.loc[signal, item["canonical_names"]] = 0.05
    exec_end = effective_end
    end_idx = sessions.index(exec_end)
    relevant = sorted(set(pd.Timestamp(x) for x in targets_by_signal))
    issues = []
    current, executions = set(), {}
    for signal in relevant:
        signal_index = sessions.index(signal)
        if signal_index + 1 < len(sessions):
            executions[sessions[signal_index + 1]] = targets_by_signal[signal.date().isoformat()]
    for day in sessions[first_fill_index:end_idx + 1]:
        day_issues = []
        if day in executions:
            previous = current
            current = set(executions[day])
            for name in previous | current:
                if not np.isfinite(opens.at[day, name]) or opens.at[day, name] <= 0:
                    day_issues.append({"date": day.date().isoformat(), "symbol": name,
                                       "input": "next_session_raw_open", "reason": "missing intended order observation"})
        for name in current:
            if not np.isfinite(closes.at[day, name]) or closes.at[day, name] <= 0:
                day_issues.append({"date": day.date().isoformat(), "symbol": name,
                                   "input": "held_position_raw_close", "reason": "missing or invalid raw close mark"})
        if day_issues:
            issues = sorted(day_issues, key=lambda row: (row["input"], row["symbol"]))
            break
    if issues:
        gap = issues[0]
        stop_index = sessions.index(pd.Timestamp(gap["date"]))
        effective_end = min(effective_end, sessions[stop_index - 1])
        exec_end = effective_end
        blockers.append(gap)
    if exec_end < pd.Timestamp(first_fill):
        return {"candidate_id": candidate, "status": "BLOCKED_BEFORE_FIRST_FILL",
                "first_material_blocker": blockers[0] if blockers else signal_blocker,
                "blockers": blockers, "actual_order_count": 0,
                "valuation_scenario": valuation_scenario, "slippage_bps_per_side": slippage_bps,
                "valid_through": exec_end.date().isoformat(), "starting_capital_inr": CAPITAL,
                "ending_nav_inr": CAPITAL, "ending_cash_inr": CAPITAL, "ending_invested_inr": 0.0,
                "ending_cash_receivable_inr": 0.0, "ending_locked_claim_inr": 0.0,
                "max_drawdown_pct": 0.0, "turnover_inr": 0.0, "fees_inr": 0.0}
    equity, orders, stats = cash_engine._simulate(
        {"open": opens, "close": closes}, targets, rebalance, CAPITAL, 1.0, slippage_bps,
        start=date(2018, 1, 1), end=exec_end.date(), drawdown_limit_pct=1000.0,
        cash_distributions=distributions, cash_distribution_payment_dates=payment_dates,
        detached_claim_events=claim_events, liquidate_terminal=False,
    )
    residual = (equity["nav"] - equity["cash_inr"] - equity["invested_inr"]
                - equity["cash_receivable_inr"] - equity["locked_claim_inr"]).abs()
    if residual.max() > 0.05 or not np.isfinite(residual).all():
        raise AssertionError(f"order-to-NAV reconciliation failed for {candidate}")
    retained_resize = []
    prior = set()
    for schedule_index, item in enumerate(schedules):
        day = pd.Timestamp(item["signal_date"])
        if day < exec_end:
            execution = sessions[sessions.index(day) + 1]
            filled = orders.loc[orders["time"].eq(execution)]
            if schedule_index == 0 and len(filled.loc[filled["side"].eq("buy")]) != 20:
                raise AssertionError(f"{candidate} {day.date()} target had fewer than 20 fills")
            retained = set(item["canonical_names"]) & prior
            resized = filled.loc[filled["symbol"].isin(retained), ["symbol", "side", "quantity"]]
            retained_resize.append({"signal_date": day.date().isoformat(), "execution_date": execution.date().isoformat(),
                                    "retained_names": len(retained), "retained_names_with_resize_orders": int(resized["symbol"].nunique()),
                                    "retained_resize_order_count": int(len(resized))})
        prior = set(item["canonical_names"])
    order_frame = orders.copy()
    if not order_frame.empty:
        order_frame["reference_open_raw"] = [opens.at[row.time, row.symbol] for row in order_frame.itertuples()]
        order_frame["slippage_cost_inr"] = order_frame["quantity"] * (
            order_frame["fill_price"] - order_frame["reference_open_raw"]
        ).abs()
        order_frame["candidate_id"] = candidate
    LOCAL.mkdir(parents=True, exist_ok=True)
    output_stem = f"{candidate.lower().replace('-', '_')}_{valuation_scenario}_{int(slippage_bps)}bps"
    order_path = LOCAL / f"{output_stem}_orders.csv"
    equity_path = LOCAL / f"{output_stem}_equity.csv"
    events_path = LOCAL / f"{output_stem}_events.json"
    order_frame.to_csv(order_path, index=False)
    equity.to_csv(equity_path, index_label="date")
    events_path.write_text(json.dumps({"cash_distribution_events": stats["cash_distribution_events"],
                                     "detached_claim_events": stats["detached_claim_events"],
                                     "valuation_scenario": valuation_scenario}, indent=2) + "\n", encoding="utf-8")
    position_quantities = {}
    for order in orders.itertuples(index=False):
        if getattr(order, "order_type", None) == "corporate_action_whole_claim_disposal":
            continue
        signed_quantity = int(order.quantity) * (1 if order.side == "buy" else -1)
        position_quantities[order.symbol] = position_quantities.get(order.symbol, 0) + signed_quantity
    ending_positions = []
    for name, quantity in position_quantities.items():
        if quantity <= 0:
            continue
        mark = float(closes.at[exec_end, name])
        ending_positions.append({"canonical": name, "quantity": quantity,
                                 "raw_close_inr": mark, "market_value_inr": quantity * mark})
    ending_positions.sort(key=lambda row: (-row["market_value_inr"], row["canonical"]))
    invested_rebuilt = sum(row["market_value_inr"] for row in ending_positions)
    if abs(invested_rebuilt - float(equity["invested_inr"].iloc[-1])) > 0.05:
        raise AssertionError(f"ending positions do not reconcile for {candidate}")
    for position in ending_positions:
        position["weight_of_invested_pct"] = (
            position["market_value_inr"] / invested_rebuilt * 100 if invested_rebuilt else 0.0
        )
    concentration = {
        "position_count": len(ending_positions),
        "largest_position_pct_of_invested": ending_positions[0]["weight_of_invested_pct"] if ending_positions else 0.0,
        "top_five_pct_of_invested": sum(row["weight_of_invested_pct"] for row in ending_positions[:5]),
        "hhi": sum((row["weight_of_invested_pct"] / 100) ** 2 for row in ending_positions),
        "invested_reconciliation_residual_inr": invested_rebuilt - float(equity["invested_inr"].iloc[-1]),
    }
    path_nav = [(date(2018, 1, 1), CAPITAL)] + [
        (timestamp.date(), float(nav)) for timestamp, nav in equity["nav"].items()
    ]
    high_water, high_water_day = CAPITAL, date(2018, 1, 1)
    max_dd, max_dd_peak, max_dd_peak_day, max_dd_trough_day = 0.0, CAPITAL, date(2018, 1, 1), date(2018, 1, 1)
    for day, nav in path_nav[1:]:
        if nav > high_water:
            high_water, high_water_day = nav, day
        drawdown = nav / high_water - 1
        if drawdown < max_dd:
            max_dd, max_dd_peak, max_dd_peak_day, max_dd_trough_day = (
                drawdown, high_water, high_water_day, day
            )
    recovery_day = next((day for day, nav in path_nav
                         if day > max_dd_trough_day and nav >= max_dd_peak), None)
    recovery = {
        "max_drawdown_pct": max_dd * 100,
        "peak_date": max_dd_peak_day.isoformat(),
        "trough_date": max_dd_trough_day.isoformat(),
        "recovery_status": "RECOVERED" if recovery_day else "NOT_RECOVERED_BY_PREFIX_END",
        "recovery_date": recovery_day.isoformat() if recovery_day else None,
        "trough_to_recovery_calendar_days": (recovery_day - max_dd_trough_day).days if recovery_day else None,
    }
    if not np.isclose(max_dd * 100, stats["max_drawdown_pct"], atol=1e-9):
        raise AssertionError(f"drawdown path does not reconcile for {candidate}")
    status = ("ACTUAL_PREFIX_STOPPED_AT_FIRST_MATERIAL_GAP" if blockers else
              "ACTUAL_PREFIX_STOPPED_AT_UNRESOLVED_SIGNAL" if signal_blocker else
              "ACTUAL_PREFIX_TO_EVALUATION_CUTOFF")
    result = {"candidate_id": candidate,
              "status": status, "valuation_scenario": valuation_scenario,
              "slippage_bps_per_side": slippage_bps,
              "valid_through": exec_end.date().isoformat(),
              "starting_capital_inr": CAPITAL, "actual_order_count": int(len(orders)),
              "actual_buy_count": int(orders["side"].eq("buy").sum()),
              "actual_sell_count": int(orders["side"].eq("sell").sum()),
              "first_order_date": orders["time"].min().date().isoformat() if len(orders) else None,
              "ending_nav_inr": float(equity["nav"].iloc[-1]),
              "ending_cash_inr": float(equity["cash_inr"].iloc[-1]),
              "ending_invested_inr": float(equity["invested_inr"].iloc[-1]),
              "ending_cash_receivable_inr": float(equity["cash_receivable_inr"].iloc[-1]),
              "ending_locked_claim_inr": float(equity["locked_claim_inr"].iloc[-1]),
              "max_drawdown_pct": float(stats["max_drawdown_pct"]),
              "drawdown_recovery": recovery, "ending_positions": ending_positions,
              "ending_concentration": concentration,
              "turnover_inr": float(stats["turnover_inr"]), "fees_inr": float(stats["total_fees_inr"]),
              "fees_by_component_inr": stats["fees_by_component_inr"],
              "slippage_cost_inr": float(order_frame["slippage_cost_inr"].sum()) if len(order_frame) else 0.0,
              "max_nav_reconciliation_residual_inr": float(residual.max()),
              "cash_distributions_inr": float(stats["cash_distributions_inr"]),
              "cash_distribution_entitlements_inr": float(stats["cash_distribution_entitlements_inr"]),
              "cash_distribution_events": stats["cash_distribution_events"],
              "detached_claim_events": stats["detached_claim_events"],
              "retained_name_resizing_by_rebalance": retained_resize,
              "first_material_blocker": blockers[0] if blockers else signal_blocker,
              "later_material_blockers": blockers[1:] if len(blockers) > 1 else [],
              "orders_file_local": str(order_path.relative_to(ROOT)),
              "equity_file_local": str(equity_path.relative_to(ROOT)),
              "events_file_local": str(events_path.relative_to(ROOT)),
              "cagr": "NOT REPORTED: stopped prefix, not a full-period result"}
    return result


def self_check() -> None:
    global LOCAL
    cash_engine._self_check()
    assert normalize_index_label("Nifty 200") == normalize_index_label("NIFTY 200") == "NIFTY200"
    assert choose_selection_bound(0.1, 0.7, 0.75) is False
    assert choose_selection_bound(0.1, 0.8, 0.75) is True
    assert np.isclose((296.05 / ((296.05 + 0.1 * 207) / 1.1)), 1.0281136543, atol=1e-9)
    assert IDFC_INFERENCE["classification"] == "supported_debt_event_inference"
    sessions = list(pd.to_datetime(["2018-04-02", "2018-04-03", "2018-04-04", "2018-04-05", "2018-04-06"]))
    action = pd.DataFrame([{"ex_date": pd.Timestamp("2018-04-05"), "resolved_symbol": "PARENT",
                            "symbol": "PARENT", "isin": "INE000A01001", "type": "dividend",
                            "raw_subject": "Dividend", "cash_amount": 2.0}])
    data = pd.DataFrame([{"date": day, "symbol": "PARENT", "isin": "INE000A01001", "canonical": "INE000A01001"}
                         for day in sessions])
    exit_targets = {"2018-04-02": ["INE000A01001"], "2018-04-04": []}
    distributions, payment_dates, claims, blockers = action_gate(
        "NIFTY200-A-Q", exit_targets, action, data, sessions, date(2018, 4, 2), date(2018, 4, 5))
    assert distributions == [("INE000A01001", date(2018, 4, 5), 2.0)] and not blockers and not claims
    assert payment_dates[("INE000A01001", date(2018, 4, 5))] == date(2018, 5, 5)
    entry_targets = {"2018-04-02": [], "2018-04-04": ["INE000A01001"]}
    distributions, _, _, blockers = action_gate(
        "NIFTY200-A-Q", entry_targets, action, data, sessions, date(2018, 4, 2), date(2018, 4, 5))
    assert not distributions and not blockers

    # Entitlement changes at the event open; the engine must use the actual pre-open quantity.
    trade_days = pd.to_datetime(["2018-04-03", "2018-04-04", "2018-04-05", "2018-05-07",
                                "2018-06-18", "2018-06-19"])
    names = ["PARENT", "CHILD"]
    opens = pd.DataFrame({"PARENT": [100, 100, 90, 92, 95, 96],
                          "CHILD": [np.nan, np.nan, np.nan, np.nan, 20, 22]}, index=trade_days)
    closes = opens.copy()
    targets = pd.DataFrame(0.0, index=trade_days, columns=names)
    targets.loc[trade_days[0], "PARENT"] = 0.5
    rebalance = pd.Series(False, index=trade_days)
    rebalance.loc[trade_days[:2]] = True
    claim_event = {"parent_symbol": "PARENT", "child_symbol": "CHILD", "ex_date": date(2018, 4, 5),
                   "listing_date": date(2018, 6, 18), "sale_date": date(2018, 6, 19), "ratio": "0.761",
                   "detached_unit_mark": 10.0, "base_detached_unit_mark": 10.0, "scenario": "base"}
    dividend = [("PARENT", date(2018, 4, 5), 2.0)]
    payment_day = {("PARENT", date(2018, 4, 5)): date(2018, 5, 5)}
    equity, orders, stats = cash_engine._simulate(
        {"open": opens, "close": closes}, targets, rebalance, 10_000.0, 1.0, 50.0,
        start=date(2018, 4, 4), end=date(2018, 6, 19), drawdown_limit_pct=1000.0,
        cash_distributions=dividend, cash_distribution_payment_dates=payment_day,
        detached_claim_events=[claim_event], liquidate_terminal=False,
    )
    record = stats["detached_claim_events"][0]
    assert record["parent_quantity_before_ex_open"] > 0
    assert Decimal(record["entitlement_exact"]) == Decimal(record["parent_quantity_before_ex_open"]) * AGEL_RATIO
    assert int(orders.loc[orders["time"].eq(pd.Timestamp("2018-04-05")) & orders["side"].eq("sell"), "quantity"].sum()) == record["parent_quantity_before_ex_open"]
    ex_row, paid_row, listing_row, sale_row = (equity.loc[pd.Timestamp(day)] for day in
                                               ("2018-04-05", "2018-05-07", "2018-06-18", "2018-06-19"))
    assert ex_row["cash_receivable_inr"] == record["parent_quantity_before_ex_open"] * 2.0
    assert ex_row["cash_distribution_paid_inr"] == 0 and ex_row["locked_claim_inr"] > 0
    assert paid_row["cash_distribution_paid_inr"] == ex_row["cash_receivable_inr"] and paid_row["cash_receivable_inr"] == 0
    assert listing_row["locked_claim_inr"] == float(Decimal(record["entitlement_exact"])) * 20.0
    assert record["whole_units_sold"] == record["whole_units"]
    disposal = orders.loc[orders.get("order_type", pd.Series(index=orders.index, dtype=object)).eq(
        "corporate_action_whole_claim_disposal")]
    assert len(disposal) == 1 and disposal.iloc[0]["time"] == pd.Timestamp("2018-06-19")
    assert sale_row["locked_claim_inr"] == float(Decimal(record["fractional_units_exact"])) * 20.0

    entry_targets = pd.DataFrame(0.0, index=trade_days, columns=names)
    entry_targets.loc[trade_days[1], "PARENT"] = 0.5
    entry_rebalance = pd.Series(False, index=trade_days)
    entry_rebalance.loc[trade_days[1]] = True
    entry_equity, _, entry_stats = cash_engine._simulate(
        {"open": opens, "close": closes}, entry_targets, entry_rebalance, 10_000.0, 1.0, 50.0,
        start=date(2018, 4, 5), end=date(2018, 4, 5), drawdown_limit_pct=1000.0,
        detached_claim_events=[claim_event], liquidate_terminal=False,
    )
    assert entry_stats["detached_claim_events"][0]["parent_quantity_before_ex_open"] == 0
    assert entry_stats["detached_claim_events"][0]["entitlement_exact"] == "0.000"
    assert entry_equity.iloc[0]["locked_claim_inr"] == 0

    # RELCAPITAL carries RHFL only across the ex-date, never for a post-ex-date entry.
    rel_days = pd.to_datetime(["2017-09-04", "2017-09-05", "2017-09-08", "2017-09-21",
                               "2017-09-25", "2017-10-02"])
    rel_parent = pd.DataFrame({"close": [100.0, 70.0, 75.0, 70.0, 72.0, 80.0]}, index=rel_days)
    rhfl = pd.Series({rel_days[2]: 20.0, rel_days[5]: np.nan})
    assert np.isclose(interval_return(rel_parent, rhfl, rel_days[0], rel_days[2]), -0.05)
    assert np.isclose(interval_return(rel_parent, rhfl, rel_days[1], rel_days[2]), 75.0 / 70.0 - 1)
    assert np.isclose(interval_return(rel_parent, rhfl, rel_days[4], rel_days[5]), 80.0 / 72.0 - 1)

    # A finite score cannot clear an unmatched merger dependency.
    score_sessions = list(pd.date_range("2017-01-02", periods=300, freq="B"))
    score_index = {day: i for i, day in enumerate(score_sessions)}
    signal_day = score_sessions[280]
    price_values = np.linspace(10.0, 20.0, len(score_sessions))
    finite_score, _ = audit.score_at(price_values, 280, "A")
    dep = {"candidate_id": "NIFTY200-A-M", "signal_date": signal_day.date().isoformat(), "rule": "A",
           "date": "2017-09-05", "entity": "UNKNOWN|INE000A01001", "input": "signal_merger",
           "source": "NSE corporate-action feed", "reason": "unreviewed merger entitlement"}
    dep_key = audit.dependency_key(dep)
    unknown = pd.DataFrame([{"candidate_id": dep["candidate_id"], "signal_date": dep["signal_date"],
                             "symbol": "UNKNOWN", "isin": "INE000A01001", "canonical": "INE000A01001",
                             "score": finite_score, "rank": 1, "score_status": "UNKNOWN_DATA",
                             "unresolved_reason": dep["reason"], "unresolved_dependency_keys": [dep_key]}])
    dep["dependency_key"] = dep_key
    score_frame = pd.DataFrame({"adj_close": price_values, "close": price_values,
                                "adj_factor_cumulative": np.ones(len(score_sessions))}, index=score_sessions)
    unresolved_target = choose_target(dep["candidate_id"], signal_day, [], score_sessions, unknown, score_index,
                                      {"INE000A01001": score_frame}, pd.Series(dtype=float), [], {dep_key: dep})
    assert unresolved_target["target_status"] == "BLOCKED"
    assert unresolved_target["unresolved"][0]["unmatched_dependency_keys"][0]["reason"] == dep["reason"]

    # An actual later raw-open gap keeps the earlier executed prefix and its capital path.
    gap_days = list(pd.to_datetime(["2018-01-30", "2018-01-31", "2018-02-01", "2018-02-02", "2018-02-05"]))
    gap_names = [f"ISIN{i:02d}" for i in range(20)]
    gap_rows = [{"date": day, "canonical": name, "isin": name, "symbol": f"S{i:02d}",
                 "open": (np.nan if day == gap_days[-1] and i == 0 else 100.0), "close": 100.0}
                for day in gap_days for i, name in enumerate(gap_names)]
    gap_data = pd.DataFrame(gap_rows)
    gap_actions = pd.DataFrame(columns=["ex_date", "symbol", "resolved_symbol", "isin", "type", "raw_subject", "cash_amount"])
    first_schedule = {"signal_date": gap_days[0].date().isoformat(), "canonical_names": gap_names,
                      "selected": [{"canonical": name} for name in gap_names]}
    second_schedule = {"signal_date": gap_days[3].date().isoformat(), "canonical_names": gap_names,
                       "selected": [{"canonical": name} for name in gap_names]}
    with tempfile.TemporaryDirectory(dir=ROOT) as temp_dir:
        previous_local = LOCAL
        LOCAL = Path(temp_dir) / "ledgers"
        try:
            prefix = run_account("NIFTY200-A-M", pd.DataFrame(), [first_schedule, second_schedule], gap_data,
                                 gap_actions, gap_days, "2018-02-05")
        finally:
            LOCAL = previous_local
    assert prefix["status"] == "ACTUAL_PREFIX_STOPPED_AT_FIRST_MATERIAL_GAP"
    assert prefix["actual_order_count"] >= 20 and prefix["valid_through"] == "2018-02-02"
    assert prefix["ending_positions"] and prefix["ending_concentration"]["invested_reconciliation_residual_inr"] < 0.05
    assert np.isclose(prefix["drawdown_recovery"]["max_drawdown_pct"], prefix["max_drawdown_pct"])


def choose_selection_bound(lower: float, upper: float, cutoff: float) -> bool:
    return upper >= cutoff


def normalize_index_label(value: object) -> str:
    return "".join(str(value).upper().split())


def matched_tri_results(accounts: list[dict]) -> tuple[list[dict], str]:
    tri_path = ROOT / "work" / "data" / "index_daily" / "nifty200_tri_raw_2017_2026.json"
    source = json.loads(tri_path.read_text(encoding="utf-8"))
    if normalize_index_label(source.get("index", "")) != "NIFTY200" or "Gross Total Return" not in source.get("series", ""):
        raise ValueError("registered NIFTY 200 Gross TRI source metadata mismatch")
    values = {}
    for request in source.get("requests", []):
        if request.get("httpStatus") != 200:
            raise ValueError("registered NIFTY 200 TRI capture contains a failed request")
        for row in request.get("rows", []):
            if normalize_index_label(row.get("Index Name", "")) != "NIFTY200":
                raise ValueError(f"unexpected index in registered TRI capture: {row.get('Index Name')!r}")
            day = pd.to_datetime(row["Date"], format="%d %b %Y").date()
            value = float(row["TotalReturnsIndex"])
            if day in values or not np.isfinite(value) or value <= 0:
                raise ValueError(f"invalid or duplicate registered TRI row: {row}")
            values[day] = value
    results = []
    for account in accounts:
        end_day = date.fromisoformat(account["valid_through"])
        start_day = date.fromisoformat(account["first_order_date"]) if account.get("first_order_date") else None
        if end_day not in values:
            results.append({"candidate_id": account["candidate_id"],
                            "valuation_scenario": account["valuation_scenario"],
                            "slippage_bps_per_side": account["slippage_bps_per_side"],
                            "status": "BLOCKED_NO_EXACT_MATCHED_TRI_DATE", "matched_through": end_day.isoformat()})
            continue
        if start_day is None:
            tri_return = 0.0
            tri_nav = CAPITAL
            cash_wait_days = (end_day - date(2018, 1, 1)).days
        elif start_day not in values:
            results.append({"candidate_id": account["candidate_id"],
                            "valuation_scenario": account["valuation_scenario"],
                            "slippage_bps_per_side": account["slippage_bps_per_side"],
                            "status": "BLOCKED_NO_EXACT_TRI_ENTRY_DATE", "entry_date": start_day.isoformat()})
            continue
        else:
            tri_return = values[end_day] / values[start_day] - 1
            tri_nav = CAPITAL * (1 + tri_return)
            cash_wait_days = (start_day - date(2018, 1, 1)).days
        strategy_return = float(account["ending_nav_inr"]) / CAPITAL - 1
        results.append({"candidate_id": account["candidate_id"],
                        "valuation_scenario": account["valuation_scenario"],
                        "slippage_bps_per_side": account["slippage_bps_per_side"],
                        "status": "MATCHED_GROSS_TRI_WITH_CASH_WAIT",
                        "cash_wait_days": cash_wait_days,
                        "tri_entry_date": start_day.isoformat() if start_day else None,
                        "matched_through": end_day.isoformat(),
                        "tri_start_value": values[start_day] if start_day else None,
                        "tri_end_value": values[end_day],
                        "tri_gross_return_pct": tri_return * 100,
                        "tri_reference_ending_nav_inr": tri_nav,
                        "strategy_net_return_pct": strategy_return * 100,
                        "excess_vs_gross_tri_pct_points": (strategy_return - tri_return) * 100,
                        "tri_execution_assumption": "cash at zero yield from 2018-01-01 through first strategy fill date; index exposure begins at that date's official close; no ETF wrapper fee or tracking error"})
    return results, audit.sha256_file(tri_path)


def run() -> dict:
    sessions, data, actions, signals, index, series_by_canonical, child, dependency_records, cache_manifest = setup()
    cache_manifest_artifact = ROOT / "outputs" / "nifty200_signal_cache_manifest_cycle2_2026-11-02.json"
    cache_manifest_artifact.write_text(json.dumps(cache_manifest, indent=2) + "\n", encoding="utf-8")
    for (symbol, date_text) in RIGHTS:
        if not actions["symbol"].eq(symbol).where(actions["ex_date"].eq(pd.Timestamp(date_text)), False).any():
            raise ValueError(f"registered rights source event missing for {symbol} {date_text}")
    for (symbol, date_text), amount in DIVIDENDS.items():
        rows = actions.loc[actions["symbol"].eq(symbol) & actions["ex_date"].eq(pd.Timestamp(date_text))]
        if rows.empty or not pd.to_numeric(rows["cash_amount"], errors="coerce").eq(amount).any():
            raise ValueError(f"registered dividend source event/amount missing for {symbol} {date_text}")
    all_certificates, first_blockers, correction_log = {}, {}, []
    for candidate in CONFIGURATIONS:
        all_certificates[candidate] = []
        prior = []
        dates = sorted(signals.loc[signals["candidate_id"].eq(candidate), "signal_date"].drop_duplicates())
        for date_text in dates:
            day = pd.Timestamp(date_text)
            cert = choose_target(candidate, day, prior, sessions, signals, index,
                                 series_by_canonical, child, correction_log, dependency_records)
            if cert["target_status"].startswith("CERTIFIED") and index[day] + 1 >= len(sessions):
                cert["target_status"] = "BLOCKED"
                cert["unresolved"].append({"input": "next_session_order",
                                           "reason": "no source-session execution date follows this certified decision"})
            cert["canonical_names"] = [r["canonical"] for r in cert["selected"]]
            all_certificates[candidate].append(cert)
            if cert["target_status"] != "CERTIFIED_UNDER_REGISTERED_SOURCE_CORRECTIONS":
                first_blockers[candidate] = {"date": date_text, "kind": "signal_or_order",
                                             "unresolved": cert["unresolved"]}
                break
            prior = [r["canonical"] for r in cert["selected"]]
    correction_path = ROOT / "outputs" / "nifty200_source_corrections_cycle2_2026-11-02.csv"
    pd.DataFrame(correction_log).drop_duplicates().to_csv(correction_path, index=False)
    cutoff = max(day for day in sessions if day <= audit.CUTOFF)
    accounts, cost_sensitivities = [], []
    for candidate in CONFIGURATIONS:
        certified = [item for item in all_certificates[candidate]
                     if item["target_status"] == "CERTIFIED_UNDER_REGISTERED_SOURCE_CORRECTIONS"]
        end_day = first_blockers.get(candidate, {}).get("date", cutoff.date().isoformat())
        signal_blocker = first_blockers.get(candidate)
        for scenario in ("base", "zero_mark_stress"):
            accounts.append(run_account(candidate, signals, certified, data, actions, sessions,
                                        end_day, scenario, SLIPPAGE_BPS, signal_blocker))
        for bps in (10.0, 100.0, 200.0):
            cost_sensitivities.append(run_account(candidate, signals, certified, data, actions, sessions,
                                                  end_day, "base", bps, signal_blocker))
    all_accounts = accounts + cost_sensitivities
    tri_results, tri_sha256 = matched_tri_results(all_accounts)
    tri_by_case = {(row["candidate_id"], row["valuation_scenario"], row["slippage_bps_per_side"]): row
                   for row in tri_results}
    blocker_summary = []
    for candidate, certificates in all_certificates.items():
        blocked = next((item for item in certificates
                        if item["target_status"] != "CERTIFIED_UNDER_REGISTERED_SOURCE_CORRECTIONS"), None)
        if blocked is None:
            blocker_summary.append({"candidate_id": candidate, "certified_signal_count": len(certificates),
                                    "first_signal_blocker": None})
            continue
        grouped = {}
        for issue in blocked["unresolved"]:
            refs = issue.get("unmatched_dependency_keys", [])
            if not refs:
                refs = [{"key": "", "entity": issue.get("symbol", ""),
                         "input": issue.get("input", "unknown"), "date": blocked["signal_date"],
                         "reason": issue.get("reason", "unresolved dependency")}]
            for ref in refs:
                key = ref.get("key", "")
                dependency = dependency_records.get(key, ref)
                group_key = tuple(str(dependency.get(field, "")) for field in
                                  ("entity", "input", "reason", "source", "resolution_attempt", "impact"))
                group = grouped.setdefault(group_key, {"keys": set(), "dates": set()})
                if key:
                    group["keys"].add(key)
                if dependency.get("date"):
                    group["dates"].add(str(dependency["date"]))
        group_rows = []
        for group_key, group in sorted(grouped.items()):
            entity, input_name, reason, source, attempt, impact = group_key
            keys = sorted(group["keys"])
            dates = sorted(group["dates"])
            group_rows.append({"entity": entity, "input": input_name, "reason": reason,
                               "source": source, "resolution_attempt": attempt, "impact": impact,
                               "dependency_count": len(keys), "date_start": dates[0] if dates else None,
                               "date_end": dates[-1] if dates else None,
                               "dependency_keys_sha256": hashlib.sha256("\n".join(keys).encode()).hexdigest(),
                               "dependency_key_samples": keys[:3]})
        blocker_summary.append({"candidate_id": candidate,
                                "certified_signal_count": sum(
                                    item["target_status"] == "CERTIFIED_UNDER_REGISTERED_SOURCE_CORRECTIONS"
                                    for item in certificates),
                                "first_signal_blocker": {"signal_date": blocked["signal_date"],
                                                         "status": blocked["target_status"],
                                                         "unresolved_dependency_groups": group_rows}})
    experiment_rows = []
    for account in all_accounts:
        tri = tri_by_case.get((account["candidate_id"], account["valuation_scenario"],
                               account["slippage_bps_per_side"]), {})
        experiment_rows.append({"cycle_id": "2026-11-02-cycle2", "candidate_id": account["candidate_id"],
                                "valuation_scenario": account["valuation_scenario"],
                                "slippage_bps_per_side": account["slippage_bps_per_side"],
                                "valid_through": account.get("valid_through", ""), "status": account["status"],
                                "orders": account.get("actual_order_count", 0),
                                "turnover_inr": account.get("turnover_inr", ""),
                                "fees_inr": account.get("fees_inr", ""),
                                "slippage_cost_inr": account.get("slippage_cost_inr", ""),
                                "ending_nav_inr": account.get("ending_nav_inr", ""),
                                "max_drawdown_pct": account.get("max_drawdown_pct", ""),
                                "matched_tri_return_pct": tri.get("tri_gross_return_pct", ""),
                                "excess_vs_matched_tri_pct_points": tri.get("excess_vs_gross_tri_pct_points", ""),
                                "cagr": "NOT REPORTED: stopped/provisional prefix"})
    experiment_path = ROOT / "outputs" / "experiment_register_cycle2_2026-11-02.csv"
    pd.DataFrame(experiment_rows).to_csv(experiment_path, index=False)
    cumulative_experiment_path = ROOT / "outputs" / "experiment_register_cumulative_2026-11-02.csv"
    previous_experiment_path = ROOT / "outputs" / "experiment_register_2026-10-31.csv"
    previous_experiments = pd.read_csv(previous_experiment_path) if previous_experiment_path.is_file() else pd.DataFrame()
    cumulative = pd.concat([previous_experiments, pd.DataFrame(experiment_rows)], ignore_index=True, sort=False)
    cumulative.to_csv(cumulative_experiment_path, index=False)
    ledger_bundle_path = ROOT / "outputs" / "nifty200_cycle2_actual_ledgers_2026-11-02.json"
    actual_results_path = ROOT / "outputs" / "nifty200_cycle2_actual_results_2026-11-02.json"
    blocker_summary_path = ROOT / "outputs" / "nifty200_cycle2_dependency_blockers_2026-11-02.json"
    ledgers = []
    for account in accounts + cost_sensitivities:
        ledger = {key: account.get(key) for key in
                  ("candidate_id", "valuation_scenario", "slippage_bps_per_side", "status", "valid_through")}
        ledger["ending_positions"] = account.get("ending_positions", [])
        ledger["ending_concentration"] = account.get("ending_concentration", {})
        ledger["drawdown_recovery"] = account.get("drawdown_recovery", {})
        for field, key in (("orders", "orders_file_local"), ("equity", "equity_file_local"),
                           ("events", "events_file_local")):
            local_path = account.get(key)
            if not local_path:
                ledger[field] = [] if field != "events" else {}
                continue
            path = ROOT / local_path
            if field == "events":
                ledger[field] = json.loads(path.read_text(encoding="utf-8"))
            else:
                ledger[field] = json.loads(pd.read_csv(path).to_json(orient="records", date_format="iso"))
        ledgers.append(ledger)
    ledger_bundle_path.write_text(json.dumps(ledgers, indent=2) + "\n", encoding="utf-8")
    blocker_summary_path.write_text(json.dumps({
        "protocol_id": "NIFTY200-v1.6-AGEL-locked-claim-base-zero-stress",
        "signal_schedule_blockers": blocker_summary,
        "account_stop_blockers": [{"candidate_id": account["candidate_id"],
                                   "valuation_scenario": account["valuation_scenario"],
                                   "slippage_bps_per_side": account["slippage_bps_per_side"],
                                   "valid_through": account.get("valid_through"),
                                   "blocker": ({key: account["first_material_blocker"].get(key)
                                                for key in ("date", "kind", "symbol", "canonical", "event",
                                                            "entity", "input", "reason", "source_subject")}
                                               if account.get("first_material_blocker") and
                                               "unresolved" not in account["first_material_blocker"] else
                                               {"date": account.get("valid_through"), "kind": "signal_or_order",
                                                "reason": "Ranking-changing signal dependencies remain unresolved; see grouped signal schedule blockers."})}
                                   for account in all_accounts]}, indent=2) + "\n", encoding="utf-8")
    result = {
        "protocol_id": "NIFTY200-v1.6-AGEL-locked-claim-base-zero-stress",
        "evaluation": {"start": "2018-01-01", "full_end": audit.CUTOFF.date().isoformat(),
                       "matched_through": {row["candidate_id"]: row.get("valid_through") for row in accounts}},
        "capital_inr": CAPITAL, "cash_yield": "zero", "base_slippage_bps_per_side": SLIPPAGE_BPS,
        "score_certificates": all_certificates, "accounts": accounts,
        "cost_sensitivities": cost_sensitivities,
        "matched_tri_benchmark": {"series": "official NIFTY 200 Gross TRI",
                                  "source_sha256": tri_sha256,
                                  "cash_waiting_time_included": True, "results": tri_results},
        "source_cache_schema": cache_manifest,
        "correction_log_local": str(correction_path.relative_to(ROOT)),
        "experiment_register_local": str(experiment_path.relative_to(ROOT)),
        "cumulative_experiment_register_local": str(cumulative_experiment_path.relative_to(ROOT)),
        "actual_ledgers_bundle": str(ledger_bundle_path.relative_to(ROOT)),
        "actual_results_summary": str(actual_results_path.relative_to(ROOT)),
        "dependency_blockers_summary": str(blocker_summary_path.relative_to(ROOT)),
        "signal_cache_manifest_artifact": str(cache_manifest_artifact.relative_to(ROOT)),
        "performance_gate": "NO FULL-PERIOD CAGR; no short-prefix 20% claim; no ranking or deployment",
        "research_limits": [
            "IDFC event classification remains an evidence-supported inference, not a located exact original notice.",
            "The AGEL prelisting value is an MSCI-inspired model convention using raw AEL cum/ex closes; it is not observed market price or proof of 2018 NIFTY index treatment.",
            "AGEL fractional trustee sale date, fill, fees, and cash payment are not evidenced; residual fractions are nonspendable fixed-mark receivables.",
            "Unobserved dividend pay dates use the registered 30-calendar-day delayed cash assumption; no interest is credited.",
            "Costs remain uncalibrated. Zero-mark stress is not a proven final-wealth lower bound because sizing can change.",
        ],
    }
    summary_fields = ("candidate_id", "status", "valuation_scenario", "slippage_bps_per_side",
                      "valid_through", "starting_capital_inr", "actual_order_count", "actual_buy_count",
                      "actual_sell_count", "first_order_date", "ending_nav_inr", "ending_cash_inr",
                      "ending_invested_inr", "ending_cash_receivable_inr", "ending_locked_claim_inr",
                      "max_drawdown_pct", "drawdown_recovery", "turnover_inr", "fees_inr",
                      "fees_by_component_inr", "slippage_cost_inr", "cash_distributions_inr",
                      "cash_distribution_entitlements_inr", "max_nav_reconciliation_residual_inr",
                      "ending_positions", "ending_concentration", "cagr")
    actual_results_path.write_text(json.dumps({
        "protocol_id": result["protocol_id"], "capital_inr": CAPITAL,
        "cash_yield": "zero", "performance_gate": result["performance_gate"],
        "accounts": [{key: account.get(key) for key in summary_fields} for account in accounts],
        "cost_sensitivities": [{key: account.get(key) for key in summary_fields} for account in cost_sensitivities],
        "matched_tri_benchmark": result["matched_tri_benchmark"],
        "research_limits": result["research_limits"],
        "candidate_dependency_audit": "nifty200_candidate_dependency_audit_2026-11-02.json",
        "dependency_blockers": blocker_summary_path.name,
        "actual_ledgers": ledger_bundle_path.name,
    }, indent=2) + "\n", encoding="utf-8")
    OUT.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    output_paths = [OUT, correction_path, experiment_path, cumulative_experiment_path,
                    ledger_bundle_path, actual_results_path, blocker_summary_path, cache_manifest_artifact]
    for account in accounts + cost_sensitivities:
        for key in ("orders_file_local", "equity_file_local", "events_file_local"):
            if account.get(key):
                output_paths.append(ROOT / account[key])
    manifest_path = ROOT / "outputs" / "nifty200_cycle2_source_code_schema_manifest_2026-11-02.json"
    manifest = {
        "cycle_id": "2026-11-02-cycle2", "protocol_id": result["protocol_id"],
        "generation_command": "python work/audit_strategy_dependencies.py; python work/advance_nifty200_cash_prefixes.py",
        "audit_code_sha256": audit.sha256_file(ROOT / "work" / "audit_strategy_dependencies.py"),
        "runner_code_sha256": audit.sha256_file(Path(__file__)),
        "account_engine_code_sha256": audit.sha256_file(ROOT / "work" / "upstox_quant.py"),
        "signal_cache_schema": cache_manifest["schema_version"],
        "signal_cache_manifest_sha256": audit.sha256_file(audit.SIGNAL_CACHE / "signal_cache_manifest.json"),
        "signal_cache_sources": cache_manifest["sources"],
        "signal_cache_outputs": cache_manifest["output_sha256"],
        "matched_tri_source_sha256": tri_sha256,
        "curated_output_sha256": {path.relative_to(ROOT).as_posix(): audit.sha256_file(path)
                                   for path in sorted(set(output_paths)) if path.is_file()},
    }
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    result["source_code_schema_manifest"] = str(manifest_path.relative_to(ROOT))
    OUT.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    manifest["curated_output_sha256"][OUT.relative_to(ROOT).as_posix()] = audit.sha256_file(OUT)
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))
    return result


if __name__ == "__main__":
    self_check()
    run()
