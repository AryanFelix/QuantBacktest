# Indian sector ETF rotation sensitivity

**2026-10-27 fee-model correction:** This static result snapshot predates the instrument-specific ETF STT replay. Use the current sensitivity CSV and consolidated ledger for numeric results; older figures below are superseded where they differ. See the [fee-model audit](../work/research/fee_model_audit.md).


**As of:** 2026-10-27  
**Upstox candle history through:** 2026-10-23  
**Account:** ₹10 lakh per run; maximum observed drawdown screen 20%

## Hypotheses and comparison set

The established sector rule is monthly 12–1 momentum: rank five sector ETFs by 252-session return ending 21 sessions before month-end, keep only positive-return ETFs above their 200-session SMA, and equal-weight the top one, two, or three. The 200-session gate and 12–1 score use only each ETF's available history; an ETF without enough history is ineligible. Signals use month-end closes and execute at the next session's open.

Controls are a monthly equal-weight basket of the same five sector ETFs and the existing 50/50 NIFTYBEES Donchian 55/20 plus GOLDBEES SMA200 strategy. An exploratory fixed mix combines 25% NIFTYBEES Donchian, 50% equal-weight sector ETFs, and 25% GOLDBEES SMA200. The mixed portfolio was added after observing the equal-weight sector result in this same history; it is post-hoc research, not a pre-registered test.

The sector universe is BANKBEES, ITBEES, AUTOBEES, PHARMABEES, and PSUBNKBEES. The five histories overlap on 1,176 daily sessions from 2022-01-25 through 2026-10-23. The account evaluation begins 2022-01-03; ETF-specific pre-inception bars remain unavailable, so later-launched funds become eligible only after their own required lookback. Since the universe contains funds that survive today and their inception dates differ, the screen has fund-survivorship and availability bias.

Each of six portfolios is replayed at 50/75/95/100% maximum gross exposure, 10/25/50/100 bps adverse slippage per side, and four flat-start periods: 2022–2023 training, 2024 validation, 2025-01-01–2026-10-23 holdout, and continuous 2022-01-03–2026-10-23. The price, target, fill, fee, and NAV calculations reuse `work/upstox_quant.py`; fees follow the current Upstox/NSE equity-delivery schedule uniformly across historical dates, with zero cash yield. There are 384 scenarios. The 2025+ window was already reviewed in the broader research and is not an untouched lockbox.

## Results at 50 bps per side

The training-only screen selected the top-one sector momentum rule at a 75% exposure cap, because it had the highest training CAGR among rows with training drawdown no worse than 20%. It returned +56.97% / -19.31% in training, then -1.55% / -19.75% in 2024, and -9.99% / -21.50% in 2025+. The continuous account returned +44.97% and reached -30.20% close-marked drawdown. This selection fails the later drawdown screen and is rejected.

The post-hoc 25/50/25 NIFTY/sector/Gold mix at a 100% gross cap returned +71.02% with -12.52% maximum drawdown over 2022–2026, compared with +61.26% / -14.62% for the 100% NIFTY/Gold control. At 100 bps the respective full-period results were +61.62% / -12.57% and +47.50% / -16.58%. The mixed rule lagged the control in 2025+: +16.51% versus +31.41% at 50 bps, while drawdown was lower (-12.53% versus -14.63%). The apparent full-period improvement is therefore concentrated earlier in the sample.

The sector-only equal-weight control returned +80.98% / -17.11% at 50 bps and 100% exposure, but gained only +3.37% in 2025+. The top-three momentum rule at 75% exposure returned +38.34% / -19.99% continuously, then lost 17.33% in 2025+. It uses almost all the requested drawdown budget. Neither standalone rotation nor the mixed portfolio is a validated winner; the mixed portfolio is a candidate for prospective paper comparison only after return-data checks.

## Official sector index return cross-check

On 2026-10-27, daily official Nifty Bank, Nifty IT, Nifty Auto, Nifty Pharma, and Nifty PSU Bank price-index and total-return-index (TRI) values were retrieved from NSE Indices' [historical-data report](https://www.niftyindices.com/reports/historical-data). The report's first-party JavaScript calls page-backed routes `/BackPage/getHistoricaldatatabletoString` and `/BackPage/getTotalReturnIndexString`, with a 365-day maximum query window; five yearly chunks were used for each index. This is an observed website interface, not a documented/stable API contract. Raw responses are saved in `work/data/index_daily/sector_price_index_raw_2022_2026.json` and `work/data/index_daily/sector_tri_raw_2022_2026.json`.

All five price-index and TRI series contain the same 1,176 dates as their matching Upstox ETF close series, from 2022-01-25 through 2026-10-23. The returned NTR field is `-` on every sector row, so this comparison uses gross TRI only. From the first common close to the final close, the ETF market-price return was below the sector gross TRI by 1.61–7.79 percentage points; the TR-minus-price-index spread was 5.85–15.50 points. These are close-to-close source comparisons before ETF transaction costs. The ETF-minus-TRI gap also reflects management expenses, tracking difference, and ETF market-price deviations; it is not an exact estimate of the holder's cash distribution or tracking error.

| ETF | ETF close return | Sector price-index return | Sector TRI return | TRI less price index | ETF less TRI |
|---|---:|---:|---:|---:|---:|
| BANKBEES | +47.41% | +43.97% | +49.82% | +5.85 pp | -2.41 pp |
| ITBEES | +0.06% | -7.81% | +1.66% | +9.48 pp | -1.61 pp |
| AUTOBEES | +121.47% | +115.77% | +125.87% | +10.10 pp | -4.40 pp |
| PHARMABEES | +97.03% | +93.47% | +100.57% | +7.10 pp | -3.54 pp |
| PSUBNKBEES | +199.37% | +191.67% | +207.16% | +15.50 pp | -7.79 pp |

