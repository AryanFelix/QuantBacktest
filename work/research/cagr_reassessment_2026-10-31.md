# CAGR target reassessment — 2026-10-31

## Decision

The current evidence does not support a durable, investable after-cost 20% CAGR strategy. One existing rule reaches 20.72% from 2020 to October 2026 and 23.06% from 2023, but the full 2014–2026 compound rate is 10.40%, below matched NIFTY 50 TRI at 11.83%. It also saw a -32.43% full-history conservative OHLC drawdown bound. A 2014–2019 training-only exposure selection, frozen for 2020 onward, returned 13.60%, not 20%. The live Smallcap 250 TRI reached 20.36% from 2020 with -43.48% close drawdown, but its HDFC ETF only has price bars from February 2023 and produced 16.39% after modeled costs. The high beta result is real index performance, not a backtest of an investable ETF position during 2020 onward.

The user has relaxed the previous 20% drawdown ceiling. We therefore allow 100% unlevered exposure in the current leaderboard and report actual risk rather than rejecting any drawdown level. The reference capital remains ₹10 lakh.

## Five leading candidates

The front section of `outputs/quant_research_report.md` is ranked by the largest relevant observed CAGR for each candidate, with every window named. It records matched benchmark return, close drawdown, conservative OHLC bound, and the present limitations.

| Candidate | Net CAGR | Same-window benchmark | Close / OHLC drawdown | Interpretation |
|---|---:|---:|---:|---|
| Quarterly NIFTY/Gold 63-session inverse-vol rule, 100% active exposure; 2020–2026 | 20.72% | NIFTY 50 TRI 10.79% | -25.10% / -29.31% | Meets target in selected recent window only; 2014–2026 CAGR 10.40%, training-selected future exposure 13.60%. |
| MID150BEES 100% buy-and-hold; 2021–2026 | 18.23% | Midcap 150 TRI 18.64%; NIFTY 50 TRI 9.87% | -21.23% / -37.65% | Beats broad NIFTY but trails its direct Midcap benchmark; from ETF inception in 2019 it returned 17.77% vs Midcap TRI 18.15%. |
| MID150BEES 200-day moving-average rule; 100% cap; 2021–2026 | 17.20% | Midcap 150 TRI 18.64%; NIFTY 50 TRI 9.87% | -12.18% / -23.04% | Materially reduces close drawdown, gives up return, and still trails its direct benchmark. |
| HDFCSML250 100% buy-and-hold; 21 Feb 2023–23 Oct 2026 | 16.39% net at 50 bps/side | Smallcap 250 TRI 18.10%; NIFTY 50 TRI 7.95% | -25.90% / -28.82% | Price-only Upstox ETF history; modeled fees and slippage included. It beats NIFTY, trails its own TRI, and cannot validate the earlier 2020+ index result. |
| Tata Nifty Midcap150 Momentum 50 Direct Growth live NAV; 20 Oct 2022–30 Sep 2026 | 15.82% | Momentum 50 TRI 16.97%; NIFTY 50 TRI 7.85% | Not reported in AMC return table | Actual live fund evidence, net of fund expenses; it misses 20% and trails its own benchmark. |

The first candidate's full 2020–2026 result grew ₹10 lakh to ₹35.42 lakh after modeled charges: ₹15,826 fees and ₹520,536 estimated slippage at 50 bps per side. Its 2014–2019 training return was -0.51%; its 2020–2022 validation return was 16.91%; and the already-inspected 2023+ return was 23.06%. The 50% solo exposure selected on training data produced 13.60% over 2020–2026. Do not treat the 100% headline as a locked out-of-sample result.

## MID150BEES execution-aware screen

The 1,915 Upstox daily bars run from 2019-02-04 to 2026-10-30. To match available official index data, the execution backtests end on 2026-10-23. Official Midcap 150 TRI and NIFTY 50 TRI were reindexed to the exact 1,910 ETF price sessions in each run; three Upstox sessions are missing from the ETF bars. Ten cases compare 95% and 100% cash exposure for buy-and-hold and a close-above-SMA200 long/flat rule, from 2019, 2021, and 2023 start dates where appropriate.

