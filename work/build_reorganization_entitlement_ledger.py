import csv
import os
import tempfile
from datetime import date
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "work" / "data" / "universe_sources"
SUCCESSOR_DATA = ROOT / "work" / "data" / "reorganization_successors"
OUT = ROOT / "outputs" / "corporate_action_entitlements.csv"
MANIFEST = ROOT / "outputs" / "data_manifest.csv"

SPECS = [
    ("HDFC_2023", "HDFC", "Merger", "2023-07-01", "", "", "HDFCBANK", "42/25 (1.68)", "2023-07-01", "https://nsearchives.nseindia.com/corporate/HDFCBANK_19072023144457_SEintimation_Reg34.pdf", "https://archives.nseindia.com/content/circulars/CML57423.pdf", "Shares were allotted 2023-07-14; HDFC's last traded session was 2023-07-12."),
    ("RELIANCE_2023", "RELIANCE", "Demerger", "2023-07-01", "2023-07-20", "2023-07-20", "JIOFIN", "1", "2023-07-20", "https://nsearchives.nseindia.com/annual_reports/AR_24850_RELIANCE_2023_2024_07082024143222.pdf", "", "Jio Financial Services shares were issued 1:1; first quote in the cache is after a 32-day unlisted interval."),
    ("ITC_2025", "ITC", "Demerger", "2025-01-01", "2025-01-06", "2025-01-06", "ITCHOTELS", "1/10 (0.1)", "2025-01-06", "https://nsearchives.nseindia.com/corporate/ITC_27012025211253_SE_COA_.pdf", "", "ITC Hotels shares were issued 1:10; first quote in the cache is after a 23-day interval."),
    ("SIEMENS_2025", "SIEMENS", "Demerger", "2025-03-25", "2025-04-07", "2025-04-07", "ENRIN", "1", "2025-04-07", "https://nsearchives.nseindia.com/corporate/ixbrl/INTEGRATED_FILING_INDAS_108362_04082025184525_iXBRL_WEB.html", "https://nsearchives.nseindia.com/corporate/SIEMENS_14052024212329_Outcome14052024.pdf", "Siemens Energy India shares were issued 1:1; first quote in the cache is after a 73-day interval."),
    ("TATA_MOTORS_2025", "TATAMOTORS", "Demerger and rename", "2025-10-01", "2025-10-14", "2025-10-14", "TMCV", "1", "2025-10-14", "https://nsearchives.nseindia.com/corporate/TATAMOTORSSJS_12112025224654_NSEBSECOAFINAL.pdf", "", "One TMCV share was issued per old TATAMOTORS share; first TMCV quote in the cache is after a 29-day interval."),
    ("TATA_MOTORS_2025", "TATAMOTORS", "Continuing share after rename", "2025-10-01", "2025-10-14", "2025-10-14", "TMPV", "1", "2025-10-14", "https://nsearchives.nseindia.com/corporate/TATAMOTORSSJS_12112025224654_NSEBSECOAFINAL.pdf", "", "The old TATAMOTORS share continued as TMPV; this row is not an additional share allotment."),
    ("HINDUNILVR_2025", "HINDUNILVR", "Demerger", "2025-12-01", "2025-12-05", "2025-12-05", "KWIL", "1", "2025-12-05", "https://nsearchives.nseindia.com/corporate/HINDUNILVR_13122025214953_SEIntimationCostofAcquisitionFinalsigned.pdf", "https://nsearchives.nseindia.com/corporate/HINDUNILVR_29112025134344_SEIntimationFAQs.pdf", "Kwality Wall's shares were issued 1:1; first quote in the cache is after a 73-day interval."),
    ("VEDL_2026", "VEDL", "Demerger", "2026-05-01", "2026-04-30", "2026-05-01", "VAML", "1", "2026-05-01", "https://nsearchives.nseindia.com/corporate/VEDL_16052026123241_VEDLSEIntimationCostofApportionmentsigned.pdf", "", "One share of each resulting company was issued per VEDL share; first quote in the cache is after a 45-day interval."),
    ("VEDL_2026", "VEDL", "Demerger", "2026-05-01", "2026-04-30", "2026-05-01", "VOGL", "1", "2026-05-01", "https://nsearchives.nseindia.com/corporate/VEDL_16052026123241_VEDLSEIntimationCostofApportionmentsigned.pdf", "", "One share of each resulting company was issued per VEDL share; first quote in the cache is after a 45-day interval."),
    ("VEDL_2026", "VEDL", "Demerger", "2026-05-01", "2026-04-30", "2026-05-01", "VISL", "1", "2026-05-01", "https://nsearchives.nseindia.com/corporate/VEDL_16052026123241_VEDLSEIntimationCostofApportionmentsigned.pdf", "", "One share of each resulting company was issued per VEDL share; first quote in the cache is after a 45-day interval."),
    ("VEDL_2026", "VEDL", "Demerger", "2026-05-01", "2026-04-30", "2026-05-01", "VEDPOWER", "1", "2026-05-01", "https://nsearchives.nseindia.com/corporate/VEDL_16052026123241_VEDLSEIntimationCostofApportionmentsigned.pdf", "", "One share of each resulting company was issued per VEDL share; first quote in the cache is after a 45-day interval."),
]

