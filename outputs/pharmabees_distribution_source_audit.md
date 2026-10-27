# PHARMABEES alleged 2026 distribution: source audit

**Reviewed:** 2026-10-27
**Instrument:** Nippon India Nifty Pharma ETF; NSE symbol `PHARMABEES`; ISIN `INF204KC1089`; AMFI scheme ID `12257` under Nippon India Mutual Fund (`MF_ID=21`).

## Finding

The reported ₹6.50/unit event with an 11 June 2026 ex-date is **not confirmed by the primary records reviewed**. Keep it out of ETF total-return adjustments and portfolio cash flows. This is an evidence limit, not a finding that the ETF paid zero distributions.

The follow-up [primary-source review](../work/research/pharmabees_june_2026_primary_event_update.md) checked the AMC notice archive and exchange corporate-action pages. It reached the same unresolved conclusion; no backtest cash-flow adjustment was made.

The lead is a third-party ATS dividend-history page, which labels ₹6.50 as a final dividend, gives 11 June 2026 as the ex-date and 13 June 2026 as the record date, and says the data came from BSE. Its displayed 1.20% yield is internally inconsistent with ₹6.50 divided by its stated ₹26.65 close (about 24.4%). The page provides no BSE notice number or primary filing link for this row. Treat it as an unverified lead only.

## Primary-source checks

- **AMFI scheme-dividend selector:** the official [Scheme Dividends page](https://www.amfiindia.com/otherdata/scheme-dividends) was queried for Nippon India MF, scheme ID `12257` (“Nippon India Nifty Pharma ETF”), for each year 2022–2026. The 2026 query returned HTTP 200 and an empty record list; the other four year queries were also empty. This is an observed negative result from AMFI's selector, but its coverage/completeness is undocumented. Saved mapping and responses: `work/data/api_probes/amfi_nippon_sector_scheme_ids.json` and `work/data/api_probes/amfi_sector_etf_scheme_dividends_2022_2026.json`.
- **Nippon AMC scheme identity:** the AMC's [Nifty Pharma ETF page](https://mf.nipponindiaim.com/FundsAndPerformance/Pages/NipponIndia-Nifty-Pharma-ETFWebsite.aspx) identifies the product. Its June 2026 [product note](https://mf.nipponindiaim.com/FundsAndPerformance/ProductNotes/NipponIndia-Nifty-Pharma-ETF-Jun-2026.pdf) describes the ETF and its benchmark, but the reviewed document does not confirm this alleged payment. The AMC page's generic IDCW-reinvestment performance convention is not evidence that a particular distribution occurred.
- **NSE identity check:** NSE's [quote page](https://www.nseindia.com/get-quote/equity/PHARMABEES/Nippon-India-Mutual-Fund---Nippon-India-Nifty-Pharma-ETF) identifies `PHARMABEES` and ISIN `INF204KC1089` as a listed mutual-fund scheme. The [July 2021 listing circular](https://nsearchives.nseindia.com/content/circulars/CML48853.pdf) corroborates the Nippon ETF/ISIN identity. Neither item confirms the 2026 cash event.
- **Upstox corporate-actions response:** the exact-ISIN call to `https://api.upstox.com/v2/fundamentals/INF204KC1089/corporate-actions` returned API success with zero records on 2026-10-26. Upstox's available response supplies no completeness guarantee, so this cannot establish that no distribution occurred. Credential-free capture: `work/data/api_probes/sector_etf_corporate_actions_2026-10-26.json`.

## Backtest treatment

The existing corporate-action audit records the hypothetical ₹49,504–₹75,088 exposure as diagnostic only and does not credit it to NAV. Keep that treatment until an AMC/Trustee declaration or exchange filing confirms the amount, ex-date/record date, and units entitled. If confirmed, rerun the affected sector ETF portfolios with cash credited to units held before the official ex-date; do not infer an event from a price or NAV move.

## Sources and local evidence

- Third-party lead only: [ATS PHARMABEES dividend history](https://adityatrading.in/stocks/pharmabees/dividends/).
- Official selector: [AMFI Scheme Dividends](https://www.amfiindia.com/otherdata/scheme-dividends).
- Official product identity/context: [Nippon AMC scheme page](https://mf.nipponindiaim.com/FundsAndPerformance/Pages/NipponIndia-Nifty-Pharma-ETFWebsite.aspx) and [June 2026 product note](https://mf.nipponindiaim.com/FundsAndPerformance/ProductNotes/NipponIndia-Nifty-Pharma-ETF-Jun-2026.pdf).
- Official exchange identity: [NSE PHARMABEES quote page](https://www.nseindia.com/get-quote/equity/PHARMABEES/Nippon-India-Mutual-Fund---Nippon-India-Nifty-Pharma-ETF) and [NSE listing circular](https://nsearchives.nseindia.com/content/circulars/CML48853.pdf).
- Existing event matrix: `outputs/sector_etf_corporate_action_audit.csv`, PHARMABEES row.
