"""Select the 50-bps price-signal sector rule using training OHLC risk only."""

from __future__ import annotations

import csv
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SENSITIVITY = ROOT / "outputs" / "sector_rotation_sensitivity.csv"
OHLC = ROOT / "outputs" / "sector_rotation_ohlc_audit.csv"
TRI = ROOT / "outputs" / "sector_tri_signal_momentum_sensitivity.csv"
TRI_OHLC = ROOT / "outputs" / "sector_tri_signal_momentum_ohlc_audit.csv"
OUTPUT = ROOT / "outputs" / "sector_rotation_ohlc_training_selection.json"


def _read(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def main() -> None:
    rows = _read(SENSITIVITY)
    risk_rows = _read(OHLC)
    assert len(rows) == 384 and len(risk_rows) == 96
    risk = {
        (row["strategy"], row["period"], float(row["exposure_cap_pct"])): row
        for row in risk_rows
    }
    candidates = []
    for row in rows:
        if not row["strategy"].startswith("sector_momentum12_1_top"):
            continue
        if row["period"] != "train_2022_2023" or int(float(row["slippage_bps_per_side"])) != 50:
            continue
        audit = risk[(row["strategy"], row["period"], float(row["exposure_cap_pct"]))]
        if audit["within_20pct_under_bound"] == "True":
            candidates.append({**row, **audit})
    assert candidates, "No momentum candidate passed the training OHLC bound"
    selected = max(candidates, key=lambda row: float(row["cagr_pct"]))
    strategy = selected["strategy"]
    tri_strategy = strategy.replace("sector_momentum12_1_", "sector_tri_momentum12_1_")
    selected_periods = []
    tri_rows = _read(TRI)
    tri_risk_rows = _read(TRI_OHLC)
    tri_risk = {
        (row["strategy"], row["period"], float(row["exposure_cap_pct"])): row
        for row in tri_risk_rows
    }
    for period in ("validation_2024", "holdout_2025_plus", "continuous_2022_plus"):
        price_row = next(row for row in rows if row["strategy"] == strategy and row["period"] == period and float(row["exposure_cap_pct"]) == float(selected["exposure_cap_pct"]) and int(float(row["slippage_bps_per_side"])) == 50)
        price_audit = risk[(strategy, period, float(selected["exposure_cap_pct"]))]
        tri_row = next(row for row in tri_rows if row["strategy"] == tri_strategy and row["period"] == period and float(row["exposure_cap_pct"]) == float(selected["exposure_cap_pct"]) and int(float(row["slippage_bps_per_side"])) == 50)
        tri_audit = tri_risk[(tri_strategy, period, float(selected["exposure_cap_pct"]))]
        selected_periods.append({
            "period": period,
            "etf_price_signal": {
                "total_return_pct": float(price_row["total_return_pct"]),
                "close_max_drawdown_pct": float(price_row["max_drawdown_pct"]),
                "ohlc_bound_pct": float(price_audit["simultaneous_ohlc_drawdown_bound_pct"]),
                "within_20pct": price_audit["within_20pct_under_bound"] == "True",
            },
            "official_tri_signal_same_top_n_and_cap": {
                "total_return_pct": float(tri_row["total_return_pct"]),
                "close_max_drawdown_pct": float(tri_row["max_drawdown_pct"]),
                "ohlc_bound_pct": float(tri_audit["simultaneous_ohlc_drawdown_bound_pct"]),
                "within_20pct": tri_audit["within_20pct_under_bound"] == "True",
            },
        })
    result = {
        "selection_cost_bps_per_side": 50,
        "training_period": "2022-01-03 through 2023-12-29",
        "selection_universe": "three 12–1 momentum top-N rules; 50/75/95/100% exposure caps",
        "criterion": "highest net CAGR among top-N sector momentum candidates passing the conservative daily OHLC drawdown screen",
        "selected_strategy": strategy,
        "selected_top_n": int(float(selected["top_n"])),
        "selected_exposure_cap_pct": float(selected["exposure_cap_pct"]),
        "training_return_pct": float(selected["total_return_pct"]),
        "training_cagr_pct": float(selected["cagr_pct"]),
        "training_close_drawdown_pct": float(selected["max_drawdown_pct"]),
        "training_ohlc_bound_pct": float(selected["simultaneous_ohlc_drawdown_bound_pct"]),
        "training_within_20pct": selected["within_20pct_under_bound"] == "True",
        "same_rule_results": selected_periods,
        "caveat": "Although the rule is selected from the training split, the later periods and broad research history were already inspected; this is not an untouched lockbox.",
    }
    OUTPUT.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(f"selected={strategy} cap={result['selected_exposure_cap_pct']:.0f}% training_ohlc={result['training_ohlc_bound_pct']:.2f}%")


if __name__ == "__main__":
    main()
