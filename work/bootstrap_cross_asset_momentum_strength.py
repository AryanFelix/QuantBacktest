"""Stationary-bootstrap drawdown stress for cost-specific ETF momentum paths."""

from pathlib import Path

import pandas as pd

import bootstrap_etf_drawdown_risk as bootstrap


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs" / "cross_asset_momentum_strength_block_bootstrap.csv"
CASES = [
    (50, 45, "work/backtests/cross_asset_momentum_strength_weighted/full_2014_2026__cap45/equity.csv"),
    (100, 35, "work/backtests/cross_asset_momentum_strength_100bps/full_2014_2026__cap35/equity.csv"),
    (150, 30, "work/backtests/cross_asset_momentum_strength_150bps/full_2014_2026__cap30/equity.csv"),
    (200, 25, "work/backtests/cross_asset_momentum_strength_200bps/full_2014_2026__cap25/equity.csv"),
]


def main() -> None:
    bootstrap.check_sampler()
    rows = []
    for case_number, (slippage, cap, path) in enumerate(CASES):
        returns, start = bootstrap.load_returns(path)
        for block_number, mean_block in enumerate(bootstrap.BLOCK_LENGTHS):
            results = bootstrap.simulate(
                returns,
                bootstrap.SEED + 500_000 + case_number * 100_000 + block_number * 10_000,
                mean_block,
            )
            for horizon, metrics in results.items():
                rows.append({
                    "strategy": "Cross-asset ETF momentum-strength",
                    "slippage_bps_per_side": slippage,
                    "gross_exposure_cap_pct": cap,
                    "bootstrap_start": start,
                    "history_observations": len(returns),
                    "mean_block_sessions": mean_block,
                    "simulations": bootstrap.SIMULATIONS,
                    "horizon": horizon,
                    **metrics,
                    "source_equity": path,
                })
    table = pd.DataFrame(rows)
    assert len(table) == len(CASES) * len(bootstrap.BLOCK_LENGTHS) * len(bootstrap.HORIZONS)
    assert table["probability_drawdown_below_20pct"].between(0, 100).all()
    assert table["p05_max_drawdown_pct"].le(table["median_max_drawdown_pct"]).all()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    table.to_csv(OUT, index=False)
    print(f"wrote {len(table)} bootstrap summaries to {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
