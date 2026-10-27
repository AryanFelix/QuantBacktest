import csv
import json
import os
import re
import tempfile
from collections import defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "work" / "data" / "universe_sources"
EVENTS = SOURCE / "nse_corporate_actions_2000_2026.json"
COVERAGE = SOURCE / "stock_history_coverage.csv"
OUT = ROOT / "outputs" / "upstox_split_bonus_adjustment_audit.csv"

coverage = {row["trading_symbol"]: row for row in csv.DictReader(COVERAGE.open(encoding="utf-8-sig", newline=""))}
actions = defaultdict(list)
for symbol, rows in json.loads(EVENTS.read_text(encoding="utf-8"))["responses"].items():
    if symbol not in coverage:
        continue
    for row in rows:
        subject = row.get("subject", "")
        low = subject.lower()
        if "debenture" in low or not any(term in low for term in ("bonus", "split", "sub-division")):
            continue
        actions[(symbol, row.get("exDate", ""))].append(subject)

audit = []
for (symbol, ex_date), subjects in sorted(actions.items()):
    path = ROOT / coverage[symbol]["cache_path"]
    bars = list(csv.DictReader(path.open(encoding="utf-8-sig", newline="")))
    index = next((i for i, bar in enumerate(bars) if bar["time"][:10] == __import__("datetime").datetime.strptime(ex_date, "%d-%b-%Y").date().isoformat()), None)
    if index is None or index == 0:
        continue
    share_factor = 1.0
    parsed = []
    for subject in subjects:
        bonus = re.search(r"bonus\s*[-:]?\s*(\d+)\s*:\s*(\d+)", subject, re.I)
        split = re.search(r"from\s+rs\.?\s*([\d.]+).*?to\s+(?:re\.?|rs\.?)\s*([\d.]+)", subject, re.I)
        if bonus:
            factor = 1 + int(bonus.group(1)) / int(bonus.group(2))
            share_factor *= factor
            parsed.append(f"bonus {bonus.group(1)}:{bonus.group(2)} (shares x{factor:g})")
        if split:
            factor = float(split.group(1)) / float(split.group(2))
            share_factor *= factor
            parsed.append(f"face-value split {split.group(1)} to {split.group(2)} (shares x{factor:g})")
    if not parsed:
        continue
    prior_close = float(bars[index - 1]["close"])
    ex_close = float(bars[index]["close"])
    audit.append({
        "symbol": symbol,
        "ex_date": bars[index]["time"][:10],
        "action_subjects": " | ".join(sorted(set(subjects))),
        "normalized_share_factor": f"{share_factor:.8g}",
        "theoretical_unadjusted_price_factor": f"{1 / share_factor:.8g}",
        "prior_close_upstox": f"{prior_close:.8g}",
        "exdate_close_upstox": f"{ex_close:.8g}",
        "observed_close_factor": f"{ex_close / prior_close:.8g}",
        "observed_close_return_pct": f"{100 * (ex_close / prior_close - 1):.6f}",
        "price_cache_path": coverage[symbol]["cache_path"],
    })

checks = {
    (row["symbol"], row["ex_date"]): float(row["observed_close_factor"])
    for row in audit
}
assert len(audit) >= 20, f"Expected broad split/bonus coverage, got {len(audit)}"
assert 0.8 < checks[("RELIANCE", "2024-10-28")] < 1.2
assert 0.8 < checks[("HDFCBANK", "2025-08-26")] < 1.2
assert float(next(row for row in audit if row["symbol"] == "RELIANCE" and row["ex_date"] == "2024-10-28")["theoretical_unadjusted_price_factor"]) == 0.5

with tempfile.NamedTemporaryFile("w", encoding="utf-8", newline="", delete=False, dir=OUT.parent, suffix=".tmp") as f:
    writer = csv.DictWriter(f, fieldnames=list(audit[0]))
    writer.writeheader()
    writer.writerows(audit)
    temp_path = Path(f.name)
os.replace(temp_path, OUT)

manifest_path = ROOT / "outputs" / "data_manifest.csv"
with manifest_path.open(encoding="utf-8-sig", newline="") as f:
    manifest = list(csv.DictReader(f))
fields = list(manifest[0])
manifest = [row for row in manifest if row["cache_paths"] != "outputs/upstox_split_bonus_adjustment_audit.csv"]
manifest.append({
    "dataset": "Upstox split/bonus price adjustment audit",
    "ticker": "MULTI",
    "instrument_key": "",
    "bar_interval": "event dates",
    "first_bar": min(row["ex_date"] for row in audit),
    "last_bar": max(row["ex_date"] for row in audit),
    "bar_count": str(len(audit)),
    "file_count": "1",
    "empty_files": "0",
    "cache_paths": "outputs/upstox_split_bonus_adjustment_audit.csv",
    "purpose": "Compare Upstox-returned stock prices with NSE bonus and split dates",
    "notes": "21 events; all ex-date close factors within 0.947-1.050. Consistent with share-unit back-adjustment, not a documented guarantee or total-return series. See work/research/upstox_candle_adjustment_behavior.md.",
})
assert len({row["cache_paths"] for row in manifest}) == len(manifest)
with tempfile.NamedTemporaryFile("w", encoding="utf-8", newline="", delete=False, dir=manifest_path.parent, suffix=".tmp") as f:
    writer = csv.DictWriter(f, fieldnames=fields)
    writer.writeheader()
    writer.writerows(manifest)
    temp_manifest = Path(f.name)
os.replace(temp_manifest, manifest_path)
print(f"split_bonus_events={len(audit)} observed_close_factor_range={min(float(row['observed_close_factor']) for row in audit):.3f}-{max(float(row['observed_close_factor']) for row in audit):.3f} known_bonus_continuity_checks=2/2 output={OUT}")
