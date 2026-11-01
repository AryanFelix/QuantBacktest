# NIFTY 200 first-signal correction protocol — 2026-11-02

**Registered before this cycle's cash-account runs.** Applies to the four frozen A-M, A-Q, B-M, and B-Q configurations only. It does not change the universe, signal windows, rebalance dates, top-20 rule, rank-25 retention, execution, capital, cost or evaluation assumptions.

## Score correction rule

Use source-confirmed event terms to correct the existing TejHQ adjusted-price series only when the local factor did not already apply the event. For a cash dividend `D`, multiply the adjusted price series from the economic ex-date onward by `P/(P-D)`, where `P` is the prior source-session raw close. For a rights event with new-share ratio `r` per old share and full subscription price `K`, use `TERP=(P+r*K)/(1+r)` and multiply the series from ex-date onward by `P/TERP`. Apply multiple verified events once each in date order. A free-right sensitivity `K=0` is a conservative upper bound for A momentum only; B is always recalculated from the corrected daily series because the event-day return changes volatility.

These are signal-history corrections under a total-return/TERP convention. They are not a held-account subscription, entitlement, fill, or cash receipt. The portfolio engine continues to use raw prices and only source-verified entitlements actually owned.

## Event evidence registered for the initial decisions

| Entity and event | Source terms to use | Primary evidence |
|---|---|---|
| CANBK, 2017-02-17 | 1:10; ₹207 full issue price (₹197 premium plus ₹10 face value) | [Canara Bank rights issue archive](https://www.canarabank.bank.in/rights-issue-2017) |
| INDHOTEL, 2017-10-04 | 1:5; ₹75 full issue price (₹74 premium plus ₹1 face value) | [2017 letter of offer](https://www.bseindia.com/downloads/ipo/IHL_041020171506.pdf) |
| KARURVYSYA, 2017-10-12 | 1:6; ₹76 full issue price (₹74 premium plus ₹2 face value) | [2017 letter of offer](https://www.kvb.co.in/docs/rights-issue-17-letter-of-offer-rights-issue-2017.pdf) |
| COLPAL, 2017-12-18 | ₹4 per share; retain the separate 2017-10-25 ₹4 event as already applied by the vendor factor | [MSE action history](https://www.msei.in/corporates/corporate-securities-information/corporate-update/default?symbol=COLPAL&type=4&vmode=vm) |
| ENGINERSIN, 2017-09-11 | ₹0.50 per share; record date 2017-09-12 | [Issuer FY2016–17 report](https://engineersindia.com/storage/2019/01/Annual_Report_2016-17.pdf) |
| TATASTEEL, 2018-01-31 | 4:25 fully paid at ₹510 and 2:25 partly paid at ₹615; aggregate TERP uses both entitlements and full call liability | [SEBI-hosted letter of offer](https://www.sebi.gov.in/sebi_data/attachdocs/jan-2018/1516794446987.pdf) |
| PEL, 2018-01-31 | 1:23 at ₹2,380 full issue price (₹2,378 premium plus ₹2 face value) | [Issuer exchange filing, 2018-02-01](https://www.piramal.com/wp-content/uploads/2020/04/PEL_SE_intimation_Rights_Issue_01022018-2.pdf) |
| RELCAPITAL, 2017-09-05 | One RHFL share per RELCAPITAL share; record date 2017-09-06. For A's endpoint return only, include the separately observed RHFL close at the signal endpoint and the source-confirmed ₹10.50 RELCAPITAL dividend during the window. | [MSE demerger circular](https://www.msei.in/SX-Content/Circulars/2017/August/Circular-5456.pdf), [Nifty Indices notice](https://www.niftyindices.com/Press_Release/ind_prs29082017.pdf) |

The RHFL local EOD series first observes the successor on 2017-09-22. A B score whose fixed volatility window crosses the 2017-09-05 ex-date cannot use a fabricated child mark for 2017-09-05 through 2017-09-21. Its exact score remains unknown; selection may be certified only if its supported return numerator is nonpositive, since the registered volatility denominator is positive.

The 2017-12-14 IDFCBANK vendor event is labeled “Interest Payment”, has record date 2017-12-15, and is attached to common equity ISIN INE092T01019. IDFC's issuer rating filing identifies debt ISIN INE092T08352 as an 8.75% NCD with a 2017-12-17 interest date; CDSL's 2017-09 issuer report lists that debt ISIN. The match of issuer, coupon date, event label, and nearby record date supports a debt-event/mis-mapped-ISIN inference, but the exact original event notice was not found. Preserve that inference and the vendor row in the certificate; do not call it directly source-proven.

## Certification and stopping rule

Recompute each affected A score from its source-corrected series and each affected B score from the complete corrected price path. Keep unresolved scores visible. Certify a selected set only when source-corrected scores or conservative bounds establish the same positive top-20 and any rank-25 retention decision. If a required B mark is absent, do not synthesize it; retain an exact score/status and stop only if its selection bound can change the target. Account orders use the certified target at the next source-calendar session, then raw opens/closes, integer shares, existing fee helper, 50 bp per-side slippage and zero cash yield.

