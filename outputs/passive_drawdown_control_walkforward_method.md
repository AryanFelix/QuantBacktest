# Passive NIFTY/Gold drawdown-control walk-forward selection

**Protocol frozen:** 2026-10-27  
**Capital:** ₹10 lakh for each independent period replay  
**Base allocation:** 60% gross exposure, split equally between NIFTYBEES and GOLDBEES; trigger cuts to 30% and recovers at half the drawdown trigger  
**Primary cost:** current modeled Upstox/NSE delivery fees plus 50 bps per side  
**Risk screen:** simultaneous daily OHLC drawdown bound no worse than -20%

## Frozen experiment

Compare only the already specified 8%, 10%, and 12% close-NAV drawdown triggers. Select the highest net-return rule that passes the -20% OHLC screen on 2015-01-02 through 2019-12-31 at 50 bps per side; ties prefer the lower trigger. If none pass, record no selection. Do not tune the recovery ratio, high/low exposure, cost level, or dates.

Replay all three fixed trigger rules and 45%/60% passive controls on independent ₹10 lakh accounts over training (2015–2019), validation (2020–2022), and later pseudo-holdout (2023-01-01 through 2026-10-23). Run the selected trigger on validation and pseudo-holdout at 10 and 100 bps as cost sensitivities; the selected 50-bps cases are already included in the all-trigger comparison. Each period starts from cash and resets its high-water mark, so segment returns and drawdowns are not a continuous account path.

Signals use completed daily close NAV and target changes fill at the next open. The control is not an intraday stop. The existing simulator applies whole-unit sizing, current delivery fees, 0% cash yield, and known NIFTYBEES distributions; GoldBeES distribution coverage remains unresolved. The 2020+ records and this strategy family have already been inspected, so the later periods are not an untouched lockbox. No historical result guarantees a future 20% maximum drawdown.

## Additional 200-bps-per-side stress

The original 50-bps training run had no threshold activations, so the 8% and 10% rules tied on net return and the specified lower-trigger tie-break selected 8%. A supplementary 200-bps-per-side replay kept both thresholds unchanged and added a fixed 45% passive reference. Continuous 2015–2026 returns were +125.69% / -17.41% OHLC for the passive path, +130.01% / -16.95% for the 8% trigger, and +132.92% / -16.94% for the 10% trigger. The passive path modeled ₹299 in fees and ₹44,116 in slippage over four orders; the 8% rule modeled ₹648 and ₹64,197 over 10 orders; 10% modeled ₹649 and ₹64,934 over 10 orders. Independent-cash validation returned +19.34% / -16.61% and +19.67% / -16.68%; already-inspected 2023+ pseudo-holdout returned +53.27% / -13.74% and +53.23% / -13.80% for 8%/10%, respectively. All historical paths passed the 20% envelope. This is a deliberate high-friction sensitivity, not a measured spread or independent validation; these remain paper challengers.

A separate 5,000-path paired-OHLC stateful bootstrap applied the same 200-bps cost to 10-year synthetic paths. At 63-session mean blocks, the -20% envelope-breach estimate was 20.12% for the passive 45% path, 11.74% for the 8% trigger, and 18.74% for the 10% trigger. Across 21/63/126-session blocks, rates were 12.26/11.74/9.42% for 8% and 22.22/18.74/14.52% for 10%. At 63-session blocks, fifth-percentile OHLC drawdowns were -23.20%/-21.18%/-22.06% for passive/8%/10%, while median CAGRs were 7.44%/6.45%/6.94%. These conditional resampling estimates do not make the 20% limit reliable or guaranteed; each 5th-percentile path breaches.

Runner: `work/select_passive_drawdown_control_walkforward.py`. Results: `outputs/passive_drawdown_control_walkforward.csv`; frozen rule record: `outputs/passive_drawdown_control_walkforward_selection.json`. Reproduce the added stress with `python work/stress_passive_drawdown_control_200bps.py` and paired-OHLC bootstrap with `python work/bootstrap_passive_drawdown_control_200bps.py`; outputs are `outputs/passive_drawdown_control_200bps_stress.csv` and `outputs/stateful_drawdown_control_200bps_bootstrap.csv`.
