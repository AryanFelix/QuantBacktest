# NIFTY/Gold trend exposure cap: transaction-cost stress

**Protocol frozen:** 2026-10-27  
**Capital:** ₹10 lakh per run  
**Instruments:** NIFTYBEES and GOLDBEES  
**Signals and rebalance:** unchanged quarterly 50/50 sleeves; NIFTYBEES Donchian 55/20 and GOLDBEES SMA200, prior-close signals and next-session-open orders  
**Fee model:** current modeled Upstox/NSE delivery charges, held constant across all cost scenarios  
**Risk screens:** train-time simultaneous daily OHLC drawdown bounds of -20% and -15%

## Frozen experiment

At each per-side slippage level (10, 50, 100, and 200 bps), replay the 16 gross exposure caps from 25% through 100% in 5-point steps over 2014-01-01 to 2022-12-30. Select the cap with the highest net training return whose simultaneous OHLC drawdown bound passes the relevant risk screen; ties select the lower cap. If no cap passes, record no eligible cap and do not run a holdout case for that screen. Otherwise freeze the selected cap and replay 2023-01-01 to 2026-10-23 in a fresh ₹10 lakh account with the same slippage and fee assumptions. Do not retune using the later period.

The -20% screen is the requested risk limit. The -15% screen is a five-point training buffer sensitivity. Costs change, but indicators, target sleeves, rebalance timing, sizing, instrument universe, and drawdown convention do not. Save the complete training grid so cap selection can be reproduced. Assert that the 50-bps case recovers the prior 70% and 40% choices and their saved test returns before accepting the output.

The OHLC bound assumes all held daily highs occur before all held daily lows; it is a conservative envelope, not a realized intraday path or a guarantee on future loss. Slippage is a stress assumption rather than measured market impact. ETF cash distributions (especially GOLDBEES), cash yield, investor tax, and partial fills remain outside this experiment. The 2023+ history and related strategy family have already been examined, so this is a robustness check on pseudo-out-of-sample evidence, not a pristine lockbox.

Runner: `work/stress_etf_exposure_cap_costs.py`. Results: `outputs/etf_exposure_cap_cost_stress.csv` and `outputs/etf_exposure_cap_cost_stress_training_grid.csv`.
