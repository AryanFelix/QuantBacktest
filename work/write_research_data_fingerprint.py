"""Hash the frozen price, universe, dividend, action, benchmark and sector inputs."""

from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIXED = [
    "work/data/universe_sources/nifty50_monthly_universe_2020_2026.csv",
    "work/data/universe_sources/stock_monthly_universe_coverage.csv",
    "work/data/universe_sources/nse_corporate_actions_2000_2026.json",
    "work/data/universe_sources/current_nifty50_constituents_2026-09-30.csv",
    "outputs/stock_dividend_share_unit_alignment.csv",
    "work/data/etf_daily/NSE_EQ_INF204KB14I2-days-1-2014-01-01-2026-10-23.csv",
    "work/data/etf_daily/GOLDBEES-days-1-2014-01-01-2026-10-23.csv",
    "work/data/index_daily/NIFTY50TR-days-1-2014-01-01-2026-10-23.csv",
    "outputs/data_manifest.csv",
]


def main() -> None:
    coverage_path = ROOT / "work/data/universe_sources/stock_history_coverage.csv"
    with coverage_path.open(encoding="utf-8-sig", newline="") as handle:
        stock_paths = [row["cache_path"] for row in csv.DictReader(handle)]
    assert len(stock_paths) == 70 and len(set(stock_paths)) == 70
    etf_paths = [path.relative_to(ROOT).as_posix() for path in (ROOT / "work/data/etf_daily").rglob("*.csv")]
    paths = sorted(set(stock_paths + etf_paths + FIXED + ["work/data/universe_sources/stock_history_coverage.csv"]))
    files = []
    for relative in paths:
        path = ROOT / relative
        if not path.is_file():
            raise FileNotFoundError(path)
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        files.append({"path": relative, "sha256": digest, "bytes": path.stat().st_size})
    combined = hashlib.sha256("".join(f"{row['path']}:{row['sha256']}\n" for row in files).encode()).hexdigest()
    result = {"as_of": "2026-10-31", "stock_history_files": len(stock_paths), "input_files": len(files),
              "combined_sha256": combined, "files": files}
    output = ROOT / "outputs/research_data_fingerprint_2026-10-31.json"
    output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print({key: value for key, value in result.items() if key != "files"})


if __name__ == "__main__":
    main()
