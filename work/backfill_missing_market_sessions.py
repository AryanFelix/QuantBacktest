"""Fetch the finite NSE session dates absent from the local raw market panel."""

from __future__ import annotations

import hashlib
import io
import json
import argparse
import sys
import time
import zipfile
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow.dataset as ds
import requests


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "work" / "data" / "public_research" / "nse_calendar_backfill"
RAW = DATA / "raw"
OUT = ROOT / "outputs"
TEJHQ_RAW = ROOT / "work" / "data" / "public_research" / "tejhq" / "nse"
ADJUSTED = ROOT / "work" / "data" / "public_research" / "tejhq" / "prices_adjusted"
ACTIONS = ROOT / "work" / "data" / "public_research" / "tejhq" / "actions"
IDENTITY_BRIDGES = ROOT / "work" / "data" / "public_research" / "isin_bridges" / "reviewed_identity_bridges.csv"
sys.path.insert(0, str(ROOT / "work"))
import capture_sector_tri_signal_history as tri_capture

DATES = (
    "2016-10-30", "2017-10-19", "2018-11-07", "2019-10-27", "2020-02-01", "2020-11-14",
    "2021-11-04", "2022-10-24", "2023-11-12", "2024-03-02", "2024-05-18", "2024-11-01",
    "2025-10-21", "2026-02-01", "2026-06-05", "2026-06-15", "2026-06-16", "2026-06-22",
)


def source_url(day: str) -> str:
    date = datetime.strptime(day, "%Y-%m-%d")
    if date >= datetime(2024, 1, 1):
        return f"https://nsearchives.nseindia.com/content/cm/BhavCopy_NSE_CM_0_0_0_{date:%Y%m%d}_F_0000.csv.zip"
    month = date.strftime("%b").upper()
    return f"https://archives.nseindia.com/content/historical/EQUITIES/{date:%Y}/{month}/cm{date:%d}{month}{date:%Y}bhav.csv.zip"


def source_name(day: str) -> str:
    date = datetime.strptime(day, "%Y-%m-%d")
    if date >= datetime(2024, 1, 1):
        return f"BhavCopy_NSE_CM_0_0_0_{date:%Y%m%d}_F_0000.csv.zip"
    month = date.strftime("%b").upper()
    return f"cm{date:%d}{month}{date:%Y}bhav.csv.zip"


