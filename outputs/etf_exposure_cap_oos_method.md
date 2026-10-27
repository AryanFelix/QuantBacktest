# NIFTY/Gold exposure cap: training selection and frozen later test

**Run date:** 2026-10-27<br>
**Capital:** ₹10 lakh per run<br>
**Risk preference:** maximum historical drawdown 20%<br>
**Execution costs:** current modeled Upstox/NSE delivery charges plus 50 bps slippage per side<br>
**Data:** saved Upstox daily ETF OHLC through 2026-10-23

## Rule and selection

The portfolio uses NIFTYBEES Donchian 55/20 and GOLDBEES 200-session SMA signals, with fixed 50/50 sleeve weights and quarterly rebalancing. Signals use completed closes and orders execute at the next session open. The tested gross exposure cap is applied when sizing at a rebalance; price drift can move actual exposure between those dates. Remaining cash earns 0% and every period is terminally liquidated.

The 16 candidate caps are 25% through 100% in 5-point increments. Training runs use 2014-01-01 through 2022-12-30. The primary rule selects the highest net training return whose simultaneous daily OHLC drawdown bound is no worse than -20%; ties prefer the lower cap. A -15% threshold is reported only as a 5-point safety-buffer sensitivity. The frozen test runs use 2023-01-01 through 2026-10-23, each with a fresh ₹10 lakh account.

Each run uses whole ETF units, current product-specific delivery fees applied uniformly over history, and 50 bps adverse slippage per executed side. The output includes the reconstructed order ledger and checks daily close NAV against it.

## Results

| Training screen | Selected cap | Training return | Training OHLC bound | Frozen 2023+ return | 2023+ close MDD | 2023+ OHLC bound | 2023+ fees | 2023+ slippage | End value |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| User limit: -20% | 70% | +31.11% | -19.07% | +55.71% | -14.24% | -16.81% | ₹3,356 | ₹66,489 | ₹15.57L |
| 5-point buffer: -15% | 40% | +19.99% | -14.50% | +37.80% | -11.70% | -13.86% | ₹2,958 | ₹48,449 | ₹13.78L |

On the same 2023+ test, fixed 45% and 50% controls returned +43.28% / -15.36% OHLC and +48.92% / -16.81% OHLC, respectively. These are comparisons, not alternate training selections. The 70% cap passed the frozen test's historical envelope with 3.19 percentage points of headroom. Its training result was close to the screen, with only 0.93 points of headroom.

The selected 70% cap's constant-cap full-history row in the wider grid returned +107.75% from 2014 through 2026, with a -19.07% OHLC envelope. That row is a full-sample diagnostic; the more relevant evidence for this selection is the frozen 2023+ replay. The related stationary bootstrap of the 70% control estimated a 7.30% close-drawdown breach frequency over a simulated ten-year path with 63-session mean blocks; its 5th-percentile maximum drawdown was -21.19%. That bootstrap is conditional on the observed return stream and is not a forecast.

## Data checks and limits

The 70% training order ledger had zero NIFTYBEES units before the known 2014-03-10 and 2015-02-18 ex-dates, so those two documented cash distributions did not affect this replay. GoldBeES price returns remain subject to incomplete distribution history. The strategy uses daily candles and the OHLC envelope assumes held highs precede held lows on each date; that is not the observed intraday path or a future loss cap.

The broader history and candidate families have already been inspected. This is chronological pseudo-out-of-sample evidence, not a pristine lockbox. Slippage is modeled rather than measured; market impact, investor taxes, and cash yield are excluded. The 70% rule remains a research candidate, not a guaranteed 20% drawdown strategy or live-trading instruction.

## Reproduction

- Runner: [`work/select_etf_exposure_cap_oos.py`](../work/select_etf_exposure_cap_oos.py)
- All training and frozen-test metrics: [`etf_exposure_cap_oos.csv`](etf_exposure_cap_oos.csv)
- Frozen selection record: [`etf_exposure_cap_oos_selection.json`](etf_exposure_cap_oos_selection.json)
- Per-run equity and order ledgers: `work/backtests/etf_exposure_cap_oos/`
- Related 50-bps exposure frontier: [`intraday_ohlc_exposure_sensitivity.csv`](intraday_ohlc_exposure_sensitivity.csv)
- Related resampling risk analysis: [`etf_drawdown_bootstrap_method.md`](etf_drawdown_bootstrap_method.md)
