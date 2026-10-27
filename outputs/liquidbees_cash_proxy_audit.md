# Cash-proxy and token-access audit

**Checked:** 2026-10-26  
**Scope:** Determine whether LIQUIDBEES or an overnight-rate index can represent idle cash in the current backtests. No strategy return was recalculated in this audit.

## Findings

- Upstox has 2,923 daily LIQUIDBEES candles from 2015-01-01 through 2026-10-23. The cached market-price close stays near ₹1,000 (first ₹999.99; last ₹1,000.00; observed low ₹999.84 and high ₹1,000.15). This is not a total-return series.
- Nippon’s scheme document says daily IDCW is discretionary and reinvested into additional fractional units to keep the scheme NAV near its ₹1,000 face value. Its published performance is explicitly calculated on an IDCW-reinvestment basis. A flat market-price series therefore omits the economics needed for a cash-return backtest. [Scheme information document](https://mf.nipponindiaim.com/InvestorServices/SIDETF/NipponIndia-ETF-Nifty-1D-Rate-Liquid-BeES.pdf), [official performance page](https://mf.nipponindiaim.com/FundsAndPerformance/Pages/NipponIndia-ETF-Nifty-1D-Rate-Liquid-BeES-ETF-Website.aspx).
- The sampled Upstox LIQUIDBEES corporate-actions response contains zero records. That response is not evidence that no IDCW was declared.
- As a benchmark check, the official NSE Indices history page returned 2,993 unique Nifty 1D Rate Index closes from 2014-01-01 through 2026-10-23. The index measures overnight TREPS lending returns; it is a benchmark, not an investable LIQUIDBEES return after fund expenses, tracking, execution, and tax. [NSE Indices historical data](https://www.niftyindices.com/reports/historical-data), [index factsheet](https://www.niftyindices.com/Factsheet/Factsheet_Nifty_1D_Rate.pdf), [methodology](https://www.niftyindices.com/Methodology/Method_Nifty_1D_Rate.pdf).
- The official history response has a material 2020 gap. Its 2020 annual query returned 115 records, with observations on 2020-01-27 and then 2020-08-13, leaving no returned records from 2020-01-28 through 2020-08-12. A separate 2020-01-01 to 2020-06-30 query returned only 19 records, ending on 2020-01-27. This is a gap in the retrieved history; it does not establish whether the index itself was or was not calculated during those dates.
- The raw annual-window responses and the gap probe are saved in `work/data/index_daily/`. The first test save accidentally captured the previous page’s 2026 rows; validation caught it, that temporary file was removed, and it was not used in analysis.

## Backtest treatment

No cash-return series is substituted into historical strategy returns. Existing backtests retain their documented 0% cash-yield assumption. The LIQUIDBEES price series is excluded as a cash proxy, and the incomplete 1D Rate history is retained only as source evidence until the gap is reconciled. No missing dates were interpolated or assigned synthetic returns.

## Upstox token discovery

The current process environment does not contain `UPSTOX_ANALYTICS_TOKEN`, while the value name is present in the current user's `HKCU\Environment`. `work/upstox_quant.py` reads the token from that registry key when it is absent from the process environment. The earlier live API probe authenticated using that fallback and matched the cached 2026-10-23 NIFTYBEES candle, so restarting Codex is not required for this research runner. The token value was not read into this note or printed.
