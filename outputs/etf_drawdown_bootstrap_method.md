# NIFTY/Gold ETF drawdown block-bootstrap stress

**As of:** 2026-10-27  
**Capital per path:** ₹10 lakh  
**Purpose:** Stress the historical 20% maximum-drawdown screen under resampled net return paths; this is not a forecast or an independent strategy validation.

## Design

The 16 source paths are the passive 22.5%/22.5% NIFTY/Gold initial allocation; the quarterly fixed 50/50 NIFTY/Gold control and 63-session inverse-vol 50/50 active-sleeve candidate at 50 bps; fixed-rule 45% and 70% gross caps at 50 bps; the 65% solo / 16% volatility-throttle and 80% / 16% candidates at 50 and 100 bps; passive 45%, 50%, 55%, and 60% initial-exposure mixes on the common 2015+ history at 50 bps; and 8%, 10%, and 12% high-water drawdown triggers that cut a passive 60% mix to 30%, with recovery at half the trigger, at 50 bps. Daily NAV returns include modeled fees and slippage with instrument-specific ETF STT. The 2014-start passive mix contributes 3,164 daily return observations beginning 2014-01-02; the other 2014-start paths contribute 3,103 each beginning 2014-03-31; the common-history exposure and drawdown-control variants contribute 2,920 each beginning 2015-01-02. All histories end 2026-10-23. The paths were regenerated after session-date normalization and the ETF-unit STT correction; see [the timestamp and OHLC audit](etf_daily_timestamp_and_intraday_risk_audit.md) and [fee-model audit](../work/research/fee_model_audit.md).

For each configuration and each mean block length (21, 63, and 126 sessions), 5,000 paths were drawn with a stationary bootstrap. A new historical block begins with probability 1/L each session, giving a geometric mean block length of L sessions. Returns are sampled in their historical order within each block, with circular wraparound at the end of the source series. Horizons are 252, 756, 1,260, and 2,520 sessions. Each path starts at ₹10 lakh; drawdown is measured from its own running NAV peak, including starting capital. The seed is fixed in `work/bootstrap_etf_drawdown_risk.py` for reproducibility.

The 192-row output `etf_drawdown_bootstrap.csv` reports the fraction of simulated paths that crossed -20% drawdown, Monte Carlo standard error, median and 5th-percentile drawdown, median and 10th-percentile CAGR, and ending NAV percentiles for each horizon, cost, and block-length combination.

## Ten-year results

| Strategy and cost | Breach at 21 / 63 / 126-session blocks | Median max DD (63) | 5th-percentile max DD (63) | Median CAGR (63) |
|---|---:|---:|---:|---:|
| Passive NIFTY/Gold 22.5% each initial, 50 bps | 3.40% / 2.40% / 1.62% | -13.17% | -18.24% | 7.43% |
| Passive NIFTY/Gold 45% initial; 2015 common, 50 bps | 3.68% / 3.58% / 3.78% | -14.22% | -19.16% | 7.42% |
| Passive NIFTY/Gold 50% initial; 2015 common, 50 bps | 6.12% / 4.90% / 5.60% | -14.94% | -19.94% | 8.01% |
| Passive NIFTY/Gold 55% initial; 2015 common, 50 bps | 8.30% / 7.28% / 8.24% | -15.58% | -20.95% | 8.53% |
| Passive NIFTY/Gold 60% initial; 2015 common, 50 bps | 11.42% / 10.00% / 10.68% | -16.58% | -22.03% | 9.10% |
| Passive NIFTY/Gold DD8% cut 60→30, recover at 4%, 50 bps | 2.62% / 1.46% / 0.86% | -12.22% | -17.36% | 7.82% |
| Passive NIFTY/Gold DD10% cut 60→30, recover at 5%, 50 bps | 2.98% / 1.96% / 1.74% | -12.37% | -17.83% | 7.90% |
| Passive NIFTY/Gold DD12% cut 60→30, recover at 6%, 50 bps | 8.08% / 6.70% / 7.76% | -14.71% | -20.83% | 7.69% |
| Quarterly fixed 50/50 control, 50 bps | 7.82% / 9.26% / 10.66% | -14.01% | -21.92% | 7.25% |
| Quarterly inverse-vol 50/50 active sleeves, 50 bps | 7.58% / 9.94% / 10.66% | -14.13% | -22.11% | 7.32% |
| Fixed control, 45% gross cap, 50 bps | 3.12% / 3.54% / 3.86% | -12.74% | -19.08% | 4.81% |
| Fixed control, 70% gross cap, 50 bps | 5.80% / 7.30% / 7.92% | -13.95% | -21.19% | 6.16% |
| 65% solo / 16% throttle, 50 bps | 20.32% / 21.66% / 25.66% | -17.40% | -25.42% | 8.64% |
| 80% solo / 16% throttle, 50 bps | 34.94% / 38.96% / 43.60% | -18.86% | -28.89% | 9.29% |
| 65% solo / 16% throttle, 100 bps | 51.12% / 59.50% / 68.16% | -21.47% | -35.99% | 5.52% |
| 80% solo / 16% throttle, 100 bps | 71.30% / 78.74% / 86.64% | -25.27% | -41.83% | 5.52% |

