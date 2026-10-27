# NIFTYBEES / GOLDBEES NAV coverage update (2026-10-27)

## Conclusion

A split-normalized NAV price series is now reconstructed from 2014-01-01 through 2026-10-23. A complete investor total-return series is not established because GoldBeES cash distributions have not been ruled out by a complete issuer ledger, and the NAV capture does not reinvest cash payouts.

## Scheme lineage and source reconciliation

The 2016 lineage has two steps. The AMC notice dated August 29, 2016 identifies R*Shares Nifty/Gold ETFs as transferor schemes and the corresponding Goldman Sachs ETFs as the surviving schemes. Separately, the Goldman Sachs Mutual Fund schemes were transferred to Reliance Mutual Fund, effective November 5, 2016. Notice No. 127 dated October 28, 2016 gives that effective date and says the previously announced scheme mergers also take effect then. ([August 29 AMC merger notice](https://mf.nipponindiaim.com/InvestorServices/Addenda/Intimation-letter-BSE-NSE.pdf), [AMC notice to Goldman schemeholders](https://investeasy.nipponindiaim.com/rmfGsamnew/Documents/NoticetoUnitholdersforTransferofGoldmanSachsMutualFundSchemestoRelianceMutualFund.pdf), [Notice No. 127](https://mf.nipponindiaim.com/InvestorServices/Addenda/Notice-No-127-W12xH16.pdf))

The Oct 2025 AMFI SAI also states the November 5, 2016 successor-merger date, but its GoldBeES lineage footnote reverses the transferor and surviving scheme and says September 2016. The contemporaneous AMC notice and Notice No. 127 support the direction and timing above; the SAI inconsistency is documented in the [GoldBeES distribution audit](goldbees_distribution_history_audit_2026-10-28.md).

- AMFI history selector `mf=49` returns Goldman scheme 115728, ISIN `INF732E01011`, and scheme 115744, ISIN `INF732E01102`, from 2014-01-01 through their last NAV on 2016-11-03.
- Nippon first-party history IDs 503/495 match both Goldman NAV series exactly on 246 common sessions per ETF, 2015-11-02 through 2016-11-03.
- After the merger, AMFI scheme codes 140084/140088 and current ISINs `INF204KB14I2`/`INF204KB17I5` match the Nippon service on 2016-11-07 through 2016-11-10. Unlabeled Nippon service IDs 21/24 are not used.
- Nippon's full service history returns 2,772 observations per scheme from 2015-11-01 through 2026-10-23. Goldman history adds 695 NIFTY and 694 Gold rows from 2014-01-01 through 2016-11-03. AMFI's current historical-download page documents a 90-day request limit; the capture uses consecutive 90-day Goldman windows.

Primary data routes: [AMFI Goldman query, Jan 2014](https://portal.amfiindia.com/DownloadNAVHistoryReport_Po.aspx?mf=49&frmdt=01-Jan-2014&todt=10-Jan-2014), [AMFI Goldman query, Nov 2015](https://portal.amfiindia.com/DownloadNAVHistoryReport_Po.aspx?mf=49&frmdt=01-Nov-2015&todt=10-Nov-2015), [AMFI successor query, Nov 2016](https://portal.amfiindia.com/DownloadNAVHistoryReport_Po.aspx?mf=21&frmdt=01-Nov-2016&todt=10-Nov-2016), [Nippon full history service](https://mf.nipponindiaim.com/_vti_bin/RMF.Services/MobileAppService.svc/GetTrackNAVs?SchemeIDs=503%2C495&NAVPeriod=Historical&FromDate=2014-01-01&ToDate=2026-10-23).

## Share-unit and market-price check

Nippon's issuer actions identify the 1:10 NIFTYBEES and 1:100 GOLDBEES splits effective in December 2019. Raw NAVs are divided by those factors through 2019-12-20 to express earlier values on the current share basis. This is only a unit conversion; it does not adjust NAV returns for cash distributions. ([NIFTYBEES actions](https://investeasy.nipponindiaim.com/rmfGsamnew/Products/NiftyBeES/CorporateAction.aspx), [GOLDBEES actions](https://investeasy.nipponindiaim.com/rmfGsamnew/Products/GoldBeES/CorporateAction.aspx), [NSE NIFTYBEES actions](https://www.nseindia.com/get-quote/equity/NIFTYBEES/Nippon-India-ETF-Nifty-50-BeES))

Comparing this split-normalized NAV against saved Upstox daily closes through 2026-10-23:

| ETF | Matched sessions | Market sessions without NAV | Median market premium | 5th–95th percentile |
|---|---:|---:|---:|---:|
| NIFTYBEES | 3,153 | 13 | +0.03% | -0.25% to +0.30% |
| GOLDBEES | 2,910 | 11 | -0.27% | -2.80% to +0.48% |

This supports the historical share-unit mapping and price-series lineage. It is not proof of complete NAV coverage on every market session, distribution reinvestment, or executable fills.

## Investor-return treatment

NSE lists NIFTYBEES dividends of ₹7 per pre-split unit (ex-date 2014-03-10) and ₹8 (ex-date 2015-02-18); project backtests book ₹0.70/₹0.80 in their current-unit historical price basis when the simulated portfolio held units. The corporate-action dates and split are visible in [NSE's quote page](https://www.nseindia.com/get-quote/equity/NIFTYBEES/Nippon-India-ETF-Nifty-50-BeES). The AMC's GoldBeES actions page lists the split but does not certify that no cash distributions ever occurred; zero GoldBeES distributions remain unverified.

## Reproduction and limits

Run `python work/capture_amfi_goldman_etf_nav.py`. The raw source responses are kept in ignored `work/data/api_probes/etf_nav_lineage_2014_2026.json`; the public aggregate is [etf_nav_market_close_reconciliation.csv](../../outputs/etf_nav_market_close_reconciliation.csv). Strategy results still use Upstox exchange-price OHLC, modeled fees and stated slippage; this NAV capture validates the share-price basis but does not change those executions or establish a future drawdown limit.
