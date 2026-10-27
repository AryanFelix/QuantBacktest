# NIFTY/Gold trailing-volatility throttle sensitivity

**2026-10-27 fee-model correction:** This static result snapshot predates the instrument-specific ETF STT replay. Use the current sensitivity CSV and consolidated ledger for numeric results; older figures below are superseded where they differ. See the [fee-model audit](../work/research/fee_model_audit.md).


**Status:** corrected retrospective risk-throttle screen. The revision-4 freeze predates the data correction; all 50 bps full-history throttle cases now fail the 20% close-drawdown screen.

## Rule and calculation

The base portfolio uses NIFTYBEES Donchian 55/20 and GOLDBEES 200-session SMA signals, the existing 63-session inverse-vol split when both sleeves are active, and 65% gross exposure when one sleeve is active. It holds cash when neither signal is active.

At each signal-change or quarter-end rebalance, the screen computes 63-session annualized sample volatility from the base portfolio's close-to-close returns, using the prior session's base weights. It multiplies current base targets by `min(1, volatility threshold / trailing volatility)` and holds that scale until the next rebalance. The estimate uses only closes available at the signal close; modeled orders fill at the next session open. No leverage is used, and the scale cannot increase exposure above the base portfolio.

Thresholds were 8%, 10%, 12%, 14%, and 16%; the no-throttle 65% portfolio is the control. The 60 cases cover five chronological windows and 10/50 bps per-side slippage. Each starts with ₹10 lakh, uses integer ETF units, current Upstox/NSE delivery fees applied uniformly, zero cash interest, and terminal liquidation. Data are saved Upstox daily ETF candles through 2026-10-23.

## Corrected results at 50 bps per side

| Rule | 2014–2026 return / CAGR / DD | 2023+ return / CAGR / DD | Continuous fees | Continuous slippage |
|---|---:|---:|---:|---:|
| No throttle | +152.55% / 7.65% / -23.80% | +79.19% / 16.85% / -18.32% | ₹112,571 | ₹470,381 |
| 8% base-volatility throttle | +101.78% / 5.75% / -23.54% | +74.35% / 16.00% / -10.44% | ₹93,087 | ₹383,446 |
| 10% base-volatility throttle | +127.38% / 6.76% / -23.80% | +81.41% / 17.23% / -12.71% | ₹101,378 | ₹420,182 |
| 12% base-volatility throttle | +142.69% / 7.31% / -23.80% | +81.79% / 17.30% / -14.86% | ₹107,099 | ₹445,851 |
| 14% base-volatility throttle | +152.14% / 7.64% / -23.80% | +82.21% / 17.37% / -16.91% | ₹111,089 | ₹463,824 |
| 16% base-volatility throttle | +155.58% / 7.76% / -23.80% | +82.13% / 17.36% / -17.40% | ₹112,573 | ₹470,400 |

All six settings breach the continuous 20% drawdown screen at 50 bps per side; full-history drawdown ranges from -23.54% to -23.80%. The 16% throttle returned +155.58% at -23.80%, while the 12% throttle returned +142.69% at the same -23.80% maximum drawdown. The throttle reduced later-slice drawdown, but did not reduce the earlier peak-to-trough loss that controls the full-history result. The previous “all 60 cases passed” conclusion is superseded. See the 60-row ledger for the 10 bps cases and all five windows; these also do not establish an intraday or forward risk limit.

## Reproduction

Run `python work/sensitivity_volatility_target.py`. The script writes the 60-row screen to this CSV and saves per-run equity/order ledgers plus `summary.csv` and `strategy.json` under `work/backtests/volatility_target_sensitivity/`. Seven baseline fields are asserted against the established 65% quarterly path before the run is considered complete.
