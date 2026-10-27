"""Audit NSE corporate-action dividend amounts against the point-in-time stock universe."""

from __future__ import annotations

import csv
import json
import os
import re
import tempfile
from bisect import bisect_left
from collections import Counter
from datetime import date
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "work" / "data" / "universe_sources"
START = date(2020, 1, 1)
END = date(2026, 10, 23)
ALIASES = {"TATAMOTORS": "TMPV", "ZOMATO": "ETERNAL", "LTIM": "LTM", "INFRATEL": "INDUSTOWER"}
RUPEE_AMOUNT = re.compile(r"(?:₹|\bRs\.?|\bRe\.?)\s*([0-9][0-9,]*(?:\.[0-9]+)?)", re.I)
PERCENT = re.compile(r"([0-9]+(?:\.[0-9]+)?)\s*%")
DIVIDEND_EVENT = re.compile(r"\bdiv(?:idend|idned)?(?=[^a-z]|$)", re.I)
VERIFIED_DIVIDEND_OVERRIDES = {
    ("VEDL", "2022-03-09"): {
        "record_date": "10-Mar-2022",
        "face_value": "1",
        "amount": 13.0,
        "method": "primary-source override: FY2021-22 third interim dividend; record date matched",
        "urls": (
            "https://www.vedantalimited.com/eng/investor-relations-shareholder-information.php",
            "https://www.bseindia.com/bseplus/AnnualReport/500295/73739500295.pdf",
        ),
    },
}


def _amount(value: str) -> float:
    return float(value.replace(",", ""))


def parse_dividend(subject: str, face_value: str | None) -> tuple[float | None, str]:
    amounts = [_amount(value) for value in RUPEE_AMOUNT.findall(subject)]
    if amounts:
        return sum(amounts), "explicit rupee-per-share amount"
    percentages = [_amount(value) for value in PERCENT.findall(subject)]
    try:
        face = _amount(str(face_value)) if face_value not in {None, "", "-"} else None
    except ValueError:
        face = None
    if percentages and face is not None:
        return sum(percentages) * face / 100.0, "percent of stated face value"
    return None, "unparsed dividend amount"


def resolve_dividend_amount(symbol: str, ex_date: date, event: dict) -> tuple[float | None, str, str]:
    subject = str(event.get("subject", ""))
    value, method = parse_dividend(subject, event.get("faceVal"))
    source_urls = ""
    override = VERIFIED_DIVIDEND_OVERRIDES.get((symbol, ex_date.isoformat()))
    if value is None and override:
        assert event.get("recDate") == override["record_date"]
        assert str(event.get("faceVal")) == override["face_value"]
        assert subject == "Interim Dividend"
        value = override["amount"]
        method = override["method"]
        source_urls = ";".join(override["urls"])
    return value, method, source_urls


