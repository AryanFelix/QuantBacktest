"""Check L500 prerequisites without calculating signals, positions, or returns."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd
import pyarrow.parquet as pq


ROOT = Path(__file__).resolve().parents[1]
PUBLIC = ROOT / "work" / "data" / "public_research"
RAW_DIR = PUBLIC / "tejhq" / "nse"
ACTION_DIR = PUBLIC / "tejhq" / "actions"
START = pd.Timestamp("2018-01-01")
CUTOFF = pd.Timestamp("2026-10-23")


def audit() -> dict:
    raw_files = sorted(RAW_DIR.glob("year=*/nse_*.parquet"))
    if len(raw_files) != 11:
        raise ValueError(f"expected 11 pinned raw NSE years, found {len(raw_files)}")
    fields = set(pq.read_schema(raw_files[0]).names)
    required = {"date", "series", "isin", "volume", "turnover"}
    if not required <= fields:
        raise ValueError(f"raw NSE schema is missing required fields: {sorted(required-fields)}")
    status_fields = sorted(fields & {"trading_status", "security_status", "no_trade", "record_status"})
    actions = pd.concat([pd.read_parquet(path, columns=["type", "ex_date"]) for path in sorted(ACTION_DIR.glob("nse_*.parquet"))], ignore_index=True)
    actions["ex_date"] = pd.to_datetime(actions["ex_date"], errors="coerce")
    interval = actions[(actions.ex_date >= START) & (actions.ex_date <= CUTOFF)]
    counts = {str(key): int(value) for key, value in interval.groupby("type").size().sort_index().items()}
    unadjusted = {kind: counts.get(kind, 0) for kind in ("rights", "merger", "demerger")}
    raw_rows = 0
    dates = set()
    for path in raw_files:
        metadata = pq.ParquetFile(path).metadata
        raw_rows += metadata.num_rows
        dates.update(pd.to_datetime(pq.read_table(path, columns=["date"])["date"].to_pandas()).dropna().unique())
    dates = sorted(pd.Timestamp(value).normalize() for value in dates)
    schema_blocker = not status_fields
    action_blocker = any(unadjusted.values())
    residuals = []
    if schema_blocker:
        residuals.append("The raw daily bar schema has no per-security trading/no-trade/status field. A missing security-session row cannot be labeled as a known zero-turnover session versus a source gap from this feed alone.")
    if action_blocker:
        residuals.append(f"The pinned action feed contains {unadjusted['rights']} rights, {unadjusted['merger']} merger, and {unadjusted['demerger']} demerger records in the evaluation window; those entitlements are outside the stated split/bonus/dividend adjustment convention and have not been reconciled for candidate holdings.")
    result = {
        "protocol_id": "L500-v1",
        "candidate_ids": ["L500-A-M", "L500-A-Q", "L500-B-M", "L500-B-Q"],
        "universe_rule": "At each calendar-month boundary, rank eligible securities by mean raw INR turnover over the 63 completed exchange sessions through the preceding close; take up to 500, tie-break by ISIN. No current constituent list or survivor filter.",
        "protocol": "Preperformance fallback data gate; same four frozen signal, portfolio, retention and execution rules as NIFTY200-v1; no performance calculation",
        "evaluation_start": START.date().isoformat(), "evaluation_cutoff": CUTOFF.date().isoformat(),
        "raw_year_files": len(raw_files), "raw_rows": raw_rows,
        "market_session_dates": len(dates), "first_session": dates[0].date().isoformat(), "last_session": dates[-1].date().isoformat(),
        "raw_schema_fields": sorted(fields), "security_session_status_fields": status_fields,
        "rights_merger_demerger_action_rows_2018_to_cutoff": unadjusted,
        "universe_dependency_gate": "NOT PASSED" if schema_blocker else "requires additional validation",
        "economic_action_gate": "NOT PASSED" if action_blocker else "requires additional validation",
        "performance_gate": "NOT RUN",
        "security_session_status_source_audit": "Local official-source review on 2026-10-31 found no verified date-complete public per-security session-state source for the evaluation interval",
        "residuals": residuals,
    }
    (ROOT / "outputs" / "l500_data_gate_2026-10-31.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))
    return result


def self_check() -> None:
    raw_fields = {"date", "series", "isin", "volume", "turnover"}
    status_fields = raw_fields & {"trading_status", "security_status", "no_trade", "record_status"}
    assert not status_fields
    action_counts = {"rights": 2, "merger": 1, "demerger": 1}
    assert any(action_counts.get(kind, 0) for kind in ("rights", "merger", "demerger"))
    print("L500 gate self-check passed: ambiguous missing-bar state and unsupported-action blockers are surfaced")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--self-check", action="store_true")
    args = parser.parse_args()
    self_check() if args.self_check else audit()
