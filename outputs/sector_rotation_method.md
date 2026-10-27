# Indian sector ETF rotation sensitivity

**2026-10-27 fee-model correction:** The current 384-case replay applies instrument-specific ETF STT. Results below reflect the corrected sensitivity CSV and consolidated ledger. See the [fee-model audit](../work/research/fee_model_audit.md).


**As of:** 2026-10-27  
**Upstox candle history through:** 2026-10-23  
**Account:** ₹10 lakh per run; maximum observed drawdown screen 20%

## Hypotheses and comparison set

The established sector rule is monthly 12–1 momentum: rank five sector ETFs by 252-session return ending 21 sessions before month-end, keep only positive-return ETFs above their 200-session SMA, and equal-weight the top one, two, or three. The 200-session gate and 12–1 score use only each ETF's available history; an ETF without enough history is ineligible. Signals use month-end closes and execute at the next session's open.

Controls are a monthly equal-weight basket of the same five sector ETFs and the existing 50/50 NIFTYBEES Donchian 55/20 plus GOLDBEES SMA200 strategy. An exploratory fixed mix combines 25% NIFTYBEES Donchian, 50% equal-weight sector ETFs, and 25% GOLDBEES SMA200. The mixed portfolio was added after observing the equal-weight sector result in this same history; it is post-hoc research, not a pre-registered test.

The sector universe is BANKBEES, ITBEES, AUTOBEES, PHARMABEES, and PSUBNKBEES. The five histories overlap on 1,176 daily sessions from 2022-01-25 through 2026-10-23. The account evaluation begins 2022-01-03; ETF-specific pre-inception bars remain unavailable, so later-launched funds become eligible only after their own required lookback. Since the universe contains funds that survive today and their inception dates differ, the screen has fund-survivorship and availability bias.

Each of six portfolios is replayed at 50/75/95/100% maximum gross exposure, 10/25/50/100 bps adverse slippage per side, and four flat-start periods: 2022–2023 training, 2024 validation, 2025-01-01–2026-10-23 holdout, and continuous 2022-01-03–2026-10-23. The price, target, fill, fee, and NAV calculations reuse `work/upstox_quant.py`; fees follow the current Upstox/NSE equity-delivery schedule uniformly across historical dates, with zero cash yield. There are 384 scenarios. The 2025+ window was already reviewed in the broader research and is not an untouched lockbox.

## Results at 50 bps per side

The original close-MDD training screen selected top-one sector momentum at a 75% exposure cap. With the corrected fees it returned +58.19% / -19.18% close drawdown in training, -0.95% / -19.63% in 2024, and -8.62% / -20.97% in 2025+. The continuous account returned +48.76% but reached -29.77% close drawdown, so this selected rule fails the 20% risk screen.

The post-hoc 25/50/25 NIFTY/sector/Gold mix at a 100% gross cap returned +72.92% / -12.51% close drawdown over 2022–2026, compared with +64.18% / -14.22% for the 100% NIFTY/Gold control. At 100 bps the respective full-period results were +63.48% / -12.56% and +50.15% / -16.20%. The mixed rule lagged the control in 2025+: +17.05% versus +32.24% at 50 bps and +14.37% versus +28.13% at 100 bps. This is a post-hoc mix, and the full-period gain does not establish a durable advantage.

The sector-only equal-weight control returned +81.67% / -17.08% close drawdown at 50 bps and 100% exposure, but gained only +3.66% in 2025+. The price-signal top-three momentum rule at 75% returned +41.16% continuously; order-by-order risk re-marking puts its conservative OHLC bound at -19.67%, while its 2025+ return was -16.37% and the bound was -19.25%. It has little room under the 20% screen and loses in the holdout.

## Risk-aware training selection and official-TRI signal challenger

The same three top-N price-signal rules were screened using the conservative daily high-before-low OHLC bound, not close drawdown alone. At 50 bps, top-three at 75% was the training choice (+37.43%, -18.75% OHLC). It returned +17.46% / -9.59% in 2024, then -16.37% / -19.25% in 2025+, and +41.16% / -19.67% continuously. The full run passes the historical bound by only 0.33 percentage points; the later return is negative. See `outputs/sector_rotation_ohlc_audit.csv` and `outputs/sector_rotation_ohlc_training_selection.json`.

