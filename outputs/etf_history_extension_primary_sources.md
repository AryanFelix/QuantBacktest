# NIFTY/Gold ETF history extension: source audit

**Reviewed:** 2026-10-27  
**Scope:** whether the current NIFTYBEES/GOLDBEES candidate can be tested over a longer executable ETF sample. No API call, backtest, or trade was made for this note.

## Saved coverage versus fund inception

| ETF | Official scheme inception | Earliest saved daily candle | Saved rows |
|---|---|---|---:|
| NIFTYBEES | 28 Dec 2001 ([Nippon India product page](https://mf.nipponindiaim.com/FundsAndPerformance/Pages/NipponIndia-ETF-Nifty-50-BeES.aspx)) | 1 Jan 2014 | 3,167 |
| GOLDBEES | 8 Mar 2007 ([Nippon India May 2026 product note](https://mf.nipponindiaim.com/FundsAndPerformance/ProductNotes/NipponIndia-ETF-Gold-BeES-May-2026.pdf)) | 1 Jan 2015 | 2,922 |

Both saved histories end on 23 Oct 2026. The NIFTYBEES file is `work/data/etf_daily/NSE_EQ_INF204KB14I2-days-1-2014-01-01-2026-10-23.csv`; the GOLDBEES file is `work/data/etf_daily/GOLDBEES-days-1-2014-01-01-2026-10-23.csv`. The common saved sample therefore omits roughly seven years during which both ETFs existed, including the 2008 crisis. This is a cache start gap, not evidence that the funds or market prices did not exist.

The Upstox daily instrument key for NIFTYBEES is `NSE_EQ|INF204KB14I2`. The forward-paper probe records GOLDBEES as `NSE_EQ|INF204KB17I5` in `work/data/api_probes/forward_paper_latest.json`; the historical-candle row in the data manifest currently leaves GOLDBEES's key blank.

## Can Upstox extend the sample?

Upstox's [Historical Candle V3 documentation](https://upstox.com/developer/api-documentation/v3/get-historical-candle-data/) says daily candles are available from January 2000, with a maximum retrieval window of one decade leading up to each `to_date`. It documents OHLCV responses and an optional `from_date`; it does not promise that every instrument has complete candles back to its inception or specify a corporate-action adjustment guarantee.

The documented date range is sufficient in principle to request NIFTYBEES back to its 2001 inception and GOLDBEES back to its 2007 inception, in multiple windows. This is not yet verified for either exact instrument. Make the authenticated read-only requests, inspect returned dates and prices, and compare the earliest bars and share-unit transitions with official AMC/NSE records before extending the backtest.

## Research implication

A longer ETF backtest is potentially legitimate from the earliest verified exchange-traded bars of both funds; do not substitute Nifty index values for pre-inception ETF fills. The common tradable sample may begin in 2007, subject to the GOLDBEES API coverage check. Before using it for the ₹10 lakh/20% screen, reconcile all ETF cash distributions and splits over the extended window. The existing exact-ISIN Upstox corporate-action probe returned no NIFTYBEES events despite known 2014/2015 distributions, so an empty action response is not completeness evidence (`work/data/api_probes/ETF_corporate_actions_2026-10-26.json`). No existing performance result is updated by this source audit.
