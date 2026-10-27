# NIFTY/Gold active-sleeve allocation ratio study

**Specification frozen before this run:** 2026-10-27
**Capital:** ₹10 lakh per path
**Primary cost:** current modeled ETF delivery fees and 50 bps adverse slippage per side
**Training screen:** conservative daily OHLC drawdown bound no worse than -20%

## Question and fixed strategy rules

The existing active NIFTY/Gold control uses a fixed 50/50 allocation between two independent signals. This study changes only the relative sleeve allocation and rebalance frequency:

- NIFTYBEES is active when the prior session's close is above the prior-session 55-day Donchian entry / 20-day exit state.
- GOLDBEES is active when the prior session's close is above its 200-session simple moving average.
- When a sleeve is active, its target is its fixed share of the strategy budget. The inactive sleeve's share stays in cash; it is not redistributed. For example, a 70/30 ratio with only NIFTY active targets 70% NIFTY and 30% cash before applying the gross cap.
- Signals and scheduled month-end or quarter-end rebalances execute at the next available session open. Share quantities are integer units, the account begins in cash, and positions are liquidated at the end of each evaluation window.
- The aggregate gross exposure cap is applied after the sleeve weights. Cash earns 0%.

The grid has 11 NIFTY shares of the joint active budget (0%, 10%, …, 100%), 9 gross exposure caps (30%, 40%, 45%, 50%, 60%, 70%, 80%, 90%, and 100%), and two rebalance schedules (monthly and quarterly): 198 rules. At the primary 50-bps cost, each rule is evaluated on 2015–2019 training, 2020–2022 validation, 2023–2026 holdout, continuous 2020+, and continuous 2015+ windows. Windows start with fresh ₹10 lakh, so only the fully continuous windows carry their own gains forward.

## Selection and evaluation

Select only from 2015–2019. Retain candidates whose order-by-order conservative OHLC bound passes -20%; choose the highest net return, then the shallower OHLC bound, lower cap, allocation closest to 50/50, and quarterly schedule as deterministic tie-breaks. Freeze that allocation, cap, and frequency before reading its later-window results. Do not retune using 2020+ data.

The training grid receives an OHLC audit at 50 bps. The frozen selection and a monthly 50/50/45%-cap reference receive 50-bps OHLC audits on every later and continuous window. Report the selected rule's 10/50/100-bps cost sensitivity in the 2020+, 2023+, and 2015+ windows; the extra costs are not used for selection.

## Accounting and limits

Fees use the shared Upstox/NSE ETF model with instrument-specific STT. Fixed slippage is applied on each traded side and reported separately. Known NIFTYBEES distributions are not credited because the existing 50/50 active-sleeve paths held no NIFTYBEES units at their known ex-dates; the signal gates are common to all ratios. Gold ETF distribution completeness, tax, cash yield, live spreads, and market impact remain unresolved. The OHLC envelope assumes held assets hit their daily highs before lows; it is a conservative same-day bound, not an enforceable future loss cap.

This ratio grid is a post-hoc research experiment because the surrounding 2014–2026 history has already been studied. Its later periods are chronological tests of a newly frozen parameter, not a pristine independent lockbox. A positive result would identify a paper candidate only.

## Reproduction

- Runner: `work/sensitivity_nifty_gold_allocation_ratio.py`.
- 50-bps 198-rule × five-window grid: `outputs/nifty_gold_allocation_ratio_sensitivity.csv`.
- All 198 training OHLC audits: `outputs/nifty_gold_allocation_ratio_training_ohlc.csv`.
- Frozen selection and selected/reference later-window OHLC audits: `outputs/nifty_gold_allocation_ratio_selection.json` and `outputs/nifty_gold_allocation_ratio_oos_ohlc.csv`.
- Selected rule and fixed-reference cost sensitivity: `outputs/nifty_gold_allocation_ratio_cost_sensitivity.csv`.
- Post-run interpretation and results: `outputs/nifty_gold_allocation_ratio_results.md`.
- Training order ledgers for all candidates and selected/reference later-window ledgers are stored locally under `work/backtests/nifty_gold_allocation_ratio/`.
