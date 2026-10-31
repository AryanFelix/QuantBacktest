"""Download a pinned personal-research snapshot from TejHQ's public dataset."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote

import pyarrow.parquet as pq
import requests


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "work" / "data" / "public_research" / "tejhq"
REVISION = "2d6629d656fcb715a03b859f7cff8fbd53a7f420"
YEARS = tuple(range(2016, 2027))
API = "https://huggingface.co/api/datasets/tejhq/indian-markets/tree/"
BASE = "https://huggingface.co/datasets/tejhq/indian-markets/resolve/"


def file_paths() -> list[str]:
    return sorted(
        [f"nse/year={year}/nse_{year}.parquet" for year in YEARS]
        + [f"prices_adjusted/nse_{year}.parquet" for year in YEARS]
        + [f"actions/nse_{year}.parquet" for year in YEARS]
        + ["symbol_history/nse.parquet"]
    )


def target_path(relative: str) -> Path:
    path = (DATA / relative).resolve()
    if not path.is_relative_to(DATA.resolve()):
        raise ValueError(f"Unsafe dataset path: {relative}")
    return path


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def parquet_summary(path: Path) -> dict:
    parquet = pq.ParquetFile(path)
    fields = parquet.schema_arrow.names
    result = {"rows": parquet.metadata.num_rows, "columns": fields}
    for date_field in ("date", "ex_date"):
        if date_field not in fields:
            continue
        minimum, maximum = [], []
        col = fields.index(date_field)
        for group in range(parquet.metadata.num_row_groups):
            stats = parquet.metadata.row_group(group).column(col).statistics
            if stats and stats.has_min_max:
                minimum.append(str(stats.min))
                maximum.append(str(stats.max))
        if minimum:
            result["date_field"] = date_field
            result["date_min"] = min(minimum)
            result["date_max"] = max(maximum)
        break
    return result


def atomic_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False, dir=path.parent, suffix=".tmp") as handle:
        json.dump(value, handle, indent=2, sort_keys=True)
        handle.write("\n")
        temporary = Path(handle.name)
    os.replace(temporary, path)


def download() -> list[dict]:
    session = requests.Session()
    response = session.get(API + REVISION, params={"recursive": "true"}, timeout=(10, 60))
    response.raise_for_status()
    metadata = {item["path"]: item for item in response.json() if item.get("type") == "file"}
    records = []
    for relative in file_paths():
        item = metadata.get(relative)
        if not item or len(item.get("lfs", {}).get("oid", "")) != 64:
            raise ValueError(f"Pinned dataset object missing or lacks SHA-256: {relative}")
        expected_sha = item["lfs"]["oid"]
        expected_bytes = item["lfs"]["size"]
        target = target_path(relative)
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.is_file() and sha256_file(target) == expected_sha:
            pass
        else:
            url = BASE + REVISION + "/" + quote(relative, safe="/")
            with session.get(url, params={"download": "true"}, stream=True, timeout=(10, 120)) as response:
                response.raise_for_status()
                with tempfile.NamedTemporaryFile("wb", delete=False, dir=target.parent, suffix=".part") as handle:
                    temporary = Path(handle.name)
                    for chunk in response.iter_content(1024 * 1024):
                        if chunk:
                            handle.write(chunk)
                    handle.flush()
                    os.fsync(handle.fileno())
            actual_sha = sha256_file(temporary)
            actual_bytes = temporary.stat().st_size
            if actual_sha != expected_sha or actual_bytes != expected_bytes:
                temporary.unlink(missing_ok=True)
                raise ValueError(f"Pinned object mismatch for {relative}: {actual_bytes} bytes, {actual_sha}")
            os.replace(temporary, target)

        stat = parquet_summary(target)
        record = {
            "source": "TejHQ public Hugging Face dataset, built from NSE/BSE public bhavcopy/action files",
            "url": BASE + REVISION + "/" + quote(relative, safe="/"),
            "revision": REVISION,
            "path": relative,
            "retrieved_at_utc": datetime.now(timezone.utc).isoformat(),
            "bytes": target.stat().st_size,
            "sha256": expected_sha,
            **stat,
        }
        records.append(record)
        print(f"{relative}: {record['bytes']} bytes, {stat['rows']} rows, sha256 verified")

    manifest = {
        "dataset": "tejhq/indian-markets",
        "revision": REVISION,
        "purpose": "personal historical research; raw files local only",
        "requested_years": [YEARS[0], YEARS[-1]],
        "files": records,
    }
    atomic_json(DATA / "manifest.json", manifest)
    return records


def self_check() -> None:
    paths = file_paths()
    assert len(paths) == 34 and len(set(paths)) == 34
    assert paths[0] == "actions/nse_2016.parquet"
    assert paths[-1] == "symbol_history/nse.parquet"
    assert len(REVISION) == 40 and set(REVISION) <= set("0123456789abcdef")
    assert all(not target_path(path).is_relative_to(ROOT / "outputs") for path in paths)
    print("collector self-check passed: pinned revision, 34 unique paths, local-only target")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--self-check", action="store_true")
    args = parser.parse_args()
    if args.self_check:
        self_check()
    else:
        download()


if __name__ == "__main__":
    main()

