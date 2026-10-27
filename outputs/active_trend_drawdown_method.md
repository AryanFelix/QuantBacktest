# NIFTY/Gold active-trend drawdown throttle

- **Run date:** 2026-10-27
- **Starting capital:** ₹10 lakh per fresh run
- **Risk screen:** maximum simultaneous daily OHLC drawdown bound of 20%
- **Execution:** prior-close signals, next-session open fills, whole ETF units, modeled Upstox/NSE delivery charges, 50 bps adverse slippage per side, 0% cash yield, terminal liquidation
- **Data cutoff:** 2026-10-23

## Frozen comparison

The portfolio uses the quarterly fixed 50/50 active sleeves: NIFTYBEES Donchian 55/20 and GOLDBEES SMA200. It rebalances when either sleeve signal changes and at quarter end. A close-marked NAV drawdown trigger schedules a cap reduction for the next open; recovery at half the trigger schedules the original cap for the next open.

Five candidates were compared: fixed 70%, fixed 40%, and 70%-to-35% caps triggered at 8%, 10%, or 12% close drawdown, recovering at 4%, 5%, or 6%, respectively. Training uses 2014-01-02 through 2022-12-30. GoldBeES has no bars before 2015, so its sleeve remains inactive until its trend signal can be formed; the NIFTY sleeve can trade on its own earlier signal. Selection is the highest net training return among candidates whose conservative simultaneous OHLC drawdown bound stays at or above -20%. The selected rule is then replayed, with every candidate retained as context, on a fresh ₹10 lakh account over 2023-01-01 through 2026-10-23.

## Results

| Candidate | Segment | Net return | Close MDD | OHLC bound | Fees | Slippage | Trigger / recovery events |
|---|---|---:|---:|---:|---:|---:|---:|
| Fixed 70% | Training | +31.11% | -17.18% | -19.07% | ₹12,085 | ₹249,697 | 0 / 0 |
| Fixed 40% | Training | +19.99% | -13.67% | -14.50% | ₹10,834 | ₹191,997 | 0 / 0 |
| 70%-to-35%, trigger 8% / recover 4% | Training | +19.04% | -15.06% | -17.17% | ₹11,423 | ₹215,110 | 2 / 2 |
| 70%-to-35%, trigger 10% / recover 5% | Training | +25.83% | -15.06% | -18.51% | ₹11,919 | ₹240,245 | 1 / 1 |
| 70%-to-35%, trigger 12% / recover 6% | Training | +25.13% | -15.59% | -18.62% | ₹12,076 | ₹243,975 | 1 / 1 |
| Fixed 70% | 2023+ replay | +55.71% | -14.24% | -16.81% | ₹3,356 | ₹66,489 | 0 / 0 |
| Fixed 40% | 2023+ replay | +37.80% | -11.70% | -13.86% | ₹2,958 | ₹48,449 | 0 / 0 |
| 70%-to-35%, trigger 8% / recover 4% | 2023+ replay | +57.99% | -12.98% | -14.66% | ₹3,163 | ₹56,923 | 1 / 0 |
| 70%-to-35%, trigger 10% / recover 5% | 2023+ replay | +57.60% | -13.20% | -14.96% | ₹3,185 | ₹56,821 | 1 / 0 |
| 70%-to-35%, trigger 12% / recover 6% | 2023+ replay | +55.97% | -14.10% | -16.81% | ₹3,179 | ₹56,499 | 1 / 0 |

Fixed 70% wins the frozen training selector, so the drawdown throttle is not promoted as the selected strategy. The 8% throttle has a better return and smaller OHLC bound in the later slice, but that result is retrospective: the broader 2023+ history was already inspected. It remains a non-selected comparator in paper revision 9.

## Accounting and limits

- Fixed-cap active paths were reconciled against the shared portfolio simulator. Existing passive 45% and 60% paths were also rechecked after extending the drawdown simulator.
- The order-ledger audit reproduces close NAV within ₹0.03 for every path. The OHLC envelope assumes all held highs precede all held lows within each day; it is a conservative envelope, not an observed intraday path or a future loss guarantee.
- Fees use the current modeled delivery schedule uniformly across historical periods. Slippage is a fixed stress assumption, not measured market impact. Taxes, ETF cash distributions beyond the existing NIFTYBEES event list, and cash yield are excluded.
- The holdout is a chronological pseudo-OOS replay, not a pristine lockbox, because the test history and related strategy family were examined in prior research. Drawdown triggers react after a close and cannot prevent overnight gaps or guarantee a 20% maximum loss.
- This is research evidence, not a live-trading instruction. No broker orders were placed.

## Reproduction

- Runner: [`work/backtest_active_trend_drawdown_control.py`](../work/backtest_active_trend_drawdown_control.py)
- Shared simulator: [`work/backtest_passive_mix_drawdown_control.py`](../work/backtest_passive_mix_drawdown_control.py)
- Full candidate metrics: [`active_trend_drawdown_control.csv`](active_trend_drawdown_control.csv)
- Frozen training selection and candidate definition: [`active_trend_drawdown_selection.json`](active_trend_drawdown_selection.json)
- Per-run NAV and order ledgers: `work/backtests/active_trend_drawdown/`
