"""Re-mark all 50-bps sector ETF rotation ledgers against daily OHLC ranges."""

from __future__ import annotations

import csv
from pathlib import Path

import audit_etf_intraday_drawdown as audit


ROOT = Path(__file__).resolve().parents[1]
INPUT = ROOT / "outputs" / "sector_rotation_sensitivity.csv"
OUTPUT = ROOT / "outputs" / "sector_rotation_ohlc_audit.csv"


def main() -> None:
    with INPUT.open(encoding="utf-8-sig", newline="") as handle:
        source_rows = list(csv.DictReader(handle))
    cases = [row for row in source_rows if int(float(row["slippage_bps_per_side"])) == 50]
    assert len(cases) == 6 * 4 * 4 == 96
    results = []
    keys = set()
    for row in cases:
        key = (row["strategy"], row["period"], float(row["exposure_cap_pct"]), 50)
        assert key not in keys
        keys.add(key)
        artifact = row["source_artifact"]
        assert artifact.endswith("/summary.json")
        run_path = artifact.removesuffix("/summary.json")
        label = f"{row['strategy']}__{row['period']}__{int(float(row['exposure_cap_pct']))}cap__50bps"
        result = audit.run_case(label, run_path)
        assert result["max_close_replay_error_inr"] <= 0.03
        results.append({
            "strategy": row["strategy"],
            "period": row["period"],
            "exposure_cap_pct": float(row["exposure_cap_pct"]),
            "slippage_bps_per_side": 50,
            "close_max_drawdown_pct": result["close_max_drawdown_pct"],
            "simultaneous_ohlc_drawdown_bound_pct": result["simultaneous_ohlc_drawdown_bound_pct"],
            "bound_peak_date": result["bound_peak_date"],
            "bound_trough_date": result["bound_trough_date"],
            "within_20pct_under_bound": result["within_20pct_under_bound"],
            "max_close_replay_error_inr": result["max_close_replay_error_inr"],
            "source_artifact": f"{run_path}/equity.csv;{run_path}/orders.csv",
        })
    assert len(results) == len(keys) == 96
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(results[0]))
        writer.writeheader()
        writer.writerows(results)
    print(f"audited={len(results)} risk_ledgers; all close-NAV replays reconcile within INR 0.03")


if __name__ == "__main__":
    main()
