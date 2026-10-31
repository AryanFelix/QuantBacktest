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
EXTRACTION_REVIEWS = SOURCE / "reviewed_source_extraction_reviews.csv"
MANUAL_EXTRACTIONS = SOURCE / "reviewed_manual_extractions.csv"
ANCHOR_DATE = pd.Timestamp("2026-09-30")
START_DATE = pd.Timestamp("2018-01-01")
DEFERRED_NOTICE_FILES = {"ind_prs18022020.pdf", "ind_prs12032020.pdf", "ind_prs19032020.pdf"}

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
    if filename == "ind_prs20022026_1.pdf":
        match = re.search(r"(?i)effective\s+from\s+February\s+24,?\s+2026", text)
        if not match:
            raise ValueError("KWIL exclusion notice no longer contains its reviewed effective date")
        effective = "2026-02-24"
    if not announcement:
        date_match = re.search(r"ind_prs(\d{2})(\d{2})(\d{4})", filename)
        if date_match:
            announcement = datetime.strptime("".join(date_match.groups()), "%d%m%Y").date().isoformat()
    if not effective:
        effective = parse_month_date(DATE_RE.search(title))
    return announcement, effective


def section_events(text: str) -> list[dict]:
    lines = [(page_no, line) for page_no, page in enumerate(text.split("\f"), 1)
             for line in page.replace("\r", "").splitlines()]
    headings = [i for i, (_, line) in enumerate(lines) if HEADING_RE.search(line)]
    events = []
    for start in headings:
        end = next((i for i in range(start + 1, len(lines)) if NEXT_HEADING_RE.search(lines[i][1])), len(lines))
        side = ""
        pending = ""
        for page_no, line in lines[start + 1:end]:
            lowered = line.lower()
            if "exclud" in lowered:
                side = "exclude"
                pending = ""
            elif "includ" in lowered:
                side = "include"
                pending = ""
            if re.fullmatch(r"\s*\d{1,3}[.)]?\s*", line):
                pending = line.strip().rstrip(".)") + " "
                continue
            candidate = pending + " ".join(line.split()) if pending else line
            row = ROW_RE.match(candidate)
            if not row or not side:
                if pending and line.strip():
                    pending = candidate + " "
                continue
            company = " ".join(row.group(2).split()).strip(" .")
            symbol = row.group(3).upper().strip(".")
            if company.lower() in {"company name", "symbol", "sr. no."} or symbol in {"SYMBOL", "NO"}:
                pending = ""
                continue
            events.append({"page_ref": f"p.{page_no}", "side": side, "company": company, "symbol": symbol})
            pending = ""
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


def xls_crosscheck_rows(rows: list[dict]) -> list[dict]:
    return [row for row in rows if row["effective_date"]
            and "2018-01-01" <= row["effective_date"] <= "2020-07-31"
            and row["filename"] not in DEFERRED_NOTICE_FILES]


def needs_visual_review(text_chars: int, pages_without_text: int) -> bool:
    return text_chars <= 100 or pages_without_text > 0


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
        {"page_ref": "p.1", "side": "exclude", "company": "Alkem Laboratories Ltd", "symbol": "ALKEM"},
        {"page_ref": "p.1", "side": "include", "company": "Apar Industries Ltd", "symbol": "APARINDS"},
    ]
    announced, effective = release_metadata(
        "PRESS RELEASE\nMumbai, August 10, 2026\nprior event effective from July 20, 2023",
        "ind_prs10082026.pdf", "Replacements w.e.f. September 30, 2026",
    )
    assert announced == "2026-08-10" and effective == "2026-09-30"
    assert not section_events("Only a paragraph mentioning Nifty 200.")
    assert needs_visual_review(0, 3) and needs_visual_review(101, 1) and not needs_visual_review(101, 0)
    assert section_events(sample.replace("14)", "l)").replace("15)", "m)")) == events
    for title in ("Nifty 200 Alpha 30", "Nifty 200 Momentum 30", "Nifty 200 Quality 30"):
        assert not section_events(f"14) {title}\nThe following companies are being included:\n1 Example Ltd. EXAMPLE")
    wrapped = """12) NIFTY 200
The following companies are being included:
Sr. No. Company Name Symbol
6
Indian Railway Catering And Tourism
Corporation Ltd. IRCTC
13) NIFTY Auto
"""
    assert section_events(wrapped) == [
        {"page_ref": "p.1", "side": "include", "company": "Indian Railway Catering And Tourism Corporation Ltd", "symbol": "IRCTC"}
    ]
    assert release_metadata(
        "Mumbai, February 20, 2026. Historical inclusion effective from December 05, 2025. "
        "Exclude effective from February 24, 2026.",
        "ind_prs20022026_1.pdf", "Exclusion of Kwality Wall's (India) Ltd. from Nifty Indices",
    ) == ("2026-02-20", "2026-02-24")
    fixture = [
        {"effective_date": "2020-03-27", "filename": "ind_prs18022020.pdf"},
        {"effective_date": "2020-06-26", "filename": "ind_prs10062020.pdf"},
    ]
    assert xls_crosscheck_rows(fixture) == [fixture[1]]
    print("membership parser self-check passed: boundaries, wrapped rows, and event-specific dates")


