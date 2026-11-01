"""Correct the first source-backed signals and run their actual cash-account prefixes."""

from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow.dataset as ds

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "work"))
import audit_strategy_dependencies as audit
import upstox_quant as cash_engine

DETAIL = audit.PUBLIC / "strategy_dependencies" / "nifty200"
OUT = ROOT / "outputs" / "nifty200_sequential_prefix_evidence_2026-11-02.json"
LOCAL = DETAIL / "sequential_cash_prefixes_2026-11-02"
CAPITAL = 1_000_000.0
SLIPPAGE_BPS = 50.0

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
FIRST_DATES = {
    "NIFTY200-A-M": ["2018-01-31", "2018-02-28", "2018-03-28"],
    "NIFTY200-B-M": ["2018-01-31", "2018-02-28", "2018-03-28"],
    "NIFTY200-A-Q": ["2018-03-28"],
    "NIFTY200-B-Q": ["2018-03-28"],
}


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
    sessions, intervals, data, actions, symbols, reviewed, unreviewed, canonical, history = audit.load_data()
    signals = pd.read_csv(DETAIL / "signal_dependencies.csv", dtype=str).fillna("")
    signals["score"] = pd.to_numeric(signals["score"], errors="coerce")
    signals["rank"] = pd.to_numeric(signals["rank"], errors="coerce")
    index = {day: i for i, day in enumerate(sessions)}
    by_canonical = {}
    for name, group in data.groupby("canonical", sort=False):
        frame = group.sort_values("date").drop_duplicates("date").set_index("date").reindex(sessions)
        by_canonical[name] = frame
    return sessions, data, actions, signals, index, by_canonical, source_child_series()


def interval_return(parent: pd.DataFrame, child: pd.Series, start: pd.Timestamp,
                    end: pd.Timestamp) -> float:
    demerger = pd.Timestamp("2017-09-05")
    dividend_date = pd.Timestamp("2017-09-21")
    if start not in parent.index or end not in parent.index:
        raise ValueError("RELCAPITAL endpoint missing from the source-session calendar")
    p0, p1 = float(parent.at[start, "close"]), float(parent.at[end, "close"])
    if not np.isfinite([p0, p1]).all() or min(p0, p1) <= 0:
        raise ValueError("RELCAPITAL endpoint close missing or invalid")
    q_child = 1.0 if start >= demerger else 0.0
    initial = p0
    if q_child:
        if start not in child.index or not np.isfinite(child.get(start, np.nan)):
            raise ValueError(f"RHFL start mark missing on {start.date()}")
        initial += float(child.at[start])
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


def choose_target(candidate: str, day: pd.Timestamp, prior: list[str], sessions: list[pd.Timestamp], signals: pd.DataFrame,
                  index: dict, series_by_canonical: dict, child: pd.Series,
                  correction_log: list[dict]) -> dict:
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
            if details.get("score_status") == "UNKNOWN_DATA":
                if details.get("selection_bound") == "NONPOSITIVE":
                    selection_bounds.append({"symbol": row["symbol"], "reason": details["method"],
                                             "return_numerator": details["return_numerator"],
                                             "selection_bound": "NONPOSITIVE; cannot displace a positive target"})
                    continue
                unresolved.append({"symbol": row["symbol"], "reason": row["unresolved_reason"], **details})
                continue
        else:
            unresolved.append({"symbol": row["symbol"], "reason": row["unresolved_reason"]})
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
                data: pd.DataFrame, sessions: list[pd.Timestamp], start: date, end: date):
    wanted = set().union(*(set(items) for items in targets_by_signal.values()))
    action_rows = actions.loc[actions["ex_date"].between(pd.Timestamp(start), pd.Timestamp(end))].copy()
    distributions, blockers = [], []
    for _, event in action_rows.iterrows():
        if str(event["type"]).lower() in {"agm", "meeting"}:
            continue
        symbol = str(event["resolved_symbol"]).upper()
        if not symbol:
            continue
        rows = data.loc[data["symbol"].eq(symbol), "canonical"].dropna().astype(str).unique()
        if len(rows) != 1 or rows[0] not in wanted:
            continue
        canon = rows[0]
        active_targets = [(sessions[sessions.index(pd.Timestamp(signal_text)) + 1], target)
                          for signal_text, target in targets_by_signal.items()]
        active = [(execution, target) for execution, target in active_targets if execution <= event["ex_date"]]
        if not active or canon not in max(active, key=lambda item: item[0])[1]:
            continue
        if str(event["type"]).lower() == "dividend" and np.isfinite(pd.to_numeric(event["cash_amount"], errors="coerce")):
            distributions.append((canon, event["ex_date"].date(), float(event["cash_amount"])))
        else:
            is_adani_demerger = (
                symbol == "ADANIENT" and event["ex_date"] == pd.Timestamp("2018-04-05")
                and str(event["raw_subject"]).lower() == "scheme of arrangement"
            )
            details = ({
                "reason": "held ADANIENT shares entitled to 761 AGEL shares per 1,000; AGEL had no listed daily mark until 2018-06-18",
                "held_claim_ratio": "761 AGEL shares per 1,000 ADANIENT shares",
                "last_valid_account_mark_date": "2018-04-04",
                "resolution_required": "a contemporaneous source-backed daily fair-value series for the claim from 2018-04-05 through 2018-06-17, or official evidence of earlier cash settlement; include scheme fractional-treatment terms",
                "primary_evidence": [
                    "https://www.bseindia.com/downloads/ipo/20186131279Adani%20Green%20Energy%20Limited%20-%20Information%20Memorandum.pdf",
                    "https://nsearchives.nseindia.com/corporate/listcontract3_07022019173803_ADANIGREEN_outcome_315.pdf",
                ],
            } if is_adani_demerger else {
                "reason": "held-position entitlement or share conversion is not modeled by the cash engine"
            })
            blockers.append({"date": event["ex_date"].date().isoformat(), "symbol": symbol,
                             "canonical": canon, "event": event["type"], "source_subject": event["raw_subject"],
                             **details})
    if blockers:
        blockers.sort(key=lambda row: (row["date"], row["symbol"]))
        return distributions, blockers
    return distributions, []


