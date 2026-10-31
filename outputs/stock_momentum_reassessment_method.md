# NIFTY 50 cross-sectional momentum reassessment — 2026-10-31

## Scope and frozen comparison

The earlier restored-universe top-10 12–1 screen returned 12.39% CAGR for 2021–October 2026 at 50 bps per side, and 1.02% in 2025–October 2026. This bounded rerun tests three fixed signals (6–1 return; 12–1 return; equal blend of 6–1 and 12–1 returns divided by trailing annualized volatility), top 5/10/15 names, and two exposure policies. The second policy cuts the risky sleeve to 50% when 63-session NIFTYBEES realized volatility exceeds its prior 252-session 90th percentile or its close is at least 10% below the 126-session high. All cases rebalance monthly, require positive signal momentum, use equal weights, and keep a two-rank exit buffer. Both all-saved and 13-name action-restricted universes are reported; training selection uses only the all-saved universe. No parameters were added after seeing the results.

Point-in-time NIFTY 50 memberships are reconstructed from NSE notices. The cached Upstox daily files cover 70 symbols, not the full NIFTY 500. Stock rankings use dividend-adjusted histories; execution uses cash OHLC, integer shares, next-session opens, the existing modeled cash-delivery fee helper, and 10/50 bps adverse slippage per side. Zero cash yield is assumed. Strategy returns are matched to NIFTY 50 TRI over the same date windows. The currently available 2025–October 2026 period has already been inspected in earlier work and is not a fresh holdout.

The complete candidate matrix and monthly picks are in `stock_momentum_reassessment_frontier.csv` and `stock_momentum_reassessment_picks.csv`. For transparency, the table below ranks all-saved-universe candidates using 2021–2023 training CAGR at 50 bps; later periods remain separate. Action-restricted sensitivity rows are in the frontier CSV.

| Rank | Strategy | Train CAGR | 2024 CAGR | 2025+ CAGR | Full CAGR | Full close / OHLC DD |
|---:|---|---:|---:|---:|---:|---:|
| 1 | all_saved__momentum_12_1_top15_full_exposure_buffer2 | 23.88% | 11.98% | -4.94% | 11.90% | -26.63% / -29.66% |
| 2 | all_saved__momentum_12_1_top15_half_exposure_in_stress_buffer2 | 22.66% | 1.94% | -8.16% | 8.35% | -28.47% / -29.48% |
| 3 | all_saved__momentum_12_1_top10_full_exposure_buffer2 | 21.20% | 17.60% | -4.30% | 11.86% | -28.49% / -30.67% |
| 4 | all_saved__momentum_12_1_top10_half_exposure_in_stress_buffer2 | 20.88% | 6.46% | -7.22% | 8.71% | -27.73% / -29.33% |
| 5 | all_saved__vol_adjusted_blend_6_12_top15_full_exposure_buffer2 | 19.80% | 18.02% | -7.63% | 10.03% | -23.76% / -25.78% |

## Training-only selected candidate

The highest training-CAGR row at 50 bps is `all_saved__momentum_12_1_top15_full_exposure_buffer2`. Its frozen later-window results are:

| Period | CAGR | NIFTY 50 TRI CAGR | Excess | Close MDD | OHLC bound | Fees | Slippage |
|---|---:|---:|---:|---:|---:|---:|---:|
| train_2021_2023 | 23.88% | 16.95% | +6.93 pp | -21.72% | -24.64% | ₹43,238 | ₹103,703 |
| validation_2024 | 11.98% | 10.04% | +1.93 pp | -17.46% | -19.19% | ₹14,767 | ₹36,447 |
| holdout_2025_plus | -4.94% | -1.50% | -3.44 pp | -26.63% | -29.66% | ₹35,439 | ₹100,146 |
| full_2021_2026 | 11.90% | 9.66% | +2.24 pp | -26.63% | -29.66% | ₹93,443 | ₹240,296 |

This is an exploratory, finite grid rather than evidence of a durable winner. Any discrepancy between its training result and the later windows is evidence against extrapolating the training CAGR. Each full-period rule and the prior 20.72% NIFTY/Gold result are retrospective comparisons across repeatedly inspected data.

## Conservative intraday envelope and action checks

For every strategy/day, the audit marks pre-trade and post-trade holdings at available opens, highs, and lows, then reconciles reconstructed close NAV to the shared simulator. The OHLC drawdown assumes each held asset reaches its high before the combined portfolio reaches its low, which is conservative and not a realizable intraday path. Known NSE split, bonus, rights, merger, demerger, or scheme-action events overlapping planned holding intervals are counted in the CSV. The existing Upstox audit finds split/bonus close continuity consistent with backward unit adjustment, but this is not an API guarantee; merger, demerger, rights, dividend, successor-share, and historical unit coverage are not fully resolved. The action-restricted policy excludes the 13 names already flagged for unresolved rights/merger/demerger paths. Neither policy makes corporate-action accounting complete.

## Reproduction and limits

Run `python work/backtest_stock_momentum_reassessment.py` from the repository root. The script asserts that signal dates precede execution, gross target weights do not exceed 100%, OHLC replay close NAV reconciles to the cash simulator, and the envelope remains non-positive relative to running highs. This is not independent verification: data through 2026-10-23 and earlier result slices have already been inspected. Costs use a current modeled schedule, slippage is assumed rather than measured, cash earns zero, and there is no derivatives financing or margin model.
