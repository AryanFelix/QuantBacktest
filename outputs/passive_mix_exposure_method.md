# Passive NIFTY/Gold initial-exposure screen

**Run date:** 2026-10-27  
**Common history:** 2015-01-02 through 2026-10-23  
**Capital:** ₹10,00,000 per run  
**Costs:** current modeled ETF delivery charges and 50 bps per-side slippage  
**Risk limit:** conservative same-day OHLC drawdown bound no worse than -20%

## Rule and selection

The rule buys equal NIFTYBEES and GOLDBEES units at the first available next-open execution, then holds without rebalancing. The initial aggregate target is screened from 30% to 100% of NAV in 5-point steps; cash earns 0%. Initial capital is split evenly between the ETFs, subject to whole-unit quantities and modeled costs. The tested paths include known NIFTYBEES cash distributions using the saved post-split unit conversion; GOLDBEES distributions are omitted because completeness is unverified.

For the training screen, each exposure starts fresh on 2015-01-02 and is terminally liquidated on 2019-12-31. The rule selects the highest net-return exposure passing the conservative daily OHLC screen. Its selected exposure is then replayed continuously from 2015-01-02 through 2026-10-23 without selling at the 2019 boundary. The later 2020+ return is measured from the continuous account's 2019 year-end NAV to terminal liquidation. All dates in the later window were previously examined elsewhere in the research, so this is pseudo-out-of-sample evidence, not a pristine lockbox.

## Results

The 2015–2019 selector chose 100% initial exposure: +44.97% with a -17.83% OHLC bound in the training fold. On the continuous common-history path, that exposure returned +284.10% but failed the 20% drawdown screen at -26.69%. The 60% exposure was the highest 5-point grid value passing the full-period OHLC screen; 65% failed at -20.37%.

| Initial gross exposure | 2015–2026 net return | Post-2019 return on carried NAV | Close MDD | OHLC bound | 10-year bootstrap breach at 21 / 63 / 126-session blocks |
|---:|---:|---:|---:|---:|---:|
| 45% | +129.00% | +89.45% | -15.58% | -17.37% | 3.68% / 3.58% / 3.78% |
| 50% | +143.36% | +97.52% | -16.19% | -18.04% | 6.12% / 4.90% / 5.60% |
| 55% | +157.69% | +105.29% | -16.73% | -18.63% | 8.30% / 7.28% / 8.24% |
| 60% | +172.02% | +112.77% | -17.20% | -19.23% | 11.42% / 10.00% / 10.68% |
| 65% | +186.37% | +120.00% | -17.62% | -20.37% | Not run; OHLC fail |

The passive exposure drifts as assets appreciate relative to cash: peak and terminal gross exposure were 79.46% / 76.23% for the 45% start, 82.57% / 79.70% for 50%, 85.29% / 82.78% for 55%, and 87.70% / 85.53% for 60%. The initial allocation is not a maintained exposure cap.

The 45% path has the most historical and resampled drawdown room among these compared sizes. At 50%, the 63-session bootstrap estimates a 4.90% ten-year breach rate, while the 21- and 126-session cases are 6.12% and 5.60%; its fifth-percentile maximum drawdowns are -20.46%, -19.94%, and -20.21%. The 55% and 60% variants earn more in sample but their estimated breach rates rise to roughly 7–11%, and their fifth-percentile drawdowns are below -20%. These are conditional resampling estimates, not forecasts or guarantees.

## Reproduction and limits

Run `python work/sensitivity_passive_mix_exposure.py`. The 30 train/continuous rows are in [`passive_mix_exposure_sensitivity.csv`](passive_mix_exposure_sensitivity.csv); equity and order ledgers are under `work/backtests/passive_mix_exposure/`. Each path uses whole ETF units, current modeled fees, 50 bps per-side slippage, zero cash yield, and terminal liquidation. Known NIFTYBEES distributions are credited; Gold distribution history remains incomplete. Price-only ETF candles, transaction-cost modeling, and daily OHLC ordering leave material uncertainty. Historical and bootstrap drawdown screens do not cap future losses.
