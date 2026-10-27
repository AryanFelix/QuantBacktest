# NIFTY opening-gap fade sensitivity

**As of:** 2026-10-27  
**Data:** Upstox 30-minute NIFTY 50 and NIFTYBEES candles, 2022-01-03–2026-10-23  
**Capital:** ₹10 lakh per run  
**Maximum requested drawdown:** 20%

## Rule

Use the NIFTY 50 index to identify an opening gap relative to the prior session's close. A gap-down signal requires the first 30-minute candle to close green while still below the prior close; a gap-up signal requires a red first candle while still above the prior close. The gap thresholds are 0.30%, 0.50%, and 0.75%. Enter NIFTYBEES at the second 30-minute candle's open, with the first NIFTYBEES candle's low/high as the long/short stop and the prior NIFTYBEES close as the target. Exit on the first stop or target touch, or at the final bar's close. Positions are closed the same day.

Sizing risks at most 0.5% of current NAV at the modeled stop, including adverse entry/stop slippage and current Upstox/NSE equity-intraday charges. Gross notional is capped at 100% of NAV; there is no leverage. The model tests long-only gap-down fades, short-only gap-up fades, and both directions. Costs are 10/25/50/100 bps adverse slippage per side. The higher fixed costs are stress assumptions, not historical spread observations.

If a 30-minute bar touches both stop and target, the stop is assumed first. A stop or target crossed at the bar open fills at that open plus adverse slippage, and the rest of that bar is ignored after the exit. Otherwise, triggers fill at their level plus adverse slippage. The NAV stress marks use the bar's raw OHLC extremes and assume the best intrabar mark can precede the worst; exit charges are reflected in realized NAV but not added to the open-position extreme marks.

## Data handling and periods

There are 1,192 common session dates. Eleven are excluded from signal generation because one or both feeds have fewer or more than 13 bars, or their full timestamp arrays do not match. These are special/short sessions or feed mismatches. Their latest closes remain available as prior-session references. The remaining 1,181 sessions have 13 aligned bars in both feeds. The index-to-ETF mapping is a spot-index signal and ETF execution proxy; there is no hedge or index-futures position.

Each period resets to ₹10 lakh: train 2022–2023, validation 2024, holdout 2025-01-01–2026-10-23, and continuous 2022-01-03–2026-10-23. The later periods are retrospective, not untouched lockboxes. There are 144 cases (3 thresholds × 3 direction modes × 4 costs × 4 periods). Run-level NAV, trades, summaries, and this sensitivity are preserved under `work/backtests/intraday_gap_fade/` and `outputs/intraday_gap_fade_sensitivity.csv`.

## Results and decision

All 36 continuous-period cases lost money. At 10 bps, the best full-period single-direction result was the 0.75% gap-up short at -5.25% return / -5.85% drawdown (33 trades); the corresponding gap-down long returned -5.30% / -6.53% (36 trades). The combined 0.75% rule lost 10.28% / -11.70%. At 50 bps, the best single-direction result was the 0.75% gap-up short at -7.46% / -7.68%; the combined 0.75% case lost 16.15% / -16.15%.

For the 0.50% combined rule at 50 bps, train, validation, and the already-inspected 2025+ segment returned -10.22%, -2.55%, and -7.84%, respectively; continuous return was -19.38% with -19.38% maximum drawdown and 67 trades. The 100 bps cases can appear less negative because the cost-aware target feasibility check rejects most trades (up to 240 of 264 signals); three 2024 gap-down-long cases reject every signal and record no trades. This is not evidence that higher costs improve the edge. The strategy family is rejected on current evidence.

Limitations include 30-minute OHLC intrabar ambiguity, unobserved bid/ask and queue fills, spot-index-to-ETF tracking, current fees applied historically, no taxes or funding, and the price-only ETF series' distribution treatment. The simulator has an assert-based rule/exit/position-sizing self-check in `work/backtest_intraday_gap_fade.py`.