def sha256(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def parse_archive(content: bytes, day: str, name: str) -> pd.DataFrame:
    with zipfile.ZipFile(io.BytesIO(content)) as archive:
        names = [name for name in archive.namelist() if name.lower().endswith(".csv")]
        if len(names) != 1:
            raise ValueError(f"{name}: expected one CSV, found {names}")
        frame = pd.read_csv(archive.open(names[0]), dtype=str)
    frame.columns = [str(column).strip() for column in frame.columns]
    if "TradDt" in frame:
        frame["date"] = pd.to_datetime(frame["TradDt"], errors="coerce").dt.strftime("%Y-%m-%d")
        columns = {"TckrSymb": "symbol", "SctySrs": "series", "ISIN": "isin", "OpnPric": "open", "HghPric": "high",
                   "LwPric": "low", "ClsPric": "close", "PrvsClsgPric": "prev_close", "LastPric": "last",
                   "TtlTradgVol": "volume", "TtlTrfVal": "turnover", "TtlNbOfTxsExctd": "trades"}
    else:
        stamp = frame.get("TIMESTAMP", frame.get("DATE", pd.Series(index=frame.index, dtype=str)))
        frame["date"] = pd.to_datetime(stamp, errors="coerce", dayfirst=True).dt.strftime("%Y-%m-%d")
        columns = {"SYMBOL": "symbol", "SERIES": "series", "ISIN": "isin", "OPEN": "open", "HIGH": "high",
                   "LOW": "low", "CLOSE": "close", "PREVCLOSE": "prev_close", "LAST": "last",
                   "TOTTRDQTY": "volume", "TOTTRDVAL": "turnover", "TOTALTRADES": "trades"}
    frame = frame.rename(columns=columns)
    required = {"date", "symbol", "series", "open", "high", "low", "close"}
    if not required <= set(frame.columns):
        raise ValueError(f"{name}: missing columns {sorted(required - set(frame.columns))}; got {list(frame.columns)}")
    dates = sorted(frame["date"].dropna().unique())
    if dates != [day]:
        raise ValueError(f"{name}: requested {day}, archive rows carry dates {dates}")
    frame = frame.loc[frame["series"].astype(str).str.strip().isin({"EQ", "BE"})].copy()
    for field in ("open", "high", "low", "close", "prev_close", "last", "volume", "turnover", "trades"):
        if field in frame:
            frame[field] = pd.to_numeric(frame[field].astype(str).str.replace(",", "", regex=False).str.strip(), errors="coerce")
    if "isin" not in frame or frame["isin"].isna().any() or frame["isin"].astype(str).str.strip().eq("").any():
        raise ValueError(f"{name}: cash rows lack an ISIN field")
    prices = frame[["open", "high", "low", "close"]].to_numpy(dtype=float)
    if not np.isfinite(prices).all() or (prices <= 0).any():
        raise ValueError(f"{name}: cash OHLC contains missing, nonfinite, or nonpositive values")
    if (frame["high"] < frame[["open", "low", "close"]].max(axis=1)).any() or (frame["low"] > frame[["open", "high", "close"]].min(axis=1)).any():
        raise ValueError(f"{name}: invalid OHLC ordering")
    if frame["isin"].duplicated().any():
        raise ValueError(f"{name}: duplicate cash ISIN rows")
    frame["date"] = day
    frame["source_file"] = name
    frame["source_sha256"] = sha256(content)
    return frame


def expected_factor_change(events: list[dict], previous_close: float) -> float:
    change = 1.0
    for event in events:
        kind = str(event["type"]).lower()
        if kind == "split":
            change *= float(event["face_value_from"]) / float(event["face_value_to"])
        elif kind == "bonus":
            change *= 1 + float(event["ratio_num"]) / float(event["ratio_den"])
        elif kind == "dividend":
            amount = float(event["cash_amount"])
            if previous_close <= amount:
                raise ValueError("dividend is not below previous close")
            change *= previous_close / (previous_close - amount)
        elif kind != "buyback":
            raise ValueError(f"unsupported adjustment event: {kind}")
    return change


def select_gap_factor(factor_before: float, factor_after: float, events: list[tuple[pd.Timestamp, float]], target: pd.Timestamp) -> tuple[float, str]:
    if not np.isfinite([factor_before, factor_after]).all() or factor_before <= 0 or factor_after <= 0:
        return np.nan, "unresolved_factor_source"
    if not events:
        if np.isclose(factor_before, factor_after, rtol=1e-7, atol=1e-9):
            return factor_after, "adjacent_factor_match"
        return np.nan, "unresolved_factor_jump_without_action"
    expected = float(np.prod([ratio for _, ratio in events]))
    if not np.isclose(expected, factor_after / factor_before, rtol=2e-4, atol=2e-5):
        return np.nan, "unresolved_factor_ratio"
    applied = float(np.prod([ratio for day, ratio in events if day <= target]))
    return factor_before * applied, "verified_interval_action_factor"


def calendar_sessions() -> list[pd.Timestamp]:
    sessions = set()
    for path in sorted(TEJHQ_RAW.glob("year=*/nse_*.parquet")):
        dates = ds.dataset(path).to_table(columns=["date"])["date"].to_pylist()
        sessions.update(pd.Timestamp(day) for day in dates if day is not None)
    sessions.update(pd.Timestamp(day) for day in DATES)
    return sorted(sessions)


def benchmark_marks() -> dict[str, dict]:
    requested = set(DATES)
    official = {}
    for year in sorted({int(day[:4]) for day in DATES}):
        start = datetime(year, 1, 1).date()
        end = datetime(year, 12, 31).date()
        for row in tri_capture._get_rows("Nifty 50", start, end):
            day = datetime.strptime(row["Date"], "%d %b %Y").date().isoformat()
            if day in requested:
                official[day] = {"tri": float(row["TotalReturnsIndex"]), "ntr": float(row["NTR_Value"])}
    if set(official) != requested:
        raise ValueError(f"official NIFTY 50 TRI response lacks requested dates: {sorted(requested - set(official))}")
    return official


def adjusted_backfill(panel: pd.DataFrame, sessions: list[pd.Timestamp]) -> tuple[pd.DataFrame, dict]:
    positions = {day: idx for idx, day in enumerate(sessions)}
    reference_dates = set()
    for day in map(pd.Timestamp, DATES):
        pos = positions[day]
        reference_dates.update(sessions[max(0, pos - 8):pos])
        reference_dates.update(sessions[pos + 1:pos + 9])
    adjusted_files = sorted(ADJUSTED.glob("nse_*.parquet"))
    adjusted_ds = ds.dataset([str(path) for path in adjusted_files], format="parquet")
    expression = ds.field("date").isin([day.date() for day in sorted(reference_dates)])
    expression &= ds.field("symbol").isin(sorted(panel["symbol"].unique()))
    neighbor = adjusted_ds.to_table(
        columns=["date", "symbol", "series", "isin", "adj_factor_cumulative"], filter=expression
    ).to_pandas()
    neighbor["date"] = pd.to_datetime(neighbor["date"])
    neighbor = neighbor.sort_values(["symbol", "series", "date"])
    groups = {(key[0].upper(), key[1].upper()): frame.reset_index(drop=True)
              for key, frame in neighbor.groupby(["symbol", "series"], sort=False)}

    action_rows = []
    for path in sorted(ACTIONS.glob("nse_*.parquet")):
        action_rows.extend(ds.dataset(path).to_table().to_pylist())
    actions = pd.DataFrame(action_rows)
    actions["ex_date"] = pd.to_datetime(actions["ex_date"])
    actions = actions.drop_duplicates(["symbol", "isin", "ex_date", "type", "cash_amount", "face_value_from", "face_value_to"])
    actions_by_symbol = {str(symbol).upper(): rows.sort_values("ex_date") for symbol, rows in actions.groupby("symbol", sort=False)}
    relevant_events = actions.loc[actions["ex_date"].isin(reference_dates) & actions["symbol"].astype(str).str.upper().isin(set(panel["symbol"]))]
    raw_dates = sorted(relevant_events["ex_date"].dropna().unique())
    raw_symbols = sorted(relevant_events["symbol"].astype(str).str.upper().unique())
    raw_previous = {}
    if raw_dates and raw_symbols:
        raw_files = sorted(TEJHQ_RAW.glob("year=*/nse_*.parquet"))
        raw_ds = ds.dataset([str(path) for path in raw_files], format="parquet")
        raw_expr = ds.field("date").isin([pd.Timestamp(day).date() for day in raw_dates])
        raw_expr &= ds.field("symbol").isin(raw_symbols)
        raw_rows = raw_ds.to_table(columns=["date", "symbol", "prev_close"], filter=raw_expr).to_pylist()
        raw_previous = {(str(row["symbol"]).upper(), pd.Timestamp(row["date"])): row["prev_close"] for row in raw_rows}
    for row in panel.itertuples(index=False):
        if pd.notna(row.prev_close):
            raw_previous[(str(row.symbol).upper(), pd.Timestamp(row.date))] = float(row.prev_close)
    bridge_keys = set()
    if IDENTITY_BRIDGES.exists():
        bridges = pd.read_csv(IDENTITY_BRIDGES, dtype=str).fillna("")
        bridge_keys = {(r.symbol.upper(), r.from_isin.upper(), r.to_isin.upper(), r.economic_ex_date)
                       for r in bridges.itertuples(index=False) if r.status == "verified"}

    records = []
    for row in panel.itertuples(index=False):
        day = pd.Timestamp(row.date)
        frame = groups.get((str(row.symbol).upper(), str(row.series).upper()))
        record = row._asdict()
        record.update({"adj_factor_cumulative": np.nan, "adj_close": np.nan,
                       "factor_status": "unresolved_nearby_history", "factor_reference_before": "",
                       "factor_reference_after": ""})
        if frame is not None:
            prior = frame[frame["date"] < day]
            following = frame[frame["date"] > day]
            if not prior.empty and not following.empty:
                before, after = prior.iloc[-1], following.iloc[0]
                record["factor_reference_before"] = before["date"].date().isoformat()
                record["factor_reference_after"] = after["date"].date().isoformat()
                factor_before, factor_after = float(before["adj_factor_cumulative"]), float(after["adj_factor_cumulative"])
                event_changes = []
                action_terms_ok = True
                symbol_actions = actions_by_symbol.get(str(row.symbol).upper())
                if symbol_actions is not None:
                    interval = symbol_actions[(symbol_actions["ex_date"] > before["date"]) & (symbol_actions["ex_date"] <= after["date"])]
                    for event_day, event_rows in interval.groupby("ex_date", sort=True):
                        previous_close = raw_previous.get((str(row.symbol).upper(), pd.Timestamp(event_day)))
                        try:
                            if previous_close is None:
                                raise ValueError("event previous close is unavailable")
                            ratio = expected_factor_change(event_rows.to_dict("records"), float(previous_close))
                            event_changes.append((pd.Timestamp(event_day), ratio))
                        except (TypeError, ValueError, ZeroDivisionError):
                            event_changes = []
                            action_terms_ok = False
                            break
                bridge_ok = any(
                    (str(row.symbol).upper(), str(before["isin"]).upper(), str(after["isin"]).upper(), event_day.date().isoformat()) in bridge_keys
                    for event_day, _ in event_changes
                )
                if not action_terms_ok:
                    record["factor_status"] = "unresolved_action_terms"
                elif str(before["isin"]).upper() != str(after["isin"]).upper() and not bridge_ok:
                    record["factor_status"] = "unresolved_identity_bridge"
                else:
                    factor, status = select_gap_factor(factor_before, factor_after, event_changes, day)
                    record["adj_factor_cumulative"], record["factor_status"] = factor, status
        if pd.notna(record["adj_factor_cumulative"]):
            record["adj_close"] = float(row.close) * float(record["adj_factor_cumulative"])
        records.append(record)
    result = pd.DataFrame(records)
    summary = {
        "backfill_rows": len(result),
        "adjusted_factor_resolved_rows": int(result["adj_factor_cumulative"].notna().sum()),
        "adjusted_factor_unresolved_rows": int(result["adj_factor_cumulative"].isna().sum()),
        "factor_status_counts": result["factor_status"].value_counts().to_dict(),
        "specific_factor_residuals": result.loc[result["adj_factor_cumulative"].isna(),
                                                  ["date", "symbol", "isin", "factor_status"]].to_dict("records")[:50],
    }
    return result, summary


def main() -> None:
    RAW.mkdir(parents=True, exist_ok=True)
    session = requests.Session()
    session.headers.update({"User-Agent": "Mozilla/5.0 (compatible; QuantBacktestResearch/1.0)",
                            "Accept": "*/*", "Referer": "https://www.nseindia.com/"})
    all_rows, ledger = [], []
    for day in DATES:
        name, url = source_name(day), source_url(day)
        path = RAW / name
        if path.is_file():
            content = path.read_bytes()
        else:
            response = session.get(url, timeout=60)
            response.raise_for_status()
            content = response.content
            if not content.startswith(b"PK\x03\x04"):
                raise ValueError(f"{day}: NSE response is not a ZIP archive")
            path.write_bytes(content)
            time.sleep(0.5)
        frame = parse_archive(content, day, name)
        all_rows.append(frame)
        ledger.append({"date": day, "source": "NSE official cash-market bhavcopy", "format": "UDiFF" if "TradDt" in frame.columns else "legacy",
                       "source_url": url, "filename": name, "sha256": sha256(content), "bytes": len(content),
                       "cash_eq_be_rows": len(frame), "unique_isins": frame["isin"].nunique(),
                       "positive_turnover_rows": int(frame.get("turnover", pd.Series(0, index=frame.index)).gt(0).sum()),
                       "special_session_ohlc": "daily exchange aggregate; not split into separate intraday venues" if day in {"2024-03-02", "2024-05-18"} else "daily exchange bhavcopy"})
    panel = pd.concat(all_rows, ignore_index=True)
    panel.to_parquet(DATA / "nse_calendar_backfill.parquet", index=False)
    ledger_frame = pd.DataFrame(ledger)
    ledger_frame.to_csv(DATA / "source_ledger.csv", index=False)
    sessions = calendar_sessions()
    official_marks = benchmark_marks()
    tri_reference = pd.read_csv(ROOT / "work" / "data" / "index_daily" / "NIFTY50TR-days-1-2014-01-01-2026-10-23.csv", dtype={"date": str})
    tri_reference = tri_reference.set_index("date")
    mark_rows = []
    for day in DATES:
        marks = official_marks[day]
        tri_close = float(tri_reference.at[day, "tri"])
        ntr_close = float(tri_reference.at[day, "ntr"])
        mark_rows.append({"date": day, "official_tri": marks["tri"], "reference_tri": tri_close,
                          "tri_match": bool(np.isclose(marks["tri"], tri_close, rtol=0, atol=0.011)),
                          "official_ntr": marks["ntr"], "reference_ntr": ntr_close,
                          "ntr_match": bool(np.isclose(marks["ntr"], ntr_close, rtol=0, atol=0.011))})
    marks_frame = pd.DataFrame(mark_rows)
    marks_frame.to_csv(DATA / "official_nifty50_gap_marks.csv", index=False)
    (DATA / "official_nifty50_gap_marks_source.json").write_text(json.dumps({
        "source_page": tri_capture.SOURCE_PAGE, "source_route": tri_capture.SOURCE_ROUTE,
        "request_range_by_year": sorted({day[:4] for day in DATES}), "official_rows": mark_rows,
    }, indent=2) + "\n", encoding="utf-8")
    panel["nifty50_tri"] = panel["date"].map({d: official_marks[d]["tri"] for d in DATES})
    panel["nifty50_ntr"] = panel["date"].map({d: official_marks[d]["ntr"] for d in DATES})
    adjusted, factor_summary = adjusted_backfill(panel, sessions)
    adjusted.to_parquet(DATA / "nse_calendar_backfill_adjusted.parquet", index=False)
    (DATA / "calendar_backfill_factor_audit.json").write_text(json.dumps(factor_summary, indent=2) + "\n", encoding="utf-8")
    factor_by_date = adjusted.groupby("date").agg(
        adjusted_factor_resolved=("adj_factor_cumulative", "count"),
        adjusted_factor_unresolved=("adj_factor_cumulative", lambda values: int(values.isna().sum())),
    ).to_dict("index")
    ledger_frame["nifty50_tri_mark_match"] = ledger_frame["date"].map(marks_frame.set_index("date")["tri_match"])
    ledger_frame["nifty50_ntr_mark_match"] = ledger_frame["date"].map(marks_frame.set_index("date")["ntr_match"])
    ledger_frame["adjusted_factor_resolved"] = ledger_frame["date"].map({d: v["adjusted_factor_resolved"] for d, v in factor_by_date.items()})
    ledger_frame["adjusted_factor_unresolved"] = ledger_frame["date"].map({d: v["adjusted_factor_unresolved"] for d, v in factor_by_date.items()})
    ledger_frame.to_csv(DATA / "source_ledger.csv", index=False)
    summary = {
        "as_of": "2026-10-31", "dates_requested": len(DATES), "dates_fetched_and_date_validated": len(ledger),
        "all_dates_verified_in_raw_bhavcopy": sorted(panel["date"].unique().tolist()) == sorted(DATES),
        "raw_source_sessions_before_backfill": len(sessions) - len(DATES), "verified_sessions_added": len(DATES),
        "source_session_calendar_after_backfill": len(sessions),
        "session_rows": len(panel), "unique_security_ids": int(panel["isin"].nunique()),
        "sessions_with_positive_turnover_rows": int(ledger_frame["positive_turnover_rows"].gt(0).sum()),
        "special_session_format": "daily aggregate OHLC/turnover in the exchange EOD file; intraday venue paths are not reconstructed",
        "source_rows_local": True, "raw_files_local": True,
        "official_nifty50_tri_marks_returned": len(official_marks),
        "official_nifty50_tri_marks_matched_existing_reference": int(marks_frame["tri_match"].sum()),
        "official_nifty50_ntr_marks_returned": len(official_marks),
        "official_nifty50_ntr_marks_matched_existing_reference": int(marks_frame["ntr_match"].sum()),
        "max_tri_reference_difference": float((marks_frame["official_tri"] - marks_frame["reference_tri"]).abs().max()),
        "max_ntr_reference_difference": float((marks_frame["official_ntr"] - marks_frame["reference_ntr"]).abs().max()),
        "adjusted_factor_reconstruction": {key: value for key, value in factor_summary.items() if key != "specific_factor_residuals"},
        "adjusted_backfill_with_benchmark_join": "local nse_calendar_backfill_adjusted.parquet; unresolved factors remain null",
    }
    (OUT / "nse_calendar_backfill_summary_2026-10-31.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    ledger_frame[["date", "cash_eq_be_rows", "unique_isins", "positive_turnover_rows", "nifty50_tri_mark_match",
                  "nifty50_ntr_mark_match", "adjusted_factor_resolved", "adjusted_factor_unresolved", "special_session_ohlc"]].to_csv(
        OUT / "nse_calendar_backfill_aggregate_2026-10-31.csv", index=False)
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--self-check", action="store_true")
    args = parser.parse_args()
    if args.self_check:
        assert np.isclose(expected_factor_change([{"type": "split", "face_value_from": 10, "face_value_to": 1}], 500), 10)
        assert np.isclose(expected_factor_change([{"type": "dividend", "cash_amount": 5}], 100), 100 / 95)
        assert expected_factor_change([{"type": "buyback"}], 100) == 1
        target = pd.Timestamp("2020-01-02")
        assert select_gap_factor(0.1, 1.0, [(target, 10)], target) == (1.0, "verified_interval_action_factor")
        assert select_gap_factor(0.1, 1.0, [(target + pd.Timedelta(days=1), 10)], target) == (0.1, "verified_interval_action_factor")
        print("calendar backfill self-check passed: split, dividend, and non-price-adjusting buyback")
    else:
        main()
