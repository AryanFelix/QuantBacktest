# Cross-asset ETF momentum-strength weighting

## Result

At 50 bps per-side slippage, the development-window selector chose a 45% gross exposure cap. On the already-inspected 2023-01-01 to 2026-10-23 pseudo-holdout, ₹10 lakh became ₹12.25 lakh (+22.51%, 5.57% CAGR). Close maximum drawdown was -15.67%; the conservative daily OHLC envelope was -16.24%, leaving 3.76 percentage points under the historical 20% screen. Modeled fees were ₹6,991. The 50-bps slippage assumption is included in the simulated return.

At the same cap and friction, equal weighting returned +20.85% with a milder -13.56% OHLC envelope and ₹7,567 modeled fees. Over the continuous 2014–2022 development path, strength weighting returned +17.00% with a -18.82% OHLC bound, versus +15.06% and -19.70% for equal weights. Across full 2014–2026 history, the figures were +44.86% / -18.82% versus +40.29% / -19.70%. Strength weighting lost slightly more in the 2014–2019 training window (-4.43% versus -3.72%).

At a separate 100-bps-per-side cost stress, the same development selector reduced the chosen cap to 35%. That path returned +12.51% on 2023+ (3.20% CAGR), with a -14.13% OHLC envelope and ₹6,617 modeled fees. It passed all development windows; only 25%, 30%, and 35% caps were eligible. The 40% cap breached the continuous development bound at -20.17%, while 45% breached training at -20.25% and continuous development at -22.40%. The 100-bps value is a deliberate stress assumption, not a measured spread.

## Rule and cap selection

At each month-end, rank the available NIFTY, Gold, and sector/index ETFs by 12-minus-1-month price momentum, keep the top three with closing price above the 200-session moving average, and assign each selected ETF a weight proportional to its positive 12-minus-1 momentum score. Target changes execute at the next session's open. The eight-instrument universe is NIFTYBEES, GOLDBEES, BANKBEES, ITBEES, AUTOBEES, PHARMABEES, PSUBNKBEES, and JUNIORBEES.

The fixed ₹10 lakh account was tested at gross exposure caps from 25% to 95% in five-point increments. A cap was eligible only if its OHLC envelope stayed within 20% in 2014–2019 training, 2020–2022 selection, and continuous 2014–2022 development. The highest 2020–2022 CAGR among eligible caps was chosen; ties prefer more OHLC headroom and then lower exposure. Five caps, 25% through 45%, passed; 45% had a 6.91% selection-window CAGR and a worst development bound of -18.82%.

The 2020–2022 period is selection data, not independent validation. The 2023+ window is a retrospective pseudo-holdout, not an untouched lockbox. The risk screen also depends on the chosen 20% historical path threshold; it does not establish a future loss limit.

## Data and limitations

The daily Upstox ETF candles are frozen through 2026-10-23. The shared fee engine uses whole ETF units, current modeled NSE/Upstox delivery charges, next-open fills, and fixed adverse slippage of 50 bps on each side. It credits only the verified NIFTYBEES distributions of ₹0.70 on 2014-03-11 and ₹0.80 on 2015-02-20; Gold and sector ETF distributions remain incomplete, and cash earns zero. The schedule is applied uniformly to historical trades rather than reconstructed from dated contract notes.

ETF inceptions and coverage differ, and this current-ETF universe has no point-in-time membership archive. The OHLC auditor carries the prior close across missing bars, which can understate risk if a missing candle coincides with a gap or stale price. The envelope also assumes each held asset reaches its session high before its low. It is a modeled path bound, not a realized intraday path, executable stop, or future drawdown guarantee. Every historical window has been examined; this is a research candidate for prospective paper observation, not a validated winner or deployment instruction.

## Reproduction

- Runner: `work/sensitivity_cross_asset_momentum_strength.py`
- 50-bps, 75-case risk frontier: [`cross_asset_momentum_strength_ohlc_frontier.csv`](cross_asset_momentum_strength_ohlc_frontier.csv)
- 50-bps development selector and pseudo-holdout metrics: [`cross_asset_momentum_strength_ohlc_selection.json`](cross_asset_momentum_strength_ohlc_selection.json)
- 100-bps, 75-case cost-stress frontier: [`cross_asset_momentum_strength_100bps_frontier.csv`](cross_asset_momentum_strength_100bps_frontier.csv)
- 100-bps development selector and pseudo-holdout metrics: [`cross_asset_momentum_strength_100bps_selection.json`](cross_asset_momentum_strength_100bps_selection.json)
- Reproduction: `work/sensitivity_cross_asset_momentum_strength.py` for 50 bps and `work/stress_cross_asset_momentum_strength_cost.py` for 100 bps. Local equity/order files are under the corresponding gitignored `work/backtests/` directories. Every OHLC run asserts close-NAV reconciliation within ₹0.03.