Among the managed/rebalanced candidates, the fixed 45% cap has the lowest breach estimate across the three block lengths. The full-history passive 22.5%/22.5% mix has a 2.40% 10-year estimate at 63-session blocks and a -18.24% fifth-percentile drawdown; its historical OHLC bound is -17.36% and its net return was +145.62%. It starts at 45% gross exposure but drifts to about 79.45% at peak. On the comparable 2015+ paths, raising initial exposure from 45% to 50% increases the 63-session breach estimate from 3.58% to 4.90%, with fifth-percentile drawdown moving from -19.16% to -19.94%. The 55% and 60% exposures increase breach estimates to 7.28% and 10.00%, with fifth-percentile drawdowns of -20.95% and -22.03%. Their historical returns rise from +129.00% at 45% to +172.02% at 60%, but the higher exposures leave less historical and resampled drawdown room. These weights are initial allocations, not maintained caps. In the exploratory drawdown-trigger paths, the 8% and 10% triggers have lower 63-session breach estimates (1.46% and 1.96%) and less-negative fifth-percentile drawdowns (-17.36% and -17.83%) than the fixed 45% path while retaining higher median CAGRs (7.82% and 7.90% vs. 7.42%). The 12% trigger is materially weaker at 6.70% and -20.83%. This threshold sweep was designed after inspecting the historical data, so the favorable risk-adjusted result is retrospective and needs frozen forward observation. The 70% active cap has a 7.30% 10-year breach estimate at 63-session blocks and a -21.19% fifth-percentile maximum drawdown. The quarterly inverse-vol candidate has a 9.94% estimate at 63-session blocks and a -22.11% fifth-percentile drawdown, in addition to its -25.55% historical same-day OHLC envelope. The volatility-throttle challengers carry materially higher breach frequencies. Monte Carlo standard errors are in the CSV; uncertainty from the short historical return sample and model choice is larger and not captured by those errors.

## Limits

These frequencies are conditional on resampling the 2014–2026 historical strategy return stream. They are not probabilities that the future will behave this way. The passive mix's result also inherits incomplete GOLDBEES cash-distribution coverage and an exposure path that drifts with relative asset returns. The block bootstrap preserves short-range return clustering on average, but it assumes the observed return distribution remains relevant, cannot create unseen regimes, and treats saved strategy returns as a return process rather than rebuilding the indicators, volatility estimates, orders, fees, and position sizes from each resampled price path. A parameter grid was already inspected before these configurations were frozen. Monte Carlo error is shown in the CSV; uncertainty from the limited historical sample and model choice is larger and is not captured by that error. Prospective paper observations and realized spreads/fills remain necessary.

Reproduce with `python work/bootstrap_etf_drawdown_risk.py`. Source equity paths are named in each CSV row; the corresponding historical methodology and caveats are documented in `outputs/joint_exposure_volatility_method.md` and `outputs/cost_stress_method.md`.
