# NIFTY/Gold ETF trend parameter sensitivity

**2026-10-27 fee-model correction:** This static result snapshot predates the instrument-specific ETF STT replay. Use the current sensitivity CSV and consolidated ledger for numeric results; older figures below are superseded where they differ. See the [fee-model audit](../work/research/fee_model_audit.md).


**Run date:** 2026-10-27  
**Market data:** saved Upstox daily ETF candles through 2026-10-23  
**Capital:** ₹10,00,000 per test window  
**Risk screen:** maximum historical drawdown 20%  
**Status:** corrected local robustness diagnostic on inspected history; three scenarios breach 20% at 50 bps; not an optimization or independent validation.

## Frozen reference and perturbations

The reference is the existing monthly-rebalanced 50/50 NIFTYBEES Donchian 55/20 + GOLDBEES 200-session simple-moving-average trend portfolio. The sensitivity changes one sleeve parameter at a time around that reference:

| Variation | NIFTYBEES channel | GOLDBEES trend |
|---|---|---|
| Reference | 55-session breakout / 20-session exit | 200-session SMA |
| Entry-window checks | 40/20 and 75/20 | 200-session SMA |
| Exit-window checks | 55/10 and 55/30 | 200-session SMA |
| Gold-trend checks | 55/20 | 150-session and 250-session SMA |

This is seven portfolios total, including the reference. No value was selected from the sensitivity results. Channel thresholds use completed prior-session highs/lows (`shift(1)`); the Gold filter uses the close and moving average through the signal close. Target changes and month-end events execute at the next available session open. Each active sleeve receives 50% of NAV, so gross exposure is at most 100%; residual cash earns 0%. Daily candles use local session-date normalization; corrected ledgers supersede the pre-correction return and risk ranges.

The simulator uses integer units, current Upstox/NSE delivery charges uniformly over history, and 10/20/50 bps per-side slippage. It starts each window with ₹10 lakh, charges terminal liquidation, and marks the account daily. The five windows are 2014–2019, 2020–2022, 2023–2026-10-23, 2020–2026-10-23, and one continuous 2014–2026-10-23 account. The recent and full windows overlap previously inspected data; they are not independent holdouts.

## Corrected results

Returns below show the min-to-max range across the seven settings for each period and cost. The pass column counts variants inside the historical 20% close-drawdown screen.

| Window | 10 bps return range | 20 bps return range | 50 bps return range | Pass count at 10 / 20 / 50 bps |
|---|---:|---:|---:|---:|
| 2014–2019 training | +5.75% to +18.60% | +2.38% to +15.26% | -7.12% to +6.61% | 7/7 / 7/7 / 6/7 |
| 2020–2022 validation | +26.07% to +44.54% | +23.86% to +41.90% | +14.48% to +34.27% | 7/7 / 7/7 / 7/7 |
| 2023+ later slice | +68.89% to +75.34% | +66.44% to +74.01% | +59.34% to +70.08% | 7/7 / 7/7 / 7/7 |
| 2020–2026 flat-start | +118.74% to +152.82% | +110.38% to +146.02% | +87.20% to +126.69% | 7/7 / 7/7 / 7/7 |
| 2014–2026 continuous | +136.42% to +200.12% | +119.81% to +184.13% | +76.70% to +143.06% | 7/7 / 7/7 / 5/7 |

The corrected 105-case grid has three failures, all at 50 bps: one 2014–2019 path and two continuous 2014–2026 paths. At 50 bps, continuous returns range from +76.70% to +143.06%; five of seven parameter settings stay within 20% maximum close drawdown. The reference remains unchanged, and selecting the highest-return perturbation would be post-hoc. Do not interpret this local sweep as a robust optimization or independent validation.

The two highest-return continuous variants at 50 bps (55/30 and 40/20 NIFTYBEES Donchian channels, each with the Gold SMA200 gate) were additionally replayed through the conservative daily OHLC drawdown audit. Their close drawdowns were -15.62% and -16.72%, but their same-day high-before-low bounds were -25.53% and -25.53%; both fail the 20% risk limit. Their 2020–2022 returns (+33.66% and +34.27%) and 2023+ returns (+65.21% and +64.39%) are overlapping, previously inspected slices, not independent validation. See the [OHLC audit](etf_daily_timestamp_and_intraday_risk_audit.md) and `outputs/etf_intraday_drawdown_audit.csv`.

## Reproduction and checks

Run `python work/sensitivity_nifty_gold_parameters.py`. It saves all 105 metric rows in `outputs/etf_parameter_sensitivity.csv` and each run's daily equity and order ledger under `work/backtests/etf_parameter_sensitivity/`. The script asserts that its reference targets and rebalance dates exactly match the established replay and that reference ending balance, drawdown, fees, and order count reproduce the saved 10/50 bps results across all five windows. Other assertions enforce only 0%/50% sleeve weights, no more than 100% gross target exposure, and the month-end schedule.

These are market-price ETF tests, not official total-return index histories. Cash yield is set to zero; the separate sector ETF action review and the NIFTY/Gold action review remain applicable. Share-unit normalization and next-open fill prices remain empirical approximations. No new Upstox request was needed; the saved candle cache supplied the inputs.
