"""Synthetic regressions for NaN closes, orphan ledgers, and duplicate dates."""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "work"))
import audit_stored_position_gaps as audit


def main() -> None:
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        daily = root / "X.csv"
        pd.DataFrame({"time": ["2024-01-02", "2024-01-03", "2024-01-04"], "close": [100, float("nan"), float("nan")]}).to_csv(daily, index=False)
        price_exceptions: list[dict] = []
        x_prices = audit.read_close(daily, price_exceptions)
        assert "2024-01-03" not in x_prices
        assert any(row["kind"] == "invalid_raw_close" for row in price_exceptions)

        conflicting = root / "conflicting.csv"
        pd.DataFrame({"time": ["2024-01-02", "2024-01-02"], "close": [100, 101]}).to_csv(conflicting, index=False)
        try:
            audit.read_close(conflicting)
        except ValueError as error:
            assert "conflicting duplicate daily closes" in str(error)
        else:
            raise AssertionError("conflicting duplicate daily closes were accepted")

        runs = root / "runs"
        pair = runs / "cash_case"
        pair.mkdir(parents=True)
        pd.DataFrame({"date": ["2024-01-02", "2024-01-04"], "symbol": ["X", "X"],
                      "side": ["buy", "sell"], "quantity": [2, 2],
                      "terminal_liquidation": [False, True]}).to_csv(pair / "orders.csv", index=False)
        pd.DataFrame({"date": ["2024-01-02", "2024-01-03", "2024-01-04"], "nav": [1_000, 1_001, 1_002]}).to_csv(pair / "equity.csv", index=False)
        orphan = runs / "orphan"
        orphan.mkdir()
        pd.DataFrame({"date": ["2024-01-02"], "symbol": ["X"], "side": ["buy"], "quantity": [1]}).to_csv(orphan / "orders.csv", index=False)

        result = audit.audit_backtests(
            runs,
            {"X": x_prices, "Y": {"2024-01-02": 100.0, "2024-01-03": 100.0, "2024-01-04": 100.0}},
            price_exceptions,
        )
        counts = result["files"]
        assert (counts["discovered"], counts["paired"], counts["checked"], counts["excluded"], counts["invalid"]) == (2, 1, 1, 1, 0)
        assert counts["reconciliation"]["discovered_equals_checked_plus_excluded_plus_invalid"]
        assert counts["reconciliation"]["paired_equals_checked_plus_excluded_paired_plus_invalid_paired"]
        assert counts["reconciliation"]["discovered_equals_paired_plus_orphans"]
        assert result["coverage"]["missing_raw_close_observations"] == 2


if __name__ == "__main__":
    main()
