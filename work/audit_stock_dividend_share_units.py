"""Express historical dividend cash in the apparent Upstox candle share unit."""

from __future__ import annotations

import csv
import json
import math
import os
import re
import tempfile
from collections import Counter, defaultdict
from datetime import date, datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "work" / "data" / "universe_sources"
DIVIDENDS = ROOT / "outputs" / "stock_dividend_parse_audit.csv"
SPLIT_AUDIT = ROOT / "outputs" / "upstox_split_bonus_adjustment_audit.csv"
OUT = ROOT / "outputs" / "stock_dividend_share_unit_alignment.csv"
SUMMARY = ROOT / "outputs" / "stock_dividend_share_unit_summary.csv"
NOTE = ROOT / "work" / "research" / "stock_dividend_share_unit_alignment.md"
MANIFEST = ROOT / "outputs" / "data_manifest.csv"
START = date(2020, 1, 1)
END = date(2026, 10, 23)
ALIASES = {"TATAMOTORS": "TMPV", "ZOMATO": "ETERNAL", "LTIM": "LTM", "INFRATEL": "INDUSTOWER"}
ACTION_TERM = re.compile(r"bonus|split|sub-division", re.I)


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", newline="", delete=False, dir=path.parent, suffix=".tmp") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
        temporary = Path(handle.name)
    os.replace(temporary, path)


