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

Runner: `work/select_passive_drawdown_control_walkforward.py`. Results: `outputs/passive_drawdown_control_walkforward.csv`; frozen rule record: `outputs/passive_drawdown_control_walkforward_selection.json`.
