"""Parse official Nifty 200 change notices and reconcile them to a dated anchor."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import tempfile
from datetime import datetime
from io import BytesIO
from pathlib import Path

import pandas as pd
import pyarrow.parquet as pq
from pypdf import PdfReader


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "work" / "data"
SOURCE = DATA / "universe_sources"
PDF_DIR = SOURCE / "pdfs"
OFFICIAL = DATA / "public_research" / "official"
PUBLIC = DATA / "public_research"
CURRENT_CSV = OFFICIAL / "ind_nifty200list.csv"
EVENT_XLS = OFFICIAL / "IndexInclExcl.xls"
SYMBOL_HISTORY = PUBLIC / "tejhq" / "symbol_history" / "nse.parquet"
ARCHIVE = SOURCE / "full_release_archive_index.json"
ANCHOR_DATE = pd.Timestamp("2026-09-30")
START_DATE = pd.Timestamp("2018-01-01")

DATE_RE = re.compile(
    r"(?i)(?:shall\s+become\s+effective(?:\s+from)?|become\s+effective(?:\s+from)?|"
    r"effective\s+from|with\s+effect\s+from|w\.e\.f\.?)[\s:]*"
    r"(January|February|March|April|May|June|July|August|September|October|November|December)\s+"
    r"(\d{1,2}),?\s+(\d{4})"
)
ANNOUNCE_RE = re.compile(
    r"(?i)Mumbai,\s*(January|February|March|April|May|June|July|August|September|October|November|December)\s+"
    r"(\d{1,2}),?\s+(\d{4})"
)
HEADING_RE = re.compile(r"^\s*(?:\d+|[a-z])\)\s*Nifty\s*[- ]?\s*200(?:\s+Index)?\s*$", re.I)
NEXT_HEADING_RE = re.compile(r"^\s*(?:\d+|[a-z])\)\s+\S", re.I)
ROW_RE = re.compile(r"^\s*(\d{1,3})[.)]?\s+(.+?)\s+([A-Z0-9&._-]{1,24})\s*$")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def parse_month_date(match: re.Match | None) -> str:
    if not match:
        return ""
    month, day, year = match.groups()
    return datetime.strptime(f"{month} {day} {year}", "%B %d %Y").date().isoformat()


def release_metadata(text: str, filename: str, title: str) -> tuple[str, str]:
    announcement = parse_month_date(ANNOUNCE_RE.search(text[:2500]))
    effective = parse_month_date(DATE_RE.search(title)) or parse_month_date(DATE_RE.search(text))
    if not announcement:
        date_match = re.search(r"ind_prs(\d{2})(\d{2})(\d{4})", filename)
        if date_match:
            announcement = datetime.strptime("".join(date_match.groups()), "%d%m%Y").date().isoformat()
    if not effective:
        effective = parse_month_date(DATE_RE.search(title))
    return announcement, effective


def section_events(text: str) -> list[dict]:
    lines = text.replace("\r", "").splitlines()
    headings = [i for i, line in enumerate(lines) if HEADING_RE.search(line)]
    events = []
    for start in headings:
        end = next((i for i in range(start + 1, len(lines)) if NEXT_HEADING_RE.search(lines[i])), len(lines))
        side = ""
        for line in lines[start + 1:end]:
            lowered = line.lower()
            if "exclud" in lowered:
                side = "exclude"
            elif "includ" in lowered:
                side = "include"
            row = ROW_RE.match(line)
            if not row or not side:
                continue
            company = " ".join(row.group(2).split()).strip(" .")
            symbol = row.group(3).upper().strip(".")
            if company.lower() in {"company name", "symbol", "sr. no."} or symbol in {"SYMBOL", "NO"}:
                continue
            events.append({"side": side, "company": company, "symbol": symbol})
    return events


def read_current_members() -> tuple[set[str], list[dict]]:
    frame = pd.read_csv(CURRENT_CSV, dtype=str).fillna("")
    required = {"Company Name", "Symbol", "ISIN Code"}
    if not required <= set(frame.columns):
        raise ValueError(f"Current constituent CSV schema changed: {list(frame.columns)}")
    frame["Symbol"] = frame["Symbol"].str.strip().str.upper()
    frame["ISIN Code"] = frame["ISIN Code"].str.strip().str.upper()
    if len(frame) != 200 or frame["ISIN Code"].nunique() != 200 or frame["Symbol"].nunique() != 200:
        raise ValueError("Nifty 200 current anchor is not exactly 200 unique symbols and ISINs")
    rows = frame.to_dict("records")
    return set(frame["ISIN Code"]), rows


def active_isin(history: pd.DataFrame, symbol: str, when: pd.Timestamp, side: str) -> str:
    active = history.loc[
        (history["symbol"].astype(str).str.upper() == symbol.upper())
        & (pd.to_datetime(history["valid_from"]) <= when)
        & (history["valid_to"].isna() | (pd.to_datetime(history["valid_to"]) >= when)),
        "isin",
    ].dropna().astype(str).str.upper().unique()
    if not len(active) and side == "exclude":
        valid_to = pd.to_datetime(history["valid_to"])
        prior = history.loc[
            (history["symbol"].astype(str).str.upper() == symbol.upper())
            & (valid_to < when)
            & (valid_to >= when - pd.Timedelta(days=3)),
        ]
        if not prior.empty:
            latest = pd.to_datetime(prior["valid_to"]).max()
            active = prior.loc[pd.to_datetime(prior["valid_to"]) == latest, "isin"].dropna().astype(str).str.upper().unique()
    if len(active) != 1:
        raise ValueError(f"Expected one event ISIN for {symbol} on {when.date()}, found {list(active)}")
    return active[0]


def read_excel_events() -> list[dict]:
    frame = pd.read_excel(EVENT_XLS, sheet_name="Nifty 200")
    frame["event_date"] = pd.to_datetime(frame["Event Date"], dayfirst=True, errors="coerce")
    if frame["event_date"].isna().any():
        raise ValueError("Official IndexInclExcl.xls contains unparseable Nifty 200 event dates")
    frame = frame.drop_duplicates(["event_date", "Scrip Name", "Description"])
    return [
        {
            "event_date": row["event_date"].date().isoformat(),
            "company": str(row["Scrip Name"]).strip(),
            "side": "include" if str(row["Description"]).lower().startswith("inclusion") else "exclude",
        }
        for row in frame.to_dict("records")
    ]


def atomic_csv(path: Path, rows: list[dict], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8-sig", newline="", delete=False, dir=path.parent, suffix=".tmp") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows({key: row.get(key, "") for key in fields} for row in rows)
        temporary = Path(handle.name)
    temporary.replace(path)


def self_check() -> None:
    sample = """14) Nifty 200