def main() -> None:
    parsed_dividends = read_csv(DIVIDENDS)
    split_rows = read_csv(SPLIT_AUDIT)
    actions: dict[str, list[tuple[date, float, str]]] = defaultdict(list)
    action_pairs = set()
    for row in split_rows:
        symbol = ALIASES.get(row["symbol"], row["symbol"])
        action_date = date.fromisoformat(row["ex_date"])
        factor = float(row["normalized_share_factor"])
        assert factor > 1
        pair = (symbol, action_date)
        assert pair not in action_pairs, f"Duplicate share-action factor: {pair}"
        action_pairs.add(pair)
        actions[symbol].append((action_date, factor, row["action_subjects"]))

    membership = read_csv(SOURCE / "nifty50_monthly_universe_2020_2026.csv")
    member_symbols = {ALIASES.get(symbol, symbol) for row in membership for symbol in row["members"].split(";")}
    event_feed = json.loads((SOURCE / "nse_corporate_actions_2000_2026.json").read_text(encoding="utf-8"))
    candidate_pairs = set()
    for raw_symbol, events in event_feed["responses"].items():
        symbol = ALIASES.get(raw_symbol, raw_symbol)
        if symbol not in member_symbols:
            continue
        for event in events:
            subject = str(event.get("subject", ""))
            if "debenture" in subject.lower() or not ACTION_TERM.search(subject):
                continue
            try:
                action_date = datetime.strptime(event["exDate"], "%d-%b-%Y").date()
            except (KeyError, ValueError):
                continue
            if START <= action_date <= END:
                candidate_pairs.add((symbol, action_date))
    missing_action_pairs = candidate_pairs - action_pairs
    assert not missing_action_pairs, f"Share-action factors missing from the price audit: {sorted(missing_action_pairs)}"

    rows = []
    same_day_matches = 0
    for dividend in parsed_dividends:
        symbol = ALIASES.get(dividend["symbol"], dividend["symbol"])
        ex_date = date.fromisoformat(dividend["ex_date"])
        same_day = [row for row in actions[symbol] if row[0] == ex_date]
        later = sorted((row for row in actions[symbol] if row[0] > ex_date), key=lambda row: row[0])
        nominal = dividend["dividend_per_share_inr_unadjusted"]
        factor = math.prod(row[1] for row in later)
        if same_day:
            same_day_matches += 1
            aligned_amount = ""
            status = "same-date share action requires manual review"
        elif not nominal:
            aligned_amount = ""
            status = "unresolved dividend amount"
        else:
            aligned_amount = f"{float(nominal) / factor:.10g}"
            status = "candidate aligned amount; share-unit adjustment is inferred"
        rows.append({
            "symbol": symbol,
            "source_symbol": dividend["source_symbol"],
            "ex_date": ex_date.isoformat(),
            "record_date": dividend["record_date"],
            "face_value_inr": dividend["face_value_inr"],
            "subject": dividend["subject"],
            "nominal_dividend_per_historical_share_inr": nominal,
            "subsequent_share_factor_to_candle_unit": f"{factor:.10g}" if nominal else "",
            "candidate_dividend_per_candle_share_inr": aligned_amount,
            "subsequent_share_action_count": len(later),
            "subsequent_share_actions": " | ".join(f"{d.isoformat()} x{f:g}: {term}" for d, f, term in later),
            "same_date_share_action_count": len(same_day),
            "unit_alignment_status": status,
            "price_cache_path": dividend["price_cache_path"],
        })

    assert rows and same_day_matches == 0, f"Unexpected dividend/share-action date collision: {same_day_matches} rows"
    assert all(not row["candidate_dividend_per_candle_share_inr"] or float(row["candidate_dividend_per_candle_share_inr"]) >= 0 for row in rows)
    assert abs(10 / 2 - 5) < 1e-12
    examples = {(row["symbol"], row["ex_date"]): row for row in rows}
    for key, nominal, factor, aligned in [
        (("BAJFINANCE", "2025-05-30"), 44, 10, 4.4),
        (("NESTLEIND", "2023-11-01"), 140, 20, 7),
        (("RELIANCE", "2023-08-21"), 9, 2, 4.5),
    ]:
        row = examples[key]
        assert float(row["nominal_dividend_per_historical_share_inr"]) == nominal
        assert float(row["subsequent_share_factor_to_candle_unit"]) == factor
        assert float(row["candidate_dividend_per_candle_share_inr"]) == aligned

    parsed = [row for row in rows if row["nominal_dividend_per_historical_share_inr"]]
    adjusted = [row for row in parsed if int(row["subsequent_share_action_count"]) > 0]
    unresolved = [row for row in rows if row["unit_alignment_status"] == "unresolved dividend amount"]
    summary = [
        {"metric": "ever-member symbol dividend rows", "value": len(rows), "notes": "Event-date membership is not checked."},
        {"metric": "rows with parsed nominal amounts", "value": len(parsed), "notes": "Parsed from the corrected dividend-only event audit."},
        {"metric": "rows with a subsequent split/bonus factor", "value": len(adjusted), "notes": "Historical cash amounts divided by the cumulative share factor."},
        {"metric": "rows without a parsed subsequent split/bonus factor", "value": len(parsed) - len(adjusted), "notes": "No matching later event found in the saved NSE feed."},
        {"metric": "rows with unresolved dividend amount", "value": len(unresolved), "notes": "No candidate adjusted amount is emitted."},
        {"metric": "dividend rows sharing an ex-date with a split/bonus action", "value": same_day_matches, "notes": "Any such row is withheld for manual review."},
        {"metric": "ever-member split/bonus symbol-date candidates", "value": len(candidate_pairs), "notes": f"All {len(candidate_pairs)} candidates are covered by the 21-row Upstox price-adjustment audit."},
    ]

    fields = list(rows[0])
    write_csv(OUT, rows, fields)
    write_csv(SUMMARY, summary, ["metric", "value", "notes"])
    NOTE.write_text(
        "# Stock dividend amounts in Upstox candle share units\n\n"
        f"**Checked:** {date.today().isoformat()}\n\n"
        "## Method\n\n"
        "The dividend-event input is the corrected `outputs/stock_dividend_parse_audit.csv`; its earlier broad `div` filter matched `Sub-Division` split labels, and the first strict filter missed the feed typo `Dividned`. For each parsed dividend, the script finds later bonus/split factors for that symbol from `outputs/upstox_split_bonus_adjustment_audit.csv` and divides the nominal per-historical-share cash amount by their product. SEBI defines a bonus ratio A:B as A new shares for each B held and the share-count factor as (A+B)/B; it also describes split price/share changes as proportional. This supports the arithmetic, not Upstox's history convention.\n\n"
        f"The saved feed contains {len(candidate_pairs)} ever-member bonus/split symbol-date candidates in 2020-2026; every candidate is present in the {len(split_rows)}-row price-adjustment audit. {len(adjusted)} parsed dividend rows have a later parsed share factor; {len(parsed) - len(adjusted)} have no later factor in this saved feed. No parsed dividend ex-date coincides with one of these split/bonus dates. Examples: Bajaj Finance ₹44 divided by factor 10 becomes ₹4.40; Nestlé ₹140 divided by factor 20 becomes ₹7; Reliance ₹9 divided by factor 2 becomes ₹4.50. `outputs/stock_dividend_share_unit_alignment.csv` lists each event, the nominal amount, factor, candidate candle-unit amount, and action terms.\n\n"
        "## Interpretation and limits\n\n"
        f"The conversion is an inference: the project's {len(split_rows)}-row Upstox audit found observed ex-date close factors near 1.0 for bonus/split events that would otherwise imply large price changes, consistent with the cached history already reflecting new share units. Upstox's Historical Candle V3 documentation defines OHLC, volume, and open interest but does not specify corporate-action adjustment. Therefore the adjusted cash values are candidate research inputs, not verified Upstox accounting. The NSE corporate-actions page feed is not a completeness-guaranteed API; a missing later event would understate the conversion factor. Cash-flow timing, withholding/personal tax, same-date event aggregation, rights issues, and merger/demerger entitlements are outside this calculation. Do not use this alone to claim stock strategy P&L.\n\n"
        "Sources: [SEBI Investor Education: Corporate Actions (Feb 2025)](https://investor.sebi.gov.in/pdf/reference-material/ppt/PT-5%20Corporate%20Action%20-%20Dividends%2C%20Bonus%2C%20Splits%20etc-%20Feb%202025.pdf); [SEBI valuation circular on split adjustment](https://www.sebi.gov.in/sebi_data/mutualfundfile/jul-2018/1530853780625.pdf); [Upstox Historical Candle V3 documentation](https://upstox.com/developer/api-documentation/v3/get-historical-candle-data/).\n",
        encoding="utf-8",
    )

    manifest = read_csv(MANIFEST)
    manifest_fields = list(manifest[0])
    new_paths = {OUT.relative_to(ROOT).as_posix(), SUMMARY.relative_to(ROOT).as_posix(), NOTE.relative_to(ROOT).as_posix()}
    manifest = [row for row in manifest if row["cache_paths"] not in new_paths]
    manifest.extend([
        {"dataset": "Stock dividend share-unit alignment audit", "ticker": "symbols appearing in monthly NIFTY 50 snapshots", "instrument_key": "", "bar_interval": "event-level",
         "first_bar": START.isoformat(), "last_bar": END.isoformat(), "bar_count": str(len(rows)), "file_count": "1", "empty_files": "0",
         "cache_paths": OUT.relative_to(ROOT).as_posix(), "purpose": "Candidate cash-flow inputs for stock total-return research", "notes": "Dividends divided by later parsed split/bonus factors; Upstox share-unit behavior remains an inference."},
        {"dataset": "Stock dividend share-unit summary", "ticker": "symbols appearing in monthly NIFTY 50 snapshots", "instrument_key": "", "bar_interval": "summary",
         "first_bar": START.isoformat(), "last_bar": END.isoformat(), "bar_count": str(len(summary)), "file_count": "1", "empty_files": "0",
         "cache_paths": SUMMARY.relative_to(ROOT).as_posix(), "purpose": "Coverage counts for dividend share-unit alignment", "notes": "Ever-member symbols; source event feed completeness is not guaranteed."},
        {"dataset": "Stock dividend share-unit method", "ticker": "symbols appearing in monthly NIFTY 50 snapshots", "instrument_key": "", "bar_interval": "method note",
         "first_bar": START.isoformat(), "last_bar": END.isoformat(), "bar_count": "", "file_count": "1", "empty_files": "0",
         "cache_paths": NOTE.relative_to(ROOT).as_posix(), "purpose": "Document share-unit conversion and limitations", "notes": "Candidate adjusted cash values are not stock strategy P&L."},
    ])
    write_csv(MANIFEST, manifest, manifest_fields)
    print(f"dividend_rows={len(rows)} parsed={len(parsed)} adjusted_for_future_factors={len(adjusted)} unresolved={len(unresolved)} split_bonus_pairs={len(candidate_pairs)} same_date_collisions={same_day_matches}")


if __name__ == "__main__":
    main()
