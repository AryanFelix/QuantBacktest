# AGEL claim valuation protocol — registered before continuation results

Registered 2026-11-02 before opening any post-2018-04-04 account output. Applies identically to NIFTY200-A-M, A-Q, B-M, and B-Q. The four frozen strategies, schedule, score windows, eligibility, top-20 selection, rank-25 retention, 5% targets, next-session execution, ₹10,00,000 continuous capital, 50 bps per-side base slippage, fee helper, zero cash yield, and high-water mark remain fixed.

## Verified event terms

The issuer's investor page links the final NCLT order dated 2018-02-16. The NCLT order sanctions the Scheme at Annexure G. AGEL's post-sanction Information Memorandum says the Scheme took effect on 2018-04-01, gives the AEL record date as 2018-04-06 and ratio as 761 AGEL shares per 1,000 AEL shares, and says the new shares were credited to demat accounts on 2018-04-19. The contemporaneous BSE listing notice records an allotment date of 2018-04-08; its accessible text is a transcript, while the demat-credit date is confirmed by the issuer. BSE's 2018-03-27 corporate-action notice transcript records ex-entitlement from 2018-04-05 and the 2018-04-06 record date. NSE's June 2018 monthly market review lists ADANIGREEN on 2018-06-18.

The issuer's scheme text contains clauses 10.3 and 10.11: fractional entitlements are consolidated, issued to a trustee, sold at the trustee's discretion, and net proceeds distributed proportionally after applicable taxes and expenses; AGEL shares remain frozen in the depository until listing/trading permission. The official NCLT PDF is linked but has no text layer in the available capture, so I could not compare its authenticated Annexure G character-for-character against the issuer's scheme copy. The post-sanction Information Memorandum and listing notice reconfirm the ratio and implementation dates; I found no later corrigendum changing the ratio or the cited fraction/freeze terms in the issuer scheme page or the exchange records reviewed. Treat clauses 10.3/10.11 as issuer-source verified and consistent with the sanctioned implementation, with that annexure-level limitation retained.

The trustee's actual sale date, fill, fees, and beneficial payment date are not established by the cited sources.

Primary references:

- AEL investor page linking the final NCLT order: https://www.adanienterprises.com/investors/corporate-governance/scheme-of-arrangement
- Final NCLT order PDF: https://www.adanienterprises.com/-/media/Project/Enterprises/Investors/corporate-governance/Scheme-of-Arrangement-between-AEL-and-AGEL/NCLT-Order-dated-16022018.pdf
- NCLT order record for AGEL, CP(CAA) No. 164/NCLT/AHM/2017: https://archive.nclt.gov.in/content/ms-adani-green-energy-ltd
- Issuer AGEL information memorandum: https://www.adanigreenenergy.com/-/media/Project/GreenEnergy/Corporate-Governance/Others/Adani_Green_Energy_Limited_-_Information_Memorandum.pdf
- Issuer scheme / explanatory statement, printed p.38, clauses 10.3 and 10.11: https://www.adanigreenenergy.com/-/media/Project/GreenEnergy/Corporate-Governance/scheme-of-Arrangement-2018/Notice-and-Explanatory-Statement-UnSecured-Creditors.pdf
- Official NSE June 2018 market review listing table: https://nsearchives.nseindia.com/web/sites/default/files/inline-files/NSE_Market_Pulse_Jun2018_0.pdf
- BSE notice 20180613-36 listing AGEL, transcript: https://noticeblue.com/circulars/e91351f6-a4a1-4455-b63f-dfebcad1b9c5
- BSE notice 20180327-36 fixing the ex-entitlement and record dates, transcript: https://noticeblue.com/circulars/059c6479-0d0c-473c-a291-c68e73c197bf
- MSCI Corporate Events Methodology Jan 2020, section 2.8.2, printed pp.42–43: https://www.msci.com/eqb/methodology/meth_docs/MSCI_CEMethodology_Jan2020.pdf

The BSE notice transcript states AGEL was in the T group / trade-for-trade for 10 trading days and part of the regular IPO/other special pre-open process. No special-preopen price is assumed. MSCI's detached-security rule is used only as a valuation model: it is not an observed price and does not establish the 2018 NIFTY 200 treatment. The prior checkpoint's NSE link ending `listcontract3_07022019173803_ADANIGREEN_outcome_315.pdf` was misattributed (it is a 2019 results filing) and is superseded by these references.

## Frozen base and stress marks

For a strategy holding `Q` AEL whole shares immediately before the 2018-04-05 ex-date open, create an exact entitlement of `Q × 761 / 1000` AGEL shares. Store `floor(entitlement)` as whole child units and the exact Decimal remainder as a fractional beneficial claim. A sale of AEL at the ex-date open does not remove this entitlement; an AEL purchase on the ex-date does not add one.

Base mark: at the 2018-04-05 close, value each AGEL entitlement unit at `(AEL raw close 2018-04-04 − AEL raw close 2018-04-05) / 0.761`. This close-derived mark is first available after 2018-04-05 close; it cannot affect that day's opening orders. Carry it unchanged through 2018-06-17. Mark all entitlement units at AGEL's observed raw close on 2018-06-18. On 2018-06-19, dispose only whole child units at the observed raw regular-session open, apply the unchanged 50 bps slippage and delivery-equity fee helper, and leave the fractional beneficial claim as a nonspendable, nontradable receivable marked at the 2018-06-18 close. Keep that fractional mark fixed until a source-supported trustee payment is found; do not invent a sale date or proceeds.

Pessimistic stress mark: value all entitlement units at zero from the 2018-04-05 ex-date through 2018-06-17; then use the same observed AGEL raw close on 2018-06-18 and the same whole-unit disposal rule and fractional receivable treatment as the base path. This is one specified stress path, not a proven lower bound on final wealth because different NAV can change later target quantities.

In both paths, locked claims enter total NAV and the high-water mark and therefore affect target sizing at later close-based decisions. Claims never count as spendable cash or finance orders. Only actual cash can meet buy affordability. The ex-date entitlement is based on actual pre-open parent quantity. All model and observed marks, whole-unit disposal, residual fraction, and settlement status must be logged separately. Any missing parent/child raw price, date, identity, or permitted execution is a material blocker; no interpolation or future-price backfill is allowed.

## Dividends and costs

Dividend entitlement is quantity held before the ex-date open. Record an ex-date receivable in NAV; do not use it for orders. Use a source-supported payment date where it can be tied to the held event. Otherwise settle at the end of the 30th calendar day after ex-date as a preregistered delayed-cash assumption, with no interest; it is spendable only on the following source session. Report both the outstanding receivable and timing assumption. Compare this assumption with immediate-on-ex-date cash only as an accounting sensitivity, not as strategy selection.

Base execution cost remains 50 bps per side plus the existing current fee helper; cost sensitivities are fixed at 10, 100, and 200 bps per side alongside 50 bps when the supported prefix permits. These are uncalibrated assumptions. No path is ranked or promoted from a short prefix, and no full-period CAGR is inferred.

## Reproduction boundary

Raw source bars and the complete derived signal cache remain local. The published audit code, its source/schema manifest, deterministic generation command, curated certificates, and account/event outputs are the review artifacts. Protocol/model identifier: `NIFTY200-v1.6-AGEL-locked-claim-base-zero-stress`.