Over the inspected 2025-01-01–2026-10-23 segment, ETF close returns were -23.46% to +23.89%; the corresponding sector TRI returns were -23.15% to +25.02%. ETF-minus-TRI gaps ranged from -0.32 to -1.13 pp in that segment. The full period and recent segment are already inspected; neither is a fresh lockbox. These index series improve the benchmark but do not replace the missing ETF cash-distribution ledger or make ETF backtest NAV total-return complete. Exact comparison rows are in `outputs/sector_etf_index_total_return_comparison.csv`; the aligned daily panel is in `work/data/index_daily/sector_etf_price_pr_tri_panel_2022_2026.csv`.

## Official ETF NAV cross-check

AMFI's [NAV Download page](https://www.amfiindia.com/net-asset-value/nav-download) permits at most 90 days per history request. Fifteen first-party requests cover 1 Apr 2023 through 23 Oct 2026 for the five Nippon ETF ISINs. Requests for dates before 1 Apr 2023 redirect to the page, so the official NAV check does not cover the 2022 portion of the strategy sample. Each scheme has 880 reported NAV dates and 877 exact dates shared with ETF closes and sector indexes. Five market dates have no matching NAV; three NAV-only dates occur at quarter ends. The saved capture lists every exception, and the comparison uses the shared-date intersection without interpolation.

| ETF | NAV / sector TRI return, Apr 2023–Oct 2026 | NAV / sector TRI return, 2025–Oct 2026 | NAV max drawdown, Apr 2023–Oct 2026 |
|---|---:|---:|---:|
| BANKBEES | +36.27% / +37.30% | +7.41% / +7.87% | -18.35% |
| ITBEES | +19.59% / +20.60% | -23.46% / -23.15% | -42.17% |
| AUTOBEES | +104.98% / +107.02% | +8.99% / +9.56% | -28.25% |
| PHARMABEES | +113.29% / +115.24% | +8.92% / +9.37% | -16.55% |
| PSUBNKBEES | +116.81% / +121.13% | +23.76% / +25.02% | -29.75% |

These are unlevered, no-fee NAV and index comparisons, not a cash-distribution-adjusted ETF total-return backtest. Three sector ETFs exceeded the user's 20% historical drawdown screen on their own over the NAV window; the full portfolio screen remains separate. The capture, aligned panel, return table, and reproduction script are `work/data/api_probes/amfi_sector_etf_nav_2023_2026.json`, `work/data/index_daily/sector_etf_nav_price_tri_panel_2023_2026.csv`, `outputs/sector_etf_nav_price_tri_comparison.csv`, and `work/capture_amfi_sector_etf_nav.py`.

## Data and risk limitations

All signal and portfolio-return series in the 384-case strategy screen use saved Upstox ETF market-price candles; they are not official total-return series. Official sector PR/TR and AMFI scheme NAV histories are now available for cross-checking, but the AMFI NAV window begins in Apr 2023, has date mismatches, and is not itself proof of reinvested ETF distributions. NTR is unavailable and the actual ETF action ledger remains incomplete: Upstox's exact-ISIN action calls and AMFI's selected event queries returned empty records, with no completeness guarantee. The [primary-source memo](sector_rotation_primary_sources.md) documents the source limits. The BANKBEES action row in the older sector audit was corrected there: NSE reports ₹11/unit in 2014 and ₹13/unit in 2015; the ₹7/₹8 figures belong to NIFTYBEES. These BANKBEES events predate the 2022 test and did not change its returns.

Maximum drawdown uses daily closing NAV and can understate intraday losses. Fixed slippage is a stress assumption, not measured historical bid/ask spread. The 20% historical screen is not a future loss limit. Before promoting the mixed portfolio, reconcile official ETF distributions against these sector TRI histories, save reproducible AMC/AMFI records through the data end, and freeze it for new forward-paper observations.

## Reproducibility

- Sensitivity output: `outputs/sector_rotation_sensitivity.csv`.
- Training-only selection record: `outputs/sector_rotation_training_selection.json`.
- Runner and assert-based data/target checks: `work/sensitivity_sector_rotation.py`.
- Official Nifty sector PR/TR source capture and alignment: `work/data/index_daily/sector_price_index_raw_2022_2026.json`, `work/data/index_daily/sector_tri_raw_2022_2026.json`, and `work/normalize_sector_index_history.py`.
- Official AMFI ETF NAV capture and comparison: `work/data/api_probes/amfi_sector_etf_nav_2023_2026.json`, `work/capture_amfi_sector_etf_nav.py`, `outputs/sector_etf_nav_price_tri_comparison.csv`, and `work/data/index_daily/sector_etf_nav_price_tri_panel_2023_2026.csv`.
- Price-index/TRI comparison rows and aligned daily panel: `outputs/sector_etf_index_total_return_comparison.csv` and `work/data/index_daily/sector_etf_price_pr_tri_panel_2022_2026.csv`.
- Per-run equity, order, and summary files: `work/backtests/sector_rotation/`.
- Fee sources and event correction: `outputs/sector_rotation_primary_sources.md` and `outputs/sector_etf_corporate_action_audit.csv`.
