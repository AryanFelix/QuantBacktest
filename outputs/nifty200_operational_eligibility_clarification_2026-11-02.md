# NIFTY 200 eligibility clarification (pre-outcome)

**Registered:** 2026-11-02, before this cycle recomputes any strategy account performance.
**Protocol:** NIFTY200-v1.4-eligibility; retains the four frozen NIFTY200 A-M, A-Q, B-M and B-Q rules and their original evaluation dates, signal schedules, ranking, retention, execution, fee and capital-carry assumptions.

## Statuses

- `RULE_INELIGIBLE`: authoritative listing evidence shows the issuer had not listed, and no verified predecessor identity provides a continuous prior instrument, at the first required session of the unchanged lookback. The candidate receives no score. No pre-listing price is created and no shorter window is substituted.
- `VALID_SCORE`: every required adjusted close, identity, and material signal event is observed and resolved under the frozen rule.
- `UNKNOWN_DATA`: the candidate is not proven rule-ineligible, but one or more required prices, identities, adjustment factors, or event terms are missing or unresolved. It cannot be ranked as a known score or replaced silently.

## Unchanged windows and application

At every scheduled decision, rule A requires the existing 252-session lagged-return inputs over `[t-252, t-21]`. Rule B keeps its registered `[t-273, t-21]` price/volatility input window and 252 log returns; no denominator, skip, or warmup is shortened. Listing status is evaluated for each candidate and date with the same rule. The first observed vendor bar is not evidence of the original listing date. A verified predecessor chain can establish continuity; an unverified alias cannot.

Only authoritative dates presently established in this clarification are DMART (2017-03-21), HUDCO (2017-05-19), and AUBANK (2017-07-10), recorded with source URLs in `nifty200_listing_evidence_2026-11-02.csv`. For all other candidates, a missing lookback remains `UNKNOWN_DATA` unless independently sourced listing evidence is added before outcome review. This is a status distinction only; it does not change the four strategy formulas or choose a universe variant.

## Source evidence

- NSE lists DMART with date of listing 21-Mar-2017: https://www.nseindia.com/get-quote/equity/DMART/Avenue-Supermarts-Limited
- NSE's IPO table 2.6 lists HUDCO on 19-May-2017: https://nsearchives.nseindia.com/content/us/ismr_full2019.pdf
- NSE lists AUBANK with date of listing 10-Jul-2017, corroborated by the issuer's FY2017-18 annual report: https://www.nseindia.com/get-quote/equity/AUBANK/AU-Small-Finance-Bank-Limited and https://www.aubank.in/assets/Digital/pdf/AU%20Bank%20AR%202017-18.pdf

The first A-M decision (2018-01-31) has a first required session of 2017-01-31. The sourced DMART and HUDCO IPO dates therefore make those two missing windows `RULE_INELIGIBLE` under the existing 252-session rule. This statement is a protocol/data classification, not a strategy return result. All other unresolved inputs remain visible pending source-based review.