The 100% buy-and-hold case returned 17.77% CAGR from the ETF's available start date, with -38.43% close drawdown and -47.09% conservative OHLC envelope. Starting in 2021 raised observed CAGR to 18.23%, while close drawdown was -21.23% and the OHLC bound -37.65%. Moving from 95% to 100% exposure added only 0.52 percentage points of CAGR over 2021–2026 while worsening the OHLC envelope by about 0.89 points. The 200-day filter reduced the 2021+ OHLC bound to -23.04% but returned 17.20%.

The simulator applies a 50 bps adverse fill on each side and the current modeled NSE equity-fund-unit tariff; trades use integer shares and final liquidation. Cash yield is zero. Current modeled fee totals are ₹384 for the 100% buy-and-hold 2021+ case and ₹5,048 for its 200-day filter. Slippage is a stress assumption, not observed spread. Price closes may omit cash distributions; this series is treated as price-based evidence, not a reconstructed total-return ETF NAV.

Artifacts: [`midcap_etf_cagr_screen.csv`](../../outputs/midcap_etf_cagr_screen.csv), [`backtest_midcap_etf_cagr_screen.py`](../backtest_midcap_etf_cagr_screen.py), [`capture_midcap_etf_benchmark.py`](../capture_midcap_etf_benchmark.py), [`midcap_etf_benchmark_2019_2026.csv`](../data/index_daily/midcap_etf_benchmark_2019_2026.csv), and [`MID150BEES daily bars`](../data/etf_daily/MID150BEES-days-1-2019-02-04-2026-10-30.csv).

## New live factor-index check

The April 2026 NSE factsheets include short-period 20%+ TRI rates for some newer multi-cap momentum/quality indexes. Those are not their current live launch-period results. Recomputing only from each official live launch through 2026-10-23 gives:

| Live index and parent | Live index CAGR / close MDD | Parent TRI CAGR / close MDD | Since 2025: index / parent CAGR |
|---|---:|---:|---:|
| Nifty200 Momentum 30 / Nifty 200; 2020-08-25 onward | 15.12% / -31.56% | 14.52% / -17.80% | -9.19% / -1.32% |
| Nifty Smallcap250 Momentum Quality 100 / Nifty Smallcap 250; 2023-12-21 onward | 4.35% / -29.71% | 7.27% / -26.01% | -6.11% / -4.24% |
| Nifty500 Multicap Momentum Quality 50 / Nifty 500; 2024-09-04 onward | -11.67% / -29.06% | -3.83% / -18.59% | -9.56% / -1.64% |

