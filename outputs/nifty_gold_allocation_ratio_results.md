# NIFTY/Gold active-sleeve allocation-ratio results

**Run:** 2026-10-27 · **Capital:** ₹10 lakh · **Primary costs:** modeled delivery fees plus 50 bps adverse slippage per side

## Finding

The 198-rule allocation/frequency/cap search did not find a training-period winner. Every 2015–2019 candidate lost money after modeled costs. Of 198 candidates, 180 passed the training OHLC screen; the mechanical “highest return among passes” rule picked quarterly NIFTY-only exposure with a 30% cap, but that rule still lost 0.60% in training. Its later returns were materially below the fixed monthly 50/50 active-sleeve reference at a 45% cap. Do not promote this selected challenger.

## Frozen selection versus reference

The test windows start with fresh ₹10 lakh. “Continuous 2015+” carries the same account through the full path. Returns are net of modeled fees and the listed slippage; OHLC bounds are order-ledger audits at 50 bps. The reference is the already-used 50/50 NIFTY Donchian 55/20 and Gold SMA200 mix, rebalanced monthly, with a 45% gross cap.

| Window | Selected rule return | Selected OHLC bound | 50/50 reference return | Reference OHLC bound |
|---|---:|---:|---:|---:|
| 2015–2019 training | -0.60% | -5.76% | -7.28% | -13.39% |
| 2020–2022 validation | +15.68% | -9.97% | +23.19% | -13.77% |
| 2023–2026 holdout | +5.86% | -3.21% | +42.45% | -14.83% |
| 2020+ continuous | +23.41% (₹12.34L) | -9.97% | +77.52% (₹17.75L) | -14.83% |
| 2015+ continuous | +22.99% (₹12.30L) | -9.97% | +65.19% (₹16.52L) | -15.82% |

All reported 50-bps selected/reference paths passed the historical -20% OHLC screen. The selected rule had a lower historical drawdown envelope because its exposure cap was only 30%; it also captured much less of the later NIFTY/Gold rise. An OHLC pass is not a guarantee or enforceable drawdown limit.

## Cost sensitivity

Each cell is net return after fees and the stated slippage. Only the frozen selection and fixed reference were rerun. The 10/100-bps OHLC envelopes were not calculated; cost-row drawdowns are close-to-close only.

| Window | Rule | 10 bps | 50 bps | 100 bps |
|---|---|---:|---:|---:|
| 2020+ | Training-selected quarterly NIFTY-only, 30% cap | +25.33% | +23.41% | +21.05% |
| 2020+ | Monthly 50/50 reference, 45% cap | +95.57% | +77.52% | +57.21% |
| 2023+ | Training-selected quarterly NIFTY-only, 30% cap | +6.91% | +5.86% | +4.57% |
| 2023+ | Monthly 50/50 reference, 45% cap | +47.65% | +42.45% | +36.19% |
| 2015+ | Training-selected quarterly NIFTY-only, 30% cap | +27.99% | +22.99% | +17.01% |
| 2015+ | Monthly 50/50 reference, 45% cap | +99.10% | +65.19% | +30.64% |

At 100 bps, the reference's continuous 2015+ close drawdown is -22.19%, outside the user's 20% screen. It has no matching 100-bps OHLC audit, so no stronger intraday-risk conclusion is available for that cost case.

## Reproduction and limits

- Frozen rules and selection protocol: [method](nifty_gold_allocation_ratio_method.md).
- Full 990-row grid: [sensitivity CSV](nifty_gold_allocation_ratio_sensitivity.csv).
- Training and selected/reference OHLC replays: [training audits](nifty_gold_allocation_ratio_training_ohlc.csv), [later-window audits](nifty_gold_allocation_ratio_oos_ohlc.csv), and [selection JSON](nifty_gold_allocation_ratio_selection.json).
- Selected/reference cost grid: [cost sensitivity CSV](nifty_gold_allocation_ratio_cost_sensitivity.csv).
- Runner: `work/sensitivity_nifty_gold_allocation_ratio.py`; per-run equity, orders, and summaries are in `work/backtests/nifty_gold_allocation_ratio/` (local research cache).

The sample was already inspected, so chronological windows are not a fresh lockbox. The instrument P&L is based on ETF prices; Gold ETF distribution completeness, tax, cash yield, live spreads, and market impact remain unresolved. Fees and slippage are modeled, not broker fills. This is a rejected research challenger, not investment advice or a live-trading instruction.
