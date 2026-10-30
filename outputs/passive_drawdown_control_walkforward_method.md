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

The original 50-bps training run had no threshold activations, so the 8% and 10% rules tied on net return and the specified lower-trigger tie-break selected 8%. A supplementary 200-bps-per-side replay kept both thresholds unchanged and added a fixed 45% passive reference. Continuous 2015–2026 returns were +125.69% / -17.41% OHLC for the passive path, +130.01% / -16.95% for the 8% trigger, and +132.92% / -16.94% for the 10% trigger. After the GST-on-SEBI correction, the passive path modeled ₹299.26 in fees and ₹44,116 in slippage over four orders; the 8% rule modeled ₹648.38 and ₹64,197 over 10 orders; 10% modeled ₹649.88 and ₹64,934 over 10 orders. Independent-cash validation returned +19.34% / -16.61% and +19.67% / -16.68%; already-inspected 2023+ pseudo-holdout returned +53.27% / -13.74% and +53.23% / -13.80% for 8%/10%, respectively. All historical paths passed the 20% envelope. This is a deliberate high-friction sensitivity, not a measured spread or independent validation; these remain paper challengers.

A separate 5,000-path paired-OHLC stateful bootstrap applied the same 200-bps cost to 10-year synthetic paths. The expanded run covers six equal-sleeve passive initial allocations (20/25/30/35/40/45%) and the 8%/10% triggers: 24 policy/block summaries across 21/63/126-session mean blocks. For the 30% initial allocation, estimated OHLC-envelope breach rates were 3.78/3.18/2.94%, with fifth-percentile envelopes -19.27/-19.06/-18.93%. The 25% allocation had rates 1.30/1.24/1.08% and fifth-percentile envelopes -17.50/-17.35/-17.43%. By comparison, the 8% trigger had rates 12.26/11.74/9.42% and fifth-percentile envelopes -21.24/-21.18/-20.90%; the 10% trigger had rates 22.22/18.74/14.52% and envelopes -22.28/-22.06/-21.65%. These are conditional estimates from inspected history, not forecasts or guarantees.

At 200 bps, the 30% initial equal mix returned +83.78% over 2015–2026 with a -14.66% historical OHLC bound; independent-cash validation returned +11.75% / -9.12%, and the already-inspected 2023+ segment +24.44% / -11.32%. The 25% initial mix returned +69.82% with a -13.40% historical bound. The 30% rule is the highest tested initial allocation whose fifth-percentile OHLC envelope stayed above -20% at all three block lengths, but its narrowest margin is only 0.73 percentage points. These are initial allocations, not maintained caps: 30% drifted to 67.03% peak gross exposure in the replay. The 25% rule has more simulated cushion and less return; neither enforces a 20% future loss ceiling. All settings were examined retrospectively and remain paper-only.

A separate 30/70 composition extension found +93.33% return and -17.04% historical OHLC at 30% initial exposure, versus +77.77% / -15.66% at 25%. Stateful bootstrap breach rates for 30% 30/70 were 4.54/4.34/5.60% across 21/63/126-session blocks; its 126-block fifth percentile was -20.27%. The 25% 30/70 case had 1.86/1.94/2.78% rates and fifth percentiles -18.18/-18.22/-18.69%. The higher-return 30/70 setting therefore fails the 20% fifth-percentile screen at the longest tested block. Reproduction and limits are in the [composition cost note](passive_mix_composition_cost_method.md).

The 2026 official-fee audit found that the shared helper omitted 18% GST on SEBI turnover fees. The helper is corrected and the passive-control sensitivity and 50/200-bps stateful bootstraps were regenerated. This adds less than ₹0.60 in charges to each of the three 200-bps full-period paths and does not change the rounded return or risk conclusion. A scan of stored scenario ledgers found a maximum ₹41.34 adjustment per ledger; those outputs overlap across parameter grids and must not be summed. Other strategy tables have not all been regenerated. See [the source and fee-model audit](../work/research/cash_etf_delivery_cost_sources_2026-10-30.md); actual spreads and market impact are still unmeasured.

Runner: `work/select_passive_drawdown_control_walkforward.py`. Results: `outputs/passive_drawdown_control_walkforward.csv`; frozen rule record: `outputs/passive_drawdown_control_walkforward_selection.json`. Reproduce the 200-bps exposure/trigger stress with `python work/stress_passive_drawdown_control_200bps.py` and paired-OHLC bootstrap with `python work/bootstrap_passive_drawdown_control_200bps.py`; outputs contain 24 replays and 24 bootstrap summaries in `outputs/passive_drawdown_control_200bps_stress.csv` and `outputs/stateful_drawdown_control_200bps_bootstrap.csv`.

## 20%-to-10% trigger comparison at 200 bps

As a post-hoc sizing comparison, the 20% initial 30/70 NIFTY/Gold mix cuts its target exposure to 10% after close-NAV drawdown reaches 8%, then restores 20% after drawdown recovers to -4%; changes fill at the next open. This reuses the earlier 8/4 threshold and does not retune it on the low-exposure sample. All periods were already inspected.

| Period | Net return | Close MDD | OHLC bound | Trigger / recovery |
|---|---:|---:|---:|---:|
| Continuous 2015–2026 | +66.12% | -9.61% | -11.46% | 1 / 0 |
| Training 2015–2019 | +7.72% | -2.84% | -3.32% | 0 / 0 |
| Validation 2020–2022 | +7.09% | -3.37% | -6.46% | 0 / 0 |
| Pseudo-holdout 2023–2026 | +20.00% | -8.99% | -10.10% | 1 / 0 |

Against the fixed 20% initial 30/70 path, the trigger version had a higher continuous historical return (+66.12% vs +62.21%) and smaller OHLC envelope (-11.46% vs -13.96%). The stateful 5,000-path bootstrap, using the same sampled paths for both, estimated zero -20% envelope breaches for the trigger version at 21/63/126-session mean blocks; fifth-percentile envelopes were -14.38/-13.96/-13.62%. Fixed 20% had estimated breaches of 0.42/0.56/0.92% and fifth percentiles -16.25/-16.35/-16.80%. The trigger version's 126-block median CAGR was lower, 3.54% vs 4.06%, showing the risk/return tradeoff. Zero of 5,000 sampled breaches is not zero true risk; a rule-of-three 95% upper bound is about 0.06% per estimate.

This result is not independent validation: the continuous and later periods were inspected and the pseudo-holdout had the sole historical trigger. The 20% is an initial target, not a maintained gross exposure cap; it drifted to 56.72% peak exposure before the cut. Fees use the corrected current model, 200 bps per-side slippage is assumed rather than observed, cash yield is zero, and Gold distributions remain incomplete. It remains paper-only. Reproduce with `work/stress_passive_exposure_trigger_20_to_10_200bps.py` and `work/bootstrap_passive_exposure_trigger_20_to_10_200bps.py`; the four replay rows and three stateful summaries are in `outputs/passive_exposure_trigger_20_to_10_200bps.csv` and `outputs/passive_exposure_trigger_20_to_10_200bps_bootstrap.csv`.
