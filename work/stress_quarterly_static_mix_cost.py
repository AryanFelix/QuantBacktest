"""Stress quarterly static NIFTY/Gold cap, sleeve-ratio, and cost combinations."""

from __future__ import annotations

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
CAPS = (0.45, 0.50, 0.55, 0.60, 0.65)
COMPOSITION_CAP = 0.55
RATIOS = tuple((nifty / 100, 1 - nifty / 100) for nifty in range(0, 101, 10) if nifty != 50)
RATIOS_60 = ((0.30, 0.70), (0.40, 0.60))
OUT = ROOT / "outputs" / "quarterly_static_mix_cost_sensitivity.csv"
RUNS = ROOT / "work" / "backtests" / "quarterly_static_mix_cost"
SIM_TYPE = "quarterly_static_nifty_gold_cap_ratio_cost_sensitivity"


def main() -> None:
    _, panels, _, _ = blend.make_portfolios()
    data_end = panels["close"].index[-1].date()
    targets, events = benchmark._quarterly_static_targets(panels)
    periods = (
        ("continuous_2015_2026", date(2015, 1, 2), data_end),
        *walkforward.PERIODS,
    )
    rows = []
    for cap in CAPS:
        for slippage in COSTS:
            for period, start, end in periods:
                result = benchmark._run(
                    f"quarterly_static_50_50_{int(cap * 100):02d}pct_{period}_{slippage}bps",
                    targets, events, panels, end, start=start,
                    run_dir=RUNS / f"{int(cap * 100)}pct" / f"{slippage}bps" / period,
                    cash_distributions=benchmark.NIFTYBEES_DISTRIBUTIONS,
                    exposure_cap=cap, slippage_bps=slippage,
                )
                rows.append({
                    **result,
                    "nifty_sleeve_pct": 50,
                    "gold_sleeve_pct": 50,
                    "period": period,
                })

    assert set(targets.columns) == {"NIFTYBEES", "GOLDBEES"}
    for nifty_share, gold_share in RATIOS:
        ratio_targets = targets * 0.0
        ratio_targets["NIFTYBEES"] = nifty_share
        ratio_targets["GOLDBEES"] = gold_share
        assert (ratio_targets.sum(axis=1) - 1.0).abs().lt(1e-12).all()
        for slippage in (50, 200):
            for period, start, end in periods:
                nifty_pct, gold_pct = round(nifty_share * 100), round(gold_share * 100)
                result = benchmark._run(
                    f"quarterly_static_{nifty_pct:02d}_{gold_pct:02d}_55pct_{period}_{slippage}bps",
                    ratio_targets, events, panels, end, start=start,
                    run_dir=(
                        RUNS / "55pct" / f"{nifty_pct:02d}_{gold_pct:02d}"
                        / f"{slippage}bps" / period
                    ),
                    cash_distributions=benchmark.NIFTYBEES_DISTRIBUTIONS,
                    exposure_cap=COMPOSITION_CAP, slippage_bps=slippage,
                )
                rows.append({
                    **result,
                    "nifty_sleeve_pct": nifty_pct,
                    "gold_sleeve_pct": gold_pct,
                    "period": period,
                })

    for nifty_share, gold_share in RATIOS_60:
        ratio_targets = targets * 0.0
        ratio_targets["NIFTYBEES"] = nifty_share
        ratio_targets["GOLDBEES"] = gold_share
        assert (ratio_targets.sum(axis=1) - 1.0).abs().lt(1e-12).all()
        for slippage in (50, 200):
            for period, start, end in periods:
                nifty_pct, gold_pct = round(nifty_share * 100), round(gold_share * 100)
                result = benchmark._run(
                    f"quarterly_static_{nifty_pct:02d}_{gold_pct:02d}_60pct_{period}_{slippage}bps",
                    ratio_targets, events, panels, end, start=start,
                    run_dir=(
                        RUNS / "60pct" / f"{nifty_pct:02d}_{gold_pct:02d}"
                        / f"{slippage}bps" / period
                    ),
                    cash_distributions=benchmark.NIFTYBEES_DISTRIBUTIONS,
                    exposure_cap=0.60, slippage_bps=slippage,
                )
                rows.append({
                    **result,
                    "nifty_sleeve_pct": nifty_pct,
                    "gold_sleeve_pct": gold_pct,
                    "period": period,
                })

    table = pd.DataFrame(rows)
    expected = (
        len(CAPS) * len(COSTS) * len(periods)
        + len(RATIOS) * 2 * len(periods)
        + len(RATIOS_60) * 2 * len(periods)
    )
    assert len(table) == expected == 176
    assert not table.duplicated([
        "gross_exposure_cap_pct", "nifty_sleeve_pct", "gold_sleeve_pct",
        "slippage_bps_per_side", "period",
    ]).any()
    assert table["max_close_replay_error_inr"].max() <= 0.03
    reference = pd.read_csv(ROOT / "outputs" / "nifty_gold_common_history_benchmarks.csv")
    baseline = reference.loc[reference["strategy"].eq("quarterly_static_50_50_45pct")].iloc[0]
    actual = table.loc[
        table["gross_exposure_cap_pct"].eq(45)
        & table["slippage_bps_per_side"].eq(50)
        & table["period"].eq("continuous_2015_2026")
    ].iloc[0]
    for key, base_key in (
        ("ending_balance_inr", "ending_balance_inr"),
        ("total_fees_inr", "total_fees_inr"),
        ("total_slippage_inr", "total_slippage_inr"),
        ("ohlc_drawdown_bound_pct", "ohlc_drawdown_bound_pct"),
    ):
        # The older benchmark predates the GST-on-SEBI fee correction.
        tolerance = 0.51 if key in {"ending_balance_inr", "total_fees_inr"} else 0.03
        assert abs(float(actual[key]) - float(baseline[base_key])) <= tolerance, (key, actual[key], baseline[base_key])
    table.to_csv(OUT, index=False)

    ledger = stock.read_csv(ROOT / "outputs" / "backtest_summary.csv")
    fields = list(ledger[0])
    ledger = [
        row for row in ledger
        if row["simulation_type"] not in {
            SIM_TYPE,
            "quarterly_static_50_50_cap_cost_sensitivity",
            "quarterly_static_50_50_45pct_cost_sensitivity",
        }
    ]
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
            "gross_exposure_cap_pct": row["gross_exposure_cap_pct"],
            "slippage_bps_per_side": row["slippage_bps_per_side"],
            "fees_inr": row["total_fees_inr"],
            "slippage_cost_inr": row["total_slippage_inr"],
            "order_count": row["order_count"],
            "within_20pct": row["within_20pct_ohlc"],
            "selection_or_sizing": (
                f"Quarterly static {row['nifty_sleeve_pct']:.0f}/{row['gold_sleeve_pct']:.0f} "
                "NIFTY/Gold target; "
                f"{row['gross_exposure_cap_pct']:.0f}% aggregate cap at rebalance"
            ),
            "source_artifact": (
                "outputs/quarterly_static_mix_cost_sensitivity.csv;"
                "outputs/quarterly_static_mix_cost_method.md;"
                "work/stress_quarterly_static_mix_cost.py"
            ),
            "notes": (
                f"OHLC envelope {row['ohlc_drawdown_bound_pct']:.4f}%; current modeled fees; "
                f"{row['slippage_bps_per_side']} bps/side; cap applies at quarterly rebalances only."
            ),
        })
        ledger.append(record)
    stock.atomic_csv(ROOT / "outputs" / "backtest_summary.csv", ledger, fields)

    manifest_path = ROOT / "outputs" / "data_manifest.csv"
    manifest = stock.read_csv(manifest_path)
    manifest_fields = list(manifest[0])
    manifest_dataset = "Quarterly static NIFTY/Gold cap and composition cost sensitivity"
    manifest = [
        row for row in manifest
        if row["dataset"] not in {
            "Quarterly static NIFTY/Gold 45% cap cost stress",
            "Quarterly static NIFTY/Gold cost sensitivity",
            manifest_dataset,
        }
    ]
    manifest.append({
        "dataset": manifest_dataset,
        "ticker": "NIFTYBEES; GOLDBEES",
        "instrument_key": "NSE_EQ|INF204KB14I2; NSE_EQ|INF204KB17I5",
        "bar_interval": "daily candles; quarterly rebalance; terminal liquidation",
        "first_bar": "2015-01-02",
        "last_bar": data_end.isoformat(),
        "bar_count": "176 rows: 80 cap/cost rows, 80 ratio/cost rows at 55% cap, and 16 ratio/cost rows at 60% cap",
        "file_count": "176 exact-fee replays + CSV + runner + per-run ledgers",
        "empty_files": "0",
        "cache_paths": (
            "outputs/quarterly_static_mix_cost_sensitivity.csv;"
            "work/stress_quarterly_static_mix_cost.py;"
            "work/backtests/quarterly_static_mix_cost/"
        ),
        "purpose": "Stress quarterly NIFTY/Gold ratios at 55/60% caps plus the 45/50/55/60/65% equal-weight cap frontier at 10/50/100/200 bps per-side slippage",
        "notes": (
            "The 45%-cap 50-bps row matches the old common-window benchmark within ₹0.51 on ending NAV/fees "
            "because that file predates GST-on-SEBI correction; slippage/OHLC match within ₹0.03. "
            "The cap applies only at quarterly rebalance dates; all periods have been inspected."
        ),
    })
    for row in manifest:
        if row["dataset"] == "Consolidated backtest metric ledger":
            row["bar_count"] = str(len(ledger))
            row["notes"] = row["notes"].replace(
                "Sixteen quarterly static NIFTY/Gold 45%-cap cost-stress rows added. ",
                "",
            ).replace(
                "Eighty quarterly static NIFTY/Gold cost-stress rows added.",
                "",
            ).replace(
                "One hundred sixty quarterly static NIFTY/Gold cap/ratio cost rows added.",
                "",
            )
            phrase = "One hundred seventy-six quarterly static NIFTY/Gold cap/ratio cost rows added."
            if phrase not in row["notes"]:
                row["notes"] = row["notes"].rstrip() + " " + phrase
    stock.atomic_csv(manifest_path, manifest, manifest_fields)
    print(f"wrote {len(rows)} quarterly exposure-cost rows through {data_end}")


if __name__ == "__main__":
    main()
