# Britannia bonus debenture signal bound — 2026-11-03

At the 2019-09-30 signal, the vendor labels Britannia's 2019-08-22 action as a bonus but omits a share ratio. Exchange and issuer evidence identifies one ₹30 debenture for each eligible equity share, at 8% annual coupon over three years. The NCD was allotted on 2019-08-28 and was listed only on 2019-10-09; its price was therefore not used as a September mark.

For a shareholder entitled on the ex-date, total undiscounted contractual cash flows are at most ₹37.20 per old equity share: ₹30 principal plus three ₹2.40 coupons. At a non-negative required yield, this is an upper bound on the claim value before redemption. The signal audit adds that maximum only to a return window that begins before the ex-date and ends after it. It does not turn the NCD into an equity share, invent a market quote, or change account holdings.

The classifier also checks adjacent raw close, adjusted close, and cumulative factors; the bonus event must not change common-equity units, and factors must remain flat through the score endpoint. A and B use the bound only when their maximum return numerator is non-positive. If the bound is positive or the price/factor scope check fails, the candidate remains unresolved. A held-position event still requires an actual NCD valuation and blocks account execution; the signal-ranking bound does not settle an entitlement mark.

Sources:

- [NSE Britannia corporate actions](https://www.nseindia.com/companies-listing/corporate-filings-actions?symbol=BRITANNIA): 2019-08-22 ex-date, 2019-08-23 record date, one debenture for one share.
- [NSE allotment filing](https://nsearchives.nseindia.com/corporate/BRITANNIA_28082019165059_OUTCOMEBONUSDEBENTURECOMMITTEEALLOTMENT_260.pdf): 24.03 crore debentures at ₹30, 8% coupon, allotted 2019-08-28.
- [Britannia FY2019–20 annual report](https://www.bseindia.com/bseplus/annualreport/500825/5008250320.pdf): three-year terms and NCD listing/redemption disclosures.

The exact action row and daily price rows remain in the local research cache. This note records the bound, not a priced or investable debenture position.
