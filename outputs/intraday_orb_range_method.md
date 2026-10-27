# NIFTY 30-minute opening-range breakout sensitivity

**As of:** 2026-10-27  
**Capital:** ₹10 lakh per run  
**Instrument:** NIFTY 50 30-minute signal; NIFTYBEES intraday executions

## Rule and experiment

The first NIFTY 50 30-minute candle defines the opening range. A close above that range on the second candle signals a long entry at the next candle open; the opposite side of the first range is the stop. The position exits at the first stop touch, with gap-through fills at that candle's open, or at the final 30-minute close. It is flat overnight. Position size risks 0.5% of current account equity at the stop, subject to a 95% exposure cap. Statutory intraday fees use the current Upstox/NSE schedule.

The sensitivity adds only one rule: skip the session unless the first index candle's high-low width is at least 0%, 0.30%, 0.40%, or 0.50% of that candle's close. The thresholds were chosen from the training/validation opening-range distribution before comparing costs; there is no upper-width cut. Slippage is 10, 25, 50, or 100 bps per side. The 10 bps value is the base estimate; the higher values are fixed cost stresses, not measured historical spreads.

Periods reset to ₹10 lakh: train 2022-01-03–2023-12-29, validation 2024, holdout 2025-01-01–2026-10-23, plus a continuous 2022-01-03–2026-10-23 path. The holdout was already inspected for the original ORB rule, so the filtered results are retrospective comparisons, not untouched validation. The 64 cases include 16 continuous paths and 48 period/cost sensitivity rows. Per-run summaries, equity, and trade ledgers are under `work/backtests/intraday_orb_range_sensitivity/`.

## Results

No threshold made the strategy profitable over the continuous period. At 10 bps per side, returns across the full period were -25.20% (no filter), -15.67% (0.30%), -5.93% (0.40%), and -4.11% (0.50%). Their maximum drawdowns were -25.98%, -16.43%, -6.86%, and -5.08%, respectively. The 0.50% filter passed the 20% drawdown budget through 25 bps per side but still lost 15.87% over the full window; at 50 bps its full-window loss was 32.40% and drawdown breached the budget.

Validation alone favored a 0.30% minimum at 10 bps (+2.28%), but it lost 8.25% in training and 10.11% in the inspected 2025–2026 holdout. The baseline long-only ORB lost 10.65%, 2.81%, and 13.79% in those periods at 10 bps. Filtering reduced trade counts and drawdown, but did not create a durable net edge. Reject this ORB family for deployment on current evidence.

The daily NAV marks only the end of each session. Stop and next-bar fills are modeled from 30-minute OHLC, so intrabar order, queue position, actual bid/ask spread, and partial fills are unknown. The experiment does not model investor taxes or financing. Reproduction: `work/sensitivity_intraday_orb_range.py`; shared simulator and assert-based implementation check: `work/upstox_quant.py`; row-level output: `outputs/intraday_orb_range_sensitivity.csv`.
