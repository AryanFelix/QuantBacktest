# Stateful drawdown-control bootstrap stress

**Run date:** 2026-10-27

**Capital:** ₹10,00,000

**Source history:** NIFTYBEES and GOLDBEES daily Upstox OHLC, 2015-01-02 through 2026-10-23 (2,921 common sessions)

**Policies:** fixed 45%, fixed 60%, and 60%-to-30% drawdown controls at 8%, 10%, and 12% triggers

**Costs:** current modeled NSE fees, ₹0 cash yield, and 50 bps per-side slippage

## Method

`work/bootstrap_stateful_drawdown_control.py` samples paired daily bars from the common ETF history with a stationary bootstrap. For each sampled session it carries the NIFTYBEES and GOLDBEES gap/open, high/open, low/open, and close/open ratios together. This retains observed cross-ETF and within-bar dependence inside historical blocks. Each path chains the sampled gap from its preceding synthetic close.

For 21-, 63-, and 126-session mean blocks, the runner simulates 5,000 ten-year paths of 2,520 sessions. It rebuilds the whole-unit holdings, next-open drawdown cuts and recoveries, known NIFTYBEES cash distribution, current instrument-specific fees, 50 bps slippage, and terminal liquidation on every sampled OHLC path. Cash earns 0%. The same sampled index is used for both ETFs on each day. The only distribution in the tested source window is the previously documented NIFTYBEES ₹0.80 event; Gold ETF distributions remain unmodeled because their history is unverified.

The close drawdown uses terminal NAV and its running close high-water mark, including initial capital. The intraday envelope includes pre-trade opening NAV and the post-trade portfolio marked at both ETFs' highs and lows. It assumes the portfolio highs occur before the lows on each day; it is a conservative bound rather than a synchronized intraday path. The terminal liquidation is included. Initial synthetic prices use the close immediately before the 2015 start, preserving realistic whole-share sizing at entry.

Before generating bootstrap results, a deterministic replay of the actual historical index sequence is checked against `work/backtest_passive_mix_drawdown_control.py` for all five policies. Ending balance, fees, slippage, order counts, trigger and recovery counts, close drawdown, and OHLC envelope must match within stated tolerances. Vectorized fees are also checked against the shared scalar fee calculator for both ETF products, both order sides, and ₹10,000/₹250,000 notionals. Those assertions passed for this run.

## Results

Each probability is a 10-year path-level estimate from 5,000 paths. The table shows the fraction whose close drawdown or conservative OHLC envelope breached -20%. `p05 OHLC` is the fifth percentile of the worst envelope drawdown; CAGR and ending balances are path medians and tenth percentiles. Results are net of modeled costs.

| Rule | OHLC breach, 21 / 63 / 126 blocks | Close breach at 63 blocks | Median / p10 CAGR at 63 blocks | Median / p10 ending value at 63 blocks | p05 OHLC at 63 blocks |
|---|---:|---:|---:|---:|---:|
| Fixed 45% | 22.28% / 19.62% / 19.38% | 2.58% | 7.58% / 4.68% | ₹20.76L / ₹15.80L | -23.03% |
| Fixed 60% | 58.78% / 56.48% / 57.02% | 8.52% | 9.30% / 5.90% | ₹24.34L / ₹17.74L | -26.49% |
| 8% cut; recover at 4% | 10.58% / 10.28% / 8.28% | 0.04% | 6.96% / 4.03% | ₹19.59L / ₹14.84L | -21.03% |
| 10% cut; recover at 5% | 20.20% / 16.42% / 13.64% | 0.26% | 7.33% / 4.19% | ₹20.28L / ₹15.07L | -21.74% |
| 12% cut; recover at 6% | 31.10% / 23.78% / 17.78% | 0.82% | 7.54% / 4.42% | ₹20.69L / ₹15.41L | -22.32% |

At 63-session blocks, Monte Carlo standard errors for the OHLC breach estimates are 0.43–0.70 percentage points. The 8% control has the lowest estimated envelope-breach frequency, 8.28–10.58% across block lengths, but its median CAGR is 6.95–7.01%. The 10% control's envelope-breach estimate ranges from 13.64% to 20.20%, and its median CAGR is 7.33–7.50%. Fixed 45% has a 7.56–7.58% median CAGR and a 19.38–22.28% envelope-breach estimate. None keeps all resampled OHLC paths inside the requested 20% drawdown limit; the 8% control's fifth-percentile envelope is still -21.03% at 63-session blocks.

The historical 2015–2026 path passed the -20% daily OHLC screen for all five rules, but that single inspected path does not establish a future maximum drawdown. The block resampling reuses a finite, repeatedly inspected history, assumes the sampled return/bar distribution remains relevant, and cannot generate unseen regimes. The breach frequencies are conditional stress estimates, not forecasts, guarantees, or independent out-of-sample validation. Slippage is a fixed cost stress, not realized spread or market impact. Paper observation remains necessary before any implementation decision.

## Reproduction

Run `python work/bootstrap_stateful_drawdown_control.py`. The 15 policy/block summaries, including Monte Carlo error, cost averages, and transition counts, are in [`stateful_drawdown_control_bootstrap.csv`](stateful_drawdown_control_bootstrap.csv). The historical policies and their transaction ledgers are in [`passive_drawdown_control_method.md`](passive_drawdown_control_method.md) and `work/backtests/passive_drawdown_control/`.
