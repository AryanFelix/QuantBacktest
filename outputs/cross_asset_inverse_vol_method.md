# Cross-asset ETF inverse-volatility comparison

This fixed-cap sizing ablation changes only the weights inside the monthly top-three 12–1 momentum portfolio. At each month-end, the selected ETFs receive weights proportional to inverse 63-session close-return volatility; the portfolio retains the 45% gross cap selected for equal weights by the earlier 50-bps development risk screen. Signals use month-end closes and trades execute next session open. The same eight ETF price histories, current modeled fees, 50-bps-per-side slippage, verified NIFTYBEES payouts, and daily OHLC risk audit are used.

| Window | Inverse-vol return | Inverse-vol OHLC | Equal-weight return | Equal-weight OHLC |
|---|---:|---:|---:|---:|
| Training, 2014–2019 | -3.32% | -16.93% | -3.72% | -18.23% |
| Selection, 2020–2022 | +14.84% | -15.44% | +18.92% | -14.62% |
| Continuous development, 2014–2022 | +11.57% | -18.58% | +15.06% | -19.70% |
| 2023–2026 pseudo-holdout | +20.46% | -12.87% | +20.85% | -13.56% |
| Full history, 2014–2026 | +35.44% | -18.58% | +40.29% | -19.70% |

Inverse-vol weighting passed the 20% OHLC screen in training, selection, continuous development, and the already-inspected pseudo-holdout. It reduced the holdout envelope by 0.69 percentage points but reduced net return by 0.39 points there, 3.49 points over continuous development, and 4.85 points over full history. It is not promoted as the return-seeking choice; it is a lower-drawdown sizing sensitivity with no independent evidence of improved future performance.

The 45% cap was inherited from the equal-weight selector and was not re-optimized for inverse-vol weighting. There are no independent dates: all windows have been inspected. The risk envelope assumes held-asset highs precede lows on each session and is not a future loss limit. Gold and sector ETF distributions remain incomplete, so results are not fully distribution-adjusted total returns.

Reproduce with `work/audit_cross_asset_inverse_vol.py`. The five-window summary is [`cross_asset_inverse_vol_ohlc_frontier.csv`](cross_asset_inverse_vol_ohlc_frontier.csv), selection/gate status is in [`cross_asset_inverse_vol_ohlc_selection.json`](cross_asset_inverse_vol_ohlc_selection.json), and local per-run equity/order files are under the gitignored `work/backtests/cross_asset_inverse_vol/` directory. Each close-NAV replay asserts agreement within ₹0.03.
