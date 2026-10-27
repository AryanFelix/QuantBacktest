from __future__ import annotations

import base64
import csv
import json
import re
from io import BytesIO
from pathlib import Path

from pypdf import PdfReader

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "work" / "data" / "universe_sources"
PDF_DIR = SOURCE / "pdfs"
CANDIDATES = json.loads((SOURCE / "reconstitution_candidates.json").read_text(encoding="utf-8"))
extra_payloads = {}
for path in [*SOURCE.glob("releases_corporate_actions*.json"), SOURCE / "releases_exclusions.json"]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, str):
        data = json.loads(data)
    extra_payloads.update(data)
archive_index = json.loads((SOURCE / "full_release_archive_index.json").read_text(encoding="utf-8"))
known_names = {item["url"].rsplit("/", 1)[-1] for item in CANDIDATES}
CANDIDATES.extend(
    item for item in archive_index
    if item["filename"] in extra_payloads and item["filename"] not in known_names
)

payloads: dict[str, str] = {}
for path in [*SOURCE.glob("releases_batch_*.json"), *SOURCE.glob("releases_suffix_batch_*.json"), SOURCE / "releases_2016_2018.json", *SOURCE.glob("releases_corporate_actions*.json"), SOURCE / "releases_exclusions.json"]:
    if not path.exists():
        continue
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, str):
        data = json.loads(data)
    if not isinstance(data, dict):
        raise ValueError(f"Expected filename-to-base64 map in {path.name}")
    for name, encoded in data.items():
        if name in payloads and payloads[name] != encoded:
            raise ValueError(f"Conflicting copies of {name}")
        payloads[name] = encoded

candidate_names = {item["url"].rsplit("/", 1)[-1] for item in CANDIDATES}
missing = candidate_names - payloads.keys()
assert not missing, f"Missing {len(missing)} official archive PDFs: {sorted(missing)}"

PDF_DIR.mkdir(parents=True, exist_ok=True)
titles = {item["url"].rsplit("/", 1)[-1]: item["text"] for item in reversed(CANDIDATES)}
records = []
texts = {}
for name in sorted(candidate_names):
    raw = base64.b64decode(payloads[name], validate=True)
    if not raw.startswith(b"%PDF-"):
        raise ValueError(f"Downloaded content is not a PDF: {name}")
    pdf_path = PDF_DIR / name
    pdf_path.write_bytes(raw)
    reader = PdfReader(BytesIO(raw))
    page_text = [page.extract_text() or "" for page in reader.pages]
    joined = "\n".join(page_text)
    texts[name] = joined
    relevant = [
        {"page": i + 1, "text": text}
        for i, text in enumerate(page_text)
        if re.search(r"nifty\s*[- ]?50|cnx\s*nifty", text, re.I)
    ]
    records.append({
        "filename": name,
        "official_url": f"https://www.niftyindices.com/Press_Release/{name}",
        "archive_title": titles.get(name, ""),
        "pdf_bytes": len(raw),
        "page_count": len(page_text),
        "mentions_nifty50": bool(relevant),
        "nifty50_pages": relevant,
    })

# Sanity check the extractor against two dated membership releases already independently inspected.
assert len(candidate_names) >= 176 and len(CANDIDATES) >= 178
assert all(name in texts for name in ("ind_prs27022014.pdf", "ind_prs20022015.pdf"))
assert all(term in texts["ind_prs27022014.pdf"].upper() for term in ("JPASSOCIAT", "RANBAXY", "TECHM", "MCDOWELL"))
assert all(term in texts["ind_prs20022015.pdf"].upper() for term in ("DLF", "JINDALSTEL", "IDEA", "YESBANK"))

(SOURCE / "nifty50_release_audit.json").write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")
with (SOURCE / "nifty50_release_audit.csv").open("w", newline="", encoding="utf-8-sig") as handle:
    writer = csv.DictWriter(handle, fieldnames=["filename", "official_url", "archive_title", "pdf_bytes", "page_count", "mentions_nifty50"])
    writer.writeheader()
    writer.writerows({key: row[key] for key in writer.fieldnames} for row in records)
print(f"audited {len(records)} official PDFs; {sum(row['mentions_nifty50'] for row in records)} contain NIFTY 50/CNX Nifty page text")
print(f"saved {PDF_DIR} and {SOURCE / 'nifty50_release_audit.json'}")
