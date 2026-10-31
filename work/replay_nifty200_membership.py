"""Replay the reviewed NIFTY 200 event ledger around an independently dated anchor."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import tempfile
from collections import Counter, defaultdict
from pathlib import Path

import pandas as pd
import pyarrow.parquet as pq


ROOT = Path(__file__).resolve().parents[1]
PUBLIC = ROOT / "work" / "data" / "public_research"
MEMBERSHIP = PUBLIC / "membership"
ANCHOR = PUBLIC / "official" / "ind_nifty200list.csv"
NIFTY100_ANCHOR = PUBLIC / "official" / "ind_nifty100list.csv"
MIDCAP100_ANCHOR = PUBLIC / "official" / "ind_niftymidcap100list.csv"
INDEX_XLS = PUBLIC / "official" / "IndexInclExcl.xls"
HISTORY = PUBLIC / "tejhq" / "symbol_history" / "nse.parquet"
ACTION_DIR = PUBLIC / "tejhq" / "actions"
RAW_DIR = PUBLIC / "tejhq" / "nse"
START = pd.Timestamp("2018-01-01")
ANCHOR_DATE = pd.Timestamp("2026-09-30")
EVALUATION_END = pd.Timestamp("2026-10-23")
DEFERRED_2020 = {"ind_prs18022020.pdf", "ind_prs12032020.pdf", "ind_prs19032020.pdf"}


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def write_rows(path: Path, rows: list[dict], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8-sig", newline="", delete=False, dir=path.parent) as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows({key: row.get(key, "") for key in fields} for row in rows)
        temporary = Path(handle.name)
    temporary.replace(path)


def identity_isin(history: pd.DataFrame, symbol: str, when: pd.Timestamp, side: str, bridge: bool = False) -> str:
    rows = history[history.symbol.str.upper().eq(symbol.upper())]
    active = rows[(rows.valid_from <= when) & (rows.valid_to.isna() | (rows.valid_to >= when))]
    if active.empty and side == "exclude":
        active = rows[(rows.valid_to < when) & (rows.valid_to >= when - pd.Timedelta(days=3))]
        if not active.empty:
            active = active[active.valid_to.eq(active.valid_to.max())]
    if active.empty and bridge:
        # A temporary dummy index symbol can precede the successor's first tradable session.
        active = rows
    values = active["isin"].dropna().astype(str).str.upper().unique()
    if len(values) != 1:
        raise ValueError(f"identity unresolved: {symbol} on {when.date()} ({side}), candidate ISINs={list(values)}")
    return values[0]


def release_status(row: dict) -> str:
    filename, symbol = row["filename"], row["symbol"].upper()
    if filename in DEFERRED_2020 and row["effective_date"] == "2020-03-27":
        return "deferred"
    if filename == "ind_prs28022024.pdf" and symbol == "IREDA" and row["side"] == "include":
        return "revoked"
    if filename == "ind_prs23082024.pdf" and row["effective_date"] == "2024-09-30":
        if (symbol == "IDEA" and row["side"] == "exclude") or (symbol == "CENTRALBK" and row["side"] == "include"):
            return "revoked"
    return "operative"


def previous_sessions() -> list[pd.Timestamp]:
    sessions = set()
    for path in sorted(RAW_DIR.glob("year=*/nse_*.parquet")):
        sessions.update(pd.to_datetime(pq.read_table(path, columns=["date"])["date"].to_pandas()).dropna().unique())
    return sorted(pd.Timestamp(value).normalize() for value in sessions)


def split_identity_bridges(history: pd.DataFrame, referenced_isins: set[str]) -> list[dict]:
    bridges = []
    for path in sorted(ACTION_DIR.glob("nse_*.parquet")):
        actions = pq.read_table(path).to_pandas()
        actions = actions[(actions["type"] == "split") & actions["ex_date"].notna()]
        source_hash = hashlib.sha256(path.read_bytes()).hexdigest()
        for row in actions.itertuples(index=False):
            effective = pd.Timestamp(row.ex_date)
            if not START <= effective <= EVALUATION_END:
                continue
            prior = history[(history["symbol"] == str(row.symbol).upper()) & (history["isin"] == str(row.isin).upper())
                            & (history["valid_to"] < effective) & (history["valid_to"] >= effective - pd.Timedelta(days=7))]
            if not prior.empty:
                prior = prior[prior["valid_to"].eq(prior["valid_to"].max())]
            successor = history[(history["symbol"] == str(row.symbol).upper()) & (history["valid_from"] == effective)]
            if len(prior) != 1 or len(successor) != 1:
                continue
            old_isin, new_isin = prior.iloc[0]["isin"], successor.iloc[0]["isin"]
            if old_isin == new_isin or not ({old_isin, new_isin} & referenced_isins):
                continue
            bridges.append({"effective_date": effective.date().isoformat(), "reference_close_date": "", "announcement_date": "",
                            "action": "isin_bridge", "symbol": row.symbol, "from_isin": old_isin, "to_isin": new_isin,
                            "isin": "", "identity_bridge": f"TejHQ face value split {row.face_value_from:g}->{row.face_value_to:g}",
                            "filename": path.name, "page_ref": row.raw_subject, "official_url": "",
                            "pdf_sha256": source_hash, "status": "operative"})
    return bridges


def day_events(rows: list[dict], state: set[str], reverse: bool) -> set[str]:
    state = set(state)
    includes = {row["isin"] for row in rows if row["action"] == "include"}
    excludes = {row["isin"] for row in rows if row["action"] == "exclude"}
    if includes & excludes:
        raise ValueError(f"same-date include/exclude collision: {sorted(includes & excludes)}")
    first, second = (includes, excludes) if reverse else (excludes, includes)
    for isin in first:
        if isin not in state:
            raise ValueError(f"remove precondition failed on {rows[0]['effective_date']}: {isin} absent")
    state.difference_update(first)
    for isin in second:
        if isin in state:
            raise ValueError(f"add precondition failed on {rows[0]['effective_date']}: {isin} already present")
    state.update(second)
    return state


def day_bridges(rows: list[dict], state: set[str], reverse: bool) -> set[str]:
    state = set(state)
    for row in rows:
        source, target = (row["to_isin"], row["from_isin"]) if reverse else (row["from_isin"], row["to_isin"])
        if source in state and target in state:
            raise ValueError(f"identity bridge collision on {row['effective_date']}: {source} and {target} both present")
        if source in state:
            state.remove(source)
            state.add(target)
    return state


def compare_xls(release_rows: list[dict], exceptions: list[dict], xls_rows: list[dict]) -> dict:
    def norm(value: str) -> str:
        return "".join(ch for ch in value.upper() if ch.isalnum())

    pdf = {
        (row["effective_date"], norm(row["company"]), row["side"])
        for row in release_rows
        if START.date().isoformat() <= row["effective_date"] <= "2020-07-31" and release_status(row) == "operative"
    }
    pdf.update(
        (row["event_effective_date"], norm(row["entity"]), row["action"])
        for row in exceptions
        if row["status"] == "operative" and row["action"] in {"include", "exclude"}
        and START.date().isoformat() <= row["event_effective_date"] <= "2020-07-31"
    )
    xls = {
        (row["event_date"], norm(row["company"]), row["side"])
        for row in xls_rows
        if START.date().isoformat() <= row["event_date"] <= "2020-07-31"
    }
    # The parser already joins the wrapped IRCTC row; this normalization guards the official Corp./Corporation label variant.
    def canonical(key: tuple[str, str, str]) -> tuple[str, str, str]:
        d, name, side = key
        if d == "2020-06-26" and name in {"INDIANRAILWAYCATERINGANDTOURISMCORPCORPLTD", "INDIANRAILWAYCATERINGANDTOURISMCORPORATIONLTD"}:
            name = "INDIANRAILWAYCATERINGANDTOURISMCORPORATIONLTD"
        return d, name, side
    pdf = {canonical(key) for key in pdf}
    xls = {canonical(key) for key in xls}
    return {
        "official_xls_pdf_match_count": len(pdf & xls),
        "official_xls_only_count": len(xls - pdf),
        "operative_pdf_only_count": len(pdf - xls),
        "matches": len(pdf & xls),
        "xls_only": sorted(xls - pdf),
        "pdf_only": sorted(pdf - xls),
    }


def count_notice_classifications(exceptions: list[dict], notice_files: set[str]) -> Counter:
    classifications: dict[str, set[str]] = defaultdict(set)
    for row in exceptions:
        if row["filename"] in notice_files:
            classifications[row["filename"]].add(row["classification"])
    if set(classifications) != notice_files or any(len(values) != 1 for values in classifications.values()):
        raise ValueError("each notice without a numbered parent table must have exactly one reviewed classification")
    return Counter(next(iter(values)) for values in classifications.values())


def is_replayable_exception(row: dict) -> bool:
    return row["status"] == "operative" and row["action"] in {"include", "exclude", "isin_bridge"}


def build() -> dict:
    release = read_rows(MEMBERSHIP / "release_events.csv")
    exceptions = read_rows(MEMBERSHIP / "reviewed_exceptions.csv")
    xls = read_rows(MEMBERSHIP / "xls_events.csv")
    anchor_rows = read_rows(ANCHOR)
    if len(anchor_rows) != 200 or len({r["ISIN Code"].strip().upper() for r in anchor_rows}) != 200:
        raise ValueError("anchor must contain 200 unique ISINs")
    anchor = {r["ISIN Code"].strip().upper() for r in anchor_rows}
    component_rows = {path: read_rows(path) for path in (NIFTY100_ANCHOR, MIDCAP100_ANCHOR)}
    component_sets = []
    for path, rows in component_rows.items():
        if len(rows) != 100 or len({r["ISIN Code"].strip().upper() for r in rows}) != 100:
            raise ValueError(f"component anchor must contain 100 unique ISINs: {path.name}")
        component_sets.append({r["ISIN Code"].strip().upper() for r in rows})
    component_union = component_sets[0] | component_sets[1]
    if component_sets[0] & component_sets[1] or component_union != anchor:
        raise ValueError("dated NIFTY 100 and Midcap 100 anchors do not form the NIFTY 200 anchor")
    history = pq.read_table(HISTORY).to_pandas()
    history["symbol"] = history["symbol"].astype(str).str.upper()
    history["isin"] = history["isin"].astype(str).str.upper()
    history["valid_from"] = pd.to_datetime(history["valid_from"])
    history["valid_to"] = pd.to_datetime(history["valid_to"])

    unresolved: list[dict] = []
    selected: list[dict] = []
    bridges: list[dict] = []
    for row in release:
        dt = pd.Timestamp(row["effective_date"])
        if not START <= dt <= EVALUATION_END or release_status(row) != "operative":
            continue
        try:
            isin = row["isin"].strip().upper() or identity_isin(history, row["symbol"], dt, row["side"])
            if row["mapping_error"] and not isin:
                raise ValueError(row["mapping_error"])
        except Exception as error:
            unresolved.append({"filename": row["filename"], "page_ref": row["page_ref"], "date": row["effective_date"], "symbol": row["symbol"], "reason": str(error)})
            continue
        selected.append({"effective_date": row["effective_date"], "isin": isin, "action": row["side"], "symbol": row["symbol"],
                         "filename": row["filename"], "page_ref": row["page_ref"], "pdf_sha256": row["pdf_sha256"],
                         "official_url": row["official_url"], "announcement_date": row["announcement_date"], "status": "operative",
                         "identity_bridge": "event_symbol"})
    for row in exceptions:
        dt = pd.Timestamp(row["event_effective_date"] or "1900-01-01")
        if not is_replayable_exception(row) or not START <= dt <= EVALUATION_END:
            continue
        if row["action"] == "isin_bridge":
            if not row["from_isin"] or not row["to_isin"]:
                unresolved.append({"filename": row["filename"], "page_ref": row["page_ref"], "date": row["event_effective_date"], "symbol": row["event_symbol"], "reason": "identity bridge needs both ISINs"})
                continue
            bridges.append({"effective_date": row["event_effective_date"], "reference_close_date": row["reference_close_date"],
                            "announcement_date": row["announcement_date"], "action": "isin_bridge", "symbol": row["event_symbol"],
                            "from_isin": row["from_isin"].upper(), "to_isin": row["to_isin"].upper(), "isin": "",
                            "identity_bridge": row["identity_symbol"], "filename": row["filename"], "page_ref": row["page_ref"],
                            "official_url": row["official_url"], "pdf_sha256": row["pdf_sha256"], "status": "operative"})
            continue
        if row["action"] not in {"include", "exclude"}:
            continue
        try:
            isin = row["isin"].strip().upper() or identity_isin(history, row["identity_symbol"], dt, row["action"], bridge=True)
        except Exception as error:
            unresolved.append({"filename": row["filename"], "page_ref": row["page_ref"], "date": row["event_effective_date"], "symbol": row["event_symbol"], "reason": str(error)})
            continue
        selected.append({"effective_date": row["event_effective_date"], "isin": isin, "action": row["action"], "symbol": row["event_symbol"],
                         "filename": row["filename"], "page_ref": row["page_ref"], "pdf_sha256": row["pdf_sha256"],
                         "official_url": row["official_url"], "announcement_date": row["announcement_date"], "status": "operative",
                         "identity_bridge": row["identity_symbol"]})
    if unresolved:
        raise ValueError("operative event identities unresolved: " + json.dumps(unresolved[:20]))

    referenced_isins = anchor | {row["isin"] for row in release if row["isin"]}
    referenced_isins |= {row["isin"].upper() for row in selected}
    referenced_isins |= {r["from_isin"].upper() for r in bridges} | {r["to_isin"].upper() for r in bridges}
    bridges.extend(split_identity_bridges(history, referenced_isins))

    grouped: dict[tuple[str, str, str], dict] = {}
    for row in selected:
        key = (row["effective_date"], row["isin"], row["action"])
        if key not in grouped:
            grouped[key] = dict(row)
        elif row["filename"] not in grouped[key]["filename"].split(";"):
            for field in ("filename", "page_ref", "official_url", "pdf_sha256", "announcement_date", "symbol", "identity_bridge"):
                if row[field] not in grouped[key][field].split(";"):
                    grouped[key][field] += ";" + row[field]
    operative = sorted(grouped.values(), key=lambda r: (r["effective_date"], r["isin"], r["action"]))

    unique_bridges = {}
    for row in bridges:
        key = (row["effective_date"], row["from_isin"], row["to_isin"])
        if key not in unique_bridges or row["official_url"]:
            unique_bridges[key] = row
    bridges = sorted(unique_bridges.values(), key=lambda r: (r["effective_date"], r["from_isin"], r["to_isin"]))
    bridge_by_date: dict[str, list[dict]] = defaultdict(list)
    for row in bridges:
        bridge_by_date[row["effective_date"]].append(row)
    before_anchor = [row for row in operative if row["effective_date"] <= ANCHOR_DATE.date().isoformat()]
    by_date: dict[str, list[dict]] = defaultdict(list)
    for row in before_anchor:
        by_date[row["effective_date"]].append(row)
    replay_residuals = []
    initial = set(anchor)
    for dt in sorted(set(by_date) | set(bridge_by_date), reverse=True):
        if dt > ANCHOR_DATE.date().isoformat():
            continue
        try:
            candidate = day_events(by_date.get(dt, []), initial, reverse=True)
            candidate = day_bridges(bridge_by_date.get(dt, []), candidate, reverse=True)
            initial = candidate
        except ValueError as error:
            replay_residuals.append({"direction": "reverse", "date": dt, "sources": sorted({r["filename"] for r in by_date.get(dt, []) + bridge_by_date.get(dt, [])}), "reason": str(error)})

    state = set(initial)
    opened = {isin: START.date().isoformat() for isin in state}
    intervals: list[dict] = []
    counts = [len(state)]
    anchor_verified = False
    anchor_reproduced = False
    all_by_date: dict[str, list[dict]] = defaultdict(list)
    for row in operative:
        all_by_date[row["effective_date"]].append(row)
    for dt in sorted(set(all_by_date) | set(bridge_by_date)):
        if dt > EVALUATION_END.date().isoformat():
            continue
        if dt > ANCHOR_DATE.date().isoformat() and not anchor_verified:
            anchor_reproduced = state == anchor
            if not anchor_reproduced:
                replay_residuals.append({"direction": "anchor_check", "date": ANCHOR_DATE.date().isoformat(),
                                         "reason": "forward state does not equal official anchor", "missing_count": len(anchor-state),
                                         "extra_count": len(state-anchor), "missing_sample": sorted(anchor-state)[:10], "extra_sample": sorted(state-anchor)[:10]})
            anchor_verified = True
        daily = all_by_date.get(dt, [])
        before = set(state)
        try:
            candidate = day_events(daily, state, reverse=False)
            candidate = day_bridges(bridge_by_date.get(dt, []), candidate, reverse=False)
            state = candidate
        except ValueError as error:
            replay_residuals.append({"direction": "forward", "date": dt, "sources": sorted({r["filename"] for r in daily + bridge_by_date.get(dt, [])}), "reason": str(error)})
            continue
        for isin in before - state:
            start = opened.pop(isin)
            end = (pd.Timestamp(dt) - pd.Timedelta(days=1)).date().isoformat()
            if end >= start:
                intervals.append({"isin": isin, "valid_from": start, "valid_to": end})
        for isin in state - before:
            opened[isin] = dt
        counts.append(len(state))
    if not anchor_verified:
        anchor_reproduced = state == anchor
        if not anchor_reproduced:
            replay_residuals.append({"direction": "anchor_check", "date": ANCHOR_DATE.date().isoformat(),
                                     "reason": "forward state does not equal official anchor", "missing_count": len(anchor-state),
                                     "extra_count": len(state-anchor), "missing_sample": sorted(anchor-state)[:10], "extra_sample": sorted(state-anchor)[:10]})
        anchor_verified = True
    end_date = EVALUATION_END.date().isoformat()
    intervals.extend({"isin": isin, "valid_from": start, "valid_to": end_date} for isin, start in opened.items())
    replay_ok = anchor_verified and anchor_reproduced and not replay_residuals

    sessions = previous_sessions()
    for row in [*operative, *bridges]:
        dt = pd.Timestamp(row["effective_date"])
        eligible = [s for s in sessions if s < dt]
        row["reference_close_date"] = row.get("reference_close_date") or (eligible[-1].date().isoformat() if eligible else "")
    if len(sessions) == 0:
        raise ValueError("raw exchange sessions unavailable for reference-close mapping")

    comparison = compare_xls(release, exceptions, xls)
    no_table = {row["filename"] for row in read_rows(MEMBERSHIP / "notice_sources.csv") if row["has_numbered_section"].lower() == "false"}
    exception_files = {row["filename"] for row in exceptions}
    uncovered_no_table = sorted(no_table - exception_files)
    if uncovered_no_table:
        raise ValueError(f"untriaged notices without parent tables: {uncovered_no_table}")
    comparison_ok = not comparison["xls_only"] and not comparison["pdf_only"]

    fields = ["effective_date", "reference_close_date", "announcement_date", "action", "symbol", "isin", "identity_bridge", "status", "filename", "page_ref", "official_url", "pdf_sha256"]
    event_fields = fields + ["from_isin", "to_isin"]
    write_rows(MEMBERSHIP / "operative_events.csv", [*operative, *bridges], event_fields)
    write_rows(MEMBERSHIP / "identity_bridges.csv", bridges, event_fields)
    for row in intervals:
        row["replay_status"] = "CERTIFIED" if replay_ok else "PARTIAL_UNCERTIFIED"
    write_rows(MEMBERSHIP / "membership_intervals.csv", sorted(intervals, key=lambda r: (r["valid_from"], r["isin"])), ["isin", "valid_from", "valid_to", "replay_status"])
    deferred = [
        {"filename": r["filename"], "effective_date": r["effective_date"], "page_ref": r["page_ref"], "symbol": r["symbol"], "status": release_status(r)}
        for r in release if release_status(r) != "operative"
    ]
    deferred.extend({"filename": r["filename"], "effective_date": r["event_effective_date"], "page_ref": r["page_ref"],
                     "symbol": r["event_symbol"], "status": r["status"], "linked_notice": r["linked_notice"]}
                    for r in exceptions if r["status"] not in {"operative", "no_parent_change"})
    no_table_classes = count_notice_classifications(exceptions, no_table)
    source_hashes = {row["filename"]: row["pdf_sha256"] for row in [*release, *exceptions]}
    failure_sources = {}
    for item in replay_residuals:
        if item["direction"] not in {"reverse", "forward"}:
            continue
        for filename in item.get("sources", []):
            key = (item["date"], filename)
            failure_sources.setdefault(key, set()).add(item["direction"])
    residual_source_manifest = [
        {"date": dt, "source_filename": filename, "source_sha256": source_hashes.get(filename, ""),
         "failed_directions": sorted(directions), "failed_direction_count": len(directions)}
        for (dt, filename), directions in sorted(failure_sources.items())
    ]
    failed_directions = Counter(item["direction"] for item in replay_residuals)
    residuals = {
        "gate": "MEMBERSHIP_REPLAY_PASSED" if replay_ok and comparison_ok else "MEMBERSHIP_REPLAY_FAILED_WITH_RESIDUALS",
        "anchor_date": ANCHOR_DATE.date().isoformat(), "evaluation_membership_end": end_date,
        "anchor_members": len(anchor), "forward_state_matches_anchor": anchor_reproduced,
        "round_trip_certified": replay_ok,
        "anchor_sha256": hashlib.sha256(ANCHOR.read_bytes()).hexdigest(),
        "official_xls_sha256": hashlib.sha256(INDEX_XLS.read_bytes()).hexdigest(),
        "component_anchors_union_to_parent": True, "component_anchor_sizes": [len(values) for values in component_sets],
        "component_anchor_hashes": {path.name: hashlib.sha256(path.read_bytes()).hexdigest() for path in component_rows},
        "operative_events": len(operative), "identity_bridges": len(bridges), "interval_rows": len(intervals),
        "minimum_members_at_event_boundary": min(counts), "maximum_members_at_event_boundary": max(counts),
        "temporary_extra_members_are_allowed": True,
        "official_xls_pdf_crosscheck_2018_2020": {key: value for key, value in comparison.items() if key not in {"xls_only", "pdf_only"}},
        "xls_crosscheck_passed": comparison_ok,
        "replay_failed_notice_date_pairs": len(failure_sources),
        "replay_failed_direction_count": sum(failed_directions.values()),
        "replay_failed_direction_counts": dict(failed_directions),
        "replay_failure_reason": "State preconditions fail in both directions for the listed notice/date batches; forward equality after skipped batches does not certify membership.",
        "replay_failure_source_manifest": residual_source_manifest,
        "notices_without_parent_tables": len(no_table), "notice_triage_class_counts": dict(no_table_classes),
        "untriaged_notices_without_parent_tables": uncovered_no_table,
        "deferred_or_revoked_parent_event_count": len(deferred),
        "finite_residuals": [
            {"source": "NSE Indices event archive and TejHQ symbol history", "case": "Eleven in-scope notice batches fail ISIN membership-state preconditions in both replay directions; source/date/hash coverage is listed above, and full row-level diagnosis remains local."},
            {"source": "official NIFTY 200 methodology and 213-document press-release archive", "case": "NIFTY 200 is the union of NIFTY 100 and NIFTY Midcap 100; the strict parser covers direct NIFTY 200 tables and reviewed exceptions, but the event-set replay has unresolved component-transition gaps."},
            {"source": "NSE/TejHQ symbol history", "case": "One unmapped event identity predates the 2018 evaluation start and does not enter this replay."},
            {"source": "TejHQ symbol history and official corporate-adjustment notices", "case": "Several temporary demerger/successor components enter the index before their successor's first tradable session; identity bridge is recorded, but tradability and economic entitlement accounting must be gated separately."},
            {"source": "TejHQ adjustment convention", "case": "Split/bonus/dividend-adjusted closes do not resolve rights, mergers or demergers; no NIFTY 200 strategy NAV is authorized by this membership pass."},
            {"source": "TejHQ public terms and NSE website terms", "case": "Source terms differ on storage/simulation; this remains a documented source-use conflict, not a data-integrity pass."},
        ],
        "performance_gate": "NOT PASSED; no strategy outcomes calculated",
    }
    local_summary = {**residuals, "replay_residuals": replay_residuals, "deferred_or_revoked_parent_events": deferred}
    (MEMBERSHIP / "replay_residuals.json").write_text(json.dumps(local_summary, indent=2) + "\n", encoding="utf-8")
    public_summary = {key: value for key, value in residuals.items() if key not in {"finite_residuals", "deferred_or_revoked_parent_events", "replay_residuals"}}
    public_summary["performance_gate"] = "NOT PASSED; no strategy outcomes calculated"
    (ROOT / "outputs" / "nifty200_membership_replay_summary_2026-10-31.json").write_text(json.dumps(public_summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(public_summary, indent=2))
    return residuals


def self_check() -> None:
    triage = [
        {"filename": "parent.pdf", "classification": "parent_prose_index_list"},
        {"filename": "parent.pdf", "classification": "parent_prose_index_list"},
        {"filename": "descendant.pdf", "classification": "descendant_only_no_parent_change"},
    ]
    assert count_notice_classifications(triage, {"parent.pdf", "descendant.pdf"}) == Counter(
        {"parent_prose_index_list": 1, "descendant_only_no_parent_change": 1}
    )
    prose_event = {"filename": "ind_prs17072023.pdf", "classification": "parent_prose_index_list",
                   "event_effective_date": "2023-07-20", "action": "include", "event_symbol": "JIOFIN", "status": "operative"}
    assert is_replayable_exception(prose_event)
    deferment = {"filename": "ind_prs23032020.pdf", "classification": "amendment_deferment",
                 "action": "defer_rebalance", "status": "deferred",
                 "linked_notice": "ind_prs18022020.pdf;ind_prs12032020.pdf;ind_prs19032020.pdf"}
    followup = {"filename": "ind_prs25032020.pdf", "classification": "amendment_deferment",
                "action": "defer_rebalance", "status": "deferred", "linked_notice": "ind_prs23032020.pdf"}
    assert not is_replayable_exception(deferment) and not is_replayable_exception(followup)
    assert {"ind_prs18022020.pdf", "ind_prs12032020.pdf", "ind_prs19032020.pdf"} <= set(deferment["linked_notice"].split(";"))
    assert followup["linked_notice"] == "ind_prs23032020.pdf"
    releases = [
        {"filename": "ind_prs19032020.pdf", "symbol": "PVR", "side": "include", "effective_date": "2020-03-27"},
        {"filename": "ind_prs18022020.pdf", "symbol": "IRCTC", "side": "include", "effective_date": "2020-03-27"},
        {"filename": "ind_prs28022024.pdf", "symbol": "IREDA", "side": "include", "effective_date": "2024-03-28"},
        {"filename": "ind_prs23082024.pdf", "symbol": "IDEA", "side": "exclude", "effective_date": "2024-09-30"},
    ]
    assert [release_status(r) for r in releases] == ["deferred", "deferred", "revoked", "revoked"]
    assert release_status({"filename": "ind_prs12032020.pdf", "symbol": "EXAMPLE", "side": "include", "effective_date": "2020-03-27"}) == "deferred"
    state = {"A", "B"}
    group = [{"effective_date": "2020-01-02", "isin": "A", "action": "exclude"}, {"effective_date": "2020-01-02", "isin": "C", "action": "include"}]
    state = day_events(group, state, reverse=False)
    assert state == {"B", "C"}
    state = day_events(group, state, reverse=True)
    assert state == {"A", "B"}
    history = pd.DataFrame([{"symbol": "JIOFIN", "isin": "INE758E01017", "valid_from": pd.Timestamp("2023-08-21"),
                             "valid_to": pd.NaT}])
    successor_isin = identity_isin(history, "JIOFIN", pd.Timestamp("2023-07-20"), "include", bridge=True)
    state = day_events([{"effective_date": "2023-07-20", "isin": successor_isin, "action": "include"}], set(), reverse=False)
    assert successor_isin in state and len(state) == 1
    state = day_events([{"effective_date": "2023-08-29", "isin": successor_isin, "action": "exclude"}], state, reverse=False)
    assert successor_isin not in state
    try:
        day_events([{"effective_date": "2020-01-02", "isin": "Z", "action": "exclude"}], set(), reverse=False)
    except ValueError:
        pass
    else:
        raise AssertionError("remove-present precondition was not enforced")
    split = [{"effective_date": "2024-05-24", "from_isin": "OLD", "to_isin": "NEW"}]
    state = {"OLD"}
    state = day_bridges(split, state, reverse=False)
    assert state == {"NEW"}
    state = day_bridges(split, state, reverse=True)
    assert state == {"OLD"}
    print("membership replay self-check passed: notice triage, defer/amendment chain, atomic replacement, strict preconditions, no fixed-count assumption")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--self-check", action="store_true")
    args = parser.parse_args()
    self_check() if args.self_check else build()
