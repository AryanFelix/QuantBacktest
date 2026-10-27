# Quarterly NIFTY/Gold exposure-cap selection

**Run date:** 2026-10-27  
**Initial capital:** ₹10,00,000 per path  
**Universe:** NIFTYBEES and GOLDBEES, 50/50 target mix  
**Costs:** current modeled product-specific fees, 50 bps per-side slippage, zero cash yield  
**Risk screen:** conservative daily OHLC drawdown bound no worse than -20%  
**Validation label:** chronological pseudo-out-of-sample only; later dates were already inspected.

## Frozen experiment

The selection grid is 10% through 100% aggregate gross exposure in 5-point steps. Every candidate uses the same quarterly static 50/50 target; the exposure cap scales the risky target at each rebalance and the remainder stays in zero-yield cash. Positions can drift between quarterly rebalances. Signals use the prior close and execute at the next session open. The path starts with ₹10 lakh, uses whole units, and liquidates at the end.

The training window is 2015-01-02 through 2019-12-31. Select the highest net training return among candidates whose conservative OHLC bound is no worse than -20%, with an exact return tie resolved toward the lower cap. All 19 grid points passed the historical bound, and the rule selected the 100% cap: +45.98% net return and -18.62% OHLC bound. Training fees were ₹1,779; modeled slippage was ₹15,212; the replay credited ₹4,651 of known NIFTYBEES distributions.

The selected 100% cap was then replayed on 2020-01-01 through 2026-10-23, from a fresh ₹10 lakh balance. It returned +169.22%, but its -26.02% OHLC bound breached the 20% limit. The fixed 45% control returned +58.82% and passed at -12.91%. Each period is a separate account simulation with terminal liquidation; it does not compound training proceeds into the test period.

## Post-hoc test-period exposure curve

The full same-grid test sensitivity is retained for diagnosis, not to revise the training selection. Because these dates were inspected before this experiment, the rows below are post-hoc historical comparisons rather than an independent holdout.

| Gross cap | 2020+ net return | OHLC bound | 20% screen |
|---:|---:|---:|---|
| 45% control | +58.82% | -12.91% | Pass |
| 65% | +93.26% | -17.88% | Pass |
| 70% | +102.80% | -19.06% | Pass |
| 75% | +112.71% | -20.27% | Fail |
| 100%, selected in training | +169.22% | -26.02% | Fail |

Among the tested 5-point exposures, 70% is the highest cap that stays inside the 20% historical OHLC envelope in the later sample, but it leaves less than 1 percentage point of headroom. The 65% row leaves about 2.12 points and returned +93.26%. Choosing either cap from this later grid would be post-hoc; neither is a validated replacement for the training-selected 100% cap, which failed its out-of-window risk check.

## Interpretation and limits

This experiment demonstrates that training risk screens did not carry over: the 100% cap passed 2015–2019 but breached 2020–2026. It does not establish a maximum future drawdown. The OHLC audit assumes held positions reach their daily highs before their lows, which is a conservative envelope under that ordering, not an executable stop or a guaranteed bound. Gross exposure is capped only at quarterly sizing events, not continuously.

The 2015 training includes the known NIFTYBEES distribution, credited to eligible units on its ex-date. The ₹0.80 per saved unit amount comes from the pre-split AMC distribution and the documented 1:10 split; the unit conversion is inferred because Upstox does not document a universal adjustment guarantee. GoldBeES' AMC action page does not certify complete distribution history; no Gold cash flows are inserted. Missing Gold distributions, share-unit treatment, or other total-return adjustments could change returns and the selected cap. See the [ETF total-return source audit](../work/research/etf_total_return_source_audit.md), [Nippon NIFTYBEES actions](https://investeasy.nipponindiaim.com/rmfGsamnew/Products/NiftyBeES/CorporateAction.aspx), [Nippon GoldBeES actions](https://investeasy.nipponindiaim.com/rmfGsamnew/Products/GoldBeES/CorporateAction.aspx), and [Upstox daily-candle documentation](https://upstox.com/developer/api-documentation/v3/get-historical-candle-data/).

Modeled net returns include current delivery fees and 50 bps slippage on both sides, applied uniformly to historical trades. Income/capital-gains taxes, variable live spreads, market impact, partial fills, and cash interest are not modeled. The independent [methodology review](static_mix_exposure_methodology_review.md) confirms the next-open timing, per-period liquidation, and pseudo-out-of-sample limitations.

## Reproduction

Run `python work/select_static_mix_exposure.py`. The 19 training rows are in [`static_mix_exposure_training.csv`](static_mix_exposure_training.csv), the frozen selection and selected test outcome are in [`static_mix_training_selection.json`](static_mix_training_selection.json), and all 19 later-period sensitivity rows are in [`static_mix_exposure_oos_test.csv`](static_mix_exposure_oos_test.csv). Per-run equity and order files are under `work/backtests/static_mix_exposure_training/` and `work/backtests/static_mix_exposure_test/`; each order path is reconciled to close-marked equity within ₹0.03.
