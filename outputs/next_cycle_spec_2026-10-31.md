# Frozen strategy and universe protocol — amendment registered 2026-10-31

## Objective and decision

Target: at least 20% net calendar-time CAGR on ₹10 lakh, unlevered and before personal tax. The former 20% drawdown cap is removed; report realized drawdown. Evaluation: 2018-01-01 through 2026-10-23, with the frozen A/B rules below. No rule may be retuned to outcomes.

NIFTY 200 remains preferred, but its dated membership replay is uncertified. L500-v1 cannot identify an absent security row without assuming it means either no-trade or a source failure. Before calculating L500 candidate counts, ranks or P&L, register one operational-eligibility amendment, L500-v2. L500-v1 remains unrun; no performance outcome was used to choose v2.

## Protocols and candidate IDs

| Protocol / IDs | Universe | Status |
|---|---|---|
| NIFTY200-v1: A-M, A-Q, B-M, B-Q | Point-in-time NIFTY 200 members, including temporary components for their announced interval | NOT RUN; replay residuals |
| L500-v1: L500-A-M, L500-A-Q, L500-B-M, L500-B-Q | Original top-500 raw-turnover fallback | Preserved, NOT RUN; operational identity of missing rows is unknown |
| L500-v2: L500v2-A-M, L500v2-A-Q, L500v2-B-M, L500v2-B-Q | Point-in-time NSE cash EQ/BE series ranked by mean raw INR turnover over the prior 63 completed source sessions through the decision close; descending turnover, then ISIN; up to 500 | Preregistered dependency audit only; no P&L |

L500-v2 eligibility is contemporaneous: every expected raw OHLC and turnover observation must be positive, finite, valid OHLC, and genuinely present for all 63 liquidity sessions and the applicable signal window. Any absent or ambiguous required observation is unknown and makes that identity ineligible at that decision date. A change of ISIN is not stitched unless a reviewed bridge supports it. Use no current constituents, future survival, later cleanliness or future event flags. If two series produce ambiguous same-ISIN observations on a session, that identity is ineligible for that session.

## Frozen signals, portfolio and schedules

| Rule | Score | Required adjusted-price observations |
|---|---|---|
| A | Adjusted 12–1 total return, excluding the latest 21 completed sessions; require positive score | Every adjusted close from session t−252 through t−21 and resolved event/identity terms across the interval |
| B | Mean of adjusted 6–1 and 12–1 total returns divided by annualized volatility of the trailing 252 adjusted close-to-close returns; both return legs omit latest 21 sessions; require positive score | Every adjusted close from t−273 through t−21 for the 252-return volatility calculation, and every close from t−252 through t−21 for both return legs; event and identity terms resolved |

For both rules, equal-weight the top 20; retain current positions while rank is 1–25, cap at 20, then fill vacancies by descending score and ISIN. Monthly signals use the final exchange session of each month; quarterly signals use final March, June, September and December sessions. Execute integer-share orders at the next session open; reject unaffordable buys and credit cash at 0%. Hold fewer than 20 securities if fewer qualify. These four configurations are fixed; no additional universe or parameter variants are authorized.

## Source corrections and current gates

The August 2021 low-text notice ind_prs23082021.pdf (SHA-256 c9b9feef248ca89f7d8c8f12009e3d5c409eb4d6c793eee061fb93bf0af1231e) was visually reviewed on all 29 pages. Page 14 has six NIFTY 200 exclusions and six inclusions effective 2021-09-30; these rows were restored. The low-text September 2018 ind_prs24092018.pdf was reviewed on all three pages and classified as CPSE-only, no parent-index change. The extraction ledger now records per-document text/page counts and a manual-review disposition, so an empty notice cannot silently be classed irrelevant.

That source correction reduced NIFTY 200 replay failures from 11 batches / 22 directional checks to 8 batches / 16 checks. All 8 remaining failed checks occur in both directions; these are cascading batch failures, not 8 independent missing archives. The 2018–2020 official XLS/PDF overlap is 111 matches with no one-sided rows. See nifty200_membership_replay_summary_2026-10-31.json; raw event rows stay local.

The finite 18-date calendar audit found all dates to be actual NSE cash sessions: 14 special sessions and 4 regular sessions. Official NSE daily EOD files add 37,576 EQ/BE rows for 3,481 identities. All 18 NSE NIFTY 50 TRI and NTR marks match local reference values exactly. The supplement leaves 117 adjusted factors unresolved (54 action terms, 47 nearby history, 11 factor ratios, 3 unexplained jumps, 2 identity bridges). Special-session files are daily aggregates; intraday venue paths are not reconstructed. See the aggregate calendar CSV and summary JSON.

## L500-v2 dependency audit; no performance authorization yet

Use the raw market calendar plus the 18 verified NSE sessions as a working calendar, not a claim of global completeness. Calculate only point-in-time eligibility, fixed signal ranks, intended next-session entry/exit identities, position intervals and daily valuation dependencies. For each unresolved input, save rule, date, entity, source, reason and affected signal/order/position locally; publish aggregate coverage only.

A missing candidate bar before entry can make that candidate ineligible under this version. A missing fill, held-position mark, identity transition or entitlement after entry remains a material unresolved dependency: do not invent a fill, zero a missing holding, use a stale mark, retroactively exclude a name, or omit a ranking-changing signal. Market-wide rights/merger/demerger counts are not strategy blockers unless they touch an actual required signal or position. Any path with a material unresolved dependency is invalid. Run no strategy outcomes until the dependency audit shows the selected universe and all ranking-changing signals/orders/valuation paths are supported.

## Performance protocol, only after dependencies pass

Use continuous ₹10 lakh capital, aligned calendar CAGR, one account high-water mark and no cash yield. Raw prices determine next-session integer-share fills. Freeze data, identity, action and benchmark hashes before outcomes. Base adverse slippage is 50 bps per side; show 10/100/200 bps uncalibrated sensitivities. Include fees, order-to-NAV reconciliation, matched TRI and passive references, annual/fold outcomes, gross/net/cost attribution, drawdown/recovery, turnover, concentration and break-even costs.

Any coverage-driven shorter diagnostic must be selected and registered before outcomes and cannot establish a full-period 20% claim. No leverage, paid purchase, supplier contact, credential inspection, Upstox API request, exposed-token use or live order is authorized in this cycle. Raw downloads and detailed entity-level dependencies remain local; only code, extraction coverage, source hashes and aggregate results are published.
