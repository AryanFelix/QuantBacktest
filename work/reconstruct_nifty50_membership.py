from __future__ import annotations

import csv
import json
import re
from datetime import date, datetime
from pathlib import Path

import pandas as pd
from pypdf import PdfReader

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "work" / "data" / "universe_sources"
AUDIT = json.loads((SOURCE / "nifty50_release_audit.json").read_text(encoding="utf-8"))
ARCHIVE = {x["filename"]: x for x in json.loads((SOURCE / "full_release_archive_index.json").read_text(encoding="utf-8"))}

ALIASES = {"ZOMATO": "ETERNAL", "TATAMOTORS": "TMPV", "DUMMYITC": "ITCHOTELS", "DUMMYHDLVR": "KWIL", "DUMMYTATAM": "TMCV"}

def canonical(symbol: str) -> str:
    symbol = symbol.upper().strip()
    return ALIASES.get(symbol, symbol)

def effective_date(doc: dict) -> date:
    text = doc.get("archive_title", "") + "\n" + "\n".join(p["text"] for p in doc["nifty50_pages"])
    pattern = re.compile(r"(?:effective from|effective on|w\.?e\.?f\.?)\s+((?:(?:Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday),\s*)?[A-Z][a-z]+\s+\d{1,2},\s+\d{4})", re.I)
    for source_text in (text, "\n".join(page.extract_text() or "" for page in PdfReader(SOURCE / "pdfs" / doc["filename"]).pages)):
        for match in pattern.finditer(source_text):
            value = re.sub(r"^(?:Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday),\s*", "", match.group(1), flags=re.I)
            try:
                return datetime.strptime(value, "%B %d, %Y").date()
            except ValueError:
                pass
    raise ValueError(f"No effective date found in {doc['filename']}")

heading = re.compile(r"^\s*(?:(?:\(?\d+\)?[.)]|[A-Za-z][.)])\s*)?(?:CNX\s+)?NIFTY\s*[- ]?50(?:\s+INDEX)?\s*$", re.I)
next_section = re.compile(r"^\s*(?:\(?\d+\)?[.)]\s+(?:NIFTY|CNX)\b|[A-Za-z][.)]\s+(?:NIFTY|CNX)\b|[A-Z]\.\s+)", re.I)
status_line = re.compile(r"following\s+(?:companies|company|scrips?)\s+(?:are|is)\s+being\s+(excluded|included)", re.I)
row_line = re.compile(r"^\s*\d+\s+(.+?)\s+([A-Z0-9][A-Z0-9&.\-]+)\s*$")
events: list[dict] = []

for doc in AUDIT:
    if doc["filename"] == "ind_prs18022020.pdf":
        continue  # Its March 27 replacement date was superseded by the March 19 notice.
    action_date = None
    for page in doc["nifty50_pages"]:
        lines = page["text"].splitlines()
        for i, line in enumerate(lines):
            if not heading.match(line):
                continue
            stop = next((j for j in range(i + 1, len(lines)) if next_section.match(lines[j])), len(lines))
            section = lines[i + 1:stop]
            labels = [(j, status_line.search(value)) for j, value in enumerate(section)]
            labels = [(j, m) for j, m in labels if m]
            if not labels:
                continue
            if action_date is None:
                action_date = effective_date(doc)
            for k, (start, match) in enumerate(labels):
                end = labels[k + 1][0] if k + 1 < len(labels) else len(section)
                for value in section[start + 1:end]:
                    row = row_line.match(value)
                    if not row:
                        continue
                    symbol = row.group(2).upper()
                    events.append({
                        "effective_date": action_date.isoformat(),
                        "symbol": canonical(symbol),
                        "raw_symbol": symbol,
                        "action": "exclude" if match.group(1).lower() == "excluded" else "include",
                        "kind": "index replacement/review",
                        "filename": doc["filename"],
                        "title": ARCHIVE.get(doc["filename"], {}).get("text", doc["archive_title"]),
                        "official_url": f"https://www.niftyindices.com/Press_Release/{doc['filename']}",
                        "page": page["page"],
                        "evidence": value.strip(),
                    })

