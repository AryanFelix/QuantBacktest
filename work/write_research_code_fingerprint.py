"""Record the exact code used in the 2026-10-31 measurement and attribution."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FILES = [
    "work/upstox_quant.py", "work/backtest_stock_momentum.py",
    "work/backtest_intraday_gap_fade.py", "work/backtest_monthly_nifty_credit_spread.py",
    "work/backtest_passive_mix_drawdown_control.py", "work/benchmark_nifty_gold_2020.py",
    "work/sensitivity_stock_nifty_gold_sleeve_split.py", "work/audit_stock_momentum_ohlc.py",
    "work/replay_donchian_gold_blend.py", "work/check_terminal_liquidation.py",
    "work/audit_stored_position_gaps.py", "work/attribute_stock_momentum_leader.py",
    "work/backtest_stock_momentum_reassessment.py",
    "work/write_research_data_fingerprint.py",
]


def main() -> None:
    rows = []
    for relative in sorted(FILES):
        path = ROOT / relative
        if not path.is_file():
            raise FileNotFoundError(path)
        rows.append({"path": relative, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()})
    digest = hashlib.sha256("".join(f"{row['path']}:{row['sha256']}\n" for row in rows).encode()).hexdigest()
    result = {"as_of": "2026-10-31", "files": rows, "combined_sha256": digest}
    output = ROOT / "outputs/research_code_fingerprint_2026-10-31.json"
    output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print({"files": len(rows), "combined_sha256": digest})


if __name__ == "__main__":
    main()