def run_account(candidate: str, signals: pd.DataFrame, schedules: list[dict],
                data: pd.DataFrame, actions: pd.DataFrame, sessions: list[pd.Timestamp],
                end_day: str) -> dict:
    targets_by_signal = {item["signal_date"]: [r["canonical"] for r in item["selected"]] for item in schedules}
    start_day = "2018-01-01"
    first_fill = sessions[sessions.index(pd.Timestamp(schedules[0]["signal_date"])) + 1].date()
    distributions, blockers = action_gate(candidate, targets_by_signal, actions, data, sessions,
                                           first_fill, pd.Timestamp(end_day).date())
    effective_end = pd.Timestamp(end_day)
    if blockers:
        stop_index = sessions.index(pd.Timestamp(blockers[0]["date"]))
        effective_end = sessions[stop_index - 1]
        if effective_end < pd.Timestamp(first_fill):
            return {"candidate_id": candidate, "status": "BLOCKED_BEFORE_FIRST_FILL",
                    "first_material_blocker": blockers[0], "blockers": blockers, "actual_order_count": 0}
        distributions = [row for row in distributions if row[1] <= effective_end.date()]
    wanted = sorted(set().union(*map(set, targets_by_signal.values())))
    quotes = data.loc[data["canonical"].astype(str).isin(wanted)].copy()
    opens = quotes.pivot_table(index="date", columns="canonical", values="open", aggfunc="first").reindex(
        index=sessions, columns=wanted)
    closes = quotes.pivot_table(index="date", columns="canonical", values="close", aggfunc="first").reindex(
        index=sessions, columns=wanted)
    rebalance = pd.Series(False, index=sessions)
    targets = pd.DataFrame(0.0, index=sessions, columns=wanted)
    for item in schedules:
        signal = pd.Timestamp(item["signal_date"])
        rebalance.loc[signal] = True
        targets.loc[signal, item["canonical_names"]] = 0.05
    exec_end = effective_end
    end_idx = sessions.index(exec_end)
    relevant = sorted(set(pd.Timestamp(x) for x in targets_by_signal))
    issue = []
    current, executions = set(), {}
    for signal in relevant:
        executions[sessions[sessions.index(signal) + 1]] = targets_by_signal[signal.date().isoformat()]
    for day in sessions[sessions.index(pd.Timestamp(first_fill)):end_idx + 1]:
        if day in executions:
            previous = current
            current = set(executions[day])
            for name in previous | current:
                if not np.isfinite(opens.at[day, name]) or opens.at[day, name] <= 0:
                    issue.append({"date": day.date().isoformat(), "symbol": name,
                                  "input": "next_session_raw_open", "reason": "missing intended order observation"})
        for name in current:
            if not np.isfinite(closes.at[day, name]) or closes.at[day, name] <= 0:
                issue.append({"date": day.date().isoformat(), "symbol": name,
                              "input": "held_position_raw_close", "reason": "missing or invalid raw close mark"})
    if issue:
        return {"candidate_id": candidate, "status": "BLOCKED_BEFORE_FIRST_ORDER", "blockers": issue,
                "actual_order_count": 0}
    equity, orders, stats = cash_engine._simulate(
        {"open": opens, "close": closes}, targets, rebalance, CAPITAL, 1.0, SLIPPAGE_BPS,
        start=date.fromisoformat(start_day), end=exec_end.date(), drawdown_limit_pct=1000.0,
        cash_distributions=distributions, liquidate_terminal=False,
    )
    residual = (equity["nav"] - equity["cash_inr"] - equity["invested_inr"]).abs()
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
    for blocker in blockers:
        event_position = order_frame.loc[order_frame["symbol"].eq(blocker["canonical"])]
        held_units = int((event_position["quantity"] * event_position["side"].map({"buy": 1, "sell": -1})).sum())
        if held_units <= 0:
            raise AssertionError(f"{candidate} {blocker['canonical']} event blocker has no held position")
        blocker["held_position_quantity_on_last_valid_mark"] = held_units
        blocker["gross_AGEL_entitlement_before_fractional_treatment"] = held_units * 761 / 1000
        blocker["fractional_treatment"] = "not inferred; source-backed scheme settlement or fractional-share terms required"
    LOCAL.mkdir(parents=True, exist_ok=True)
    order_frame.to_csv(LOCAL / f"{candidate.lower().replace('-', '_')}_orders.csv", index=False)
    equity.to_csv(LOCAL / f"{candidate.lower().replace('-', '_')}_equity.csv", index_label="date")
    result = {"candidate_id": candidate,
              "status": "ACTUAL_PREFIX_STOPPED_AT_UNRESOLVED_HELD_EVENT" if blockers else "ACTUAL_PREFIX",
              "valid_through": exec_end.date().isoformat(),
              "starting_capital_inr": CAPITAL, "actual_order_count": int(len(orders)),
              "actual_buy_count": int(orders["side"].eq("buy").sum()),
              "actual_sell_count": int(orders["side"].eq("sell").sum()),
              "first_order_date": orders["time"].min().date().isoformat() if len(orders) else None,
              "ending_nav_inr": float(equity["nav"].iloc[-1]),
              "ending_cash_inr": float(equity["cash_inr"].iloc[-1]),
              "ending_invested_inr": float(equity["invested_inr"].iloc[-1]),
              "max_drawdown_pct": float(stats["max_drawdown_pct"]),
              "turnover_inr": float(stats["turnover_inr"]), "fees_inr": float(stats["total_fees_inr"]),
              "fees_by_component_inr": stats["fees_by_component_inr"],
              "slippage_cost_inr": float(order_frame["slippage_cost_inr"].sum()) if len(order_frame) else 0.0,
              "max_nav_reconciliation_residual_inr": float(residual.max()),
              "cash_distributions_inr": float(stats["cash_distributions_inr"]),
              "cash_distribution_events": stats["cash_distribution_events"],
              "retained_name_resizing_by_rebalance": retained_resize,
              "first_material_blocker": blockers[0] if blockers else None,
              "later_material_blockers": blockers[1:] if len(blockers) > 1 else [],
              "orders_file_local": str((LOCAL / f"{candidate.lower().replace('-', '_')}_orders.csv").relative_to(ROOT)),
              "equity_file_local": str((LOCAL / f"{candidate.lower().replace('-', '_')}_equity.csv").relative_to(ROOT)),
              "cagr": "NOT REPORTED: stopped prefix, not a full-period result"}
    return result


