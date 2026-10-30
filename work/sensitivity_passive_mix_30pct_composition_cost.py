"""Stress 30% initial NIFTY/Gold compositions across modeled execution costs."""

from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "work"))

import backtest_stock_momentum as stock
import benchmark_nifty_gold_2020 as benchmark
import replay_volatility_weighted_blend as blend
import select_passive_drawdown_control_walkforward as walkforward

COSTS = (10, 50, 100, 200)
NIFTY_SHARES = (30, 40, 50, 70)
EXPOSURE = 0.30
OUT = ROOT / "outputs" / "passive_mix_30pct_composition_cost.csv"
RUNS = ROOT / "work" / "backtests" / "passive_mix_30pct_composition_cost"
STRESS = ROOT / "outputs" / "passive_mix_composition_lower_exposure_200bps.csv"
SIM_TYPE = "passive_nifty_gold_30pct_composition_cost_sensitivity"


def main() -> None:
    _, panels, _, _ = blend.make_portfolios()
    data_end = panels["close"].dropna(subset=["NIFTYBEES", "GOLDBEES"]).index[-1].date()
    periods = (
        ("continuous_2015_2026", date(2015, 1, 2), data_end),
        *walkforward.PERIODS,
    )
    rows = []
    for slippage in COSTS:
        for nifty_pct in NIFTY_SHARES:
            gold_pct = 100 - nifty_pct
            name = f"initial_30pct_nifty_{nifty_pct:02d}_gold_{gold_pct:02d}"
            targets, events = benchmark._passive_targets(panels, {
                "NIFTYBEES": nifty_pct / 100,
                "GOLDBEES": gold_pct / 100,
            })
            for period, start, end in periods:
                result = benchmark._run(
                    f"{name}_{period}_{slippage}bps", targets, events,
                    panels, end, start=start,
                    run_dir=RUNS / f"{slippage}bps" / period,
                    cash_distributions=benchmark.NIFTYBEES_DISTRIBUTIONS,
                    exposure_cap=EXPOSURE, slippage_bps=slippage,
                )
                rows.append({
                    **result,
                    "period": period,
                    "initial_exposure_pct": 100 * EXPOSURE,
                    "nifty_share_of_risky_sleeve_pct": nifty_pct,
                    "gold_share_of_risky_sleeve_pct": gold_pct,
                })

    table = pd.DataFrame(rows)
    assert len(table) == len(COSTS) * len(NIFTY_SHARES) * len(periods) == 64
    assert not table.duplicated(["slippage_bps_per_side", "nifty_share_of_risky_sleeve_pct", "period"]).any()
    assert table["max_close_replay_error_inr"].max() <= 0.03
    stress = pd.read_csv(STRESS)
    for row in table.loc[table["slippage_bps_per_side"].eq(200)].to_dict("records"):
        reference = stress.loc[
            stress["strategy"].eq(
                f"initial_30pct_nifty_{int(row['nifty_share_of_risky_sleeve_pct']):02d}_gold_"
                f"{int(row['gold_share_of_risky_sleeve_pct']):02d}_{row['period']}_200bps"
            ) & stress["period"].eq(row["period"])
        ].iloc[0]
        for key in ("ending_balance_inr", "total_fees_inr", "total_slippage_inr", "ohlc_drawdown_bound_pct"):
            assert abs(float(row[key]) - float(reference[key])) <= 0.03, (key, row[key], reference[key])
    table.to_csv(OUT, index=False)

    ledger = stock.read_csv(ROOT / "outputs" / "backtest_summary.csv")
    fields = list(ledger[0])
    ledger = [row for row in ledger if row["simulation_type"] != SIM_TYPE]
    for row in rows:
        record = {field: "" for field in fields}
        record.update({
            "simulation_type": SIM_TYPE,
            "strategy": row["strategy"],
            "universe": "NIFTYBEES + GOLDBEES",
            "period": row["period"],
            "period_start": row["period_start"],
            "period_end": row["period_end"],
            "starting_balance_inr": row["starting_balance_inr"],
            "ending_balance_inr": row["ending_balance_inr"],
            "total_return_pct": row["total_return_pct"],
            "cagr_pct": row["cagr_pct"],
            "max_drawdown_pct": row["close_mdd_pct"],
            "gross_exposure_cap_pct": row["initial_exposure_pct"],
            "slippage_bps_per_side": row["slippage_bps_per_side"],
            "fees_inr": row["total_fees_inr"],
            "slippage_cost_inr": row["total_slippage_inr"],
            "order_count": row["order_count"],
            "within_20pct": row["within_20pct_ohlc"],
            "selection_or_sizing": (
                f"Initial 30% gross allocation; NIFTY {row['nifty_share_of_risky_sleeve_pct']:.0f}% / "
                f"Gold {row['gold_share_of_risky_sleeve_pct']:.0f}% within sleeve; no rebalancing"
            ),
            "source_artifact": (
                "outputs/passive_mix_30pct_composition_cost.csv;"
                "outputs/passive_mix_composition_cost_method.md;"
                "work/sensitivity_passive_mix_30pct_composition_cost.py"
            ),
            "notes": (
                f"OHLC envelope {row['ohlc_drawdown_bound_pct']:.4f}%; current modeled fees; "
                f"{row['slippage_bps_per_side']} bps/side sensitivity; all dates inspected."
            ),
        })
        ledger.append(record)
    stock.atomic_csv(ROOT / "outputs" / "backtest_summary.csv", ledger, fields)

    manifest_path = ROOT / "outputs" / "data_manifest.csv"
    manifest = stock.read_csv(manifest_path)
    manifest_fields = list(manifest[0])
    manifest = [row for row in manifest if row["dataset"] != "Passive NIFTY/Gold 30% composition cost sensitivity"]
    manifest.append({
        "dataset": "Passive NIFTY/Gold 30% composition cost sensitivity",
        "ticker": "NIFTYBEES; GOLDBEES",
        "instrument_key": "NSE_EQ|INF204KB14I2; NSE_EQ|INF204KB17I5",
        "bar_interval": "daily candles; static initial allocation; paired OHLC risk at 200 bps",
        "first_bar": "2015-01-02",
        "last_bar": data_end.isoformat(),
        "bar_count": f"{len(rows)} rows; {len(COSTS)} costs x {len(NIFTY_SHARES)} compositions x {len(periods)} periods",
        "file_count": f"{len(rows)} exact-fee replays + CSV + runner + per-run ledgers",
        "empty_files": "0",
        "cache_paths": (
            "outputs/passive_mix_30pct_composition_cost.csv;"
            "work/sensitivity_passive_mix_30pct_composition_cost.py;"
            "work/backtests/passive_mix_30pct_composition_cost/"
        ),
        "purpose": "Compare 30% initial NIFTY/Gold compositions at 10/50/100/200 bps per-side slippage across chronological periods",
        "notes": (
            "The 200-bps rows reconcile to the expanded composition ledger within ₹0.03. "
            "Slippage is assumed, not measured; all later periods were previously inspected."
        ),
    })
    for row in manifest:
        if row["dataset"] == "Consolidated backtest metric ledger":
            row["bar_count"] = str(len(ledger))
            phrase = "Sixty-four 30%-initial NIFTY/Gold composition cost-stress rows added."
            if phrase not in row["notes"]:
                row["notes"] = row["notes"].rstrip() + " " + phrase
    stock.atomic_csv(manifest_path, manifest, manifest_fields)
    print(f"wrote {len(rows)} cost-stress rows through {data_end}")


if __name__ == "__main__":
    main()
