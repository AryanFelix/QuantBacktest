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
from audit_stock_dividend_terms import parse_dividend


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
RELEVANT_ACTIONS = {"split", "bonus", "dividend", "rights", "merger", "demerger", "spinoff", "other"}
REVIEWED_ACTION_CASH = {
    ("ENGINERSIN", "INE510A01010", "2017-09-11", "dividend"): 0.50,
}
REVIEWED_DIVIDEND_NOTICE_GROUPS = {
    ("SRF", "INE647A01010", "2017-08-16", "2017-08-18", "dividend"): 6.0,
}


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


def routine_dividend_factor_check(cash_amounts: list[float], previous_close: float,
                                 previous_factor: float, exdate_factor: float) -> tuple[bool, str]:
    cash = np.asarray(cash_amounts, dtype=float)
    if not len(cash) or not np.isfinite(cash).all() or (cash < 0).any():
        return False, "missing_or_invalid_dividend_cash_terms"
    if not np.isfinite([previous_close, previous_factor, exdate_factor]).all() or min(previous_close, previous_factor, exdate_factor) <= 0:
        return False, "missing_or_invalid_adjacent_price_or_factor"
    aggregate_cash = float(cash.sum())
    if aggregate_cash >= previous_close or aggregate_cash > previous_close * 0.10:
        return False, "cash_term_exceeds_registered_routine_dividend_limit"
    expected = previous_close / (previous_close - aggregate_cash)
    observed = exdate_factor / previous_factor
    if not np.isclose(expected, observed, rtol=2e-4, atol=2e-5):
        return False, f"adjusted_factor_mismatch; expected={expected:.10g}; observed={observed:.10g}"
    return True, "routine_dividend_terms_match_adjacent_provider_adjustment_factor"


def action_validation_detail(resolved_symbol: str, ex_date: pd.Timestamp, kind: str, isin: str,
                             reasons: dict[tuple[str, pd.Timestamp, str, str], str]) -> str:
    if not resolved_symbol:
        return "unresolved_date_valid_action_identity"
    key = (resolved_symbol.upper(), pd.Timestamp(ex_date), kind.lower(), isin.upper())
    if key in reasons:
        return reasons[key]
    if kind.lower() in {"rights", "merger", "demerger", "spinoff", "other"}:
        return f"{kind.lower()}_signal_entitlement_or_adjusted_value_model_unresolved"
    return "routine_action_terms_or_factor_not_validated"


def normalize_action_records(actions: pd.DataFrame) -> pd.DataFrame:
    actions = actions.copy()
    actions["type"] = actions["type"].astype(str).str.lower()
    for idx, row in actions.iterrows():
        amount, _ = parse_dividend(str(row.get("raw_subject", "")), None)
        if pd.isna(row.get("cash_amount")) and amount is not None:
            actions.at[idx, "cash_amount"] = amount
        if row["type"] == "other" and amount is not None and str(row.get("raw_subject", "")).lower().startswith("int div"):
            actions.at[idx, "type"] = "dividend"
    for (symbol, isin, ex_date, kind), amount in REVIEWED_ACTION_CASH.items():
        mask = (actions["symbol"].eq(symbol) & actions["isin"].eq(isin)
                & actions["ex_date"].eq(pd.Timestamp(ex_date)) & actions["type"].eq(kind))
        assert mask.any() and pd.to_numeric(actions.loc[mask, "cash_amount"], errors="coerce").dropna().empty
        actions.loc[mask, "cash_amount"] = amount
    for (symbol, isin, ex_date, record_date, kind), amount in REVIEWED_DIVIDEND_NOTICE_GROUPS.items():
        mask = (actions["symbol"].eq(symbol) & actions["isin"].eq(isin)
                & actions["ex_date"].eq(pd.Timestamp(ex_date))
                & actions["record_date"].astype(str).eq(record_date) & actions["type"].eq(kind))
        known = pd.to_numeric(actions.loc[mask, "cash_amount"], errors="coerce").dropna().unique()
        assert mask.sum() == 2 and known.tolist() == [amount]
        actions.loc[mask, "cash_amount"] = amount
    return actions.drop_duplicates(["symbol", "isin", "ex_date", "type", "ratio_num", "ratio_den",
                                    "cash_amount", "face_value_from", "face_value_to"])


def routine_share_factor_check(kind: str, term_rows: pd.DataFrame, previous_close: float,
                               exdate_close: float, previous_factor: float,
                               exdate_factor: float) -> tuple[bool, str]:
    terms = term_rows[["ratio_num", "ratio_den", "face_value_from", "face_value_to"]].drop_duplicates()
    if len(terms) != 1 or not np.isfinite([previous_close, exdate_close, previous_factor, exdate_factor]).all():
        return False, "conflicting_terms_or_missing_adjacent_raw_price_factor"
    if min(previous_close, exdate_close, previous_factor, exdate_factor) <= 0:
        return False, "invalid_adjacent_raw_price_or_factor"
    term = terms.iloc[0]
    if kind == "split":
        values = pd.to_numeric(pd.Series([term["face_value_from"], term["face_value_to"]]), errors="coerce").to_numpy()
        if not np.isfinite(values).all() or min(values) <= 0:
            return False, "missing_or_invalid_split_face_value_terms"
        expected = float(values[0] / values[1])
    elif kind == "bonus":
        values = pd.to_numeric(pd.Series([term["ratio_num"], term["ratio_den"]]), errors="coerce").to_numpy()
        if not np.isfinite(values).all() or min(values) <= 0:
            return False, "missing_or_invalid_bonus_ratio_terms"
        expected = float(1 + values[0] / values[1])
    else:
        raise ValueError(f"unsupported share-conversion action: {kind}")
    observed = exdate_factor / previous_factor
    if not np.isclose(expected, observed, rtol=2e-4, atol=2e-5):
        return False, f"adjusted_factor_mismatch; expected={expected:.10g}; observed={observed:.10g}"
    converted_reference = previous_close / expected
    realized_ex_return = exdate_close / converted_reference - 1
    if not np.isfinite(converted_reference) or converted_reference <= 0 or not np.isfinite(realized_ex_return):
        return False, "invalid_raw_price_unit_conversion"
    return True, (f"{kind}_terms_match_adjusted_factor; expected={expected:.10g}; "
                  f"observed={observed:.10g}; unit_adjusted_ex_return={realized_ex_return:.10g}")


def symbol_at(history: pd.DataFrame, isin: str, when: pd.Timestamp) -> str:
    active = history[(history["isin"] == str(isin).upper()) & (history["valid_from"] <= when)
                     & (history["valid_to"].isna() | (history["valid_to"] >= when))]
    values = active["symbol"].dropna().astype(str).str.upper().unique()
    return values[0] if len(values) == 1 else ""