# Index-level temporary inclusions and their later exclusions require standalone notices.
special = [
    ("2023-07-20", "JIOFIN", "include", "ind_prs17072023.pdf", "Demerger placeholder inclusion; Jio Financial listed August 21, 2023."),
    ("2023-09-07", "JIOFIN", "exclude", "ind_prs05092023.pdf", "NSE Indices exclusion after listing-price-band rule."),
    ("2025-01-06", "ITCHOTELS", "include", "ind_prs30122024.pdf", "DUMMYITC placeholder included at zero price; ITC Hotels listed January 29, 2025."),
    ("2025-02-10", "ITCHOTELS", "exclude", "ind_prs06022025_1.pdf", "NSE Indices exclusion after listing-price-band rule."),
    ("2025-10-14", "TMCV", "include", "ind_prs07102025.pdf", "DUMMYTATAM placeholder included at zero price; TMCV listed November 12, 2025."),
    ("2025-11-17", "TMCV", "exclude", "ind_prs13112025.pdf", "NSE Indices exclusion after listing-price-band rule."),
    ("2025-12-05", "KWIL", "include", "ind_prs28112025.pdf", "DUMMYHDLVR placeholder included at zero price; Kwality Wall's listed February 16, 2026."),
    ("2026-02-24", "KWIL", "exclude", "ind_prs20022026_1.pdf", "NSE Indices exclusion after listing-price-band rule."),
]
for when, symbol, action, filename, note in special:
    events.append({
        "effective_date": when,
        "symbol": canonical(symbol),
        "raw_symbol": symbol,
        "action": action,
        "kind": "temporary corporate-action membership",
        "filename": filename,
        "title": ARCHIVE[filename]["text"],
        "official_url": f"https://www.niftyindices.com/Press_Release/{filename}",
        "page": 1,
        "evidence": note,
    })

events.sort(key=lambda x: (x["effective_date"], x["filename"], x["action"], x["symbol"]))
assert any(e["effective_date"] == "2025-03-28" and e["symbol"] == "JIOFIN" and e["action"] == "include" for e in events)
assert any(e["effective_date"] == "2025-03-28" and e["symbol"] == "ETERNAL" and e["action"] == "include" for e in events)
assert any(e["effective_date"] == "2026-09-30" and e["symbol"] == "BSE" and e["action"] == "include" for e in events)
assert all(e["official_url"].startswith("https://www.niftyindices.com/Press_Release/") for e in events)

(SOURCE / "nifty50_member_events.json").write_text(json.dumps(events, ensure_ascii=False, indent=2), encoding="utf-8")
with (SOURCE / "nifty50_member_events.csv").open("w", newline="", encoding="utf-8-sig") as handle:
    writer = csv.DictWriter(handle, fieldnames=list(events[0]))
    writer.writeheader()
    writer.writerows(events)

current = set(pd.read_csv(SOURCE / "current_nifty50_constituents_2026-09-30.csv")["Symbol"].astype(str).map(canonical))
def members_as_of(when: date) -> set[str]:
    result = set(current)
    for event in reversed(events):
        if date.fromisoformat(event["effective_date"]) <= when:
            continue
        symbol = event["symbol"]
        if event["action"] == "include":
            result.discard(symbol)
        else:
            result.add(symbol)
    return result

index = pd.read_csv(ROOT / "work" / "data" / "index_daily" / "NIFTY50-days-1-2014-01-01-2026-10-23.csv")
index["time"] = pd.to_datetime(index["time"], errors="raise")
calendar = index[index["time"].dt.date >= date(2020, 1, 1)].copy()
calendar["month"] = calendar["time"].dt.to_period("M")
monthly = calendar.groupby("month", sort=True).tail(1).reset_index(drop=True)
rows=[]
for i, row in monthly.iterrows():
    signal = row["time"]
    next_daily = index[index["time"] > signal]
    execution = next_daily.iloc[0]["time"] if not next_daily.empty else pd.NaT
    as_of = execution.date() if pd.notna(execution) else signal.date()
    names = sorted(members_as_of(as_of))
    rows.append({"month": str(row["month"]), "signal_date": signal.date().isoformat(), "universe_as_of_execution": as_of.isoformat(), "execution_date": execution.date().isoformat() if pd.notna(execution) else "", "member_count": len(names), "members": ";".join(names)})
with (SOURCE / "nifty50_monthly_universe_2020_2026.csv").open("w", newline="", encoding="utf-8-sig") as handle:
    writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
    writer.writeheader()
    writer.writerows(rows)
counts = sorted(set(r["member_count"] for r in rows))
assert all(49 <= count <= 52 for count in counts), f"Unexpected constituent count in reconstructed months: {counts}"
print(f"events={len(events)} months={len(rows)} member-counts={counts} current-snapshot={len(current)}")
print('member counts by month:', {c: sum(r['member_count']==c for r in rows) for c in counts})
