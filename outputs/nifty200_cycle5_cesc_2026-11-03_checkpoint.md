# NIFTY 200 cycle 5 checkpoint — 2026-11-03

## Four fixed candidates — no rankable winner

No full-period leader is established: all four paths stop on unresolved dependencies, so the 20% CAGR objective is untested. NAV is after registered fees and slippage at 50 bps per side. The portfolio selects 20 positive-score names, retains prior names through rank 25, targets 5% each, and executes next-session raw opens.

| Candidate and frozen signal | Valid through | Ending NAV | Max drawdown | Excess vs matched gross TRI |
|---|---:|---:|---:|---:|
| NIFTY200-A-M — Rule A: 12-month total return ending 21 source sessions before the signal; monthly decisions. | 2019-10-15 | ₹791,510 | -27.08% | -24.96 pp |
| NIFTY200-A-Q — Rule A: 12-month total return ending 21 source sessions before the signal; quarterly decisions. | 2020-03-31 | ₹697,517 | -43.65% | -9.33 pp |
| NIFTY200-B-M — Rule B: mean of lagged 6- and 12-month returns divided by annualized volatility over the exact 252-return window; monthly decisions. | 2019-09-30 | ₹895,519 | -18.78% | -15.39 pp |
| NIFTY200-B-Q — Rule B: mean of lagged 6- and 12-month returns divided by annualized volatility over the exact 252-return window; quarterly decisions. | 2019-09-30 | ₹1,035,737 | -18.51% | -1.37 pp |

The common cost endpoint is 2019-09-30. The fixed 10/50/100/200 bps cases, timing sensitivities, costs, turnover, recovery, concentration, and finite blockers are in the result JSON/CSVs. R1 remains NOTRUN.

## Protocol and evidence

Protocol: `NIFTY200-v1.10-dated-eligibility-multichild-demergers-and-debenture-bound`. Capital is ₹10 lakh continuous, unlevered, zero cash yield, next-session raw-open integer-share execution, and the existing four frozen schedules. Calendar and membership replay evidence remain in `nifty200_benchmark_calendar_reconciliation_2026-11-01.json` and `nifty200_replay_residual_delta_2026-11-01.json`. CHOLAFIN extraction coverage is `nifty200_cholafin_source_extraction_coverage_2026-11-03.json`. The listing ledger and detailed source rows remain local; aggregate classifications and SHA-256 manifest are published.

CESC's October 2018 scheme grants 6 Spencer's Retail and 2 CESC Ventures shares per 10 CESC shares. Both children first traded on 2019-01-25, so a signal endpoint before that date remains unresolved. See `nifty200_cesc_composite_scheme_2018-10-30.md`.

GRUH's 1:1 bonus shares were allotted on 2018-06-08. Its merger into Bandhan was effective 2019-10-17 with 568 Bandhan shares per 1,000 GRUH shares; successor shares were allotted October 21, but the current account model does not resolve successor-share listing permission and claim marking. The A-M held-position path therefore stops at the last observed GRUH close. See `nifty200_gruh_merger_position_mark_review_2026-11-03.md`.

The Britannia 2019-08-22 bonus debenture has a ₹37.20 undiscounted contract upper bound at non-negative yield. It only clears signal contributions whose maximum return numerator is non-positive and does not value a held NCD. Source terms are documented in `nifty200_britannia_debt_distribution_bound_2026-11-03.md`.

## Remaining blockers

See `nifty200_cycle5_cesc_2026-11-03_dependency_blockers.json` for each path's first signal and account stop, exact date, identity, input, and reason. Raw price rows, order traces, and detailed source records remain local.
