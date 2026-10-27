# NIFTY/Gold expanding-window annual walk-forward

**Run date:** 2026-10-27  
**Market data:** Upstox daily ETF candles through 2026-10-23  
**Initial capital:** ₹10,00,000  
**Drawdown screen:** 20%  
**Costs:** corrected NSE/Upstox delivery charges plus 50 bps per side slippage  
**Status:** retrospective pseudo-out-of-sample diagnostic on repeatedly inspected history; not an untouched validation set.

## Method

Each January fold selects one of seven predeclared NIFTYBEES Donchian / GOLDBEES moving-average parameter combinations. Training expands from 2014-01-01 through the prior December. A candidate must pass both the close drawdown screen and the conservative daily OHLC high-before-low drawdown bound at a 45% gross exposure cap. Among eligible rules, the selector chooses the highest net training return. The fixed D55/20 + Gold SMA200 rule is replayed as a control.

Donchian entry and exit thresholds use prior-session highs/lows (`shift(1)`). Gold uses the close against its rolling simple moving average. The two active sleeves receive 50% of their target weight each, clipped by the 45% account exposure cap. Signals and month-end changes execute at the next available session open. The 2020 test starts with ₹10 lakh; each later test starts with the prior fold's actual ending balance. Holdings are liquidated at each final session close before annual reselection, and cash earns 0%. The partial 2026 test ends 2026-10-23.

The seven choices are D55/20 + Gold SMA200 (fixed control), D40/20 + SMA200, D75/20 + SMA200, D55/10 + SMA200, D55/30 + SMA200, D55/20 + SMA150, and D55/20 + SMA250. All seven passed both training drawdown screens in each of the seven folds. The selection criterion therefore ranked their net training return; it did not relax the 20% risk screen.

## Results

| Test year | Selected rule | Selected net return | Fixed D55/20 control | Selected fold OHLC bound | Full-sequence OHLC bound to date |
|---|---|---:|---:|---:|---:|
| 2020 | D55/30 + SMA200 | +10.73% | +10.73% | -12.33% | -12.33% |
| 2021 | D55/30 + SMA200 | +6.51% | +6.51% | -13.77% | -13.77% |
| 2022 | D55/30 + SMA200 | -1.02% | -1.02% | -13.33% | -13.77% |
| 2023 | D55/30 + SMA200 | +4.16% | +4.16% | -4.95% | -13.77% |
| 2024 | D55/30 + SMA200 | +5.73% | +5.73% | -4.54% | -13.77% |
| 2025 | D55/30 + SMA200 | +20.89% | +26.87% | -8.29% | -13.77% |
| 2026 through Oct 23 | D40/20 + SMA200 | -0.35% | -0.34% | -14.86% | -14.86% |

The actual chained account grows from ₹10 lakh to **₹15.49 lakh (+54.89%)** for the selected sequence and **₹16.26 lakh (+62.56%)** for the fixed control. Selected-rule modeled statutory fees total ₹12,019 and 50 bps-per-side slippage costs ₹1,79,867; the control totals are ₹11,988 fees and ₹1,85,080 slippage. Full-sequence close drawdown is -13.00% for both; full-sequence same-day high-before-low OHLC bounds are -14.86% for both, inside the requested 20% screen. The selector did not improve the control: the only material return difference was in 2025, when selected D55/30 lagged fixed D55/20 by about 5.98 percentage points. It selected D55/30 for 2020–2025 and changed to D40/20 for the partial 2026 fold.

Unlike the earlier fold-reset replay, this version trades each year at the actual carried account balance and carries the all-time close and intraday peaks across annual liquidations. Each close-marked equity path and order ledger is reconciled to within ₹0.03. The OHLC path assumes each held instrument's daily high occurs before its low; this is conservative but still a bound on historical marks, not a future loss guarantee.

## Interpretation and limits

The screen found no out-of-sample benefit from choosing the best training parameter. It is not a winner. The 45% exposure cap was chosen after earlier full-history exposure sweeps; only parameter choice was nested inside the expanding training windows. The listed test years were already inspected elsewhere in this research, so this is a chronological replay with recursive parameter selection, not a pristine lockbox. ETF market-price histories do not include a complete distribution-adjusted total-return series; cash yields, tax, market impact, and live spreads remain outside the model. The daily high-before-low bound is deliberately conservative but cannot enforce a future 20% maximum loss.

Reproduce with `python work/walk_forward_nifty_gold.py`. It stores each training candidate's equity and orders, carries test capital and peaks forward, checks every training and test ledger against the OHLC reconstruction (maximum allowed close replay error ₹0.03), asserts seven folds and fourteen selected/control rows, and writes `outputs/nifty_gold_walk_forward.csv`. The audit helper's default ₹10 lakh behavior was also re-run on its six existing portfolios. The consolidated ledger refresh is `python work/refresh_backtest_summary.py`.