The following companies are being excluded:
Sr. No. Company Name Symbol
1 Alkem Laboratories Ltd. ALKEM
The following companies are being included:
1 Apar Industries Ltd. APARINDS
15) Nifty LargeMidcap 250
"""
    events = section_events(sample)
    assert events == [
        {"side": "exclude", "company": "Alkem Laboratories Ltd", "symbol": "ALKEM"},
        {"side": "include", "company": "Apar Industries Ltd", "symbol": "APARINDS"},
    ]
    announced, effective = release_metadata(
        "PRESS RELEASE\nMumbai, August 10, 2026\nprior event effective from July 20, 2023",
        "ind_prs10082026.pdf", "Replacements w.e.f. September 30, 2026",
    )
    assert announced == "2026-08-10" and effective == "2026-09-30"
    assert not section_events("Only a paragraph mentioning Nifty 200.")
    assert section_events(sample.replace("14)", "l)").replace("15)", "m)")) == events
    assert not section_events("14) Nifty 200 Momentum 30\nThe following companies are being included:\n1 Example Ltd. EXAMPLE")
    print("membership parser self-check passed: section boundaries, actions, and dates")


def run() -> dict:
    current_members, current_rows = read_current_members()
    history = pq.read_table(SYMBOL_HISTORY).to_pandas()
    archive = json.loads(ARCHIVE.read_text(encoding="utf-8"))
    titles = {item["filename"]: item for item in archive}

    release_rows = []
    source_audit = []
    for path in sorted(PDF_DIR.glob("*.pdf")):
        pdf = PdfReader(path)
        text = "\n".join(page.extract_text() or "" for page in pdf.pages)
        if "nifty 200" not in text.lower() and "nifty200" not in text.lower():
            continue
        entry = titles.get(path.name, {})
        title = entry.get("text", "")
        announcement, effective = release_metadata(text, path.name, title)
        parsed = section_events(text)
        record = {
            "filename": path.name,
            "official_url": entry.get("url", f"https://www.niftyindices.com/Press_Release/{path.name}"),
            "archive_title": title,
            "announcement_date": announcement,
            "effective_date": effective,
            "mentions_nifty200": True,
            "has_numbered_section": bool(parsed),
            "include_rows": sum(row["side"] == "include" for row in parsed),
            "exclude_rows": sum(row["side"] == "exclude" for row in parsed),
            "pdf_sha256": sha256_file(path),
        }
        source_audit.append(record)
        for row in parsed:
            if not effective:
                row["mapping_error"] = "missing_effective_date"
                row["isin"] = ""
            else:
                try:
                    row["isin"] = active_isin(history, row["symbol"], pd.Timestamp(effective), row["side"])
                    row["mapping_error"] = ""
                except ValueError as error:
                    row["isin"] = ""
                    row["mapping_error"] = str(error)
            release_rows.append({**record, **row})

    xls_events = read_excel_events()
    pd_release_events = [
        row for row in release_rows if row["effective_date"] and "2018-01-01" <= row["effective_date"] <= "2020-07-31"
    ]
    xls_key = {(row["event_date"], re.sub(r"[^A-Z0-9]", "", row["company"].upper()), row["side"]) for row in xls_events
               if "2018-01-01" <= row["event_date"] <= "2020-07-31"}
    pdf_key = {(row["effective_date"], re.sub(r"[^A-Z0-9]", "", row["company"].upper()), row["side"]) for row in pd_release_events}

    # Keep row-level notices local; only source counts and exception totals leave the ignored data cache.
    audit_dir = PUBLIC / "membership"
    atomic_csv(audit_dir / "release_events.csv", release_rows,
               ["announcement_date", "effective_date", "side", "company", "symbol", "isin", "mapping_error",
                "filename", "official_url", "pdf_sha256", "archive_title"])
    atomic_csv(audit_dir / "notice_sources.csv", source_audit,
               ["filename", "official_url", "archive_title", "announcement_date", "effective_date",
                "mentions_nifty200", "has_numbered_section", "include_rows", "exclude_rows", "pdf_sha256"])
    atomic_csv(audit_dir / "xls_events.csv", xls_events, ["event_date", "company", "side"])

    mapping_errors = [row for row in release_rows if row["mapping_error"]]
    unmapped_sections = [row for row in source_audit if not row["has_numbered_section"]]
    manifest = {
        "anchor_date": ANCHOR_DATE.date().isoformat(),
        "start_date": START_DATE.date().isoformat(),
        "anchor_source_url": "https://www.niftyindices.com/IndexConstituent/ind_nifty200list.csv",
        "anchor_sha256": sha256_file(CURRENT_CSV),
        "anchor_members": len(current_members),
        "history_source_revision": "2d6629d656fcb715a03b859f7cff8fbd53a7f420",
        "xls_source_url": "https://archives.nseindia.com/content/indices/IndexInclExcl.xls",
        "xls_sha256": sha256_file(EVENT_XLS),
        "xls_event_rows_deduplicated": len(xls_events),
        "release_documents_mentioning_nifty200": len(source_audit),
        "release_rows_parsed": len(release_rows),
        "unmapped_release_rows": len(mapping_errors),
        "notices_without_numbered_membership_table": len(unmapped_sections),
        "xls_pdf_exact_match_rows_2018_to_2020": len(xls_key & pdf_key),
        "xls_only_event_rows_2018_to_2020": len(xls_key - pdf_key),
        "pdf_only_event_rows_2018_to_2020": len(pdf_key - xls_key),
        "membership_reconstruction": "not_yet_run; requires resolved event rows and amendment/deferment audit",
        "performance_gate": "NOT PASSED",
    }
    (audit_dir / "membership_audit.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    atomic_csv(ROOT / "outputs" / "nifty200_notice_coverage_2026-10-31.csv", source_audit,
               ["filename", "official_url", "archive_title", "announcement_date", "effective_date",
                "mentions_nifty200", "has_numbered_section", "include_rows", "exclude_rows", "pdf_sha256"])
    print(json.dumps(manifest, indent=2))
    print(f"row-level event cache: {audit_dir / 'release_events.csv'}")
    return manifest


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--self-check", action="store_true")
    args = parser.parse_args()
    self_check() if args.self_check else run()

