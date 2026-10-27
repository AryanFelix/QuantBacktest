# NSE corporate-actions feed audit

**Checked:** 2026-10-26  
**Use:** Historical event input for point-in-time stock total-return research.

## Source and request

NSE's [Corporate Filings: Corporate Actions page](https://www.nseindia.com/companies-listing/corporate-filings-actions) provides company/symbol and custom-date filters, pagination, and a CSV download. Its first-party [corporate-filings frontend script](https://www.nseindia.com/dist/js/sections/corporate-filings.js?v=16102026) loads the equity table from `/api/corporates-corporateActions?index=equities`, appending `symbol`, `from_date`, and `to_date` for a selected company/date range. This is the web page's data endpoint, not a documented Upstox or NSE developer API contract; the page implementation can change.

The research pull used `index=equities`, dates `01-01-2000` through `26-10-2026`, and 89 symbols: 69 mapped Upstox tickers, symbols in the reconstructed NIFTY 50 membership-event ledger, and explicit historical aliases. Raw responses and request metadata are saved in `work/data/universe_sources/nse_corporate_actions_2000_2026.json`. Re-run with `python work/fetch_nse_corporate_actions.py`.

## Pull results and checks

- All 89 requests returned HTTP 200; 82 symbols had records and seven returned empty lists. The file contains 2,459 records with observed ex-dates from 2005-04-29 through 2026-10-23.
- A simple subject-text audit counted 1,936 dividend-labelled rows, 76 bonus, 18 rights, 38 split, 6 demerger, and 385 other rows. These are triage counts; compound and revised labels need normalization before position accounting.
- Five known demerger rows were found at the expected symbol/date: VEDL (30-Apr-2026), ITC (06-Jan-2025), HINDUNILVR (05-Dec-2025), RELIANCE (20-Jul-2023), and TMPV (14-Oct-2025). The old `TATAMOTORS` symbol returned no records while `TMPV` returned the 2025 event, confirming that historical aliases matter.


The 816-row Upstox close-to-close price-move cross-check matched 23 moves within one calendar day of a feed row (16 exact, 7 adjacent). Four exact demerger-date matches are large drops for VEDL, TMPV, ITC, and SIEMENS. This is a date join, not evidence that every matched move was caused by the listed action. HDFC and HDFCBANK have no merger-labelled row in this feed, so the 2023 HDFC merger continues to rely on the separate issuer filing and explicit 42:25 share accounting. The cross-check is saved as `outputs/stock_move_action_crosscheck.csv`.

## Limits before strategy use

The query was accepted and returned long histories, but the page does not make a completeness or retention guarantee. The endpoint's action rows describe purpose, ex-date, record date, face value, and ISIN; a row labelled `Demerger` does not provide the resulting share entitlement or allocation terms. Dividend, split, bonus, and rights rows also need label parsing and event-date handling. Use issuer/exchange circulars for merger and demerger terms, keep the raw feed as evidence, and reconcile the normalized ledger before reporting stock strategy returns.


The separate `outputs/corporate_action_entitlements.csv` records verified share ratios and each recipient series' first cached quote after the action reference date. Nine newly issued successor securities have 23-73 calendar-day periods with no quote in the current Upstox cache. This is a market-data availability gap, not proof that the shares were unissued or unlisted throughout the interval; exchange price-discovery evidence is still needed for daily NAV accounting.

## Sources

1. NSE, [Corporate Filings: Corporate Actions](https://www.nseindia.com/companies-listing/corporate-filings-actions), accessed 2026-10-26.
2. NSE, [first-party corporate-filings frontend script](https://www.nseindia.com/dist/js/sections/corporate-filings.js?v=16102026), accessed 2026-10-26.
3. NSE, [VEDL corporate-actions page](https://www.nseindia.com/companies-listing/corporate-filings-actions?symbol=VEDL), accessed 2026-10-26.
