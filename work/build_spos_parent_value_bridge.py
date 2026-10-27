import csv
import json
import os
import tempfile
from collections import defaultdict
from fractions import Fraction
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ENTITLEMENTS = ROOT / "outputs" / "corporate_action_entitlements.csv"
PARENT_RAW = ROOT / "work" / "data" / "nse_spos_parent_open_raw.json"
SUCCESSOR_RAW = ROOT / "work" / "data" / "nse_spos_successor_probes_raw.json"
OUT = ROOT / "outputs" / "corporate_action_spos_value_bridge.csv"
MANIFEST = ROOT / "outputs" / "data_manifest.csv"


def read_csv(path):
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path, rows, fields):
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", newline="", delete=False, dir=path.parent, suffix=".tmp") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
        temporary = Path(handle.name)
    os.replace(temporary, path)


parents = json.loads(PARENT_RAW.read_text(encoding="utf-8"))
successors = json.loads(SUCCESSOR_RAW.read_text(encoding="utf-8"))
parent_quotes = {}
for result in parents["results"]:
    assert result["http_status"] == 200
    assert len(result["data"]) == 1
    quote = result["data"][0]
    assert quote["CH_SERIES"] == "EQ"
    parent_quotes[(result["symbol"], result["date"])] = quote

successor_probes = {}
for result in successors["results"]:
    assert result["http_status"] == 200
    successor_probes[(result["symbol"], result["date"])] = len(result["data"])

groups = defaultdict(list)
for row in read_csv(ENTITLEMENTS):
    if "Demerger" in row["action"] and "Continuing" not in row["action"]:
        groups[row["event_id"]].append(row)

bridge = []
for event_id, recipients in groups.items():
    first = recipients[0]
    quote = parent_quotes[(first["source_symbol"], first["ex_date"].split("-")[2] + "-" + first["ex_date"].split("-")[1] + "-" + first["ex_date"].split("-")[0])]
    prior_close = float(quote["CH_PREVIOUS_CLS_PRICE"])
    parent_open = float(quote["CH_OPENING_PRICE"])
    residual = round(max(0.0, prior_close - parent_open), 2)
    ratios = [Fraction(row["units_per_source_share"].split()[0]) for row in recipients]
    proxy = round(residual / float(ratios[0]), 2) if len(recipients) == 1 else ""
    probe_counts = [successor_probes[(row["recipient_symbol"], row["ex_date"].split("-")[2] + "-" + row["ex_date"].split("-")[1] + "-" + row["ex_date"].split("-")[0])] for row in recipients]
    gaps = [int(row["calendar_days_to_first_quote"]) for row in recipients]
    bridge.append({
        "event_id": event_id,
        "source_symbol": first["source_symbol"],
        "ex_date": first["ex_date"],
        "nse_previous_close": f"{prior_close:.2f}",
        "nse_ex_date_parent_open": f"{parent_open:.2f}",
        "implied_residual_value_per_source_share": f"{residual:.2f}",
        "demerged_recipients": ";".join(row["recipient_symbol"] for row in recipients),
        "units_per_source_share": ";".join(f"{row['recipient_symbol']}:{row['units_per_source_share']}" for row in recipients),
        "successor_archive_rows_on_ex_date": ";".join(f"{row['recipient_symbol']}:{count}" for row, count in zip(recipients, probe_counts)),
        "single_recipient_implied_value_per_new_share": f"{proxy:.2f}" if proxy != "" else "",
        "first_cached_successor_quote_date": ";".join(f"{row['recipient_symbol']}:{row['first_cached_quote_on_or_after_event']}" for row in recipients),
        "calendar_days_to_first_cached_quote": ";".join(f"{row['recipient_symbol']}:{gap}" for row, gap in zip(recipients, gaps)),
        "valuation_basis": "max(0, NSE prior close - ex-date parent open); index/entitlement proxy, not a successor trade",
    })