def _atomic_csv(path: Path, rows: list[dict], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", newline="", delete=False, dir=path.parent, suffix=".tmp") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
        temporary = Path(handle.name)
    os.replace(temporary, path)


def _read_history_dates() -> dict[str, tuple[Path, list[date]]]:
    coverage = pd.read_csv(SOURCE / "stock_history_coverage.csv", dtype=str)
    histories = {}
    for row in coverage.itertuples(index=False):
        symbol = ALIASES.get(row.trading_symbol, row.trading_symbol)
        path = ROOT / row.cache_path
        frame = pd.read_csv(path, usecols=["time"])
        dates = sorted(pd.to_datetime(frame["time"], errors="raise").dt.date.unique())
        histories[symbol] = (path, dates)
    for alias, target in ALIASES.items():
        if target in histories:
            histories[alias] = histories[target]
    return histories


def main() -> None:
    assert parse_dividend("Dividend-Rs.10/- Per Share", "10")[0] == 10
    assert parse_dividend("Dividend-Re 1 Per Share", "10")[0] == 1
    assert parse_dividend("Dividend-₹2.50 Per Share", "10")[0] == 2.5
    assert parse_dividend("AGM/Dividend-40%", "10")[0] == 4
    assert parse_dividend("Final Dividend Rs.25 and Special Dividend Rs.10 Per Share", "10")[0] == 35
    assert parse_dividend("Dividend declared; amount not stated", "10")[0] is None
    override_event = {"subject": "Interim Dividend", "faceVal": "1", "recDate": "10-Mar-2022"}
    resolved = resolve_dividend_amount("VEDL", date(2022, 3, 9), override_event)
    assert resolved[0] == 13.0 and "primary-source override" in resolved[1] and "vedantalimited.com" in resolved[2]
    assert resolve_dividend_amount("VEDL", date(2022, 3, 8), override_event)[0] is None
    assert DIVIDEND_EVENT.search("Interim Div70%")
    assert DIVIDEND_EVENT.search("Interim Dividned - Rs 135 Per Share")
    assert not DIVIDEND_EVENT.search("Face Value Split (Sub-Division) - From Rs 10 To Re 1")

    membership = pd.read_csv(SOURCE / "nifty50_monthly_universe_2020_2026.csv", dtype=str)
    member_symbols = {ALIASES.get(symbol, symbol) for value in membership["members"] for symbol in value.split(";")}
    archive = json.loads((SOURCE / "nse_corporate_actions_2000_2026.json").read_text(encoding="utf-8"))
    histories = _read_history_dates()
    candidate_events = []
    for response_symbol, events in archive["responses"].items():
        symbol = ALIASES.get(response_symbol, response_symbol)
        if symbol not in member_symbols:
            continue
        for event in events:
            subject = str(event.get("subject", ""))
            if not DIVIDEND_EVENT.search(subject):
                continue
            try:
                ex_date = pd.to_datetime(event.get("exDate"), format="%d-%b-%Y", errors="raise").date()
            except (TypeError, ValueError):
                continue
            if not START <= ex_date <= END:
                continue
            value, parse_method, amount_source_urls = resolve_dividend_amount(
                symbol, ex_date, event,
            )
            path, sessions = histories.get(symbol, (None, []))
            pos = bisect_left(sessions, ex_date)
            prior_date = sessions[pos - 1] if pos else None
            exact_bar = pos < len(sessions) and sessions[pos] == ex_date
            candidate_events.append({
                "symbol": symbol, "source_symbol": response_symbol, "isin": event.get("isin", ""),
                "ex_date": ex_date.isoformat(), "record_date": event.get("recDate", ""),
                "face_value_inr": event.get("faceVal", ""), "subject": subject,
                "dividend_per_share_inr_unadjusted": value if value is not None else "",
                "parse_method": parse_method, "exact_price_bar": exact_bar,
                "amount_source_urls": amount_source_urls,
                "prior_price_bar_date": prior_date.isoformat() if prior_date else "",
                "price_cache_path": path.relative_to(ROOT).as_posix() if path else "",
            })

    keys = Counter((row["symbol"], row["ex_date"]) for row in candidate_events)
    rows = []
    for row in candidate_events:
        key = (row["symbol"], row["ex_date"])
        row["same_symbol_exdate_row_count"] = keys[key]
        row["same_symbol_exdate_multirow_group"] = keys[key] > 1
        rows.append(row)
    assert rows and all(not row["dividend_per_share_inr_unadjusted"] or float(row["dividend_per_share_inr_unadjusted"]) >= 0 for row in rows)

    in_scope = pd.DataFrame(rows)
    summaries = []
    def metric(name: str, value, note: str = "") -> None:
        summaries.append({"scope": "overall", "metric": name, "value": value, "notes": note})

    parsed = in_scope["dividend_per_share_inr_unadjusted"].astype(str).str.len() > 0
    event_count = len(rows)
    parsed_count = int(parsed.sum())
    unresolved_count = event_count - parsed_count
    exact_bar_count = int(in_scope["exact_price_bar"].sum())
    multirow_count = int(in_scope["same_symbol_exdate_multirow_group"].sum())
    multirow_group_count = int(sum(value > 1 for value in keys.values()))
    metric("dividend rows from ever-member universe symbols 2020-01-01 to 2026-10-23", event_count, "A symbol is included if it appears in any monthly snapshot; this is not an as-of-date membership filter.")
    metric("rows with parsed nominal per-share amount", parsed_count)
    metric("rows with unresolved dividend amount", unresolved_count)
    metric("exact ex-date stock bars present", exact_bar_count, "Price-date coverage only; no assertion that the feed is complete.")
    metric("rows in same-symbol/ex-date multi-row groups", multirow_count, "Separate notices are retained; reconcile before aggregating cash flows.")
    metric("same-symbol/ex-date multi-row groups", multirow_group_count)
    metric("parsed nominal amounts needing price-series share-unit alignment", parsed_count, "Upstox stock prices appear share-unit adjusted after some bonus/split events; this audit does not convert historical dividend units.")
    for year, group in in_scope.groupby(in_scope["ex_date"].str[:4]):
        year_parsed = group["dividend_per_share_inr_unadjusted"].astype(str).str.len() > 0
        summaries.append({"scope": str(year), "metric": "ever-member symbol dividend rows / parsed", "value": f"{len(group)} / {int(year_parsed.sum())}", "notes": "Unadjusted nominal per-share amounts; membership is not checked on each event date."})

    audit_path = ROOT / "outputs" / "stock_dividend_parse_audit.csv"
    summary_path = ROOT / "outputs" / "stock_dividend_parse_summary.csv"
    _atomic_csv(audit_path, rows, list(rows[0]))
    _atomic_csv(summary_path, summaries, ["scope", "metric", "value", "notes"])
    note_path = ROOT / "work" / "research" / "stock_dividend_parse_audit.md"
    note_path.write_text(
        "# NSE stock dividend terms: parse and price-date audit\n\n"
        f"**Checked:** {date.today().isoformat()}\n\n"
        "This audit filters the saved NSE corporate-actions page feed to dividend-labelled events for symbols appearing in at least one reconstructed monthly NIFTY 50 snapshot, with ex-dates from 2020-01-01 through 2026-10-23. This is an ever-member symbol filter, not proof that a symbol belonged to NIFTY 50 on that event date. It parses explicit Rs/Re/₹ amounts as rupees per share; percent-only announcements are converted using the feed's stated face value. Multiple explicit amounts in one subject are summed. A verified VEDL event override is keyed by ex-date, record date, face value, and exact subject; its primary-source URLs are stored on that event row. Other unparsed labels and same-symbol/ex-date multi-row groups remain visible for review; separate notices are not silently deduplicated or aggregated.\n\n"
        "## Primary-source reconciliation\n\n"
        "The NSE page feed labels VEDL's 2022-03-09 ex-date and 10-Mar-2022 record date only as Interim Dividend. Vedanta's shareholder dividend history identifies a third interim dividend of ₹13 per ₹1 share paid on 23-Mar-2022; the BSE-hosted FY2021-22 annual report matches the 10-Mar record date and ₹13 amount. The event-level amount_source_urls field retains both documents. This resolves the amount for this row only; it does not establish completeness of the NSE event feed.\n\n"
        "Revision note (2026-10-26): the earlier broad `div` filter also matched `Sub-Division` split notices; the first strict filter then missed the NSE feed typo `Dividned`. The current rule excludes the split labels and retains that dividend spelling. Earlier counts are superseded.\n\n"
        f"The event-level output is `outputs/stock_dividend_parse_audit.csv`; counts by parse status and year are in `outputs/stock_dividend_parse_summary.csv`. In this run, {event_count} event rows were found, {parsed_count} amounts parsed, {unresolved_count} amounts remained unstated, {exact_bar_count} ex-dates matched a cached price bar, and {multirow_count} rows belonged to {multirow_group_count} same-symbol/ex-date multi-row groups. The join checks price-date coverage only. This is not proof that the NSE page feed is complete. It also does not reconcile revised notices, same-day cash aggregation, taxes, rights, or merger/demerger entitlements.\n\n"
        "Amounts are nominal at the historical share unit. Upstox price history appears adjusted for some later bonus/split events; dividend amounts must be converted into the same share units before adding cash to a simulated position. No stock total-return backtest is authorized by this parser audit alone.\n\n"
        "Source: `work/data/universe_sources/nse_corporate_actions_2000_2026.json`; source-contract limits are in `work/research/nse_corporate_actions_api.md`.\n",
        encoding="utf-8",
    )

    manifest_path = ROOT / "outputs" / "data_manifest.csv"
    with manifest_path.open(encoding="utf-8-sig", newline="") as handle:
        manifest = list(csv.DictReader(handle))
    fields = list(manifest[0])
    manifest_rows = [
        {"dataset": "NSE member dividend term parse audit", "ticker": "symbols appearing in monthly NIFTY 50 snapshots", "instrument_key": "", "bar_interval": "event-level",
         "first_bar": START.isoformat(), "last_bar": END.isoformat(), "bar_count": str(len(rows)), "file_count": "1", "empty_files": "0",
         "cache_paths": audit_path.relative_to(ROOT).as_posix(), "purpose": "Stock total-return input and corporate-action QA", "notes": "NSE label amounts plus event-level source-linked overrides and price-date join; symbol membership is ever-member. Candidate share-unit alignment and same-date aggregation are recorded separately."},
        {"dataset": "NSE member dividend parse summary", "ticker": "symbols appearing in monthly NIFTY 50 snapshots", "instrument_key": "", "bar_interval": "summary",
         "first_bar": START.isoformat(), "last_bar": END.isoformat(), "bar_count": str(len(summaries)), "file_count": "1", "empty_files": "0",
         "cache_paths": summary_path.relative_to(ROOT).as_posix(), "purpose": "Dividend parse coverage report", "notes": "Year and parse-status counts; source completeness is not guaranteed."},
        {"dataset": "NSE member dividend parse method", "ticker": "symbols appearing in monthly NIFTY 50 snapshots", "instrument_key": "", "bar_interval": "method note",
         "first_bar": START.isoformat(), "last_bar": END.isoformat(), "bar_count": "", "file_count": "1", "empty_files": "0",
         "cache_paths": note_path.relative_to(ROOT).as_posix(), "purpose": "Document parsing rules and remaining adjustments", "notes": "No backtest result is produced by this audit."},
    ]
    new_paths = {row["cache_paths"] for row in manifest_rows}
    manifest = [row for row in manifest if row["cache_paths"] not in new_paths]
    _atomic_csv(manifest_path, manifest + manifest_rows, fields)
    print(f"member_dividend_rows={event_count} parsed={parsed_count} unresolved={unresolved_count} exact_price_bars={exact_bar_count} multirow_groups={multirow_group_count}")


if __name__ == "__main__":
    main()
