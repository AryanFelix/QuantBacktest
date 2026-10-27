# NIFTY/Gold joint exposure and volatility-throttle screen

**2026-10-27 fee-model correction:** This static result snapshot predates the instrument-specific ETF STT replay. Use the current sensitivity CSV and consolidated ledger for numeric results; older figures below are superseded where they differ. See the [fee-model audit](../work/research/fee_model_audit.md).


**Status:** corrected retrospective interaction screen. Revision 5 preserves the pre-correction 80% / 16% experiment; corrected continuous drawdown is -28.03%, outside the requested 20% screen. No broker orders are placed.

## Rule and design

The base signals are NIFTYBEES Donchian 55/20 and GOLDBEES 200-session SMA. When both sleeves are active, the portfolio keeps the existing quarterly 63-session inverse-volatility split. When one sleeve is active, the screen sets gross exposure to 65%, 70%, 75%, or 80%. It then tests annual volatility targets of 14%, 16%, and 18%, plus the existing 65% no-throttle control.

At each signal-change or quarter-end close, the throttle multiplies current base targets by min(1, volatility target / trailing realized volatility). Realized volatility is the 63-session annualized sample standard deviation of close-to-close returns for that exposure rule, using its unthrottled weights lagged by one session. Resulting orders fill at the following session's open. Gross exposure never exceeds 100%.

The 130 runs cover 13 rules, five windows, and 10/50 bps per-side slippage. The windows are 2014–2019, 2020–2022, 2023 onward, 2020 onward, and continuous 2014 onward. Each run starts with ₹10 lakh, applies current Upstox/NSE delivery charges uniformly, earns zero on cash, and liquidates at the end. Continuous metrics for the 65% no-throttle control now use normalized daily session dates; pre-correction values are superseded.

## Corrected results at 50 bps per side

| Rule | 2014–2026 ending value / return / CAGR / DD | 2023+ return / CAGR / DD |
|---|---:|---:|
| 65% solo, no throttle | ₹25.26L / +152.55% / 7.65% / -23.80% | +79.19% / 16.85% / -18.32% |
| 65% solo, 16% target | ₹25.56L / +155.58% / 7.76% / -23.80% | +82.13% / 17.36% / -17.40% |
| 70% solo, 16% target | ₹26.24L / +162.37% / 7.98% / -25.23% | +87.33% / 18.24% / -18.49% |
| 75% solo, 16% target | ₹26.78L / +167.83% / 8.16% / -26.64% | +92.14% / 19.05% / -18.86% |
| 80% solo, 14% target | ₹26.41L / +164.09% / 8.04% / -28.03% | +96.81% / 19.81% / -16.92% |
| 80% solo, 16% target | ₹27.33L / +173.28% / 8.33% / -28.03% | +96.98% / 19.84% / -18.86% |
| 80% solo, 18% target | ₹27.86L / +178.61% / 8.50% / -28.03% | +97.69% / 19.95% / -20.57% |

After session-date normalization, every tested rule in the 50 bps, continuous 2014–2026 comparison breaches the 20% close-drawdown screen. The 65%/16% rule returned +155.58% but reached -23.80%; the 80%/16% rule returned +173.28% but reached -28.03%. The 2023+ slice looks materially better, but it has been inspected and does not repair the continuous-history failures. The prior conclusion that 80%/16% passed all ten period/cost cases is superseded. Keep the immutable revision-5 configuration only as a record of the pre-correction experiment; it is not a risk-qualified candidate.

The screen covers 130 cases; the full normalized ledger is authoritative for every period and friction setting. Close-marked results do not include an OHLC portfolio envelope for these throttle variants. A historical screen cannot cap future losses.

## Reproduction

Run work/sensitivity_joint_exposure_volatility.py. The 130-row metric screen is in [joint_exposure_volatility_sensitivity.csv](joint_exposure_volatility_sensitivity.csv); per-run equity/order ledgers and the strategy specification are under work/backtests/joint_exposure_volatility_sensitivity/. The runner checks that seven no-throttle metrics match the established 65% quarterly path.
