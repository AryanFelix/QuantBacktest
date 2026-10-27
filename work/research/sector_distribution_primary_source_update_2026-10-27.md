# Sector ETF distribution-source update

**Checked:** 2026-10-27
**Scope:** AUTOBEES and PHARMABEES cash-distribution claims; source verification only.

## Event claims and current status

| ETF | Exact claim found | Verification status |
|---|---|---|
| AUTOBEES (ISIN `INF204KC1337`) | ₹10.50/unit, ex-date 2026-06-09, record date 2026-06-11 | Not verified from a primary event notice in the material reviewed. The [secondary event page](https://adityatrading.in/stocks/autobees/dividends/) attributes its data to BSE corporate actions but provides no filing or notice link. |
| PHARMABEES (ISIN `INF204KC1089`) | ₹6.50/unit, ex-date 2026-06-11, record date 2026-06-13 | Not verified from a primary event notice in the material reviewed. The [secondary event page](https://adityatrading.in/stocks/pharmabees/dividends/) attributes its data to BSE corporate actions but provides no filing or notice link. |

The claims are leads, not accepted cash-flow inputs. No source reviewed here supplies an issuer, exchange, or AMFI event document that confirms both the amount and dates for either ETF.

## First-party checks

- The issuer's [AUTOBEES page](https://mf.nipponindiaim.com/FundsAndPerformance/Pages/NipponIndia-Nifty-Auto-ETF.aspx) and [PHARMABEES page](https://mf.nipponindiaim.com/FundsAndPerformance/Pages/NipponIndia-Nifty-Pharma-ETF.aspx) identify each scheme and describe its objective as tracking the respective sector index's total returns before expenses. These product pages are not event ledgers.
- The issuer's [dividend-notice index](https://mf.nipponindiaim.com/investor-service/downloads/dividend-notice) lists several scheme notices. A text search of the returned list did not find either ETF by its scheme name; this page view is not a complete historical event query and cannot establish that no payment occurred.
- AMFI's [Scheme Dividends page](https://www.amfiindia.com/otherdata/scheme-dividends) was queried for Nippon India Mutual Fund, the exact ETF scheme IDs (AUTOBEES `12373`, PHARMABEES `12257`), and each year 2022–2026. All ten selected requests returned HTTP 200 with zero rows in the saved capture. An empty result is not a guarantee that AMFI's event feed is complete. See `work/data/api_probes/amfi_nippon_sector_scheme_ids.json` and `work/data/api_probes/amfi_sector_etf_scheme_dividends_2022_2026.json` (retrieved 2026-10-26 UTC).
- The saved Upstox exact-ISIN corporate-action probe also returned successful empty lists for both funds. Its request/response record is `work/data/api_probes/sector_etf_corporate_actions_2026-10-26.json`; the [documented endpoint](https://upstox.com/developer/api-documentation/get-corporate-actions/) does not promise complete historical coverage.
- The official [NSE corporate-actions page](https://www.nseindia.com/companies-listing/corporate-filings-actions) and [BSE corporate-actions page](https://www.bseindia.com/corporates/corporates_act.html) are potential exchange sources. The BSE page returned HTTP 403 to the web retrieval used for this check, and no matching official event document was found in indexed results. This is a retrieval gap, not evidence of no event.

## Backtest treatment

Keep both events unverified in the primary ledger. For sector-ETF performance, run cash-flow sensitivities that exclude and include the two claimed payments on their stated ex-dates, but label the included case as secondary-source-only. Do not use an empty AMFI/Upstox result, a matching price movement, or the ETF's benchmark objective to infer a zero or a confirmed distribution. Promote amounts to the primary event ledger only after obtaining an issuer/exchange notice with matching scheme identity, amount, ex-date, and record date.