def membership_symbol_map(history: pd.DataFrame, events: pd.DataFrame,
                          reviewed: list[dict[str, str]]) -> dict[str, set[str]]:
    result: dict[str, set[str]] = {}
    for row in history[["isin", "symbol"]].dropna().itertuples(index=False):
        result.setdefault(str(row.isin).upper(), set()).add(str(row.symbol).upper())
    for row in events.to_dict("records"):
        symbol = str(row.get("symbol", "")).upper()
        isin = str(row.get("isin", "")).upper()
        if symbol and isin:
            result.setdefault(isin, set()).add(symbol)
        if symbol and row.get("action") == "isin_bridge":
            for key in ("from_isin", "to_isin"):
                value = str(row.get(key, "")).upper()
                if value:
                    result.setdefault(value, set()).add(symbol)
    for row in reviewed:
        for key in ("from_isin", "to_isin"):
            result.setdefault(row[key].upper(), set()).add(row["symbol"].upper())
    return result


def member_identity_at(interval_isin: str, when: pd.Timestamp, history: pd.DataFrame,
                       symbols_by_isin: dict[str, set[str]],
                       history_by_isin: dict[str, pd.DataFrame] | None = None,
                       history_by_symbol: dict[str, pd.DataFrame] | None = None) -> tuple[str, str, str]:
    interval_isin = str(interval_isin).upper()
    isin_rows = history_by_isin.get(interval_isin, history.iloc[0:0]) if history_by_isin is not None else history[history["isin"].eq(interval_isin)]
    direct = isin_rows[(isin_rows["valid_from"] <= when)
                       & (isin_rows["valid_to"].isna() | (isin_rows["valid_to"] >= when))]
    direct_symbols = direct["symbol"].dropna().astype(str).str.upper().unique()
    if len(direct_symbols) == 1:
        return direct_symbols[0], interval_isin, "date_valid_interval_isin"
    if len(direct_symbols) > 1:
        return "", interval_isin, "ambiguous_date_valid_symbol_identity"
    candidates = set()
    for symbol in symbols_by_isin.get(interval_isin, set()):
        symbol_rows = history_by_symbol.get(symbol, history.iloc[0:0]) if history_by_symbol is not None else history[history["symbol"].eq(symbol)]
        active = symbol_rows[(symbol_rows["valid_from"] <= when)
                             & (symbol_rows["valid_to"].isna() | (symbol_rows["valid_to"] >= when))]
        active_isins = active["isin"].dropna().astype(str).str.upper().unique()
        if len(active_isins) == 1:
            candidates.add((symbol, active_isins[0]))
        elif len(active_isins) > 1:
            return "", interval_isin, "ambiguous_date_valid_symbol_identity"
    if len(candidates) == 1:
        symbol, isin = next(iter(candidates))
        return symbol, isin, "exact_membership_symbol_date_history"
    return "", interval_isin, "unresolved_date_valid_membership_identity"


def identity_closure(member_isins: set[str], symbols_by_isin: dict[str, set[str]],
                     history: pd.DataFrame) -> set[str]:
    symbols = set().union(*(symbols_by_isin.get(isin, set()) for isin in member_isins))
    return {str(isin).upper() for isin in history.loc[history["symbol"].isin(symbols), "isin"].dropna()}


def resolve_action_symbols(actions: pd.DataFrame, history: pd.DataFrame,
                           reviewed: list[dict[str, str]]) -> tuple[pd.Series, pd.Series]:
    bridge_action_symbols: dict[tuple[str, pd.Timestamp], set[str]] = {}
    for row in reviewed:
        if row.get("action_feed_isin") and row.get("economic_ex_date"):
            key = (row["action_feed_isin"].upper(), pd.Timestamp(row["economic_ex_date"]).normalize())
            bridge_action_symbols.setdefault(key, set()).add(row["symbol"].upper())
    result = pd.Series("", index=actions.index, dtype=object)
    method = pd.Series("unresolved", index=actions.index, dtype=object)
    dated_actions = actions.loc[actions["ex_date"].notna()].reset_index(names="_row")
    if not dated_actions.empty:
        history_lookup = history[["isin", "symbol", "valid_from", "valid_to"]].copy()
        history_lookup = history_lookup.rename(columns={"symbol": "history_symbol"})
        history_lookup = history_lookup[history_lookup["valid_from"].notna()]
        overlap_isins = set()
        for isin, group in history_lookup.sort_values(["isin", "valid_from"]).groupby("isin", sort=False):
            ends = group["valid_to"].shift()
            has_previous = pd.Series(True, index=group.index).shift(fill_value=False)
            starts = group["valid_from"]
            if (has_previous & (ends.isna() | starts.le(ends).fillna(False))).any():
                overlap_isins.add(isin)
        dated_actions = dated_actions.sort_values(["ex_date", "isin"], kind="stable")
        history_lookup = history_lookup.sort_values(["valid_from", "isin"], kind="stable")
        joined = pd.merge_asof(
            dated_actions,
            history_lookup,
            left_on="ex_date",
            right_on="valid_from",
            by="isin",
            direction="backward",
            allow_exact_matches=True,
        )
        active = joined["valid_from"].notna() & (joined["valid_to"].isna() | joined["ex_date"].le(joined["valid_to"]))
        active &= ~joined["isin"].isin(overlap_isins)
        result.loc[joined.loc[active, "_row"]] = joined.loc[active, "history_symbol"].str.upper().to_numpy()
        method.loc[joined.loc[active, "_row"]] = "date_valid_vendor_isin"
    bridge_symbol = {key: next(iter(names)) for key, names in bridge_action_symbols.items() if len(names) == 1}
    unresolved = result.eq("") & actions["ex_date"].notna()
    exact_bridge = pd.Series(list(zip(actions.loc[unresolved, "isin"], actions.loc[unresolved, "ex_date"])), index=actions.index[unresolved]).map(bridge_symbol)
    result.loc[exact_bridge.dropna().index] = exact_bridge.dropna().to_numpy()
    method.loc[exact_bridge.dropna().index] = "exact_reviewed_action_bridge"
    unresolved = result.eq("") & actions["ex_date"].notna()
    symbol_events = actions.loc[unresolved, ["symbol", "ex_date"]].reset_index(names="_row")
    symbol_lookup = history[["isin", "symbol", "valid_from", "valid_to"]].dropna(subset=["valid_from"]).copy()
    symbol_overlaps = set()
    for symbol, group in symbol_lookup.sort_values(["symbol", "valid_from"]).groupby("symbol", sort=False):
        ends = group["valid_to"].shift()
        has_previous = pd.Series(True, index=group.index).shift(fill_value=False)
        if (has_previous & (ends.isna() | group["valid_from"].le(ends).fillna(False))).any():
            symbol_overlaps.add(symbol)
    if not symbol_events.empty:
        symbol_events = symbol_events.sort_values(["ex_date", "symbol"], kind="stable")
        symbol_lookup = symbol_lookup.sort_values(["valid_from", "symbol"], kind="stable")
        joined = pd.merge_asof(
            symbol_events, symbol_lookup, left_on="ex_date", right_on="valid_from",
            by="symbol", direction="backward", allow_exact_matches=True,
        )
        active = joined["valid_from"].notna() & (joined["valid_to"].isna() | joined["ex_date"].le(joined["valid_to"]))
        active &= ~joined["symbol"].isin(symbol_overlaps) & joined["isin"].notna()
        result.loc[joined.loc[active, "_row"]] = joined.loc[active, "symbol"].str.upper().to_numpy()
        method.loc[joined.loc[active, "_row"]] = "exact_vendor_symbol_date_history"
    return result, method


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
        return "Checked the date-valid vendor ISIN, exact reviewed action bridge, and exact vendor-symbol/date identity; routine terms also require adjacent raw/adjusted-factor agreement. No nearest-ISIN match or entitlement was assumed."
    if kind == "held_position_close":
        return "Checked the exact ISIN/session in pinned TejHQ EOD and the 18-date official NSE supplement; no stale or zero mark was substituted."
    if kind == "conditional_target_open_observation":
        return "Checked the exact ISIN/execution date in pinned TejHQ EOD and the 18-date official NSE supplement for this name-change diagnostic; this is not a simulated fill."
    if kind == "next_session_order":
        return "Checked the corrected source-session calendar through the evaluation cutoff; no in-window next session is available."
    return "Retained as unresolved after the exact source/date/entity checks recorded above."