These are gross index TRI figures before fund expense and trading costs. The momentum/quality rules have not delivered a live 20% CAGR in these windows; the newest two have underperformed their parent indices, while Nifty200 Momentum 30 has a modest live excess return with materially larger drawdown. The official [Nifty200 Momentum 30 factsheet](https://www.niftyindices.com/Factsheet/Factsheet_Nifty200_Momentum30.pdf), [Smallcap250 Momentum Quality 100 factsheet](https://www.niftyindices.com/Factsheet/Factsheet_NiftySmallcap250MomentumQuality100.pdf), and [Nifty500 Multicap Momentum Quality 50 factsheet](https://www.niftyindices.com/Factsheet/Factsheet_Nifty500MulticapMQ50.pdf) state their launch dates. Pre-launch base-date backfills are excluded here.

Artifacts: [`live_factor_tri_comparison.csv`](../../outputs/live_factor_tri_comparison.csv), [`capture_live_factor_tri_comparison.py`](../capture_live_factor_tri_comparison.py), and [`live_momentum_quality_tri_2020_2026.csv`](../data/index_daily/live_momentum_quality_tri_2020_2026.csv).

## Small-cap index and ETF screen

The official Nifty Smallcap 250 TRI has a live launch date of 1 April 2016. Since that launch through 23 October 2026 it compounded at 15.10% with -59.78% close drawdown. From 2020 it returned 20.36% CAGR with -43.48% close drawdown, versus NIFTY 50 TRI 10.79% and -38.27%. From 2023 its CAGR cooled to 15.95%. These are matched-session official index total-return series; no pre-launch base-date backfill is included in the reported segments. See the [NSE Smallcap 250 factsheet](https://www.niftyindices.com/Factsheet/ind_Nifty_Smallcap_250.pdf) for the launch date.

The Upstox instrument master and daily candles were screened for six Smallcap 250 ETFs. HDFCSML250 had the longest available live price history in this set: 909 bars from 21 February 2023 through 23 October 2026. A 100% buy-and-hold grew ₹10 lakh to ₹17.45 lakh after current modeled charges and 50 bps adverse slippage per side: 16.39% CAGR, -25.90% close drawdown, and -28.82% conservative OHLC envelope. At 100 bps per side the CAGR was 16.07%. The close-above-SMA200 long/flat rule returned 2.68% at 50 bps and 0.47% at 100 bps. It avoids the recent -43.48% index drawdown only because the ETF data begins after the earlier period; it does not establish a high-return trend rule.

The ETF comparison reindexes official Smallcap 250 and NIFTY 50 TRIs to the exact Upstox ETF sessions. ETF market closes are price-only and can omit distributions. The assumed spread/slippage is not measured. Results and reproduction are in [`smallcap_etf_cagr_screen.csv`](../../outputs/smallcap_etf_cagr_screen.csv), [`smallcap250_index_benchmark_comparison.csv`](../../outputs/smallcap250_index_benchmark_comparison.csv), and [`backtest_smallcap_etf_cagr_screen.py`](../backtest_smallcap_etf_cagr_screen.py); local input/cache paths are recorded in the manifest.

## Leverage and next research direction

Upstox's current Standard MTF pricing is ₹20/day per ₹40,000 borrowed, approximately 18.25% simple annualized on the borrowed amount, before brokerage, pledge costs, and tax. That is not cheap leverage against a 12–18% unlevered signal and is a negative expected carry at the observed midcap and stock-momentum returns. MTF is for eligible stock delivery; it does not make the MID150BEES ETF itself a funded position. See [Upstox MTF charges](https://upstox.com/help-center/t-251427/). Futures/option leverage requires a separate, contract-specific capital and liquidation model; it is not approximated by multiplying the cash strategy return.

The official Nifty50 TR 2x Leverage index also fails to produce a 20% result over its actual launch sample. From 30 June 2014 to 23 October 2026 it compounded at 12.58% with -64.25% close drawdown, versus NIFTY 50 TRI 10.57% and -38.27%. From 2020 onward the 2x index returned 12.99% with the same -64.25% drawdown. NSE's formula doubles the daily NIFTY 50 TR return and deducts previous-day TREPS funding for the calendar gap; it does not represent a traded, fee-net futures account. Actual execution, futures roll, taxes, and margin/liquidation effects would reduce or alter returns. See the [official leverage factsheet](https://www.niftyindices.com/Factsheet/Nifty50_TR_2X_Leverage.pdf), [`nifty50_2x_leverage_comparison.csv`](../../outputs/nifty50_2x_leverage_comparison.csv), and [`capture_nifty50_2x_leverage.py`](../capture_nifty50_2x_leverage.py).

The next high-value experiment is point-in-time cross-sectional momentum and quality over a broader NIFTY 200 / Midcap 150 / Smallcap 250 universe, with delisted names, corporate actions, survivorship-safe constituents, and distribution-inclusive returns. Freeze a small rule set in training, evaluate it chronologically after the freeze, and model turnover before claiming 20%. Current stock work uses NIFTY 50 members and has unresolved corporate-action and universe limitations.

## Reproduction and limits

`capture_midcap_etf_benchmark.py`, `backtest_midcap_etf_cagr_screen.py`, and `capture_live_factor_tri_comparison.py` each contain assertions for session ranges, positive index marks, benchmark alignment, and close-NAV order replay. The ETF order ledgers reconcile to the shared simulator within three paise; the 10 displayed cases are saved under `work/backtests/midcap_etf_cagr_screen/`.

Every date shown has been inspected in this research; no later period is an untouched lockbox. The OHLC bound assumes each day's highs occur before its lows, and is a conservative envelope rather than a synchronized market path. Current fee schedules are applied uniformly to historical cash ETF backtests; taxes, live spread, impact, fills, ETF distributions, and future liquidation risk can change realized results. No strategy can promise a 20% CAGR or a future drawdown ceiling.

