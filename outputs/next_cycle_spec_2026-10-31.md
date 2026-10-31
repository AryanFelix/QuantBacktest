# Frozen strategy and universe protocol — status at 2026-10-31

## Objective and decision

Target: at least 20% net calendar-time CAGR on ₹10 lakh, unlevered and before personal tax. The former 20% drawdown cap is removed; drawdown is reported as realized risk. The predefined evaluation remains 2018-01-01 through 2026-10-23, with at least 252 completed sessions of signal warm-up. No rule may be retuned to the observed outcomes.

The original NIFTY 200 universe was given the first data-gate timebox. Its dated replay remains uncertified. Per the predeclared fallback, a separate protocol version, **L500-v1**, was evaluated before performance. Its security-session and corporate-action gates also failed. Therefore no universe passed for performance and all eight candidate IDs below remain NOT RUN.

## Protocol amendment and candidate IDs

| Protocol / IDs | Universe | Rule |
|---|---|---|
| NIFTY200-v1: A-M, A-Q, B-M, B-Q | Contemporaneous NIFTY 200 constituents, with temporary components retained for their announced interval | The four frozen A/B signal and rebalance rules below |
| L500-v1: L500-A-M, L500-A-Q, L500-B-M, L500-B-Q | At each calendar-month boundary, select up to 500 eligible securities by mean raw INR turnover over the 63 completed exchange sessions through the preceding close; rank descending, break ties by ISIN. Use only point-in-time listing/identity/session data. No current constituent list or survivor filter. | Same respective A/B signal, portfolio, retention and execution rules as NIFTY200-v1; only the universe changes |

The fallback universe did not reach selection because the available bar feed cannot distinguish a known non-trading session from a missing source record. No liquidity ranking or candidate-specific performance was computed. The four L500 IDs are pending data validation, not failed strategies.

## Frozen signal and portfolio rules

| Rule | Score and eligibility | Portfolio | Schedule |
|---|---|---|---|
| A | 12–1 total return, excluding the latest 21 completed sessions; require positive score | Equal-weight top 20; retain current positions while rank is 1–25, capped at 20; fill remaining slots by descending score and ISIN | Monthly or quarterly |
| B | Mean of 6–1 and 12–1 total return divided by trailing 252-session annualized volatility; both legs omit latest 21 sessions; require positive score and 252 observations | Same as A | Monthly or quarterly |

Monthly decisions use the last exchange session of each month; quarterly decisions use the last session of March, June, September and December. Execute integer-share orders at the next session’s open; reject unaffordable buys and keep residual cash at zero yield. Hold fewer than 20 securities if fewer than 20 qualify. No extra quality, regime, timing, holding-count or allocation variants are authorized in this cycle.

## Data gate and current residuals

The NIFTY 200 current anchor is dated 2026-09-30 and independently reproduces as the disjoint union of the NIFTY 100 and Midcap 100 current anchors. The 2018–2020 official XLS overlap matches 111 events with no one-sided rows. But reverse and forward replay each have 11 failed precondition checks across 11 notice/date batches. The forward state matches the anchor only after failed batches were skipped; 339 intervals are provisional. See the [source-specific replay manifest](nifty200_membership_replay_summary_2026-10-31.json). The four NIFTY200-v1 IDs remain NOT RUN.

For L500-v1, the raw feed has no per-security session-status field, so absent bars cannot be classified as known no-trade versus source gap. Across the evaluation dates it also lists 260 rights, 2 merger and 97 demerger actions. These counts are market-wide; actual candidate exposures are unknown. Entitlements, security identity, session status and listing eligibility have not passed the fallback gate. See the [L500 pre-performance audit](l500_data_gate_2026-10-31.json). The four L500-v1 IDs remain NOT RUN.

The official-source audit could not verify a public, date-complete per-security session-state archive for 2018–2026. The single next action is to assemble a source-backed historical session-state and identity panel from records already available for authorized research, then reconcile economic entitlements for event-affected securities. Keep known non-trading sessions distinct from missing rows; preserve exits and successor identities; do not use stale prices as fills or invent pre-listing history. Run exactly one data-valid universe and at most these four configurations only after all material gates pass. Detailed source notes remain local.

## Performance protocol, only after a gate passes

Use continuous capital from one initial ₹10 lakh allocation and one account high-water mark. Do not reset NAV or drawdown across folds, or average fold CAGRs. Use raw prices for fills; adjusted data may inform signals only after event/identity correctness and no-leakage are validated. Source-backed split, bonus, dividend, rights, merger and demerger accounting must not double-credit distributions or count non-executable adjusted-price jumps as profit.

Freeze the data, identity, action and benchmark hashes; coverage; chronological folds; selection rule; and costs before outcomes. Preserve the evaluation dates above when supported cleanly; any coverage-driven alternative is a separately named diagnostic selected before returns. Use 50 bps adverse slippage per side as the uncalibrated base and show 10/100/200 bps sensitivities. Report integer-share next-open fills, fees, annual and fold outcomes, matched broad TRI and investable passive references, gross/net/cost attribution, turnover, close/OHLC drawdown, recovery, concentration, break-even cost, and order-to-NAV reconciliation.

Repeatedly inspected history is retrospective, not an untouched holdout. If none reaches 20% net CAGR on its full predefined evaluation, report that plainly. No leverage, paid purchase, supplier contact, Upstox API request or live order is part of this protocol.

## Data handling and source-use note

Raw downloads, event rows, member intervals, identity bridges and detailed replay diagnostics stay local outside Git. Publish code, reviewed exception schema, source-file hashes, aggregate gate results and the non-identifying source/date/hash residual manifest. The TejHQ/NSE source-term conflict is recorded in local notes; public accessibility does not resolve that difference.
