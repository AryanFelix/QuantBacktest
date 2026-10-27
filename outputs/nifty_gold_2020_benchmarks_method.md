# NIFTY/Gold matched passive and active benchmark comparison

**Run date:** 2026-10-27  
**Market data:** Upstox ETF daily candles, 2020-01-01 through 2026-10-23  
**Initial capital:** ₹10,00,000  
**Costs:** corrected NSE/Upstox delivery fees and 50 bps per-side slippage  
**Risk screen:** 20% conservative daily OHLC drawdown bound  
**Status:** seven-path matched-period historical comparison on previously inspected data; not an untouched holdout.

## Design

All seven paths start with ₹10 lakh and use the same 2020-to-2026-10-23 session range, instrument-price caches, integer units, current statutory fee model, 50 bps per-side slippage, zero cash yield, and terminal liquidation. The daily OHLC bound assumes held positions reach their highs before their lows during each session. Equity-fund and Gold-fund STT classifications use the corrected product-specific fee model.

The passive single-asset paths put up to 45% of NAV into NIFTYBEES or GOLDBEES at the first test open, then hold the integer units through the final close. The passive mix puts 22.5% of initial NAV into each ETF and does not rebalance; its exposure can drift above 45%. The quarterly static mix targets 50/50 and rebalances every quarter, subject to a 45% aggregate gross-exposure cap. The quarterly D55/20 rule targets a combined 45% gross exposure at its signal and quarterly rebalances. The annual walk-forward rows are copied from the separately audited expanding-window replay, which liquidates at each year-end and starts the next year with the actual ending cash balance.

## Results

| Strategy | End value | Net return | Close MDD | OHLC bound | Fees | Slippage | 20% screen |
|---|---:|---:|---:|---:|---:|---:|---|
| Annual expanding-window selector | ₹15.49L | +54.89% | -13.00% | -14.86% | ₹12,019 | ₹1,79,867 | Pass |
| Annual fixed D55/20 control | ₹16.26L | +62.56% | -13.00% | -14.86% | ₹11,988 | ₹1,85,080 | Pass |
| Fixed quarterly D55/20 + Gold SMA200 | ₹17.90L | +79.04% | -12.98% | -15.36% | ₹8,377 | ₹1,57,611 | Pass |
| Quarterly static 50/50 target, 45% cap | ₹15.88L | +58.82% | -9.52% | -12.91% | ₹2,491 | ₹10,684 | Pass |
| Passive NIFTYBEES, 45% initial | ₹14.40L | +44.00% | -16.52% | -20.63% | ₹197 | ₹6,727 | Fail |
| Passive GOLDBEES, 45% initial | ₹20.49L | +104.93% | -19.04% | -22.89% | ₹212 | ₹9,842 | Fail |
| Passive NIFTYBEES/GOLDBEES, 22.5% each | ₹17.45L | +74.46% | -14.48% | -16.16% | ₹276 | ₹8,285 | Pass |

The continuous quarterly trend rule returned 4.59 percentage points more than the passive initial allocation mix, with a 0.80-point shallower OHLC bound and about ₹1.49 lakh more modeled slippage. The static quarterly mix returned less than both, but had the shallowest OHLC bound. The annual parameter selector did not outperform the continuous quarterly trend rule or passive mix. Single-asset Gold had the highest ending value, but its OHLC bound breached the requested drawdown limit; the same screen rejects passive NIFTYBEES.

## Limits and reproduction

The 45% target came from an earlier full-history risk screen, and these dates have already been inspected. This is a benchmark check, not an independent validation or evidence that the fixed quarterly strategy will win going forward. ETF market-price history is not a complete total-return series; historical fund distributions, taxes, cash yield, and live market impact remain incomplete. Passive weights drift after the initial purchase, and price-derived OHLC extremes are not a synchronized tick path.

Reproduce with `python work/benchmark_nifty_gold_2020.py`. It asserts the seven-case output, common end date, passive target exposure, and order-ledger reconciliation within ₹0.03. Per-run equity and order files are in `work/backtests/nifty_gold_2020_benchmarks/`; rows are refreshed into `outputs/backtest_summary.csv` by `python work/refresh_backtest_summary.py`. Full 2014+ and common 2015+ comparisons are documented separately in [the extended-history method](nifty_gold_history_benchmarks_method.md).
