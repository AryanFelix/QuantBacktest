import csv
import json
import os
import tempfile
from collections import defaultdict
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "work" / "data" / "universe_sources"
EVENTS = SOURCE / "nse_corporate_actions_2000_2026.json"
MOVES = SOURCE / "large_stock_daily_moves.csv"
OUT = ROOT / "outputs" / "stock_move_action_crosscheck.csv"

raw = json.loads(EVENTS.read_text(encoding="utf-8"))
actions = defaultdict(list)
for symbol, rows in raw["responses"].items():
    for row in rows:
        try:
            event_date = datetime.strptime(row["exDate"], "%d-%b-%Y").date()
        except (KeyError, ValueError):
            continue
        actions[symbol].append((event_date, row.get("subject", "")))

with MOVES.open(encoding="utf-8-sig", newline="") as f:
    moves = list(csv.DictReader(f))
results = []
for move in moves:
    trade_date = datetime.strptime(move["date"], "%Y-%m-%d").date()
    candidates = [
        (event_date, subject, (event_date - trade_date).days)
        for event_date, subject in actions.get(move["trading_symbol"], [])
        if abs((event_date - trade_date).days) <= 1
    ]
    candidates.sort(key=lambda x: (abs(x[2]), x[0], x[1]))
    labels = sorted({
        "demerger" if "demerg" in subject.lower()
        else "merger" if "merger" in subject.lower() or "amalgamat" in subject.lower()
        else "dividend" if "dividend" in subject.lower()
        else "bonus" if "bonus" in subject.lower()
        else "split" if "split" in subject.lower() or "sub-division" in subject.lower()
        else "rights" if "rights" in subject.lower()
        else "other"
        for _, subject, _ in candidates
    })
    results.append({
        **move,
        "matched_action_dates_offsets": "; ".join(f"{d.isoformat()} ({offset:+d}d)" for d, _, offset in candidates),
        "matched_action_subjects": "; ".join(dict.fromkeys(subject for _, subject, _ in candidates)),
        "matched_action_categories": "; ".join(labels),
        "match_status": "exact" if any(offset == 0 for _, _, offset in candidates) else "adjacent day" if candidates else "none",
    })

expected = {
    ("VEDL", "2026-04-30"),
    ("TMPV", "2025-10-14"),
    ("ITC", "2025-01-06"),
    ("SIEMENS", "2025-04-07"),
}
verified = {
    (row["trading_symbol"], row["date"])
    for row in results
    if "demerger" in row["matched_action_categories"] and row["match_status"] == "exact"
}
assert len(results) == len(moves)
assert expected <= verified, f"Known demerger price moves not matched: {expected - verified}"

with tempfile.NamedTemporaryFile("w", encoding="utf-8", newline="", delete=False, dir=OUT.parent, suffix=".tmp") as f:
    fields = list(moves[0].keys()) + ["matched_action_dates_offsets", "matched_action_subjects", "matched_action_categories", "match_status"]
    writer = csv.DictWriter(f, fieldnames=fields)
    writer.writeheader()
    writer.writerows(results)
    temp_path = Path(f.name)
os.replace(temp_path, OUT)
counts = defaultdict(int)
for row in results:
    counts[row["match_status"]] += 1
print(f"moves={len(results)} exact={counts['exact']} adjacent_day={counts['adjacent day']} none={counts['none']} known_demerger_checks={len(expected)}/{len(expected)} output={OUT}")
