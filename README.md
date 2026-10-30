# Indian Market Quant Research

Research and backtests for Indian index, sector, stock, ETF, derivatives, swing, and intraday strategies using Upstox history plus official NSE/AMFI cross-checks.

## Research status

The account reference is ₹10 lakh with a 20% peak-to-trough risk screen. No strategy is established as a reliable winner. The latest report compares strategy families, realistic modeled fees and slippage, chronological holdouts, and drawdown limits: [quant research report](outputs/quant_research_report.md).

The 2026 primary-source [ETF delivery fee audit](work/research/cash_etf_delivery_cost_sources_2026-10-30.md) led to a correction: the shared helper now includes GST on SEBI turnover fees, and the passive-control tables and bootstraps were regenerated. A scan of 2,637 stored order ledgers suggests prior fee totals may be low by at most ₹41.34 per ledger; those include many overlapping parameter scenarios, and not every strategy output has been regenerated. Slippage and spread remain assumed, not measured.

The monthly NIFTYBEES Donchian 55/20 + GOLDBEES 200DMA blend is under prospective paper observation at several frozen settings. Its selected 95% exposure setting returned +63.69% on the inspected 2023–2026 holdout at 50 bps per-side slippage and passed the conservative daily OHLC envelope at -16.28%; the same rule failed the 2020+ envelope at -24.41%. It is a challenger, not a validated winner. See the [OHLC audit](outputs/etf_daily_timestamp_and_intraday_risk_audit.md) and [paper protocol](outputs/forward_paper_plan.md).

At assumed 200 bps per-side slippage, the passive 30% initial equal mix returned +83.78% over 2015–2026 with a -14.66% historical OHLC bound. Its paired-OHLC bootstrap estimated 3.18% 10-year envelope-breach probability at 63-session blocks and a -19.06% fifth-percentile bound. A 20% initial 30/70 NIFTY/Gold mix returned +62.21% historically with a -13.96% OHLC bound; its 126-session bootstrap had a -16.80% fifth percentile and 0.92% estimated envelope-breach rate. A 25% 30/70 mix returned +77.77% but its 126-session estimate was 2.78%; at 30%, return rose to +93.33% but the fifth percentile crossed -20%. The higher-return 45% 30/70 anchor returned +140.01% historically, but had only 0.02 percentage points of historical OHLC headroom and a 23.72% 63-session bootstrap breach estimate, so it fails the coarse 20% risk screen. The equal-mix 30% allocation drifted to 67% peak exposure; it is an initial holding, not a maintained cap. The 8% throttle earned more (+130.01%) but had an 11.74% breach estimate and -21.18% fifth-percentile bound. Costs are assumed and the resampling is conditional on inspected history, so all candidates remain paper-only. See the [walk-forward and 200-bps stress](outputs/passive_drawdown_control_walkforward_method.md), [composition stress](outputs/passive_mix_composition_cost_method.md), and [stateful bootstrap](outputs/stateful_drawdown_control_bootstrap_method.md).

The corrected cross-asset ETF 12–1 momentum replay selected 45% exposure at 50 bps. A strength-weighted variant returned +22.51% with a -16.24% OHLC envelope on the already-inspected 2023–2026 segment; under assumed 100/150/200-bps per-side costs, selected caps fell to 35/30/25% and pseudo-holdout returns to +12.51/+6.80/+2.56%. Its conditional 63-session block bootstrap estimated a 41.98% 10-year 20% drawdown breach rate at 50 bps. These are paper candidates, not validated winners; see the [equal-weight audit](outputs/cross_asset_momentum_ohlc_method.md), [strength-weighted audit](outputs/cross_asset_momentum_strength_method.md), and [inverse-vol comparison](outputs/cross_asset_inverse_vol_method.md), which supersede the older ETF-unit STT results.

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

The expired-option preflight found empty contract lists at six sampled 2022–2023 NIFTY monthly expiries, so the frozen intraday-options training window still fails its data gate. It saves contract counts and local raw responses; no option strategy P&L is claimed from these probes. Official NSE EOD contract records may support a separate daily-mark options screen, but they cannot validate intraday fills; see the [historical options source review](work/research/nifty_historical_options_source_fallback.md).

For live candle refreshes, `work/upstox_quant.py` reads `UPSTOX_ANALYTICS_TOKEN` from the process environment or the current user's `HKCU\Environment` registry value. Keep the token out of source files, logs, commits, and issue reports. The forward-paper runner is read-only and never sends broker orders.

## Data and repository contents

This is a public repository. Raw Upstox/market-data caches, API probe responses, and most per-run equity/order histories are kept out of Git; they remain in the local `work/data/` and `work/backtests/` directories. `outputs/data_manifest.csv` records their local source paths and coverage. The repository tracks code, methods, aggregate results, frozen paper configurations, and the two OHLC-audited holdout ledgers. Reproducing the full results requires obtaining and placing the source data locally according to the manifest.

Historical results use modeled current fees and stated slippage, zero cash yield in most ETF simulations, and next-open fills. Historical drawdown screens and resampled return stresses are not guarantees of future loss limits. No live orders are placed by this research project.
