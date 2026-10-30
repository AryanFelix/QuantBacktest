"""Conditionally bootstrap quarterly static-mix net returns at 50/200 bps."""

from pathlib import Path

import pandas as pd

import bootstrap_etf_drawdown_risk as bootstrap

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs" / "quarterly_static_mix_cost_bootstrap.csv"
CAPS = (45, 50, 55, 60, 65)
COSTS = (50, 200)
RATIOS = tuple((nifty, 100 - nifty) for nifty in range(0, 101, 10) if nifty != 50)
RATIOS_60 = ((30, 70), (40, 60))


def main() -> None:
    bootstrap.check_sampler()
    rows = []
    cases = [
        (
            cap, 50, 50, cost,
            f"work/backtests/quarterly_static_mix_cost/{cap}pct/{cost}bps/"
            "continuous_2015_2026/"
            f"quarterly_static_50_50_{cap:02d}pct_continuous_2015_2026_{cost}bps/equity.csv",
        )
        for cap in CAPS for cost in COSTS
    ]
    cases.extend(
        (
            55, nifty, gold, cost,
            f"work/backtests/quarterly_static_mix_cost/55pct/{nifty:02d}_{gold:02d}/{cost}bps/"
            "continuous_2015_2026/"
            f"quarterly_static_{nifty:02d}_{gold:02d}_55pct_continuous_2015_2026_{cost}bps/equity.csv",
        )
        for nifty, gold in RATIOS for cost in COSTS
    )
    cases.extend(
        (
            60, nifty, gold, cost,
            f"work/backtests/quarterly_static_mix_cost/60pct/{nifty:02d}_{gold:02d}/{cost}bps/"
            "continuous_2015_2026/"
            f"quarterly_static_{nifty:02d}_{gold:02d}_60pct_continuous_2015_2026_{cost}bps/equity.csv",
        )
        for nifty, gold in RATIOS_60 for cost in COSTS
    )
    assert len(cases) == 34
    for cap, nifty, gold, cost, path in cases:
        returns, start = bootstrap.load_returns(path)
        for block_number, mean_block in enumerate(bootstrap.BLOCK_LENGTHS):
            seed = bootstrap.SEED + 5_000_000 + block_number * 10_000
            results = bootstrap.simulate(returns, seed, mean_block)
            for horizon, metrics in results.items():
                rows.append({
                    "strategy": f"quarterly static {nifty}/{gold} NIFTY/Gold; {cap}% cap",
                    "gross_exposure_cap_pct": cap,
                    "nifty_sleeve_pct": nifty,
                    "gold_sleeve_pct": gold,
                    "slippage_bps_per_side": cost,
                    "bootstrap_start": start,
                    "history_observations": len(returns),
                    "mean_block_sessions": mean_block,
                    "simulations": bootstrap.SIMULATIONS,
                    "horizon": horizon,
                    **metrics,
                    "source_equity": path,
                })
    table = pd.DataFrame(rows)
    assert len(table) == len(cases) * len(bootstrap.BLOCK_LENGTHS) * len(bootstrap.HORIZONS) == 408
    assert not table.duplicated([
        "gross_exposure_cap_pct", "nifty_sleeve_pct", "gold_sleeve_pct",
        "slippage_bps_per_side", "mean_block_sessions", "horizon",
    ]).any()
    assert table["probability_drawdown_below_20pct"].between(0, 100).all()
    assert table["median_ending_balance_inr"].gt(0).all()
    table.to_csv(OUT, index=False)
    manifest_path = ROOT / "outputs" / "data_manifest.csv"
    manifest = pd.read_csv(manifest_path, dtype=str).fillna("")
    dataset = "Quarterly static NIFTY/Gold cost bootstrap"
    manifest = manifest.loc[manifest["dataset"].ne(dataset)]
    manifest.loc[len(manifest)] = {
        "dataset": dataset,
        "ticker": "NIFTYBEES; GOLDBEES",
        "instrument_key": "NSE_EQ|INF204KB14I2; NSE_EQ|INF204KB17I5",
        "bar_interval": "daily net returns; stationary-block bootstrap; 21/63/126-session mean blocks; 1/3/5/10-year horizons",
        "first_bar": "2015-01-02",
        "last_bar": "2026-10-23",
        "bar_count": "408 summaries; 34 cap/ratio/cost cases x 3 block lengths x 4 horizons; 5,000 paths per case",
        "file_count": "summary CSV + runner; source equity ledgers are local",
        "empty_files": "0",
        "cache_paths": "outputs/quarterly_static_mix_cost_bootstrap.csv;work/bootstrap_quarterly_static_mix_cost.py;work/backtests/quarterly_static_mix_cost/",
        "purpose": "Estimate conditional drawdown risk for equal NIFTY/Gold targets at five caps, ten ratios at 55%, and two Gold-weighted ratios at 60%, using 50/200 bps per-side slippage",
        "notes": "Stationary bootstrap resamples inspected daily net returns with modeled costs; it does not rebuild position or OHLC paths and cannot guarantee a 20% future loss limit.",
    }
    manifest.to_csv(manifest_path, index=False)
    print(f"wrote {len(table)} return-block bootstrap summaries")


if __name__ == "__main__":
    main()