bridge.sort(key=lambda row: row["ex_date"])
assert len(bridge) == 6
assert all(count == 0 for count in successor_probes.values())
expected = {"RELIANCE_2023": "261.85", "ITC_2025": "26.00", "SIEMENS_2025": "2478.15", "TATA_MOTORS_2025": "260.75", "HINDUNILVR_2025": "40.20", "VEDL_2026": "484.10"}
assert {row["event_id"]: row["implied_residual_value_per_source_share"] for row in bridge} == expected
assert next(row for row in bridge if row["event_id"] == "ITC_2025")["single_recipient_implied_value_per_new_share"] == "260.00"
assert next(row for row in bridge if row["event_id"] == "VEDL_2026")["single_recipient_implied_value_per_new_share"] == ""

write_csv(OUT, bridge, list(bridge[0]))
manifest = read_csv(MANIFEST)
fields = list(manifest[0])
path_fields = {part for row in manifest for part in row["cache_paths"].split(";")}
new_rows = [
    {"dataset": "NSE official demerger parent ex-date OHLC source", "ticker": "RELIANCE;ITC;SIEMENS;TATAMOTORS;HINDUNILVR;VEDL", "instrument_key": "", "bar_interval": "event-date daily", "first_bar": "2023-07-20", "last_bar": "2026-04-30", "bar_count": "6", "file_count": "1", "empty_files": "0", "cache_paths": PARENT_RAW.relative_to(ROOT).as_posix(), "purpose": "Parent prior close/open inputs for event-aware shareholder valuation", "notes": "Official NSE Security-wise Archives API responses; archive Open is used as the ex-date opening value, while the SPOS residual remains an entitlement/index proxy."},
    {"dataset": "NSE successor ex-date archive availability probes", "ticker": "JIOFIN;ITCHOTELS;ENRIN;TMCV;KWIL;VAML;VOGL;VISL;VEDPOWER", "instrument_key": "", "bar_interval": "event-date daily query", "first_bar": "2023-07-20", "last_bar": "2026-04-30", "bar_count": "9", "file_count": "1", "empty_files": "0", "cache_paths": SUCCESSOR_RAW.relative_to(ROOT).as_posix(), "purpose": "Check whether successor shares have ex-date trade rows in the NSE daily archive", "notes": "All nine HTTP-200 responses returned no rows across series=ALL; no successor transaction price was found."},
    {"dataset": "NSE demerger parent-to-successor valuation bridge", "ticker": "six demergers", "instrument_key": "", "bar_interval": "event-level", "first_bar": "2023-07-20", "last_bar": "2026-04-30", "bar_count": str(len(bridge)), "file_count": "1", "empty_files": "0", "cache_paths": OUT.relative_to(ROOT).as_posix(), "purpose": "Document ex-date parent residual values and quote gaps without booking them as trades", "notes": "Values are inferred from NSE methodology and daily archive OHLC; Vedanta is an aggregate across four recipients and cannot be allocated from parent price alone."},
    {"dataset": "Reproducible NSE demerger value-bridge builder", "ticker": "six demergers", "instrument_key": "", "bar_interval": "script", "first_bar": "2023-07-20", "last_bar": "2026-04-30", "bar_count": str(len(bridge)), "file_count": "1", "empty_files": "0", "cache_paths": Path(__file__).relative_to(ROOT).as_posix(), "purpose": "Rebuild output bridge from saved official NSE responses and entitlement ledger", "notes": "Includes assert-based arithmetic and source coverage checks."},
]
for row in manifest:
    if row["dataset"] == "Demerger ex-date price-discovery method":
        row["notes"] = "Official NSE parent OHLC recovered for six events; residual is prior close less ex-date parent open, floored at zero. Successor rows remain absent on ex-dates; this is an entitlement/index proxy, not booked stock P&L."
for row in new_rows:
    if row["cache_paths"] not in path_fields:
        manifest.append(row)
write_csv(MANIFEST, manifest, fields)
print(f"events={len(bridge)} residual_values={','.join(row['implied_residual_value_per_source_share'] for row in bridge)} output={OUT}")
