"""Fill a bounded set of missing official Nifty index notices in the local cache."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import re
import tempfile
import time
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path

import requests
from pypdf import PdfReader
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "work" / "data" / "universe_sources"
PDF_DIR = SOURCE / "pdfs"
ARCHIVE = SOURCE / "full_release_archive_index.json"
NAMES = (
    "ind_prs23032020.pdf", "ind_prs25032020.pdf",
    "ind_prs04092026.pdf", "ind_prs04082026_3.pdf", "ind_prs24062026_1.pdf",
    "ind_prs22062026.pdf", "ind_prs17062026.pdf", "ind_prs02032026_2.pdf",
    "ind_prs01122025.pdf", "ind_prs22092025.pdf", "ind_prs25062025_2.pdf",
    "ind_prs20062025.pdf", "ind_prs02122024_1.pdf", "ind_prs09112023.pdf",
    "ind_prs12102021.pdf", "ind_prs23102026_1.pdf",
)


def sha256(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def atomic_write(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("wb", delete=False, dir=path.parent, suffix=".part") as handle:
        temporary = Path(handle.name)
        handle.write(content)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


def self_check() -> None:
    assert len(NAMES) == 16 and len(set(NAMES)) == 16
    assert all(re.fullmatch(r"ind_prs\d{8}(?:_\d+)?\.pdf", name) for name in NAMES)
    print("notice collector self-check passed: 16 unique official archive filenames")


def collect() -> list[dict]:
    archive = json.loads(ARCHIVE.read_text(encoding="utf-8"))
    entries = {item["filename"]: item for item in archive}
    missing = set(NAMES) - entries.keys()
    if missing:
        raise ValueError(f"Not found in official archive index: {sorted(missing)}")

    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (compatible; QuantBacktest research; personal historical archive audit)",
        "Referer": "https://www.niftyindices.com/press-release",
    })
    session.mount("https://", HTTPAdapter(max_retries=Retry(
        total=3, connect=3, read=3, status=3, backoff_factor=1.5,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=frozenset(("GET",)), respect_retry_after_header=True,
    )))
    records = []
    for index, name in enumerate(NAMES):
        entry = entries[name]
        url = entry["url"]
        if not url.startswith("https://www.niftyindices.com/Press_Release/"):
            raise ValueError(f"Unexpected source host/path: {url}")
        path = PDF_DIR / name
        if path.is_file():
            content = path.read_bytes()
            retrieved_at = "already_cached"
        else:
            if index:
                time.sleep(1.0)
            response = session.get(url, timeout=(10, 45))
            response.raise_for_status()
            content = response.content
            if not content.startswith(b"%PDF-"):
                raise ValueError(f"Archive response was not a PDF: {name}")
            atomic_write(path, content)
            retrieved_at = datetime.now(timezone.utc).isoformat()
        if not content.startswith(b"%PDF-"):
            raise ValueError(f"Cached source is not a PDF: {name}")
        text = "\n".join(page.extract_text() or "" for page in PdfReader(BytesIO(content)).pages)
        record = {
            "filename": name,
            "archive_title": entry["text"],
            "official_url": url,
            "retrieved_at_utc": retrieved_at,
            "bytes": len(content),
            "sha256": sha256(content),
            "mentions_nifty200": "nifty 200" in text.lower() or "nifty200" in text.lower(),
            "page_count": len(PdfReader(BytesIO(content)).pages),
        }
        records.append(record)
        print(f"{name}: {record['bytes']} bytes, NIFTY200={record['mentions_nifty200']}")

    manifest = SOURCE / "nifty200_notice_manifest.json"
    atomic_write(manifest, (json.dumps(records, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
    with (SOURCE / "nifty200_notice_manifest.csv").open("w", encoding="utf-8-sig", newline="") as handle:
        fields = list(records[0])
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(records)
    return records


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--self-check", action="store_true")
    args = parser.parse_args()
    self_check() if args.self_check else collect()

