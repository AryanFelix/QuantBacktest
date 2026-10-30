# Indian Market Quant Research

Research and backtests for Indian index, sector, stock, ETF, derivatives, swing, and intraday strategies using Upstox history plus official NSE/AMFI cross-checks.

## Research status

The account reference is ₹10 lakh with a 20% peak-to-trough risk screen. No strategy is established as a reliable winner. The latest report compares strategy families, realistic modeled fees and slippage, chronological holdouts, and drawdown limits: [quant research report](outputs/quant_research_report.md).

The monthly NIFTYBEES Donchian 55/20 + GOLDBEES 200DMA blend is under prospective paper observation at several frozen settings. Its selected 95% exposure setting returned +63.69% on the inspected 2023–2026 holdout at 50 bps per-side slippage and passed the conservative daily OHLC envelope at -16.28%; the same rule failed the 2020+ envelope at -24.41%. It is a challenger, not a validated winner. See the [OHLC audit](outputs/etf_daily_timestamp_and_intraday_risk_audit.md) and [paper protocol](outputs/forward_paper_plan.md).

## Reproducing the main research

The scripts are under `work/`; summary tables and methods are under `outputs/`.

```powershell
python work/replay_donchian_gold_blend.py
python work/audit_etf_intraday_drawdown.py
python work/refresh_backtest_summary.py
python work/capture_amfi_goldman_etf_nav.py
python work/capture_amfi_liquidbees_nav.py
python work/probe_nifty_expired_option_coverage.py
```

The AMFI/Nippon capture verifies the NIFTYBEES/GOLDBEES historical NAV lineage and split-normalized price basis. Its public aggregate is `outputs/etf_nav_market_close_reconciliation.csv`; raw NAV responses are ignored under `work/data/api_probes/`.

The separate LIQUIDBEES capture records official AMFI daily-IDCW payout NAVs from 2019 through 2026. Those NAVs stay near ₹1,000 and are not total returns; cash yield remains excluded until the issuer dividend feed reconciles to reported reinvestment performance. See `work/research/liquidbees_nav_source_review.md` and `outputs/liquidbees_amfi_nav_2019_2026.csv`.

The expired-option preflight found empty contract lists at six sampled 2022–2023 NIFTY monthly expiries, so the frozen intraday-options training window still fails its data gate. It saves contract counts and local raw responses; no option strategy P&L is claimed from these probes.

For live candle refreshes, `work/upstox_quant.py` reads `UPSTOX_ANALYTICS_TOKEN` from the process environment or the current user's `HKCU\Environment` registry value. Keep the token out of source files, logs, commits, and issue reports. The forward-paper runner is read-only and never sends broker orders.

## Data and repository contents

This is a public repository. Raw Upstox/market-data caches, API probe responses, and most per-run equity/order histories are kept out of Git; they remain in the local `work/data/` and `work/backtests/` directories. `outputs/data_manifest.csv` records their local source paths and coverage. The repository tracks code, methods, aggregate results, frozen paper configurations, and the two OHLC-audited holdout ledgers. Reproducing the full results requires obtaining and placing the source data locally according to the manifest.

Historical results use modeled current fees and stated slippage, zero cash yield in most ETF simulations, and next-open fills. Historical drawdown screens and resampled return stresses are not guarantees of future loss limits. No live orders are placed by this research project.