def load_data() -> tuple[list[pd.Timestamp], pd.DataFrame, pd.DataFrame, pd.DataFrame, dict[str, set[str]], list[dict], list[dict], dict[str, str], pd.DataFrame]:
    intervals = pd.read_csv(INTERVALS, dtype=str).fillna("")
    if not intervals["replay_status"].eq("CERTIFIED").all():
        raise ValueError("NIFTY 200 membership intervals are not replay-certified")
    member_isins = set(intervals["isin"].str.upper())
    reviewed = [row for row in read_csv(REVIEWED_BRIDGES) if row["status"] == "verified"]
    verified_pairs = {(r["from_isin"].upper(), r["to_isin"].upper()) for r in reviewed}
    canonical = union_find(member_isins, reviewed)
    history = pd.read_parquet(PUBLIC / "tejhq" / "symbol_history" / "nse.parquet")
    history["isin"] = history["isin"].astype(str).str.upper()
    history["symbol"] = history["symbol"].astype(str).str.upper()
    history["valid_from"] = pd.to_datetime(history["valid_from"], errors="coerce").dt.normalize()
    history["valid_to"] = pd.to_datetime(history["valid_to"], errors="coerce").dt.normalize()
    member_events = pd.read_csv(PUBLIC / "membership" / "operative_events.csv", dtype=str).fillna("")
    symbols_by_isin = membership_symbol_map(history, member_events, reviewed)
    data_isins = (member_isins | {isin for row in reviewed for isin in (row["from_isin"].upper(), row["to_isin"].upper())}
                  | identity_closure(member_isins, symbols_by_isin, history))

    raw_files = sorted(RAW_DIR.glob("year=*/nse_*.parquet"))
    raw_ds = ds.dataset([str(p) for p in raw_files], format="parquet")
    all_dates = {pd.Timestamp(x) for x in raw_ds.to_table(columns=["date"])["date"].to_pylist() if x}
    backfill_dates = pd.to_datetime(pd.read_parquet(BACKFILL, columns=["date"])["date"]).dropna()
    all_dates.update(pd.Timestamp(x) for x in backfill_dates)
    sessions = sorted(pd.Timestamp(x).normalize() for x in all_dates)

    raw = raw_ds.to_table(
        columns=["date", "symbol", "series", "isin", "open", "high", "low", "close", "turnover"],
        filter=ds.field("isin").isin(sorted(data_isins)),
    ).to_pandas()
    raw["source"] = "TejHQ public NSE EOD mirror"
    supplement = pd.read_parquet(BACKFILL, columns=["date", "symbol", "series", "isin", "open", "high", "low", "close", "turnover", "source_file"])
    supplement = supplement[supplement["isin"].astype(str).str.upper().isin(data_isins)].copy()
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
        filter=ds.field("isin").isin(sorted(data_isins)),
    ).to_pandas()
    adj["factor_status"] = ""
    adj_supplement = pd.read_parquet(ADJ_BACKFILL, columns=["date", "isin", "series", "adj_close", "adj_factor_cumulative", "factor_status"])
    adj_supplement = adj_supplement[adj_supplement["isin"].astype(str).str.upper().isin(data_isins)].copy()
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

    actions = pd.concat([pd.read_parquet(p) for p in sorted(ACTION_DIR.glob("nse_*.parquet"))], ignore_index=True)
    actions["ex_date"] = pd.to_datetime(actions["ex_date"], errors="coerce").dt.normalize()
    actions["symbol"] = actions["symbol"].astype(str).str.upper()
    actions["isin"] = actions["isin"].astype(str).str.upper()
    actions = normalize_action_records(actions)
    actions["resolved_symbol"], actions["resolution_method"] = resolve_action_symbols(actions, history, reviewed)
    actions["term_variants"] = actions.groupby(["symbol", "isin", "ex_date", "type"], dropna=False)["type"].transform("size")
    replay_rows = read_csv(REPLAY_BRIDGES)
    unreviewed = [r for r in replay_rows if (r["from_isin"].upper(), r["to_isin"].upper()) not in verified_pairs]
    return sessions, intervals, data, actions, symbols_by_isin, reviewed, unreviewed, canonical, history