The 2014–2026 official sector TRI histories supply a complete signal warm-up before the ETFs' common live history. The separate 144-case challenger uses those TRI values for 12–1 momentum and a 200-session trend gate, but uses Upstox ETF market prices for fills and NAV. Its 50-bps training selector picked top-two at 75% (+42.37%, -17.22% OHLC); the 2025+ return was -15.49% / -19.23% OHLC, and the continuous OHLC bound was -22.86%, so the selected path fails the full-period limit. Matching top-three at 75% returned +45.96% continuously with a -19.90% bound, only 0.10 percentage points of headroom; it lost 15.37% in 2025+ with a -19.93% bound. At 50% exposure, TRI top-three returned +29.80% with a -13.54% full bound and lost 10.16% in 2025+. The signal-source improvement is small relative to the sample and risk limits; it does not establish a winner. See [TRI signal methods/results](sector_tri_signal_momentum_method.md), [selection](sector_tri_signal_momentum_selection.json), and [primary distribution-source update](../work/research/sector_distribution_primary_source_update_2026-10-27.md).

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

The original 384-case signal and all strategy NAV series use saved Upstox ETF market-price candles; the separate 144-case challenger uses official sector TRI only for signal ranking and still books ETF market-price P&L. Neither is a complete ETF total-return reconstruction. Official sector PR/TR and AMFI scheme NAV histories are available for cross-checking, but the AMFI NAV window begins in Apr 2023, has date mismatches, and is not itself proof of reinvested ETF distributions. NTR is unavailable and the actual ETF action ledger remains incomplete. Primary checks still do not confirm secondary claims of ₹10.50 AUTOBEES cash on 2026-06-09 or ₹6.50 PHARMABEES cash on 2026-06-11; the base P&L omits both. See the [sector source memo](sector_rotation_primary_sources.md) and [distribution-source update](../work/research/sector_distribution_primary_source_update_2026-10-27.md). The BANKBEES action row in the older audit was corrected: NSE reports ₹11/unit in 2014 and ₹13/unit in 2015; the ₹7/₹8 figures belong to NIFTYBEES. Those BANKBEES events predate the 2022 test.

The 50-bps sector grids have order-ledger OHLC audits; their same-day high-before-low envelopes are conservative but can still understate gaps, slippage, and execution failures. The 10/25/100-bps rows use close drawdown only. Fixed slippage is a stress assumption, not measured historical bid/ask spread. The 20% historical screen is not a future loss limit. Before promoting any portfolio, reconcile official ETF distributions against sector TRI histories, save reproducible AMC/AMFI records through the data end, and freeze the candidate for new forward-paper observations.

## Reproducibility

- Sensitivity output: `outputs/sector_rotation_sensitivity.csv`.
- Training-only selection record: `outputs/sector_rotation_training_selection.json`.
- Training selection after the 50-bps OHLC screen: `outputs/sector_rotation_ohlc_training_selection.json`.
- 50-bps price-signal OHLC audit: `outputs/sector_rotation_ohlc_audit.csv`; reproduction: `work/audit_sector_rotation_ohlc.py` and `work/select_sector_rotation_ohlc.py`.
- Official-TRI signal challenger outputs and reproduction: `outputs/sector_tri_signal_momentum_sensitivity.csv`, `outputs/sector_tri_signal_momentum_ohlc_audit.csv`, `outputs/sector_tri_signal_momentum_selection.json`, and `work/sensitivity_sector_tri_signal.py`.
- Runner and assert-based data/target checks: `work/sensitivity_sector_rotation.py`.
- Official Nifty sector PR/TR source capture and alignment: `work/data/index_daily/sector_price_index_raw_2022_2026.json`, `work/data/index_daily/sector_tri_raw_2022_2026.json`, and `work/normalize_sector_index_history.py`.
- Official AMFI ETF NAV capture and comparison: `work/data/api_probes/amfi_sector_etf_nav_2023_2026.json`, `work/capture_amfi_sector_etf_nav.py`, `outputs/sector_etf_nav_price_tri_comparison.csv`, and `work/data/index_daily/sector_etf_nav_price_tri_panel_2023_2026.csv`.
- Price-index/TRI comparison rows and aligned daily panel: `outputs/sector_etf_index_total_return_comparison.csv` and `work/data/index_daily/sector_etf_price_pr_tri_panel_2022_2026.csv`.
- Per-run equity, order, and summary files: `work/backtests/sector_rotation/`.
- Fee sources and event correction: `outputs/sector_rotation_primary_sources.md` and `outputs/sector_etf_corporate_action_audit.csv`.
