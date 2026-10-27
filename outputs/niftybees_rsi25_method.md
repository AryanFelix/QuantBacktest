# NIFTYBEES RSI(4) pullback swing strategy

**2026-10-27 fee-model correction:** This static result snapshot predates the instrument-specific ETF STT replay. Use the current sensitivity CSV and consolidated ledger for numeric results; older figures below are superseded where they differ. See the [fee-model audit](../work/research/fee_model_audit.md).


**As of:** 2026-10-27  
**Capital:** ₹10 lakh  
**Status:** rejected on current evidence; the strategy did not produce positive full-period net returns.

## Rule and test design

Connors Research's published RSI 25 rules buy when the close is above its 200-day moving average and 4-period RSI is below 25, add a second unit after RSI falls below 20 while a position is open, and exit when RSI rises above 55 ([original rule description](https://connorsresearch.com/connors-research-traders-journal-volume-1-does-mean-reversion-still-work/)). This Indian ETF test calculates RSI with Wilder smoothing. The signal is read at the close and filled at the next session's open to avoid assuming a fill at the signal close.

The source strategy's unit size is not fixed in the publication. With ₹10 lakh and no leverage, the staged implementation buys a 50% NAV starter and adds 50% after a later RSI(4) close below 20. Two fixed-size ablations buy 50% or 100% on the initial signal and do not add. All exit on RSI(4) above 55. Positions are long only, with no stop or maximum holding period. The re-entry rule can signal again after a later exit.

The data are 3,167 daily NIFTYBEES bars from Upstox, 2014-01-01 through 2026-10-23. The 96 RSI scenarios combine three sizing rules, four per-side slippage levels (10/25/50/100 bps), four chronological periods, and two corporate-action signal treatments. Each account starts with ₹10 lakh in cash, pays current NSE/Upstox delivery charges uniformly over history, earns 0% on cash, and is liquidated at the period end. Signals use completed daily data; orders execute next open with modeled adverse slippage.

Periods are 2014–2019 training, 2020–2022 validation, 2023–2026 later holdout, and continuous 2014–2026. The rule thresholds were fixed from the published source rather than selected on these Indian results. However, all market data in this research thread have been reviewed for other strategies; the later slice is not an untouched global lockbox.

## Corporate actions

The price-only case uses raw Upstox close for signals and no cash distributions. The candidate total-return case uses a synthetic close that credits the two known NIFTYBEES distributions, at ₹0.70 and ₹0.80 per saved share unit on their 2014-03-10 and 2015-02-18 ex-dates, in both the indicator and NAV calculations. These unit conversions rely on inferred 10:1 split normalization; they are a sensitivity, not a complete total-return reconstruction. This strategy held zero shares at both ex-dates, so no distribution cash was received in any tested path. The signal adjustment can still alter subsequent indicator values. The event source and unit caveat are documented in `outputs/etf_corporate_action_audit.csv` and `outputs/dual_momentum_nifty_gold_method.md`.

Twelve comparator rows in the same sensitivity file run buy-and-hold, NIFTYBEES SMA200, and Donchian 55/20 under the candidate total-return inputs at 50 bps, over the same four periods. Indicators use the same candidate total-return adjusted OHLC; execution and NAV use raw market prices plus the candidate cash flows.

## Results

Every continuous 2014–2026 RSI result was negative, even at 10 bps per side. At 50 bps, full-period results were:

| Rule | Return | CAGR | Max drawdown | Fees | Modeled slippage | Orders |
|---|---:|---:|---:|---:|---:|---:|
| RSI(4) 25/20/55, staged 50% + 50% | -65.77% | -8.18% | -65.86% | ₹83,784 | ₹3,48,019 | 195 |
| RSI(4) 25/55, one 50% position | -41.48% | -4.17% | -41.56% | ₹65,920 | ₹2,72,988 | 146 |
| RSI(4) 25/55, one 100% position | -66.58% | -8.35% | -66.67% | ₹95,282 | ₹4,04,906 | 146 |
| NIFTYBEES buy-and-hold | +301.21% | +11.69% | -35.93% | ₹5,398 | ₹38,138 | 2 |
| NIFTYBEES SMA200 long/flat | -9.95% | -0.83% | -41.88% | ₹1,11,099 | ₹4,80,998 | 116 |
| NIFTYBEES Donchian 55/20 long/flat | +115.62% | +6.30% | -19.89% | ₹54,415 | ₹2,39,338 | 36 |

The source RSI strategy failed the 20% drawdown screen in every full-history sizing variant at every tested cost. At 50 bps in the 2023+ slice, the three RSI rules returned -14.10%, -9.13%, and -17.16%, respectively. The only positive RSI rows in the full 96-row screen were six 10-bps cases in the 2023+ slice, each under 1% return; no continuous full-period case was positive. Buy-and-hold made the most in this sample but breached the requested drawdown budget, while Donchian 55/20 was the only comparator here that passed the full-history 20% screen at 50 bps.

Do not promote RSI(4) pullback for NIFTYBEES from these data. The result is not evidence that every mean-reversion rule fails, but this published, trend-filtered swing rule did not transfer to the tested Indian ETF under next-open fills and current fees.

## Limits and reproduction

This is daily OHLC simulation, not queue-aware execution. Actual bid/ask spreads, market impact, partial fills, investor tax, and cash yield are unavailable. Dividend completeness and the Upstox candle adjustment contract remain unresolved. The next-open execution differs from the source's same-close rule but avoids using a close-derived signal and assuming a same-close fill. The drawdown screen is historical and cannot cap future losses.

Reproduce all 108 rows (96 RSI cases plus 12 comparator rows), per-run equity curves, orders, and summaries with `python work/backtest_niftybees_rsi25.py`. Main results: `outputs/niftybees_rsi25_sensitivity.csv`; runner: `work/backtest_niftybees_rsi25.py`; per-run files: `work/backtests/niftybees_rsi25/`.
