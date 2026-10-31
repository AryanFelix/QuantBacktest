# NIFTY 200 next-cycle specification — status at 2026-10-31

## Current decision

The target is a net CAGR of at least 20% on ₹10 lakh, unlevered, before personal tax. The former 20% drawdown ceiling remains removed. Preserve the 2018-01-01 through 2026-10-23 evaluation objective, with at least 252 prior trading sessions for signal warm-up. Current price data reaches further, but do not shorten or move the evaluation interval after seeing outcomes.

Public-source data has been acquired for personal research. The data gate is **NOT PASSED** because membership and event accounting are incomplete. No outcome was calculated for the four rules below. The next justified work is the 41 unparsed notices and exceptional/amended event replay documented in the [cycle checkpoint](nifty200_cycle_checkpoint_2026-10-31.md). Do not require supplier outreach or a paid license as a prerequisite for this user-authorized research; document source terms and reasonable-access limits.

## Acquired source coverage

The TejHQ dataset is pinned to revision 2d6629d656fcb715a03b859f7cff8fbd53a7f420. Raw NSE and adjusted daily series each contain 5,114,880 rows from 2016-01-01 to 2026-10-30; actions contain 23,564 rows from 2016-01-05 to 2026-11-06, including future-dated records that must not be used before their actual event dates; symbol history contains 4,934 rows. See the [per-file manifest](tejhq_public_source_manifest_2026-10-31.csv).

The official NIFTY 200 anchor is the 2026-09-30 list with 200 unique symbol/ISIN pairs. Official IndexInclExcl.xls contributes deduplicated events through 2020-07-31. The 79 notices mentioning NIFTY 200 yield 498 parsed rows; 41 notices remain unparsed. A 2018–2020 comparison has 110 exact matches, one company-name alias and 12 March 2020 proposal rows that were later deferred. No reconstructed universe is yet certified.

Keep raw bars separate from adjusted signal series. TejHQ documents price adjustment for splits, bonuses and dividends, but not rights, mergers or demergers. Source-backed issuer evidence and explicit successor entitlements are still required for those cases. New listings with fewer than 252 completed observations remain ineligible for the momentum score until eligible; do not invent prelisting bars. Missing post-listing prices and unresolved successor entitlements are distinct exceptions.

## Frozen candidate set — do not alter

| Hypothesis | Signal and eligibility | Portfolio | Rebalance |
|---|---|---|---|
| A-M | 12–1 total-return momentum, excluding the latest 21 trading sessions; require positive score | Equal-weight top 20; retain a current name while its rank is within top 25 | Monthly |
| A-Q | Same as A-M | Same as A-M | Quarterly |
| B-M | ((0.5 × 6–1 return) + (0.5 × 12–1 return)) / trailing 252-session annualized daily volatility; both momentum legs exclude latest 21 sessions; require positive score and at least 252 observations | Equal-weight top 20; retain a current name while its rank is within top 25 | Monthly |
| B-Q | Same as B-M | Same as B-M | Quarterly |

Monthly decisions use each calendar month's last trading session. Quarterly decisions use the last trading session of March, June, September and December. Execute on the next session's open, use integer shares, reject unaffordable buys, and leave residual capital in zero-yield cash. Rank positive eligible scores descending with ticker as stable tie-break. Retain currently held names ranked 1–25 first, capped at 20, then fill remaining slots from the highest-ranked eligible names. Hold fewer than 20 when fewer than 20 names qualify. Quality remains omitted; add no holding-count, timing, regime or allocation variants.

## Gate before performance

Before calculating any outcome:

1. Resolve dated scheduled, exceptional, amended, deferred and contingent membership changes into an ISIN-level ledger; distinguish announcement, reference-close, effective and retrieval dates.
2. Replay events forward and backward against the 2026-09-30 anchor and reconcile notice/XLS conflicts. Resolve symbol changes, exits, delistings, suspensions, rights, mergers, demergers and successor shares. Keep each historical member eligible for its contemporaneous period; never remove a security because of later information.
3. Verify daily raw-price continuity, security identity, series and trading-session coverage for all historical members, including exits. Never substitute forward-filled prices for executable fills. Reconcile share units and cash/action value.
4. Freeze the exact membership, price, action and benchmark inputs and hashes before calculating performance. Publish coverage, exceptions and the chosen evaluation dates first. The gate remains failed until the material exceptions are resolved.

## Evaluation, only after the gate passes

Use a continuous account with one initial ₹10 lakh allocation and a single high-water mark; do not reset either across folds or average fold CAGRs. Calculate net calendar-time CAGR on the fixed 2018-01-01 to 2026-10-23 evaluation, using the earlier signal warm-up. Define chronological development, validation and later diagnostic windows from source coverage before running any rule. All inspected history is retrospective, not an untouched holdout.

Keep 50 bps adverse slippage per side as the base assumption and show 10/100/200 bps sensitivities. The base is uncalibrated until timestamped spread, volume and order-size evidence supports calibration; do not select costs after seeing returns. Apply modeled fees uniformly and disclose that simplification. Report the four rules against matched NIFTY 200 TRI and an executable passive comparison, including annual/fold outcomes, drawdown and recovery, concentration, turnover, gross/net/cost attribution, break-even costs and ledger-to-NAV reconciliation.

If no rule reaches 20% net CAGR on the continuous evaluation with complete accounting, say so. Do not manufacture a winner from a favorable subperiod. Do not claim a newly held-out sample from repeated historical analysis. No live orders, leverage, paid data or supplier outreach. Do not use the exposed Upstox token.

## Source-use caveat

TejHQ's published terms allow personal research/backtesting but prohibit raw redistribution. NSE website terms separately restrict storing and using website content for simulation. Record this source-use conflict; do not claim that public accessibility resolves it. Keep raw downloads and row-level event records outside Git. Push only collectors/parsers, file-level source manifests, tests and aggregate coverage/results.