def audit() -> dict:
    sessions, intervals, data, actions, symbols, reviewed, unreviewed, canonical, history = load_data()
    history_by_isin = {key: frame for key, frame in history.groupby("isin", sort=False)}
    history_by_symbol = {key: frame for key, frame in history.groupby("symbol", sort=False)}
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
    identity_prices = {}
    for isin, frame in data.groupby("isin", sort=False):
        frame = frame.sort_values("date")
        duplicate_dates = set(frame.loc[frame.duplicated("date", keep=False), "date"])
        frame = frame.drop_duplicates("date", keep=False).set_index("date").reindex(sessions)
        closes = pd.to_numeric(frame["close"], errors="coerce").to_numpy(dtype=float)
        factors = pd.to_numeric(frame["adj_factor_cumulative"], errors="coerce").to_numpy(dtype=float)
        for day in duplicate_dates:
            if day in index:
                closes[index[day]] = np.nan
                factors[index[day]] = np.nan
        identity_prices[isin] = (closes, factors)
    previous_session = {sessions[i]: sessions[i - 1] for i in range(1, len(sessions))}
    factor_validated_actions = set()
    factor_validation_counts = {
        f"{kind}_events_{status}": 0
        for kind in ("dividend", "split", "bonus")
        for status in ("checked", "supported", "unresolved")
    }
    factor_validation_counts["supported_with_stale_vendor_isin"] = 0
    history_by_symbol_for_actions = {key: group for key, group in history.groupby("symbol", sort=False)}
    factor_validation_reasons: dict[tuple[str, pd.Timestamp, str, str], str] = {}

    def active_action_isin(symbol: str, when: pd.Timestamp) -> str:
        rows = history_by_symbol_for_actions.get(str(symbol).upper())
        if rows is None:
            return ""
        active = rows[(rows["valid_from"] <= when) & (rows["valid_to"].isna() | (rows["valid_to"] >= when))]
        values = active["isin"].dropna().astype(str).str.upper().unique()
        return values[0] if len(values) == 1 else ""

    for (resolved, isin, ex_date, kind), group in actions.groupby(
            ["resolved_symbol", "isin", "ex_date", "type"], dropna=False, sort=False):
        kind = str(kind).lower()
        if kind not in {"dividend", "split", "bonus"} or not resolved or pd.isna(ex_date):
            continue
        factor_validation_counts[f"{kind}_events_checked"] += 1
        prior_date = previous_session.get(pd.Timestamp(ex_date))
        position = index.get(pd.Timestamp(ex_date))
        prior_position = index.get(prior_date) if prior_date is not None else None
        event_isin = str(isin).upper()
        price_isin = event_isin if symbol_at(history, event_isin, pd.Timestamp(ex_date)) == str(resolved).upper() else active_action_isin(str(resolved), pd.Timestamp(ex_date))
        prices = identity_prices.get(price_isin)
        if prices is None or position is None or prior_position is None:
            ok, validation_reason = False, "missing_exact_identity_adjacent_rows"
        elif kind == "dividend":
            cash_amounts = pd.to_numeric(group["cash_amount"], errors="coerce").tolist()
            ok, validation_reason = routine_dividend_factor_check(cash_amounts, prices[0][prior_position],
                                                                   prices[1][prior_position], prices[1][position])
        else:
            ok, validation_reason = routine_share_factor_check(kind, group, prices[0][prior_position],
                                                                prices[0][position], prices[1][prior_position],
                                                                prices[1][position])
        identity_ok = bool(price_isin and symbol_at(history, price_isin, pd.Timestamp(ex_date)) == str(resolved).upper())
        if ok and not identity_ok:
            validation_reason = "no_unique_active_event_identity_matches_factor_price_series"
        factor_key = (str(resolved).upper(), pd.Timestamp(ex_date), kind, event_isin)
        factor_validation_reasons[factor_key] = validation_reason
        if ok and identity_ok:
            factor_validated_actions.add((str(resolved).upper(), pd.Timestamp(ex_date), kind, event_isin))
            factor_validation_counts[f"{kind}_events_supported"] += 1
            if price_isin != event_isin:
                factor_validation_counts["supported_with_stale_vendor_isin"] += 1
        else:
            factor_validation_counts[f"{kind}_events_unresolved"] += 1
    reviewed_pairs = {(r["from_isin"].upper(), r["to_isin"].upper()) for r in reviewed}
    transitions = []
    history = history.copy()
    history["valid_from"] = pd.to_datetime(history["valid_from"], errors="coerce").dt.normalize()
    history["valid_to"] = pd.to_datetime(history["valid_to"], errors="coerce").dt.normalize()
    history_by_isin = {key: group for key, group in history.groupby("isin", sort=False)}
    symbol_cache: dict[tuple[str, pd.Timestamp], str] = {}

    def symbol_on(isin: str, when: pd.Timestamp) -> str:
        key = (str(isin).upper(), pd.Timestamp(when).normalize())
        if key not in symbol_cache:
            rows = history_by_isin.get(key[0])
            active = rows[(rows["valid_from"] <= key[1]) & (rows["valid_to"].isna() | (rows["valid_to"] >= key[1]))] if rows is not None else history.iloc[0:0]
            values = active["symbol"].dropna().astype(str).str.upper().unique()
            symbol_cache[key] = values[0] if len(values) == 1 else ""
        return symbol_cache[key]

    for _, group in history.sort_values("valid_from").groupby("symbol", sort=False):
        rows = list(group.itertuples(index=False))
        for old, new in zip(rows, rows[1:]):
            pair = (str(old.isin).upper(), str(new.isin).upper())
            if previous_session.get(new.valid_from) == old.valid_to and pair not in reviewed_pairs:
                transitions.append({"symbol": str(new.symbol).upper(), "from_isin": pair[0], "to_isin": pair[1], "date": new.valid_from})
    transitions_by_symbol = {}
    for event in transitions:
        transitions_by_symbol.setdefault(event["symbol"], []).append(event)
    action_key = actions["resolved_symbol"].where(actions["resolved_symbol"].ne(""), actions["symbol"])
    actions_by_symbol = {key: frame.sort_values("ex_date").reset_index(drop=True)
                         for key, frame in actions.assign(action_key=action_key).groupby("action_key", sort=False)}

    month_ends = pd.DataFrame({"date": [d for d in sessions if START <= d <= CUTOFF]})
    month_ends = month_ends.groupby(month_ends["date"].dt.to_period("M"))["date"].max().tolist()
    month_ends = [d for d in month_ends if d.month <= 9 or d < pd.Timestamp("2026-10-01")]
    schedules = {
        "M": month_ends,
        "Q": [d for d in month_ends if d.month in {3, 6, 9, 12}],
    }
    dependencies, signals, orders, marks = [], [], [], []
    summaries = {}
    membership_identity_method_counts: dict[str, int] = {}
    membership_identity_fallback_pairs: set[tuple[str, str, str]] = set()

    for rule in ("A", "B"):
        for cadence in ("M", "Q"):
            candidate_id = f"NIFTY200-{rule}-{cadence}"
            print(f"Auditing dependencies: {candidate_id}", flush=True)
            prior: list[str] = []
            decisions = []
            for decision in schedules[cadence]:
                decision_dependency_start = len(dependencies)
                i = index[decision]
                members = intervals[(pd.to_datetime(intervals["valid_from"]) <= decision)
                                    & (pd.to_datetime(intervals["valid_to"]) >= decision)]
                member_rows = []
                for membership_isin in members["isin"].str.upper():
                    symbol, isin, identity_method = member_identity_at(
                        membership_isin, decision, history, symbols, history_by_isin, history_by_symbol
                    )
                    membership_identity_method_counts[identity_method] = membership_identity_method_counts.get(identity_method, 0) + 1
                    if identity_method == "exact_membership_symbol_date_history":
                        membership_identity_fallback_pairs.add((membership_isin, isin, symbol))
                    member_rows.append({
                        "membership_isin": membership_isin, "isin": isin, "symbol": symbol,
                        "identity_method": identity_method, "canonical": canonical.get(isin, isin),
                    })
                canonical_counts = pd.Series([r["canonical"] for r in member_rows]).value_counts()
                duplicate_canonicals = set(canonical_counts[canonical_counts.gt(1)].index)
                scored = []
                unresolved_signal_count = 0
                for member in member_rows:
                    membership_isin = member["membership_isin"]
                    isin, symbol, identity_method, canon = (
                        member["isin"], member["symbol"], member["identity_method"], member["canonical"]
                    )
                    frame = series.get(canon)
                    if frame is None:
                        frame = series.get(isin)
                    price_values = adjusted_values.get(canon, adjusted_values.get(isin))
                    raw_close_values = close_values.get(canon, close_values.get(isin))
                    reason_list = []
                    identity_ok = bool(symbol and identity_method != "unresolved_date_valid_membership_identity"
                                       and identity_method != "ambiguous_date_valid_symbol_identity"
                                       and canon not in duplicate_canonicals)
                    score, score_reason = ((None, "date_valid_membership_identity_unresolved") if not identity_ok else
                                           ((None, "missing_identity_price_series") if price_values is None else score_at(price_values, i, rule)))
                    if not identity_ok:
                        reason_list.append(identity_method if canon not in duplicate_canonicals else "duplicate_canonical_membership_identity")
                        dependencies.append({"candidate_id": candidate_id, "rule": rule, "date": decision.date().isoformat(),
                                             "entity": f"{symbol}|{membership_isin}->{isin}", "input": "signal_identity",
                                             "source": "NIFTY 200 membership symbol and TejHQ point-in-time symbol history",
                                             "reason": f"membership ISIN {membership_isin} did not resolve to one date-valid instrument; method={identity_method}",
                                             "impact": "ranking-changing candidate identity unknown"})
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
                            action_identity_key = (symbol, pd.Timestamp(event.ex_date), kind, str(event.isin).upper())
                            if not event.resolved_symbol or (event_key not in verified_action_keys and action_identity_key not in factor_validated_actions):
                                support_detail = action_validation_detail(
                                    str(event.resolved_symbol), pd.Timestamp(event.ex_date), kind,
                                    str(event.isin), factor_validation_reasons,
                                )
                                why = ("historical signal action identity unresolved against point-in-time ISIN history"
                                       if not event.resolved_symbol else "historical signal action unresolved under registered terms/factor policy")
                                variants = int(getattr(event, "term_variants", 1))
                                variant_note = f"; source contains {variants} distinct term rows" if variants > 1 else ""
                                term_note = "; vendor terms=" + ",".join(
                                    f"{field}:{getattr(event, field)}" for field in
                                    ("ratio_num", "ratio_den", "cash_amount", "face_value_from", "face_value_to")
                                    if pd.notna(getattr(event, field))
                                )
                                reason_list.append(why)
                                dependencies.append({"candidate_id": candidate_id, "rule": rule, "date": event.ex_date.date().isoformat(),
                                                     "entity": f"{symbol}|{isin}", "input": f"signal_{kind}",
                                                     "source": "TejHQ NSE corporate-action feed",
                                                     "reason": f"{why}; vendor action ISIN={event.isin}{term_note}{variant_note}; support check={support_detail}",
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
                                   "symbol": symbol, "isin": isin, "membership_interval_isin": membership_isin,
                                   "identity_resolution_method": identity_method, "canonical": canon,
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
                active = {r["canonical"]: r["membership_interval_isin"] for r in scored}
                if exec_date is None or exec_date > CUTOFF:
                    dependencies.append({"candidate_id": candidate_id, "rule": rule, "date": decision.date().isoformat(),
                                         "entity": "", "input": "next_session_order", "source": "source-session calendar",
                                         "reason": "no in-window next-session execution date", "impact": "strategy path cannot execute"})
                else:
                    execution = data[(data["date"] == exec_date) & data["canonical"].isin(set(prior) | set(target))]
                    open_by = execution.groupby("canonical")["open"].first().to_dict()
                    for canon in sorted(set(prior) ^ set(target)):
                        side = "BUY" if canon in target else "SELL"
                        membership_isin = active.get(canon, canon)
                        order_symbol, isin, execution_identity_method = member_identity_at(
                            membership_isin, exec_date, history, symbols, history_by_isin, history_by_symbol
                        )
                        open_px = open_by.get(canon, np.nan)
                        status = "OBSERVED" if np.isfinite(open_px) and open_px > 0 else "MISSING_OPEN"
                        if not order_symbol or execution_identity_method in {
                            "unresolved_date_valid_membership_identity", "ambiguous_date_valid_symbol_identity"
                        }:
                            status = "UNRESOLVED_IDENTITY"
                        orders.append({"candidate_id": candidate_id, "signal_date": decision.date().isoformat(),
                                       "execution_date": exec_date.date().isoformat(), "side": side,
                                       "symbol": order_symbol, "isin": isin, "canonical": canon,
                                       "membership_interval_isin": membership_isin,
                                       "identity_resolution_method": execution_identity_method,
                                       "raw_open": open_px if status == "OBSERVED" else "",
                                       "dependency_status": status, "conditional_signal_set": conditional})
                        if status != "OBSERVED":
                            dependencies.append({"candidate_id": candidate_id, "rule": rule, "date": exec_date.date().isoformat(),
                                                 "entity": f"{order_symbol}|{isin}",
                                                 "input": "conditional_target_identity" if not order_symbol else "conditional_target_open_observation",
                                                 "source": "TejHQ point-in-time symbol history" if not order_symbol else "TejHQ NSE cash EOD + official NSE backfill",
                                                 "reason": f"{side} conditional target lacks a unique date-valid instrument identity" if not order_symbol else f"{side} conditional target name-change has no positive finite next-session open",
                                                 "impact": "conditional target availability only; not an account fill"})
                active_at_execution = {}
                for canon in target:
                    membership_isin = active.get(canon, canon)
                    _, active_isin, _ = member_identity_at(
                        membership_isin, exec_date or decision, history, symbols, history_by_isin, history_by_symbol
                    )
                    active_at_execution[canon] = active_isin
                decisions.append({"date": decision, "exec_date": exec_date, "target": target,
                                  "active": active_at_execution, "conditional": conditional, "scores": score_map})
                for dependency in dependencies[decision_dependency_start:]:
                    dependency["signal_date"] = decision.date().isoformat()
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
                position_dependency_start = len(dependencies)
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
                    held_isin = decision_row["active"].get(canon, canon)
                    symbol = symbol_on(held_isin, start_date)
                    if not symbol:
                        dependencies.append({"candidate_id": candidate_id, "rule": rule, "date": start_date.date().isoformat(),
                                             "entity": held_isin, "input": "held_identity", "source": "TejHQ point-in-time symbol history",
                                             "reason": "held ISIN has no unique active symbol at position entry",
                                             "impact": "position identity cannot be valued or exited"})
                    if symbol:
                        symbol_actions = actions_by_symbol.get(symbol, actions.iloc[0:0])
                        held_actions = symbol_actions[symbol_actions["ex_date"].between(start_date, sessions[end_i])]
                        unique_held_events = held_actions.drop_duplicates(["symbol", "ex_date", "type", "isin"])
                        for event in unique_held_events.itertuples(index=False):
                            kind = str(event.type).lower()
                            if kind not in RELEVANT_ACTIONS:
                                continue
                            if event.resolved_symbol and (symbol, pd.Timestamp(event.ex_date), kind) in verified_action_keys:
                                continue
                            variants = int(getattr(event, "term_variants", 1))
                            variant_note = f"; source contains {variants} distinct term rows" if variants > 1 else ""
                            term_note = "; vendor terms=" + ",".join(
                                f"{field}:{getattr(event, field)}" for field in
                                ("ratio_num", "ratio_den", "cash_amount", "face_value_from", "face_value_to")
                                if pd.notna(getattr(event, field))
                            )
                            dependencies.append({"candidate_id": candidate_id, "rule": rule, "date": event.ex_date.date().isoformat(),
                                                 "entity": f"{symbol}|{event.isin}", "input": f"held_entitlement_{kind}",
                                                 "source": "TejHQ NSE corporate-action feed",
                                                 "reason": f"actual held interval crosses unreconciled {kind} terms/entitlement; vendor action ISIN={event.isin}{term_note}{variant_note}",
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
                for dependency in dependencies[position_dependency_start:]:
                    dependency["signal_date"] = decision_row["date"].date().isoformat()
            candidate_dependencies = [r for r in dependencies if r["candidate_id"] == candidate_id]
            candidate_signal_actions = [r for r in candidate_dependencies
                                        if str(r["input"]).startswith("signal_") and r["input"] not in {
                                            "signal_window", "signal_adjustment_factor", "signal_identity_bridge"}]
            candidate_held_marks = [r for r in candidate_dependencies if r["input"] == "held_position_close"]
            candidate_order_gaps = [r for r in candidate_dependencies if r["input"] == "conditional_target_open_observation"]
            summaries[candidate_id] = {
                "scheduled_decisions": len(decisions), "total_member_signal_rows": len([r for r in signals if r["candidate_id"] == candidate_id]),
                "decisions_with_unresolved_member_signals": sum(r["conditional"] for r in decisions),
                "conditional_target_name_changes": len([r for r in orders if r["candidate_id"] == candidate_id]),
                "conditional_target_expected_close_marks": expected_marks,
                "conditional_target_observed_close_marks": observed_marks,
                "conditional_target_missing_close_marks": expected_marks - observed_marks,
                "unreviewed_signal_action_path_incidences": len(candidate_signal_actions),
                "unreviewed_signal_action_unique_events": len({dependency_source_key(r) for r in candidate_signal_actions}),
                "conditional_target_held_action_path_incidences": sum(r["input"].startswith("held_entitlement_") for r in candidate_dependencies),
                "conditional_target_held_action_unique_events": len({dependency_source_key(r) for r in candidate_dependencies if r["input"].startswith("held_entitlement_")}),
                "conditional_target_open_missing_count": len(candidate_order_gaps),
                "conditional_target_open_missing_unique_entity_dates": len({dependency_source_key(r) for r in candidate_order_gaps}),
                "conditional_target_close_gap_path_incidences": len(candidate_held_marks),
                "conditional_target_close_gap_unique_entity_dates": len({dependency_source_key(r) for r in candidate_held_marks}),
                "unreviewed_identity_signal_path_incidences": sum(r["input"] == "signal_identity_bridge" for r in candidate_dependencies),
                "unresolved_adjustment_factor_signal_windows": sum(r["input"] == "signal_adjustment_factor" for r in candidate_dependencies),
                "ranking_changing_signal_dependencies": sum(r["candidate_id"] == candidate_id and r["impact"].startswith("ranking-changing signal") for r in dependencies),
                "missing_adjusted_signal_windows": sum(r["candidate_id"] == candidate_id and r["input"] == "signal_window" for r in dependencies),
                "promotable": not any(r["candidate_id"] == candidate_id for r in dependencies),
            }
            print(f"Completed dependencies: {candidate_id}", flush=True)

    for dependency in dependencies:
        dependency["resolution_attempt"] = resolution_attempt_for(dependency)
    out_dir = PUBLIC / "strategy_dependencies" / "nifty200"
    atomic_csv(out_dir / "signal_dependencies.csv", signals,
               ["candidate_id", "signal_date", "symbol", "isin", "membership_interval_isin", "identity_resolution_method",
                "canonical", "score", "rank", "score_status", "unresolved_reason"])
    atomic_csv(out_dir / "conditional_target_name_changes.csv", orders,
               ["candidate_id", "signal_date", "execution_date", "side", "symbol", "isin", "canonical", "raw_open", "dependency_status", "conditional_signal_set"])
    atomic_csv(out_dir / "position_valuation_windows.csv", marks,
               ["candidate_id", "signal_date", "execution_date", "canonical", "expected_close_marks", "observed_close_marks", "conditional_signal_set"])
    atomic_csv(out_dir / "unresolved_dependencies.csv", dependencies,
               ["candidate_id", "signal_date", "rule", "date", "entity", "input", "source", "reason", "resolution_attempt", "impact"])
    dependency_incidence, unique_dependency_sources = dependency_counts(dependencies)
    unique_close_gaps = len({dependency_source_key(r) for r in dependencies if r["input"] == "held_position_close"})
    unique_order_gaps = len({dependency_source_key(r) for r in dependencies if r["input"] == "conditional_target_open_observation"})
    dated_action_symbol_corrections = actions.loc[
        actions["resolved_symbol"].ne("") & actions["symbol"].ne(actions["resolved_symbol"])
    ]
    action_symbol_examples = dated_action_symbol_corrections[["symbol", "resolved_symbol", "ex_date", "isin", "type"]].drop_duplicates()
    result = {
        "protocol_id": "NIFTY200-v1.3", "audit_type": "non-P&L candidate dependency audit",
        "schedule_sweep_semantics": "Signal dependencies cover all frozen decisions. Name-change opens and conditional holdings are hypothetical availability diagnostics; actual strategy accounts stop at each first unresolved signal before any order.",
        "evaluation_start": START.date().isoformat(), "evaluation_cutoff": CUTOFF.date().isoformat(),
        "working_calendar_sessions_with_warmup": len(sessions),
        "evaluation_source_calendar_sessions": sum(START <= day <= CUTOFF for day in sessions),
        "calendar_basis": "TejHQ raw source dates plus 18 primary NSE EOD sessions; not globally certified",
        "membership_replay_certified": True, "membership_replay_failed_batches": 0,
        "membership_interval_isins": len(set(intervals["isin"].str.upper())),
        "loaded_point_in_time_identity_isins": int(data["isin"].nunique()),
        "additional_identity_isins_loaded_for_symbol_and_bridge_closure": len(set(data["isin"].str.upper()) - set(intervals["isin"].str.upper())),
        "membership_identity_resolution_method_counts": membership_identity_method_counts,
        "membership_identity_fallback_pairs": [
            {"membership_interval_isin": old, "active_date_valid_isin": new, "symbol": symbol}
            for old, new, symbol in sorted(membership_identity_fallback_pairs)
        ],
        "manual_verified_identity_bridges": [r["symbol"] for r in reviewed if r["membership_replay"].lower() == "true"],
        "reviewed_bridge_date_discrepancies": [
            {"symbol": r["symbol"],
             "official_trade_isin_effective_date": r.get("official_trade_isin_effective_date", ""),
             "economic_ex_date": r["economic_ex_date"],
             "vendor_first_new_observation": r["vendor_first_new_observation"],
             "discrepancy": r["identity_date_conflict"]}
            for r in reviewed if r.get("identity_date_conflict") and r["identity_date_conflict"].lower() != "no"
        ],
        "automatic_identity_bridges_not_independently_reviewed": len(unreviewed),
        "configurations": summaries, "dependency_rows": len(dependencies),
        "dependency_path_incidence_counts": dependency_incidence,
        "unique_source_entity_date_type_counts": unique_dependency_sources,
        "routine_action_factor_validation": factor_validation_counts,
        "action_event_status_counts": {
            kind: {
                "supported_under_documented_source_assumptions": factor_validation_counts[f"{kind}_events_supported"],
                "requires_exceptional_review": factor_validation_counts[f"{kind}_events_unresolved"],
                "demonstrably_invalid": 0,
            }
            for kind in ("dividend", "split", "bonus")
        },
        "action_identity_resolution_counts": actions.drop_duplicates(["symbol", "isin", "ex_date", "type"])["resolution_method"].value_counts().to_dict(),
        "date_valid_action_symbol_corrections": int(len(dated_action_symbol_corrections)),
        "date_valid_action_symbol_correction_examples": [
            {"vendor_symbol": row.symbol, "date_valid_symbol": row.resolved_symbol,
             "ex_date": pd.Timestamp(row.ex_date).date().isoformat(), "vendor_isin": row.isin,
             "type": row.type}
            for row in action_symbol_examples.head(8).itertuples(index=False)
        ],
        "factor_validation_scope": "Counts cover formula-checked NSE dividend/split/bonus groups with a resolved event identity. Unsupported groups require exceptional review, are not presumed invalid, and are not NIFTY200 blocker totals; unresolved action identities are tracked separately.",
        "conditional_target_close_gap_unique_entity_dates": unique_close_gaps,
        "conditional_target_open_gap_unique_entity_dates": unique_order_gaps,
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
    assert routine_dividend_factor_check([12.0], 1602.4, 0.871970, 0.878549)[0]
    assert routine_dividend_factor_check([2.0, 3.0], 100.0, 1.0, 100 / 95)[0]
    assert not routine_dividend_factor_check([12.0], 100.0, 1.0, 1.0)[0]
    assert not routine_dividend_factor_check([11.0], 100.0, 1.0, 1.0)[0]
    reviewed_actions = normalize_action_records(pd.DataFrame([
        {"symbol": "SRF", "isin": "INE647A01010", "ex_date": pd.Timestamp("2017-08-16"),
         "record_date": "2017-08-18", "type": "dividend", "ratio_num": np.nan,
         "ratio_den": np.nan, "cash_amount": np.nan, "face_value_from": np.nan,
         "face_value_to": np.nan, "raw_subject": "Interim Dividend"},
        {"symbol": "SRF", "isin": "INE647A01010", "ex_date": pd.Timestamp("2017-08-16"),
         "record_date": "2017-08-18", "type": "dividend", "ratio_num": np.nan,
         "ratio_den": np.nan, "cash_amount": 6.0, "face_value_from": np.nan,
         "face_value_to": np.nan, "raw_subject": "Interim Dividend - Rs 6/- Per Share"},
        {"symbol": "ENGINERSIN", "isin": "INE510A01010", "ex_date": pd.Timestamp("2017-09-11"),
         "record_date": None, "type": "dividend", "ratio_num": np.nan, "ratio_den": np.nan,
         "cash_amount": np.nan, "face_value_from": np.nan, "face_value_to": np.nan,
         "raw_subject": "Annual General Meeting/Dividend - 0.50 Per Share"},
        {"symbol": "COLPAL", "isin": "INE259A01022", "ex_date": pd.Timestamp("2017-12-18"),
         "record_date": "2017-12-19", "type": "other", "ratio_num": np.nan,
         "ratio_den": np.nan, "cash_amount": np.nan, "face_value_from": np.nan,
         "face_value_to": np.nan, "raw_subject": "Int Div - Rs 4/- Per Share"},
        {"symbol": "COLPAL", "isin": "INE259A01022", "ex_date": pd.Timestamp("2017-12-18"),
         "record_date": "2017-12-19", "type": "dividend", "ratio_num": np.nan,
         "ratio_den": np.nan, "cash_amount": 2.0, "face_value_from": np.nan,
         "face_value_to": np.nan, "raw_subject": "Special Dividend - Rs 2/- Per Share"},
    ]))
    assert len(reviewed_actions.loc[reviewed_actions["symbol"].eq("SRF")]) == 1
    assert reviewed_actions.loc[reviewed_actions["symbol"].eq("SRF"), "cash_amount"].iloc[0] == 6.0
    assert reviewed_actions.loc[reviewed_actions["symbol"].eq("ENGINERSIN"), "cash_amount"].iloc[0] == 0.5
    colpal = reviewed_actions.loc[reviewed_actions["symbol"].eq("COLPAL")]
    assert len(colpal) == 2 and colpal["cash_amount"].sum() == 6.0 and colpal["type"].eq("dividend").all()
    split_terms = pd.DataFrame([{"ratio_num": np.nan, "ratio_den": np.nan,
                                 "face_value_from": 2.0, "face_value_to": 1.0}])
    bonus_terms = pd.DataFrame([{"ratio_num": 1.0, "ratio_den": 1.0,
                                 "face_value_from": np.nan, "face_value_to": np.nan}])
    assert routine_share_factor_check("split", split_terms, 100.0, 49.0, 1.0, 2.0)[0]
    assert routine_share_factor_check("bonus", bonus_terms, 100.0, 51.0, 1.0, 2.0)[0]
    assert not routine_share_factor_check("split", split_terms, 100.0, 49.0, 1.0, 1.0)[0]
    broken = prices.copy()
    broken[30] = np.nan
    assert score_at(broken, 280, "B")[1] == "missing_or_invalid_adjusted_close"
    point_in_time = pd.DataFrame([
        {"isin": "ID1", "symbol": "OLDNAME", "valid_from": pd.Timestamp("2010-01-01"), "valid_to": pd.Timestamp("2020-08-19")},
        {"isin": "ID1", "symbol": "NEWNAME", "valid_from": pd.Timestamp("2020-08-20"), "valid_to": pd.NaT},
    ])
    assert symbol_at(point_in_time, "ID1", pd.Timestamp("2020-08-19")) == "OLDNAME"
    assert symbol_at(point_in_time, "ID1", pd.Timestamp("2020-08-20")) == "NEWNAME"
    assert symbol_at(point_in_time, "UNKNOWN", pd.Timestamp("2020-08-20")) == ""
    action_rows = pd.DataFrame([
        {"isin": "ID1", "symbol": "NEWNAME", "ex_date": pd.Timestamp("2020-08-20")},
        {"isin": "OLDID", "symbol": "NEWNAME", "ex_date": pd.Timestamp("2020-08-20")},
        {"isin": "STALE", "symbol": "NEWNAME", "ex_date": pd.Timestamp("2020-08-20")},
        {"isin": "STALE", "symbol": "OLDNAME", "ex_date": pd.Timestamp("2020-08-20")},
        {"isin": "UNKNOWN", "symbol": "UNKNOWN", "ex_date": pd.Timestamp("2020-08-20")},
    ])
    resolved, methods = resolve_action_symbols(action_rows, point_in_time, [{
        "action_feed_isin": "OLDID", "economic_ex_date": "2020-08-20", "symbol": "NEWNAME",
    }])
    assert resolved.tolist() == ["NEWNAME", "NEWNAME", "NEWNAME", "", ""]
    assert methods.tolist() == ["date_valid_vendor_isin", "exact_reviewed_action_bridge",
                                "exact_vendor_symbol_date_history", "unresolved", "unresolved"]
    renamed = pd.DataFrame([
        {"isin": "SAMEID", "symbol": "NIITTECH", "valid_from": pd.Timestamp("2010-01-01"), "valid_to": pd.Timestamp("2020-08-19")},
        {"isin": "SAMEID", "symbol": "COFORGE", "valid_from": pd.Timestamp("2020-08-20"), "valid_to": pd.NaT},
    ])
    stale_action = pd.DataFrame([{"isin": "SAMEID", "symbol": "NIITTECH", "ex_date": pd.Timestamp("2025-06-04")}])
    resolved, methods = resolve_action_symbols(stale_action, renamed, [])
    assert resolved.iloc[0] == "COFORGE" and methods.iloc[0] == "date_valid_vendor_isin"
    yesbank_history = pd.DataFrame([
        {"isin": "INE528G01027", "symbol": "YESBANK", "valid_from": pd.Timestamp("2017-09-22"), "valid_to": pd.Timestamp("2020-03-13")},
        {"isin": "INE528G01035", "symbol": "YESBANK", "valid_from": pd.Timestamp("2020-03-16"), "valid_to": pd.NaT},
    ])
    yesbank_events = pd.DataFrame([{"isin": "INE528G01035", "symbol": "YESBANK", "action": "exclude"}])
    yesbank_symbols = membership_symbol_map(yesbank_history, yesbank_events, [])
    assert "INE528G01027" in identity_closure({"INE528G01035"}, yesbank_symbols, yesbank_history)
    assert member_identity_at("INE528G01035", pd.Timestamp("2018-01-31"), yesbank_history,
                              yesbank_symbols) == ("YESBANK", "INE528G01027", "exact_membership_symbol_date_history")
    assert member_identity_at("INE528G01035", pd.Timestamp("2020-03-18"), yesbank_history,
                              yesbank_symbols) == ("YESBANK", "INE528G01035", "date_valid_interval_isin")
    hdfc_history = pd.DataFrame([
        {"isin": "INE040A01026", "symbol": "HDFCBANK", "valid_from": pd.Timestamp("2010-01-01"), "valid_to": pd.Timestamp("2019-09-19")},
        {"isin": "INE040A01034", "symbol": "HDFCBANK", "valid_from": pd.Timestamp("2019-09-20"), "valid_to": pd.NaT},
    ])
    hdfc_symbols = membership_symbol_map(hdfc_history, pd.DataFrame(), [])
    assert "INE040A01026" in identity_closure({"INE040A01034"}, hdfc_symbols, hdfc_history)
    assert member_identity_at("INE040A01034", pd.Timestamp("2018-01-31"), hdfc_history,
                              hdfc_symbols) == ("HDFCBANK", "INE040A01026", "exact_membership_symbol_date_history")
    old_quantity, old_close, split_ratio = 7, 100.0, 2.0
    new_quantity, new_unit_close = int(old_quantity * split_ratio), old_close / split_ratio
    assert new_quantity != old_quantity and np.isclose(old_quantity * old_close, new_quantity * new_unit_close)
    unrelated = union_find({"PARENT", "CHILD"}, [])
    assert unrelated["PARENT"] != unrelated["CHILD"]
    assert "other" in RELEVANT_ACTIONS
    action_day = pd.Timestamp("2017-02-17")
    assert action_validation_detail("", action_day, "rights", "ID1", {}) == "unresolved_date_valid_action_identity"
    assert action_validation_detail("CANBK", action_day, "rights", "ID1", {}) == "rights_signal_entitlement_or_adjusted_value_model_unresolved"
    assert action_validation_detail("PARENT", action_day, "merger", "ID2", {}) == "merger_signal_entitlement_or_adjusted_value_model_unresolved"
    assert action_validation_detail("CANBK", action_day, "dividend", "ID1",
                                    {("CANBK", action_day, "dividend", "ID1"): "adjusted_factor_mismatch"}) == "adjusted_factor_mismatch"
    sample = [
        {"input": "signal_dividend", "entity": "ABC|ID1", "date": "2020-01-01", "reason": "vendor action ISIN=ID1"},
        {"input": "signal_dividend", "entity": "ABC|ID1", "date": "2020-01-01", "reason": "vendor action ISIN=ID1"},
        {"input": "held_position_close", "entity": "ID1", "date": "2020-01-02", "reason": "missing"},
    ]
    incidence, unique = dependency_counts(sample)
    assert incidence["signal_dividend"] == 2 and unique["signal_dividend"] == 1
    assert unique["held_position_close"] == 1
    assert resolution_attempt_for({"input": "held_position_close"}).startswith("Checked the exact ISIN/session")
    print("candidate dependency self-check passed: windows, warmup, action normalization, dividend aggregation, split/bonus factors, and identity resolution")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--self-check", action="store_true")
    args = parser.parse_args()
    self_check() if args.self_check else audit()