def run() -> dict:
    current_members, current_rows = read_current_members()
    history = pq.read_table(SYMBOL_HISTORY).to_pandas()
    archive = json.loads(ARCHIVE.read_text(encoding="utf-8"))
    titles = {item["filename"]: item for item in archive}
    reviews = {row["filename"]: row for row in csv.DictReader(EXTRACTION_REVIEWS.open(encoding="utf-8-sig", newline=""))}
    manual_extractions = list(csv.DictReader(MANUAL_EXTRACTIONS.open(encoding="utf-8-sig", newline="")))
    manual_by_file: dict[str, list[dict]] = {}
    for row in manual_extractions:
        manual_by_file.setdefault(row["filename"], []).append(row)

    release_rows = []
    source_audit = []
    extraction_coverage = []
    for path in sorted(PDF_DIR.glob("*.pdf")):
        pdf = PdfReader(path)
        page_texts = [page.extract_text() or "" for page in pdf.pages]
        text = "\n\f\n".join(page_texts)
        page_count = len(page_texts)
        text_chars = sum(len(page.strip()) for page in page_texts)
        empty_pages = [str(i) for i, page in enumerate(page_texts, 1) if not page.strip()]
        entry = titles.get(path.name, {})
        title = entry.get("text", "")
        digest = sha256_file(path)
        review = reviews.get(path.name, {})
        reviewed_manual = manual_by_file.get(path.name, [])
        if needs_visual_review(text_chars, len(empty_pages)):
            if not review or review.get("pdf_sha256") != digest or review.get("page_count") != str(page_count) or review.get("reviewed_pages") != f"1-{page_count}":
                raise ValueError(f"low-text PDF needs complete hash-matched source review: {path.name}")
        if reviewed_manual and (not review or review.get("classification") != "exact_parent_table"):
            raise ValueError(f"manual parent rows lack a reviewed exact-table source classification: {path.name}")
        if reviewed_manual:
            expected = (int(review["include_rows"]), int(review["exclude_rows"]))
            observed = (sum(row["side"] == "include" for row in reviewed_manual), sum(row["side"] == "exclude" for row in reviewed_manual))
            if expected != observed or any(row["pdf_sha256"] != digest for row in reviewed_manual):
                raise ValueError(f"manual extraction coverage/count/hash mismatch: {path.name}")
            if any(not re.fullmatch(r"p\.\d+", row["page_ref"]) or int(row["page_ref"][2:]) > page_count for row in reviewed_manual):
                raise ValueError(f"manual extraction page outside source document: {path.name}")
        announcement, effective = release_metadata(text, path.name, title)
        parsed = section_events(text)
        if reviewed_manual:
            announcement = reviewed_manual[0]["announcement_date"]
            effective = reviewed_manual[0]["event_effective_date"]
        mention = "nifty 200" in text.lower() or "nifty200" in text.lower() or bool(reviewed_manual)
        extraction_coverage.append({
            "filename": path.name, "official_url": entry.get("url", f"https://www.niftyindices.com/Press_Release/{path.name}"),
            "pdf_sha256": digest, "page_count": page_count, "pages_with_text": page_count - len(empty_pages),
            "pages_without_text": len(empty_pages), "pypdf_text_chars": text_chars,
            "pypdf_mentions_nifty200": "true" if "nifty 200" in text.lower() or "nifty200" in text.lower() else "false",
            "candidate_parent_notice": "true" if mention else "false",
            "manual_reviewed_pages": review.get("reviewed_pages", ""),
            "manual_review_method": review.get("review_method", ""),
            "reviewed_classification": review.get("classification", ""),
            "manual_parent_include_rows": len([row for row in reviewed_manual if row["side"] == "include"]),
            "manual_parent_exclude_rows": len([row for row in reviewed_manual if row["side"] == "exclude"]),
            "extraction_status": "MANUAL_REVIEW_COMPLETE" if review else "TEXT_EXTRACTED",
        })
        if not mention:
            continue
        record = {
            "filename": path.name,
            "official_url": entry.get("url", f"https://www.niftyindices.com/Press_Release/{path.name}"),
            "archive_title": title,
            "announcement_date": announcement,
            "effective_date": effective,
            "mentions_nifty200": True,
            "has_numbered_section": bool(parsed or reviewed_manual),
            "include_rows": sum(row["side"] == "include" for row in parsed) + len([row for row in reviewed_manual if row["side"] == "include"]),
            "exclude_rows": sum(row["side"] == "exclude" for row in parsed) + len([row for row in reviewed_manual if row["side"] == "exclude"]),
            "pdf_sha256": digest,
        }
        source_audit.append(record)
        for row in [*parsed, *reviewed_manual]:
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
    pd_release_events = xls_crosscheck_rows(release_rows)
    xls_key = {(row["event_date"], re.sub(r"[^A-Z0-9]", "", row["company"].upper()), row["side"]) for row in xls_events
               if "2018-01-01" <= row["event_date"] <= "2020-07-31"}
    pdf_key = {(row["effective_date"], re.sub(r"[^A-Z0-9]", "", row["company"].upper()), row["side"]) for row in pd_release_events}

    # Keep row-level notices local; only source counts and exception totals leave the ignored data cache.
    audit_dir = PUBLIC / "membership"
    atomic_csv(audit_dir / "release_events.csv", release_rows,
               ["announcement_date", "effective_date", "page_ref", "side", "company", "symbol", "isin", "mapping_error",
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
        "membership_reconstruction": "parser output only; run work/replay_nifty200_membership.py for the dated ISIN ledger and replay gate",
        "performance_gate": "NOT PASSED",
    }
    manifest["source_extraction_documents_scanned"] = len(extraction_coverage)
    manifest["low_text_documents_visually_reviewed"] = sum(int(row["pypdf_text_chars"]) <= 100 for row in extraction_coverage)
    manifest["text_or_page_gap_documents_visually_reviewed"] = sum(
        needs_visual_review(int(row["pypdf_text_chars"]), int(row["pages_without_text"]))
        for row in extraction_coverage
    )
    manifest["manual_parent_rows_recovered"] = len(manual_extractions)
    (audit_dir / "membership_audit.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    atomic_csv(ROOT / "outputs" / "nifty200_notice_coverage_2026-10-31.csv", source_audit,
               ["filename", "official_url", "archive_title", "announcement_date", "effective_date",
                "mentions_nifty200", "has_numbered_section", "include_rows", "exclude_rows", "pdf_sha256"])
    atomic_csv(ROOT / "outputs" / "nifty200_source_extraction_coverage_2026-10-31.csv", extraction_coverage,
               ["filename", "official_url", "pdf_sha256", "page_count", "pages_with_text", "pages_without_text",
                "pypdf_text_chars", "pypdf_mentions_nifty200", "candidate_parent_notice", "manual_reviewed_pages",
                "manual_review_method", "reviewed_classification", "manual_parent_include_rows",
                "manual_parent_exclude_rows", "extraction_status"])
    unreviewed_gaps = [row["filename"] for row in extraction_coverage
                       if needs_visual_review(int(row["pypdf_text_chars"]), int(row["pages_without_text"]))
                       and row["extraction_status"] != "MANUAL_REVIEW_COMPLETE"]
    if unreviewed_gaps:
        raise ValueError(f"source extraction coverage has unreviewed low-text or page-gap PDFs: {unreviewed_gaps}")
    print(json.dumps(manifest, indent=2))
    print(f"row-level event cache: {audit_dir / 'release_events.csv'}")
    return manifest


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--self-check", action="store_true")
    args = parser.parse_args()
    self_check() if args.self_check else run()