def self_check() -> None:
    assert choose_selection_bound(0.1, 0.7, 0.75) is False
    assert choose_selection_bound(0.1, 0.8, 0.75) is True
    assert np.isclose((296.05 / ((296.05 + 0.1 * 207) / 1.1)), 1.0281136543, atol=1e-9)
    assert IDFC_INFERENCE["classification"] == "supported_debt_event_inference"
    _, blockers = action_gate(
        "NIFTY200-A-Q", {"2018-04-02": ["INE423A01024"]},
        pd.DataFrame([{"ex_date": pd.Timestamp("2018-04-05"), "resolved_symbol": "ADANIENT",
                       "type": "other", "raw_subject": "Scheme Of Arrangement", "cash_amount": np.nan}]),
        pd.DataFrame([{"symbol": "ADANIENT", "canonical": "INE423A01024"}]),
        list(pd.to_datetime(["2018-04-02", "2018-04-03", "2018-04-05"])),
        date(2018, 4, 2), date(2018, 4, 5))
    assert blockers[0]["held_claim_ratio"] == "761 AGEL shares per 1,000 ADANIENT shares"
    assert blockers[0]["last_valid_account_mark_date"] == "2018-04-04"


def choose_selection_bound(lower: float, upper: float, cutoff: float) -> bool:
    return upper >= cutoff