instruments = {}
for name in ("upstox_stock_keys.csv", "upstox_reorganization_instruments.csv", "upstox_reorganization_successors.csv"):
    path = SOURCE / name
    if path.exists():
        with path.open(encoding="utf-8-sig", newline="") as f:
            for row in csv.DictReader(f):
                instruments[row["trading_symbol"]] = row
coverage = {}
with (SOURCE / "stock_history_coverage.csv").open(encoding="utf-8-sig", newline="") as f:
    coverage = {row["trading_symbol"]: row for row in csv.DictReader(f)}

rows = []
successor_manifest_rows = []
for spec in SPECS:
    event_id, source_symbol, action, effective, ex_date, record_date, recipient, ratio, reference, source_url, extra_url, note = spec
    instrument = instruments[recipient]
    if recipient in coverage:
        relative_path = coverage[recipient]["cache_path"]
        candle_path = ROOT / relative_path
    else:
        key = instrument["instrument_key"].replace("|", "_")
        candle_path = next(SUCCESSOR_DATA.glob(f"{key}-days-1-*.csv"))
        relative_path = candle_path.relative_to(ROOT).as_posix()
    with candle_path.open(encoding="utf-8-sig", newline="") as f:
        bars = list(csv.DictReader(f))
    quote = next((bar["time"][:10] for bar in bars if bar["time"][:10] >= reference), "")
    assert quote, f"No post-event candle for {recipient}"
    gap = (date.fromisoformat(quote) - date.fromisoformat(reference)).days
    rows.append({
        "event_id": event_id,
        "source_symbol": source_symbol,
        "action": action,
        "scheme_effective_date": effective,
        "ex_date": ex_date,
        "record_date": record_date,
        "event_reference_date": reference,
        "recipient_symbol": recipient,
        "recipient_name": instrument.get("name", ""),
        "recipient_instrument_key": instrument["instrument_key"],
        "recipient_isin": instrument.get("isin", ""),
        "units_per_source_share": ratio,
        "first_cached_quote_on_or_after_event": quote,
        "calendar_days_to_first_quote": gap,
        "price_cache_path": relative_path,
        "source_filing_url": source_url,
        "additional_source_url": extra_url,
        "modeling_note": note,
    })
    if recipient not in coverage:
        times = [bar["time"][:10] for bar in bars]
        successor_manifest_rows.append({
            "dataset": "Upstox NSE reorganization successor candles",
            "ticker": recipient,
            "instrument_key": instrument["instrument_key"],
            "bar_interval": "1 day",
            "first_bar": min(times),
            "last_bar": max(times),
            "bar_count": str(len(bars)),
            "file_count": "1",
            "empty_files": "0",
            "cache_paths": relative_path,
            "purpose": "Value demerger successor-share entitlements after listing",
            "notes": f"First post-event quote is {gap} calendar days after {reference}; no tradable successor quote exists in this cache during the gap.",
        })

assert len(rows) == 11
assert sum(r["source_symbol"] == "VEDL" for r in rows) == 4
assert sum(r["recipient_symbol"] == "VEDPOWER" for r in rows) == 1
assert len({r["price_cache_path"] for r in rows}) == len({(r["event_id"], r["recipient_symbol"]) for r in rows})

with tempfile.NamedTemporaryFile("w", encoding="utf-8", newline="", delete=False, dir=OUT.parent, suffix=".tmp") as f:
    writer = csv.DictWriter(f, fieldnames=list(rows[0]))
    writer.writeheader()
    writer.writerows(rows)
    temp_path = Path(f.name)
os.replace(temp_path, OUT)

with MANIFEST.open(encoding="utf-8-sig", newline="") as f:
    reader = csv.DictReader(f)
    fields = reader.fieldnames
    manifest_rows = list(reader)
seen_paths = {row["cache_paths"] for row in manifest_rows}
manifest_rows.extend(row for row in successor_manifest_rows if row["cache_paths"] not in seen_paths)
assert len({row["cache_paths"] for row in manifest_rows}) == len(manifest_rows)
with tempfile.NamedTemporaryFile("w", encoding="utf-8", newline="", delete=False, dir=MANIFEST.parent, suffix=".tmp") as f:
    writer = csv.DictWriter(f, fieldnames=fields)
    writer.writeheader()
    writer.writerows(manifest_rows)
    temp_path = Path(f.name)
os.replace(temp_path, MANIFEST)
print(f"entitlement_rows={len(rows)} delayed_first_quotes={sum(int(r['calendar_days_to_first_quote']) > 0 for r in rows)} new_manifest_candles={len(successor_manifest_rows)} output={OUT}")
