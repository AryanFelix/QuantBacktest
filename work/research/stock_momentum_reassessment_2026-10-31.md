# Stock-momentum research slate after the 20% CAGR review — 2026-10-31

## Decision from current evidence

The existing restored-universe, point-in-time NIFTY 50 top-10 rule (positive 12–1 total-return momentum, stock and NIFTY 200-day trend filters, monthly equal weights, 95% gross exposure, next-open execution) did not establish a 20% strategy. At 10 bps/side it returned 15.01% CAGR over 2021–Oct 2026, but only 3.13% CAGR in 2025–Oct 2026. At 50 bps/side those figures fell to 12.39% and 1.02%. Its earlier 21.14% train and 20.63% 2024 validation rates are poor evidence of persistence given the sharp slowdown in the recent period. See [`stock_momentum_action_aware_screen.csv`](../../outputs/stock_momentum_action_aware_screen.csv) and [`stock_momentum_action_aware_method.md`](../../outputs/stock_momentum_action_aware_method.md).

The local history has 70 stock symbols and monthly point-in-time membership snapshots for NIFTY 50 from 2020–2026. It does not cover the NIFTY 200/500 point-in-time universe. Any result here must be described as a NIFTY 50 study, not a broad-market stock-momentum test.

## Primary-source design cues

- Jegadeesh and Titman documented positive returns for buying prior winners and selling prior losers over 3–12-month holding periods. This motivates a small, fixed 6–1 / 12–1 signal comparison; their original study is not India-specific evidence. [Journal of Finance article](https://onlinelibrary.wiley.com/doi/10.1111/j.1540-6261.1993.tb04702.x).
- NSE Indices’ Nifty200 Momentum 30 design combines 6- and 12-month price return, adjusts the score for daily volatility, weights by free-float market cap times the normalized score, caps constituent weights, and uses rank buffers to reduce turnover. This is an official model design to test, not evidence that a NIFTY 50 imitation will earn its published index returns. [Official NSE Indices page and whitepaper](https://www.niftyindices.com/docs/default-source/indices/nifty200-momentum-30-index/nifty200_momentum_30_index_whitepaper_sep_20.pdf?sfvrsn=3eb99734_4).
- Daniel and Moskowitz find momentum crashes are concentrated after market declines, in high-volatility panic states, and around sharp rebounds. A simple long-only market trend filter should not be assumed to remove this risk; evaluate rebound gaps and bear-to-bull transitions explicitly. [Journal of Financial Economics paper](https://doi.org/10.1016/j.jfineco.2015.12.002).
- Harvey, Liu, and Zhu discuss the multiple-testing problem in cross-sectional return research and propose substantially higher significance hurdles for new factors. A grid search over lookbacks, top-K values, trend filters, rebalance intervals, and weights must be treated as one family of trials, not as independent confirmation. [Review of Financial Studies paper](https://doi.org/10.1093/rfs/hhv059).

## Frozen hypotheses for the next local replay

Use dividend-adjusted stock total-return histories for ranking, point-in-time NIFTY 50 members as of the signal date, next-session-open trades, the existing fee engine, integer shares, and 10/20/50 bps per-side slippage. Compare every candidate with NIFTY 50 TRI on identical dates. Report portfolio CAGR, same-window excess CAGR, turnover, maximum close drawdown, conservative daily OHLC drawdown bound, and period-by-period results.

1. **Volatility-adjusted medium-term momentum:** rank the blend of 6- and 12-month returns divided by trailing realized volatility, using only prices available on the prior signal close. Compare the fixed official-style score to the existing 12–1 rule.
2. **Concentration and turnover:** compare top 5, 10, and 15 equal-weight holdings, with one fixed rank buffer to avoid unnecessary exits. Do not add more K values after viewing results.
3. **Crash exposure:** freeze one market-risk control using only lagged NIFTY realized volatility / drawdown information; inspect performance during panic and rebound periods separately. Treat this as risk-control research, not as another return-maximizing parameter grid.

Select any parameters using 2021–2023 only. Freeze them, then report 2024 and 2025–Oct 2026 separately as previously inspected validation periods. Nothing in this dataset is an untouched future holdout. Do not promote a candidate on a single recent CAGR: require it to beat NIFTY 50 TRI net of modeled costs over the full common sample, show the 20% target result for that full sample, and disclose every pre-defined slice and its drawdown. If no fixed candidate meets the target, record that explicitly rather than tuning the holdout.

## Limits before deployment-grade conclusions

- Current NIFTY 50 membership history is reconstructed from NSE index-review notices; it is not a reconstructed point-in-time NIFTY 200/500 security master.
- Saved action-source feeds are incomplete; rights, mergers, demergers, delistings, and ticker/share-unit changes require complete successor/entitlement accounting before a universe-wide return claim.
- Upstox daily OHLC is used with modeled slippage. It cannot prove historical executable fills, market impact, borrow availability, or a derivatives overlay's funding, roll, margin, expiry, and liquidation costs.
- A 2025–Oct 2026 slice is short, already inspected, and regime-specific. It is not independent confirmation.
