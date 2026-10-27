# Restored-universe NIFTY 50 momentum sensitivity

**Run date:** 2026-10-27
**Data:** Upstox stock daily bars and dividend notices through 2026-10-23; official NSE HDFC history through 2023-07-12  
**Capital:** ₹10,00,000 at the start of the continuous run  
**Risk screen:** maximum historical drawdown 20%  
**Status:** retrospective sensitivity of the post-hoc stock rule; not a validated winner.

## Frozen strategy and universe change

This reruns the existing post-hoc monthly top-10 strategy: positive 12–1 total-return momentum, stock close above its 200-session average, NIFTYBEES close above its 200-session average, equal weight, integer shares, next-session-open execution, and a 95% gross exposure cap. The prior version permanently excluded 13 names with rights, merger, or demerger source records. This sensitivity restores those names to ranking; it does not change signal, sizing, execution, or rebalance rules.

Before replay, `work/audit_stock_action_exclusion_rank.py` ranked all 13 names without treating their hypothetical ranks as trades. Across the four existing rules it recorded 346 potential top-K slots. For this top-10 market-gated rule, 9 excluded names would occupy 84 of 510 selected stock slots across 51 signal dates; the excluded picks appeared on 48 of those dates. The saved NSE action feed shows no such position crossing a non-dividend action date in the next monthly holding interval. 4 candidate slots overlap a saved action date in the 12–1 formation window and 3 in the stock 200DMA window; all flagged slots concern SHRIRAMFIN's Jan 2025 10-to-2 face-value subdivision. Upstox's observed close around that event is price-continuous and consistent with share-unit adjustment, an empirical inference rather than an API guarantee. The action feed is not known to be complete.

The replay computes returns from cached OHLC and dividend-adjusted price histories. It does not model merger or demerger successor shares, rights subscriptions, or unlisted entitlement marks. The absence of known action events in this rule's selected holding intervals makes the replay a useful universe sensitivity; it does not establish complete action accounting.

## Results

Results include the current NSE/Upstox cash-delivery fee model plus 10/20/50 bps per-side slippage. Windows are slices of one continuous account: validation and recent-period start balances are the prior period's ending NAV. `max_drawdown_pct` preserves the account high-water mark; cash earns 0%.

| Window | Slip bps/side | Start value | End value | Return | CAGR | Continuous max drawdown | Fees | Slippage | Orders | 20% screen |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| train_2021_2023 | 10 | ₹1,000,000 | ₹1,745,626 | +74.56% | 21.14% | -13.98% | ₹39,715 | ₹24,099 | 364 | Pass |
| validation_2024 | 10 | ₹1,745,626 | ₹2,105,523 | +20.62% | 20.63% | -15.23% | ₹16,037 | ₹10,069 | 137 | Pass |
| holdout_2025_plus | 10 | ₹2,105,523 | ₹2,226,283 | +5.74% | 3.13% | -14.83% | ₹27,554 | ₹20,167 | 147 | Pass |
| full_2021_2026 | 10 | ₹1,000,000 | ₹2,226,283 | +122.63% | 15.01% | -15.23% | ₹83,306 | ₹54,335 | 648 | Pass |
| train_2021_2023 | 20 | ₹1,000,000 | ₹1,714,265 | +71.43% | 20.39% | -14.82% | ₹39,604 | ₹47,784 | 367 | Pass |
| validation_2024 | 20 | ₹1,714,265 | ₹2,055,202 | +19.89% | 19.90% | -15.41% | ₹15,870 | ₹19,753 | 138 | Pass |
| holdout_2025_plus | 20 | ₹2,055,202 | ₹2,152,306 | +4.72% | 2.59% | -15.22% | ₹26,817 | ₹39,046 | 146 | Pass |
| full_2021_2026 | 20 | ₹1,000,000 | ₹2,152,306 | +115.23% | 14.33% | -15.41% | ₹82,291 | ₹106,583 | 651 | Pass |
| train_2021_2023 | 50 | ₹1,000,000 | ₹1,619,713 | +61.97% | 18.06% | -17.32% | ₹38,801 | ₹116,263 | 363 | Pass |
| validation_2024 | 50 | ₹1,619,713 | ₹1,915,518 | +18.26% | 18.28% | -15.70% | ₹15,159 | ₹46,506 | 136 | Pass |
| holdout_2025_plus | 50 | ₹1,915,518 | ₹1,950,820 | +1.84% | 1.02% | -16.54% | ₹24,996 | ₹89,920 | 143 | Pass |
| full_2021_2026 | 50 | ₹1,000,000 | ₹1,950,820 | +95.08% | 12.39% | -17.32% | ₹78,957 | ₹252,689 | 642 | Pass |

At 10 bps, restoring the excluded names changed the full-period return from +131.04% to +122.63% (-8.41 pp); the 2025–October 2026 return changed from +4.27% to +5.74%. At 50 bps the full-period return changed from +103.80% to +95.08%, and the recent return from +0.99% to +1.84%. This sensitivity shows the stock result depends on universe treatment; it does not establish that either variant is reliable.

The market gate itself was added after earlier results were inspected. The train, 2024 validation, and 2025+ slices are retrospective comparisons, not untouched out-of-sample evidence. The existing 20% screen is not a bound on future losses.

## Reproduction and outputs

- Rank diagnostic: `work/audit_stock_action_exclusion_rank.py`; candidate rows: `outputs/stock_action_exclusion_rank_audit.csv`.
- Portfolio replay: `work/backtest_stock_momentum_action_aware.py`; daily equity, orders, and summaries: `work/backtests/stock_momentum_action_aware/`.
- Consolidated 12-row comparison: `outputs/stock_momentum_action_aware_screen.csv`.
