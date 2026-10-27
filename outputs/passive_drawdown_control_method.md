# Passive NIFTY/Gold drawdown-control experiment

**Run date:** 2026-10-27  
**Capital:** ₹10,00,000  
**History:** 2015-01-02 through 2026-10-23  
**Risk screen:** conservative daily OHLC maximum drawdown no worse than -20%

## Rule and comparison

The portfolio begins at 60% gross exposure, split equally between NIFTYBEES and GOLDBEES. At each daily close, it measures close-marked NAV against its running NAV high-water mark, including the initial ₹10 lakh. If drawdown reaches -8%, -10%, or -12%, the policy cuts total target exposure to 30% (15% per ETF) at the next session's open. It restores 60% exposure (30% per ETF) when drawdown recovers to half the trigger, at the next open. The hysteresis avoids toggling around one threshold. The signal uses only completed close NAV; no intraday low triggers same-day trades.

Holdings are whole ETF units. The simulator uses the shared NSE fee calculator, current instrument-specific ETF STT, 0% cash yield, and known NIFTYBEES distributions. It tests 10, 50, and 100 bps per-side slippage; 100 bps is a cost stress. Each run starts with cash and liquidates at the final close. The 45% and 60% fixed passive equal-mix controls are replayed in the same runner; their equity, order counts, and fees are asserted against the established simulator before results are written.

## Results

Net return is shown for all three slippage levels. All 15 paths pass the historical daily OHLC screen.

| Policy | Net return at 10 / 50 / 100 bps | Close MDD at 50 bps | OHLC bound at 10 / 50 / 100 bps | Fees / slippage at 50 bps | Orders |
|---|---:|---:|---:|---:|---:|
| Fixed 45% initial exposure | +129.88% / +129.00% / +127.90% | -15.58% | -17.35% / -17.37% / -17.38% | ₹299 / ₹11,029 | 4 |
| Fixed 60% initial exposure | +173.19% / +172.02% / +170.54% | -17.20% | -19.20% / -19.23% / -19.27% | ₹351 / ₹14,706 | 4 |
| 8% trigger; cut 60→30; recover at 4% | +140.47% / +138.78% / +135.97% | -12.22% | -16.80% / -16.83% / -16.86% | ₹650 / ₹16,314 | 10 |
| 10% trigger; cut 60→30; recover at 5% | +143.31% / +141.16% / +137.73% | -12.37% | -16.80% / -16.83% / -16.86% | ₹652 / ₹16,505 | 10 |
| 12% trigger; cut 60→30; recover at 6% | +135.68% / +133.01% / +130.94% | -15.33% | -17.94% / -17.97% / -18.01% | ₹646 / ₹15,965 | 10 |

At 50 bps, the 8% and 10% rules returned more than the fixed 45% path and had less-negative close and OHLC drawdowns. They returned less than fixed 60%, which had only 0.73 percentage points of historical OHLC headroom. The 12% rule was weaker than the 8% and 10% rules on both return and resampled drawdown risk. Each throttle cut twice and recovered once. For the 10% rule, the cuts were filled on 2020-03-18 and 2026-03-20, with a recovery on 2020-07-08; it remained at 30% exposure at the 2026-10-23 end date.

## Conditional bootstrap stress

The 5,000-path stationary bootstrap resamples each already-generated strategy's daily net returns in blocks; it does not rebuild the price path and re-run the drawdown trigger. The percentages are therefore conditional return-process stresses, not policy-level forecasts.

| Rule | 10-year drawdown breach at 21 / 63 / 126-session blocks | 5th-percentile MDD at 63 sessions | Median CAGR at 63 sessions |
|---|---:|---:|---:|
| Fixed 45% control | 3.68% / 3.58% / 3.78% | -19.16% | 7.42% |
| Fixed 60% control | 11.42% / 10.00% / 10.68% | -22.03% | 9.10% |
| 8% trigger | 2.62% / 1.46% / 0.86% | -17.36% | 7.82% |
| 10% trigger | 2.98% / 1.96% / 1.74% | -17.83% | 7.90% |
| 12% trigger | 8.08% / 6.70% / 7.76% | -20.83% | 7.69% |

The 8% and 10% controls look stronger than the fixed 45% path in this historical-return resampling, while the 12% control does not. This evidence is not independent: the common history was already inspected, only three historical trigger events occurred, and the bootstrap does not resimulate the state transitions. Keep all three frozen for prospective paper observation to avoid picking a threshold from this sample.

## Reproduction and limits

Run `python work/backtest_passive_mix_drawdown_control.py`. The 15-case ledger is [`passive_drawdown_control_sensitivity.csv`](passive_drawdown_control_sensitivity.csv); per-case daily equity and orders are under `work/backtests/passive_drawdown_control/`. The results feed [`etf_drawdown_bootstrap.csv`](etf_drawdown_bootstrap.csv), reproduced by `work/bootstrap_etf_drawdown_risk.py`. The strategy rationale and primary-source review are in [`drawdown_trigger_experiment_rationale.md`](../work/research/drawdown_trigger_experiment_rationale.md).

High-water drawdown control is an exposure response, not a hard stop. A gap can cross the threshold before the next-open reduction; the OHLC envelope accounts for same-day high/low ordering on the historical path, not unseen future gaps. ETF distribution coverage remains incomplete for Gold, cash interest is zero, 10/50/100 bps are modeled slippage rather than measured spreads, and all historical dates were inspected. The 8/10/12% rules are separately frozen as paper-only challengers before the 2026-10-27 close; they place no broker orders and have no independent forward evidence yet.
