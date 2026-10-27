# NIFTY/Gold execution-cost stress

**2026-10-27 fee-model correction:** This static result snapshot predates the instrument-specific ETF STT replay. Use the current sensitivity CSV and consolidated ledger for numeric results; older figures below are superseded where they differ. See the [fee-model audit](../work/research/fee_model_audit.md).


**Status:** corrected retrospective cost stress on the quarterly inverse-volatility ETF blend. At the 50 bps base case, all continuous 2014–2026 rules breach the requested 20% close-drawdown screen; this does not estimate realized spreads or establish a winner.

## Design

The 125 runs combine five rules, five chronological windows, and 10/50/100/150/200 bps of fixed slippage per executed side. Rules are the 65% solo-sleeve baseline with and without a 16% annualized volatility throttle, plus 80% solo-sleeve rules with 14%, 16%, or 18% targets. When both trend sleeves are active, all rules retain the quarterly 63-session inverse-volatility split. When one is active, the rule applies its stated solo exposure; the throttle scales it by `min(1, target / trailing 63-session annualized volatility)` using lagged daily portfolio returns. Signals and risk estimates use information through the close; orders fill at the next session's open. Gross exposure is capped at 100%.

Each period starts with ₹10 lakh, earns zero on cash, uses current Upstox/NSE equity-delivery fees uniformly across history, and liquidates at the end. Windows are 2014–2019, 2020–2022, 2023 onward, 2020 onward, and continuous 2014 onward, with market data through 2026-10-23. Drawdown is measured on daily close-marked NAV, so intraday lows and gap execution can be worse. All windows and candidate rules have already been inspected; 2023 onward is not an untouched holdout. Investor taxes and actual bid/ask spreads are not modeled.

Slippage is a fixed sensitivity per side: 100 bps therefore adds 2% round-trip friction for a buy and later sell, before brokerage and statutory charges. The 100–200 bps settings are deliberately severe stress cases, not forecasts of NIFTYBEES or GOLDBEES execution. Fee and slippage amounts are reported separately.

## Corrected continuous result and risk frontier

All accounts start at ₹10 lakh and compound continuously from 2014 through 2026-10-23. `DD passes` counts how many of the five windows stayed within the historical 20% close-drawdown screen.

| Rule | Slippage per side | Ending value | Total return | Max drawdown | DD passes |
|---|---:|---:|---:|---:|---:|
| 65% solo, no throttle | 10 bps | ₹33.57L | +235.70% | -17.40% | 5/5 |
| 65% solo, no throttle | 50 bps | ₹25.26L | +152.55% | -23.80% | 4/5 |
| 65% solo, no throttle | 100 bps | ₹17.66L | +76.62% | -34.53% | 1/5 |
| 65% solo, no throttle | 150 bps | ₹12.33L | +23.32% | -45.37% | 0/5 |
| 65% solo, no throttle | 200 bps | ₹8.59L | -14.05% | -54.46% | 0/5 |
| 65% solo, 16% target | 10 bps | ₹33.97L | +239.70% | -17.40% | 5/5 |
| 65% solo, 16% target | 50 bps | ₹25.56L | +155.58% | -23.80% | 4/5 |
| 65% solo, 16% target | 100 bps | ₹17.88L | +78.76% | -34.53% | 3/5 |
| 65% solo, 16% target | 150 bps | ₹12.48L | +24.83% | -45.37% | 0/5 |
| 65% solo, 16% target | 200 bps | ₹8.70L | -12.98% | -54.46% | 0/5 |
| 80% solo, 14% target | 10 bps | ₹37.23L | +272.26% | -18.91% | 5/5 |
| 80% solo, 14% target | 50 bps | ₹26.41L | +164.09% | -28.03% | 3/5 |
| 80% solo, 14% target | 100 bps | ₹17.14L | +71.42% | -41.28% | 3/5 |
| 80% solo, 14% target | 150 bps | ₹11.09L | +10.94% | -53.10% | 0/5 |
| 80% solo, 14% target | 200 bps | ₹7.16L | -28.41% | -64.11% | 0/5 |
| 80% solo, 16% target | 10 bps | ₹38.63L | +286.30% | -18.91% | 5/5 |
| 80% solo, 16% target | 50 bps | ₹27.33L | +173.28% | -28.03% | 3/5 |
| 80% solo, 16% target | 100 bps | ₹17.68L | +76.77% | -41.28% | 1/5 |
| 80% solo, 16% target | 150 bps | ₹11.40L | +14.02% | -53.10% | 0/5 |
| 80% solo, 16% target | 200 bps | ₹7.33L | -26.68% | -62.85% | 0/5 |
| 80% solo, 18% target | 10 bps | ₹39.45L | +294.54% | -20.57% | 2/5 |
| 80% solo, 18% target | 50 bps | ₹27.86L | +178.61% | -28.03% | 1/5 |
| 80% solo, 18% target | 100 bps | ₹17.98L | +79.77% | -41.28% | 1/5 |
| 80% solo, 18% target | 150 bps | ₹11.57L | +15.67% | -53.10% | 0/5 |
| 80% solo, 18% target | 200 bps | ₹7.42L | -25.79% | -62.60% | 0/5 |

At 50 bps, every continuous 2014–2026 case fails the 20% drawdown screen; the 65%/16% rule returned +155.58% but reached -23.80%, while 80%/16% returned +173.28% at -28.03%. At 100 bps, every rule also breaches on the continuous path. Only the 10 bps cases for the 65% and 80% rules pass all five windows; the 80%/18% rule still fails. The earlier conclusions that 65%/16% passed all five windows at 100 bps and that most 50 bps cases passed are superseded by the corrected date-aligned replays.

The 100–200 bps settings are deliberately severe sensitivities, not forecasts of actual NIFTYBEES or GOLDBEES execution. A 10 bps result is also not evidence of executable spread. Full scenario details, including 2014–2026 drawdown, remain in the CSV.

## Reproduction and artifacts

Run `work/sensitivity_cost_stress.py`. It writes the 125-row screen to [cost_stress_sensitivity.csv](cost_stress_sensitivity.csv), with per-run equity and order ledgers plus the rule/cost specification under `work/backtests/cost_stress_sensitivity/`. The runner checks target exposures never exceed the unthrottled base and verifies 175 metrics against the earlier joint screen at 50 bps. All 125 scenario keys are unique.