def run() -> dict:
    sessions, data, actions, signals, index, series_by_canonical, child = setup()
    for (symbol, date_text) in RIGHTS:
        if not actions["symbol"].eq(symbol).where(actions["ex_date"].eq(pd.Timestamp(date_text)), False).any():
            raise ValueError(f"registered rights source event missing for {symbol} {date_text}")
    for (symbol, date_text), amount in DIVIDENDS.items():
        rows = actions.loc[actions["symbol"].eq(symbol) & actions["ex_date"].eq(pd.Timestamp(date_text))]
        if rows.empty or not pd.to_numeric(rows["cash_amount"], errors="coerce").eq(amount).any():
            raise ValueError(f"registered dividend source event/amount missing for {symbol} {date_text}")
    all_certificates, correction_log = {}, []
    prior_by_candidate = {candidate: [] for candidate in FIRST_DATES}
    for candidate, dates in FIRST_DATES.items():
        all_certificates[candidate] = []
        for date_text in dates:
            cert = choose_target(candidate, pd.Timestamp(date_text), prior_by_candidate[candidate], sessions,
                                 signals, index, series_by_canonical, child, correction_log)
            all_certificates[candidate].append(cert)
            if cert["target_status"] != "CERTIFIED_UNDER_REGISTERED_SOURCE_CORRECTIONS":
                break
            prior_by_candidate[candidate] = [r["canonical"] for r in cert["selected"]]
    for candidate, records in all_certificates.items():
        for cert in records:
            cert["canonical_names"] = [r["canonical"] for r in cert["selected"]]
    first_am = all_certificates["NIFTY200-A-M"][0]
    assert first_am["target_status"].startswith("CERTIFIED")
    assert max(x["free_right_score_sensitivity"] for x in first_am["source_resolved_exceptions"]
               if x["free_right_score_sensitivity"] is not None) < first_am["twentieth_positive_score"]
    first_aq = all_certificates["NIFTY200-A-Q"][0]
    tata = next(x for x in first_aq["source_resolved_exceptions"] if x["symbol"] == "TATASTEEL")
    assert tata["free_right_sensitivity_crosses_cutoff"] and tata["corrected_score"] < first_aq["twentieth_positive_score"]
    for candidate in ("NIFTY200-B-M", "NIFTY200-B-Q"):
        for cert in all_certificates[candidate]:
            for row in cert["source_resolved_exceptions"]:
                if row["free_right_score_sensitivity"] is not None:
                    assert row["baseline_annualized_volatility_pct"] is not None
                    assert row["corrected_annualized_volatility_pct"] is not None
                    assert abs(row["volatility_delta_pct"]) > 1e-9
    signals_by_candidate = {candidate: [cert for cert in records if cert["target_status"].startswith("CERTIFIED")]
                            for candidate, records in all_certificates.items()}
    accounts = []
    account_ends = {"NIFTY200-A-M": "2018-04-30", "NIFTY200-B-M": "2018-04-30",
                    "NIFTY200-A-Q": "2018-06-29", "NIFTY200-B-Q": "2018-06-29"}
    for candidate, schedules in signals_by_candidate.items():
        needed = 3 if candidate.endswith("-M") else 1
        if len(schedules) >= needed:
            accounts.append(run_account(candidate, signals, schedules[:needed], data, actions, sessions,
                                        account_ends[candidate]))
        else:
            accounts.append({"candidate_id": candidate, "status": "NO_EXECUTION_UNRESOLVED_FIRST_TARGET",
                             "actual_order_count": 0, "first_material_blocker":
                             schedules[-1].get("unresolved", []) if schedules else "first target not certified"})
    pd.DataFrame(correction_log).drop_duplicates().to_csv(
        ROOT / "outputs" / "nifty200_first_signal_corrections_2026-11-02.csv", index=False)
    result = {"protocol_id": "NIFTY200-v1.5-first-signal-source-corrections",
              "evaluation": {"start": "2018-01-01", "full_end": "2026-10-23"},
              "capital_inr": CAPITAL, "base_slippage_bps_per_side": SLIPPAGE_BPS,
              "cash_yield": "zero", "score_certificates": all_certificates,
              "accounts": accounts,
              "performance_gate": "NO FULL-PERIOD CAGR; results are sequential prefixes only",
              "research_limits": ["IDFC event classification is an evidence-supported inference, not a located exact original notice.",
                                  "RELCAPITAL B volatility remains unknown where RHFL prelisting marks are absent.",
                                  "No result is a 20% full-period CAGR claim or deployable recommendation"]}
    OUT.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))
    return result


if __name__ == "__main__":
    self_check()
    run()

