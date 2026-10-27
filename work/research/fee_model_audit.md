# Upstox fee-model audit

**Checked:** 2026-10-27  
**Capital case:** ₹10,00,000  
**Drawdown screen:** 20%

## Finding and correction

The shared fee calculator and the separate NIFTY futures calculator used a SEBI turnover-fee rate of `notional × 0.0000001`, which is ₹1 per crore. Upstox and NSE publish SEBI fees at ₹10 per crore, so the rate is `notional × 0.000001`. Both calculators and their assert-based checks now use the published amount.

The outputs in that SEBI-only pass understated the SEBI component by ₹9 per crore of turnover. The official fee schedule does not include SEBI fees in the GST base, so there is no additional GST effect from that correction; its then-current main results rounded to the same headline returns and drawdowns. The separate ETF-unit STT issue below was found later and supersedes those earlier ETF numbers.

## ETF-unit STT correction — 2026-10-27

A second audit found that the shared ETF simulations had charged the equity-share delivery STT rate to every ETF unit. NSE's published schedule distinguishes equity shares from equity-oriented-fund units: equity shares incur 0.1% on both delivery sides, equity-oriented-fund units incur nil on purchases and 0.001% on sales, and an intraday sale of an equity-oriented-fund unit is 0.025%. AMFI states STT applies only to sales/redemptions of equity-oriented-fund units, not other schemes; its tax guidance classifies Gold ETFs as non-equity/specified funds. The corrected model therefore charges GOLDBEES and LIQUIDBEES no STT, and uses the equity-fund rates for the equity-oriented ETFs in `FUND_FEE_PRODUCTS`. Stock-share and futures/options rates are unchanged by this correction.

The shared calculator, ETF symbol classification, CLI paths, and direct ETF backtest callers now carry the fund-unit fee product into each trade. Assert-based checks cover share delivery, equity-fund delivery, non-equity-fund delivery, and both intraday fund cases. Integer holdings were recalculated, so this is a full portfolio replay rather than a fee subtraction from old results.

All saved ETF-dependent screens were regenerated from the existing Upstox/NSE data cache: the 40-case ETF blend, 105 ETF parameter, 140 single-sleeve, 130 joint exposure/volatility, 60 volatility-target, 125 cost-stress, 90 India-VIX overlay, 20 OHLC exposure, eight OHLC audit, 384 sector rotation, 48 ETF composite, 108 RSI, 144 gap-fade, 64 ORB-range, 18 Donchian/Gold, 36 training-selection replay, 12 dual-momentum, and 108 bootstrap cases (including the passive NIFTY/Gold mix). The consolidated metric ledger and data manifest were refreshed. All saved-price/corporate-action, retrospective selection, spread, and drawdown caveats remain in force.

The bootstrap was subsequently expanded from 108 to 156 summaries after a 30-case passive-mix exposure sweep added four common-2015+ equity paths (45%, 50%, 55%, and 60% initial exposure) to the 10-year drawdown stress. It was then expanded to 192 summaries to include three common-2015+ drawdown-trigger paths. At 63-session blocks, the 8% and 10% trigger cases have 1.46% and 1.96% breach estimates, while the 12% case is 6.70%. The current summary ledger and data manifest are generated from the expanded output.

On 2026-10-27 a separate 15-case, stateful paired-OHLC bootstrap was added for the two fixed controls and three drawdown triggers. It reruns whole-unit positions, next-open policy transitions, the current fee model, slippage, known NIFTYBEES cash distributions, and terminal liquidation across 5,000 ten-year paths at each of three block lengths. Its historical sequential replay matches the canonical drawdown-control simulator. This price-path stress supersedes the older return-only bootstrap for evaluating the stateful controls; the older 192-row output remains reproducible and unchanged. See outputs/stateful_drawdown_control_bootstrap_method.md.

## Modeled charges

For modeled NSE cash trades, the runner includes ₹20 brokerage per executed order, instrument-specific STT, the NSE transaction charge, buy-side stamp duty, SEBI ₹10/crore, current IPFT ₹0.01/crore, ₹20 DP per scrip/day on delivery sells, and 18% GST on brokerage, transaction, demat, and IPFT charges. Current fees are applied uniformly over historical samples as a cost stress, not reconstructed historical contract notes. Slippage is modeled separately.

The futures calculator uses the published date changes for brokerage, NSE futures transaction charges, and futures STT. It uses SEBI ₹10/crore and IPFT ₹0.01/crore; margin and cash interest remain simplified assumptions.

## Current derivatives tariff recheck — 2026-10-27

The current Upstox and NSE schedules list NIFTY/equity futures STT at 0.02% on sells through 2026-03-31 and 0.05% from 2026-04-01; options STT on premium is 0.10% through March and 0.15% from April. Upstox also lists the NSE futures transaction charge moving from 0.00173% to 0.00183% on 2026-03-01. These rates match the date gates in `work/backtest_nifty50_futures.py` for its 2024-10 through 2026-09 sample. The shared `_fee_breakdown` uses the current post-change rates for futures/options on every simulated date, as a current-cost stress; the monthly options replay therefore does not reconstruct pre-April STT. This tariff check does not change the ETF-only benchmark results above. Sources: Upstox [Brokerage Charges](https://upstox.com/brokerage-charges/) and NSE [SEBI Turnover Fees, STT and Other Levies](https://www.nseindia.com/static/invest/first-time-investor-sebi-turnover-fees-stt-other-levies).

## Recomputed artifacts

After the SEBI correction, the following comparison artifacts were rerun from saved market data and their consolidated rows refreshed; the later ETF-unit correction is recorded in the next section:

- Eight walk-forward ETF/sector rows in `outputs/backtest_summary.csv`.
- Eighteen clean NIFTYBEES/GOLDBEES fixed-exposure cases and 48 NIFTY/sector/Gold composite cases.
- Six ORB train, validation, and holdout cases.
- Twenty-two monthly NIFTY expiry periods from the saved contract/candle cache; December 2024 and April 2025 remain skipped for missing data. The replay runner is `work/replay_monthly_options_cached.py`.
- Six date-aware NIFTY futures fee/slippage cases.

The refreshed ledger writer is `work/refresh_backtest_summary.py`. These replays do not change the research caveats about ETF distributions, retrospective windows, or future drawdown.

## Sources

- Upstox, [Brokerage Charges](https://upstox.com/brokerage-charges/), current brokerage, taxes, NSE charges, IPFT, DP, and GST schedule.
- NSE, [SEBI Turnover Fees, STT and Other Levies](https://www.nseindia.com/static/invest/first-time-investor-sebi-turnover-fees-stt-other-levies), ₹10/crore SEBI fee and current STT rates by transaction and instrument.
- AMFI, [Tax Regime for Mutual Funds](https://www.amfiindia.com/investor/knowledge-center-info?zoneName=TaxRegimeForMutualFunds), STT scope for equity-oriented-fund units and Gold ETF classification.
