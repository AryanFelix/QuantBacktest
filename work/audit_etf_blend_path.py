"""Summarize annual and rolling returns for continuous ETF blend paths."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
RUNS = ROOT / "work" / "backtests" / "volatility_weighted_blend"
OUT = ROOT / "outputs"
CAPITAL = 1_000_000.0
PORTFOLIOS = (
    "fixed_50_50", "inverse_vol_63d",
    "fixed_50_50_quarterly", "inverse_vol_63d_quarterly",
)
SLIPPAGE = (10, 50)


def main() -> None:
    paths, annual = [], []
    for portfolio in PORTFOLIOS:
        for slip in SLIPPAGE:
            key = f"{portfolio}__full_2014_plus__{slip}bps"
            equity = pd.read_csv(RUNS / key / "equity.csv", parse_dates=["time"]).set_index("time")
            nav = equity["nav"].astype(float)
            assert nav.index.is_unique and nav.index.is_monotonic_increasing
            full_nav = pd.concat([pd.Series([CAPITAL]), nav.reset_index(drop=True)], ignore_index=True)
            running_peak = full_nav.cummax()
            drawdown = full_nav / running_peak - 1
            trough_pos = int(drawdown.argmin())
            peak_pos = int(full_nav.iloc[:trough_pos + 1].argmax())
            peak_value = float(full_nav.iloc[peak_pos])
            recovered = bool((full_nav.iloc[trough_pos + 1:] >= peak_value).any())
            rolling = nav.pct_change(252).dropna()
            current_dd = float(full_nav.iloc[-1] / running_peak.iloc[-1] - 1)
            last_peak_pos = int(np.flatnonzero((full_nav == running_peak).to_numpy())[-1])
            summary = pd.read_csv(OUT / "volatility_weighted_blend_screen.csv")
            source = summary[(summary.portfolio == portfolio) & (summary.period == "full_2014_plus") & (summary.slippage_bps_per_side == slip)].iloc[0]
            assert abs(float(drawdown.min() * 100) - float(source.max_drawdown_pct)) < 1e-8
            paths.append({
                "portfolio": portfolio,
                "slippage_bps_per_side": slip,
                "start_date": nav.index[0].date().isoformat(),
                "end_date": nav.index[-1].date().isoformat(),
                "ending_balance_inr": float(nav.iloc[-1]),
                "total_return_pct": float(source.total_return_pct),
                "cagr_pct": float(source.cagr_pct),
                "max_drawdown_pct": float(drawdown.min() * 100),
                "max_drawdown_peak": "capital_before_first_close" if peak_pos == 0 else nav.index[peak_pos - 1].date().isoformat(),
                "max_drawdown_trough": "capital_before_first_close" if trough_pos == 0 else nav.index[trough_pos - 1].date().isoformat(),
                "max_drawdown_recovered_by_end": recovered,
                "current_drawdown_pct": current_dd * 100,
                "sessions_since_last_high": len(full_nav) - 1 - last_peak_pos,
                "rolling_252_session_windows": int(len(rolling)),
                "rolling_252_positive_pct": float((rolling > 0).mean() * 100),
                "rolling_252_p05_pct": float(rolling.quantile(0.05) * 100),
                "rolling_252_median_pct": float(rolling.median() * 100),
                "rolling_252_worst_pct": float(rolling.min() * 100),
                "rolling_252_worst_end": rolling.idxmin().date().isoformat(),
            })
            year_end = nav.groupby(nav.index.year).last()
            previous = CAPITAL
            for year, value in year_end.items():
                annual.append({
                    "portfolio": portfolio,
                    "slippage_bps_per_side": slip,
                    "year": int(year),
                    "return_pct": (float(value) / previous - 1) * 100,
                    "year_end_nav_inr": float(value),
                    "partial_year": year == nav.index[-1].year and nav.index[-1].month < 12,
                })
                previous = float(value)

    assert len(paths) == 8 and len(annual) >= 8
    audit = pd.DataFrame(paths)
    assert audit["max_drawdown_pct"].ge(-20).all()
    audit.to_csv(OUT / "etf_blend_path_audit.csv", index=False)
    pd.DataFrame(annual).to_csv(OUT / "etf_blend_annual_returns.csv", index=False)
    print(f"Wrote {len(paths)} path summaries and {len(annual)} annual rows; drawdown reconciliation passed.")


if __name__ == "__main__":
    main()
