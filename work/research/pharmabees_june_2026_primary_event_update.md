# PHARMABEES June 2026 distribution: primary-source update

**Reviewed:** 2026-10-27
**Claim:** ₹6.50 per unit; ex-date 2026-06-11; record date 2026-06-13.
**Instrument:** Nippon India Nifty Pharma ETF, NSE symbol `PHARMABEES`, ISIN `INF204KC1089`.

## Conclusion: unresolved; not confirmed or refuted

No exact primary notice or event record was found that matches the amount, dates, symbol, and ISIN. The available official evidence does not justify treating the alleged distribution as real, but the negative searches are not complete enough to prove that no payment occurred. Keep ₹6.50/unit as hypothetical and do not add it to return or cash-flow calculations unless an AMC/Trustee declaration or exchange record is produced.

## Primary-source checks

- **Instrument identity — confirmed.** Nippon AMC's [Nifty Pharma ETF factsheet](https://mf.nipponindiaim.com/investorservices/factsheetsdocuments/fundamentals-february-2023/Innerpage/Nifty-Pharma-ETF.html) identifies the scheme as Nippon India Nifty Pharma ETF and lists exchange symbol `PHARMABEES` and ISIN `INF204KC1089` (factsheet dated January 31, 2023). This matches the instrument in the claim, but is not evidence of a June 2026 event.
- **AMFI scheme-dividend selector — no record returned.** The [AMFI Scheme Dividends page](https://www.amfiindia.com/otherdata/scheme-dividends) was queried through its same-origin endpoint for Nippon India Mutual Fund (`MF_ID=21`), scheme ID `12257` (“Nippon India Nifty Pharma ETF”), for every listed year 2022–2026. Each query returned HTTP 200 with an empty record list, including 2026. This is an observed absence from that selector, whose completeness is undocumented. Raw local captures: `work/data/api_probes/amfi_nippon_sector_scheme_ids.json` and `work/data/api_probes/amfi_sector_etf_scheme_dividends_2022_2026.json`.
- **AMC notice archive — no matching declaration visible.** Nippon AMC's [Notice/Addendum archive](https://mf.nipponindiaim.com/investor-service/quick-links/notice-addendum) shows June 2026 notices, including items dated June 9–19, but none is titled as a dividend/IDCW distribution notice. Its August 12 item is a generic SID-disclosure addendum, not an announcement of this payment: [official addendum PDF](https://mf.nipponindiaim.com/InvestorServices/Addenda/54-IDCW-disclosure.pdf). The AMC's [Dividend Summary page](https://mf.nipponindiaim.com/investor-service/disclosures/dividend-summary) links a workbook “NIMF Last 5 Dividend instances as on 31st Jul 2026”; the workbook could not be read by the available web retrieval tool, so I do not treat it as checked evidence.
- **NSE — official feed, exact query not verified.** NSE's [Corporate Actions page](https://www.nseindia.com/companies-listing/corporate-filings-actions) exposes symbol, purpose, ex-date and record-date fields. The exact dynamic PHARMABEES query could not be retrieved with the available web tool, so this is not evidence that NSE has no matching record.
- **BSE — retrieval gap.** Searches for the exact amount and dates on BSE returned no indexed matching primary notice. The BSE corporate-action pages could not be retrieved in this session (403/access error); no negative finding is inferred from that failure.

## Evidence classification and use

| Question | Status | Meaning |
|---|---|---|
| Is `PHARMABEES` / `INF204KC1089` the Nippon India Nifty Pharma ETF? | Confirmed | Official AMC factsheet matches the identifiers. |
| Does a primary source confirm ₹6.50/unit, 2026-06-11 ex-date, and 2026-06-13 record date? | Unresolved | No matching AMC/Trustee/AMFI/exchange notice was located in accessible records. |
| Has a primary source disproved the event? | No | Empty AMFI results and inaccessible exchange pages do not prove that no distribution happened. |

The only exact-row lead located remains a third-party data page and is excluded from primary-source confirmation. Do not credit the alleged amount in any backtest until an official declaration or exchange notice gives the per-unit amount and entitlement dates.
