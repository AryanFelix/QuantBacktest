# Extended-history NIFTY/Gold benchmark comparison

**Run date:** 2026-10-27  
**Market data:** Upstox daily ETF candles through 2026-10-23  
**Initial capital:** ₹10,00,000 per path  
**Costs:** current modeled product-specific fees and 50 bps per-side slippage  
**Risk screen:** conservative same-day OHLC drawdown bound no worse than -20%  
**Status:** retrospective price comparison, not a validated winner or untouched holdout.

## Construction

The comparison runs the same five strategies on (1) the full available panel from 2014-01-01 through 2026-10-23 and (2) a shared-asset window from 2015-01-02 through 2026-10-23. NIFTYBEES candles begin in 2014; GOLDBEES candles begin in 2015. The full-window results therefore include a period before both ETFs have common cached history. The common-window table is the cleaner comparison of the same two instruments.

Each path starts with ₹10 lakh, uses whole units, current modeled delivery charges, 50 bps slippage on each fill, zero cash yield, and terminal liquidation. Returns are net of modeled fees and slippage. Current charges are applied uniformly to historical transactions as a cost stress, not as a reconstruction of historical fee schedules. The daily OHLC bound pessimistically orders held-asset daily highs before lows; it is an envelope, not a synchronized intraday path.

The passive single-asset paths initially deploy 45% of NAV into one ETF. The passive mix initially targets 22.5% of NAV in each ETF and then holds without rebalancing; its exposure drifts with relative prices and is not kept at 45%. The quarterly static mix requests equal ETF weights and rebalances quarterly, with a 45% aggregate exposure cap at each rebalance. The D55/20 strategy uses a quarterly trend signal and the same 45% gross target.

NIFTYBEES cash distributions of ₹7 and ₹8 per pre-split unit in 2014 and 2015 are included as ₹0.70 and ₹0.80 per saved unit, respectively, using the documented 1:10 split conversion. The unit conversion is inferred from the AMC's action history and observed price continuity; Upstox does not document a universal corporate-action adjustment guarantee. No GOLDBEES cash distributions are inserted because the available AMC page's listed events do not establish completeness. The source and conversion limits are recorded in the [ETF total-return source audit](../work/research/etf_total_return_source_audit.md). [Nippon NIFTYBEES actions](https://investeasy.nipponindiaim.com/rmfGsamnew/Products/NiftyBeES/CorporateAction.aspx), [Nippon GoldBeES actions](https://investeasy.nipponindiaim.com/rmfGsamnew/Products/GoldBeES/CorporateAction.aspx), [Upstox V3 daily candle documentation](https://upstox.com/developer/api-documentation/v3/get-historical-candle-data/).

## Results: 2014-01-01 through 2026-10-23

| Strategy | End value | Net return | CAGR | Close MDD | OHLC bound | Known cash distributions | 20% screen |
|---|---:|---:|---:|---:|---:|---:|---|
| Passive NIFTYBEES, 45% initial | ₹23.66L | +136.57% | 7.09% | -22.67% | -27.90% | ₹10,593 | Fail |
| Passive GOLDBEES, 45% initial | ₹26.54L | +165.39% | 8.08% | -20.35% | -24.45% | Unknown | Fail |
| Passive NIFTYBEES/GOLDBEES, 22.5% initial each | ₹24.56L | +145.62% | 7.41% | -15.58% | -17.36% | ₹4,774 | Pass |
| Quarterly D55/20, 45% target | ₹17.78L | +77.77% | 4.69% | -15.23% | -16.15% | ₹0 | Pass |
| Quarterly static 50/50, 45% cap | ₹20.32L | +103.18% | 5.80% | -9.48% | -12.91% | ₹4,763 | Pass |

The passive mixed allocation has the highest ending value among these screened paths, but 45% is only its initial allocation: observed gross exposure rose to about 79.45% at its peak and ended near 76.2%. It therefore should not be compared as a fixed 45% exposure strategy. The quarterly static mix delivered a lower return with more room under the historical OHLC screen. Both single-asset passive paths failed the 20% screen.

## Results: common 2015-01-02 through 2026-10-23

| Strategy | End value | Net return | CAGR | Close MDD | OHLC bound | Known cash distributions | 20% screen |
|---|---:|---:|---:|---:|---:|---:|---|
| Passive NIFTYBEES, 45% initial | ₹19.27L | +92.66% | 5.82% | -20.36% | -25.20% | ₹4,295 | Fail |
| Passive GOLDBEES, 45% initial | ₹26.54L | +165.39% | 8.78% | -20.35% | -24.45% | Unknown | Fail |
| Passive NIFTYBEES/GOLDBEES, 22.5% initial each | ₹22.90L | +129.00% | 7.41% | -15.58% | -17.37% | ₹2,147 | Pass |
| Quarterly D55/20, 45% target | ₹16.66L | +66.58% | 4.50% | -15.24% | -15.87% | ₹0 | Pass |
| Quarterly static 50/50, 45% cap | ₹19.02L | +90.23% | 5.70% | -9.48% | -12.91% | ₹2,147 | Pass |

The 2015 common-start ordering is similar: the passive mix has the highest tested return among screen-pass paths, while the quarterly static mix has a shallower bound. The Gold-only path again fails the drawdown screen. Historical prices and both windows have already been examined during this research, so this is not an independent out-of-sample result.

## Files and limitations

The 2020–2026 matched-period benchmark remains in [`nifty_gold_2020_benchmarks.csv`](nifty_gold_2020_benchmarks.csv). Extended results are in [`nifty_gold_full_history_benchmarks.csv`](nifty_gold_full_history_benchmarks.csv) and [`nifty_gold_common_history_benchmarks.csv`](nifty_gold_common_history_benchmarks.csv). Run-level equity and orders are under `work/backtests/nifty_gold_full_history_benchmarks/` and `work/backtests/nifty_gold_common_history_benchmarks/`. Reproduce with `python work/benchmark_nifty_gold_2020.py`; order/equity reconciliation is asserted to ₹0.03.

Upstox's daily OHLC documentation does not promise dividend-adjusted candles. Gold distribution completeness, cash yield, taxes, live spreads, market impact, and partial fills are unresolved. The daily OHLC bound is conservative by construction but cannot enforce a 20% future maximum drawdown. These results identify candidates for more validation; none is declared a winning or deployable strategy. Official NIFTY TRI uses constituent dividends and is useful as a market benchmark, but is not the ETF portfolio modeled here. See [NSE historical index data](https://www.niftyindices.com/reports/historical-data) and its [total-return method](https://www.niftyindices.com/resources/index-concepts/total-return-index).
