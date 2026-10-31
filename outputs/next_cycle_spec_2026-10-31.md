# Next research cycle specification — 2026-10-31

## One justified next action

Acquire access to a licensed historical NIFTY 200/500 point-in-time constituent and event archive, or provide an equivalent auditable dataset. The source, quoted price and license terms require user authorization before any purchase. Do not run the broad-universe grid before the data gate passes. Rotate the exposed Upstox token before making further Upstox requests.

## Gate and universe freeze

After source access, audit effective dates, identifiers, additions/removals, delisted and suspended securities, successor events, daily price continuity, 252-session signal warm-up, dividends, splits, bonuses, rights, mergers/demergers and publication timestamps for any proposed quality data. Select the broadest complete NIFTY 200/500 history only after this audit, then freeze the constituent file and SHA-256 fingerprint before calculating strategy outcomes. If neither universe is complete, stop at the gate and report the remaining source requirements.

## Fixed candidate set, only if the gate passes

Quality data has no point-in-time publication history in the current cache, so omit that branch. Test exactly four rule/configuration combinations:

| Hypothesis | Signal and eligibility | Portfolio | Rebalance |
|---|---|---|---|
| A-M | 12–1 total-return momentum, excluding the latest 21 trading sessions; require positive score | Equal-weight top 20; retain an existing name while its rank is within top 25; otherwise replace | Monthly |
| A-Q | Same as A-M | Same as A-M | Quarterly |
| B-M | `((0.5 × 6–1 return) + (0.5 × 12–1 return)) / trailing 252-session annualized daily volatility`; both momentum legs exclude the latest 21 sessions; require positive score and at least 252 observations | Equal-weight top 20; retain an existing name while its rank is within top 25; otherwise replace | Monthly |
| B-Q | Same as B-M | Same as B-M | Quarterly |

Monthly decisions occur at the last trading session of each calendar month; quarterly decisions use the last trading session of March, June, September and December. Execution is the next session. Rank positive eligible scores descending with ticker as the stable tie-break. Retain existing positions ranked 1–25 first, capped at 20 names, then fill remaining slots from the highest-ranked eligible names. If fewer than 20 positive names qualify, hold fewer names and leave the rest in zero-yield cash.

At each decision, use only then-known prices, membership, corporate actions and financial filings. Execute at the next session’s open, use integer shares, reject unaffordable buys before submitting them, keep residual capital in zero-yield cash, and fail any terminal position without a source-backed executable resolution. The selected research configuration, parameters and input hashes must be frozen before evaluation results are read.

## Evaluation and selection

Use the longest defensible common history after warm-up, including adverse regimes. Define and publish chronological development, validation and later diagnostic windows from the coverage dates before running any configurations. All available history has already been inspected in prior research, so the later segment is not an untouched lockbox; only observations after a future freeze can become prospective paper evidence.

Use continuous chained account value across all folds. Do not reset capital or the high-water mark and do not average fold CAGRs. Score configurations by the net calendar-time CAGR of the continuous development-plus-validation account at the preregistered base cost. Tie-break by higher minimum annual excess return over the matched point-in-time index TRI, then by lower conservative OHLC drawdown, then lower turnover. Do not reinstate a hard 20% drawdown cutoff; report actual risk.

The execution base is 50 bps adverse slippage per side, explicitly **uncalibrated** until timestamped spread/volume evidence supports calibration. Keep 10/100/200-bps stress rows and do not select a cost case after seeing results. Apply modeled current fees uniformly and label that simplification. Report gross/net/cost attribution, break-even per-side cost, matched index and investable passive comparator, annual and rolling outcomes, close drawdown, OHLC envelope, recovery time, concentration, turnover, liquidity/capacity and corporate-action exceptions.

Report a search-adjusted statistic such as Deflated Sharpe only if the complete comparable return matrix, code/data hashes and a defensible dependent-trial count can be recovered. The currently available artifact counts are not independent trials. Otherwise record why the diagnostic is unavailable.

## Stop and paper rule

If no configuration reaches 20% net CAGR over the continuous predefined evaluation while maintaining complete order/NAV/action reconciliation, state that no strategy qualified. Do not invent a winner from a favorable subperiod. At most one qualifying challenger may be frozen for forward paper, with a new immutable version and a start strictly after the freeze; leave all prior paper paths unchanged and do not add old sessions retroactively. No live orders or new leverage.
