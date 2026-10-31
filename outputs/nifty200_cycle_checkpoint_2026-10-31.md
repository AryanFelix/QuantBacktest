# NIFTY 200 replay and L500 gate checkpoint — 2026-10-31

## Decision

**No new broad-universe strategy result was produced, and no strategy has demonstrated 20% net CAGR over the predefined full evaluation.** The NIFTY 200 event ledger is useful but uncertified. The predeclared L500-v1 fallback failed its pre-performance data gate. All eight broad-universe configurations remain NOT RUN.

The objective remains at least 20% calendar-time CAGR after modeled costs on ₹10 lakh, unlevered and before personal tax. There is no hard drawdown ceiling. The evaluation dates remain 2018-01-01 through 2026-10-23, with signal warm-up before the start date.

## Frozen configurations

| Universe / ID | Rule | Status |
|---|---|---|
| NIFTY 200 — A-M | Positive 12–1 total-return momentum, omitting latest 21 sessions; equal-weight top 20, retain ranks 1–25; monthly | NOT RUN — membership/action gate |
| NIFTY 200 — A-Q | Same signal and portfolio; quarterly | NOT RUN — membership/action gate |
| NIFTY 200 — B-M | Mean of 6–1 and 12–1 total returns divided by trailing 252-session annualized volatility; both legs omit latest 21 sessions; require 252 observations; monthly | NOT RUN — membership/action gate |
| NIFTY 200 — B-Q | Same signal and portfolio; quarterly | NOT RUN — membership/action gate |
| L500-v1 — L500-A-M / L500-A-Q | Same A rules; point-in-time top-500 raw-turnover universe | NOT RUN — pre-performance data gate |
| L500-v1 — L500-B-M / L500-B-Q | Same B rules; point-in-time top-500 raw-turnover universe | NOT RUN — pre-performance data gate |

The fallback protocol, turnover lookback and execution rules are recorded in the [next-cycle specification](next_cycle_spec_2026-10-31.md). No current constituent list or current-survivor screen was substituted.

## What the source evidence established

- The pinned TejHQ revision `2d6629d656fcb715a03b859f7cff8fbd53a7f420` contains 34 files and 305,712,150 bytes. Raw and adjusted prices each have 5,114,880 matching rows from 2016-01-01 to 2026-10-30. The action feed has 23,564 rows through 2026-11-06; no action after the 2026-10-23 evaluation cutoff was applied.
- The official NIFTY 200 page and the exact union of current NIFTY 100 and Midcap 100 component anchors support 2026-09-30 as the last-trading-day-of-previous-month anchor. Each component list has 100 unique ISINs; their disjoint union equals the 200-member parent anchor. The parent and component file hashes are in the [replay summary](nifty200_membership_replay_summary_2026-10-31.json).
- The notice corpus contains 79 NIFTY 200-mentioning releases with numbered-table rows and 41 without them. All 41 exceptional notices are triaged: 16 parent prose/index-list changes, 22 descendant-only/no parent change, and 3 amendment/deferment cases. Descendant-only Alpha30/Momentum30/Quality30 changes are excluded from parent membership. The KWIL multi-date notice and the 2020 deferment chain have event-specific handling.
- The ordinary table parser plus reviewed exceptions yields 379 operative parent events and 20 identity bridges. The BDL 2-for-1 split has a source-backed old/new ISIN bridge. Temporary extra components are preserved; event-boundary membership ranges from 200 to 204.
- The independent 2018–2020 official XLS comparison has 111 exact matches, zero XLS-only events and zero operative-PDF-only events. This overlap is a check on those deltas, not proof of later archive completeness.

## Why neither universe passed

**NIFTY 200:** Reverse and forward replay each have 11 failed state-precondition checks across 11 notice/date batches (22 checks total). The forward state happens to equal the 2026-09-30 anchor after skipped batches, so equality alone is not certification. All 339 generated member intervals are `PARTIAL_UNCERTIFIED`. The finite source/date/hash list is in the [replay summary](nifty200_membership_replay_summary_2026-10-31.json); row-level diagnostics remain local. No NIFTY 200 performance or NAV was calculated.

**L500-v1 fallback:** The market-wide raw feed has 5,114,880 rows over 2,665 distinct dates, but no per-security trading/no-trade/status field. A missing security-session row therefore cannot be distinguished from a source gap using this feed alone. Its action file also contains 260 rights, 2 merger and 97 demerger records during the evaluation period. Those are market-wide records, not a claim that each affects a candidate; candidate-level entitlements have not been reconciled. The fallback gate stopped before universe formation, signals or P&L. See the [machine-readable gate](l500_data_gate_2026-10-31.json).

Both pre-performance gates failed, so the cycle’s eligible universe for performance testing is **none**. No result from this cycle can support the 20% objective. The prior NIFTY 50 momentum diagnostic remains context only at 11.90% net CAGR versus 9.66% NIFTY 50 TRI over its separately defined period; it is not an outcome for these frozen candidates.

## Single next research action

The official-source audit did not verify a public, date-complete session-state panel for 2018–2026. The next action is to assemble a source-backed historical per-security session-state and identity panel from records already available for authorized research, distinguishing traded, known no-trade, suspension/delisting and missing source rows; then reconcile rights, merger and demerger entitlements for those identifiers. Rerun the pre-performance gates before forming an L500 universe or calculating any strategy return. The detailed source note remains local.

## Reproduction and handling

Run `python work/reconstruct_nifty200_membership.py`, then `python work/replay_nifty200_membership.py`, and `python work/audit_l500_data_gate.py`. Their `--self-check` options cover the parser/replay/gate invariants. Raw bars, notices and row-level event/replay files stay under the ignored local `work/data/public_research/` cache; only source-file hashes, aggregate counts and source-specific replay residual references are published.

The TejHQ public dataset terms and NSE website terms differ on storing and using sourced data for simulation. This conflict is documented in a local source note and is not resolved by public accessibility. No paid purchase, supplier contact, Upstox request, live order or leverage was used.
