# NIFTY/Gold single-sleeve deployment sensitivity

**Run date:** 2026-10-27  
**Inputs:** saved Upstox daily ETF candles through 2026-10-23  
**Starting capital:** ₹10,00,000 per run  
**Risk limit:** 20% historical maximum drawdown  
**Status:** corrected retrospective sizing screen; the earlier 65% paper-candidate result is superseded and fails the continuous 20% drawdown screen at 50 bps

## Rule and design

The base sleeves are NIFTYBEES Donchian 55/20 and GOLDBEES 200-session SMA. When both are active, retain the existing 63-session inverse-volatility split. When only one sleeve is active, test gross exposure of 50%, 55%, 60%, 65%, 70%, 75%, or 100%; when neither is active, hold cash. Compare monthly and quarterly calendar schedules while keeping immediate signal-change events. Signals use completed closes and execute at the next session’s open. Gross exposure never exceeds 100%; there is no leverage.

The screen contains 2 schedules × 7 solo-sleeve weights × 5 chronological periods × 2 slippage assumptions = 140 cases. The periods are 2014–2019 training, 2020–2022 validation, 2023–2026 later slice, 2020–2026 flat-start, and continuous 2014–2026 compounding. Every period and the 2023+ slice have already been inspected in the broader research, so none is an untouched lockbox. Costs use current Upstox/NSE charges uniformly over history, including instrument-specific ETF STT, with 10/50 bps adverse slippage per side and 0% cash yield. The 50% solo-exposure rows were regenerated after date and fee corrections; see the [fee audit](../work/research/fee_model_audit.md).

## Corrected results at 50 bps per side

These rows were regenerated using the instrument-specific ETF STT model. The full 140-row screen is in the linked CSV.

| Period | Solo exposure | End value | Return | CAGR | Max drawdown | Fees | Slippage | Orders |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 2014–2019 training | 50% | ₹10.14L | +1.44% | 0.25% | -13.28% | ₹6,760 | ₹147,730 | 94 |
| 2014–2019 training | 65% | ₹10.03L | +0.32% | 0.05% | -16.56% | ₹7,786 | ₹191,281 | 95 |
| 2020–2022 validation | 50% | ₹13.75L | +37.50% | 11.33% | -9.01% | ₹6,011 | ₹137,396 | 83 |
| 2020–2022 validation | 65% | ₹14.45L | +44.52% | 13.21% | -9.78% | ₹6,739 | ₹167,785 | 84 |
| 2023+ later slice | 50% | ₹16.72L | +67.20% | 14.71% | -14.24% | ₹3,545 | ₹77,041 | 49 |
| 2023+ later slice | 65% | ₹18.16L | +81.62% | 17.27% | -17.82% | ₹4,014 | ₹100,451 | 49 |
| 2020–2026 flat-start | 50% | ₹23.54L | +135.41% | 13.60% | -14.23% | ₹9,870 | ₹232,420 | 130 |
| 2020–2026 flat-start | 65% | ₹26.88L | +168.76% | 15.86% | -17.82% | ₹11,425 | ₹302,460 | 131 |
| 2014–2026 continuous | 50% | ₹23.98L | +139.85% | 7.21% | -18.11% | ₹16,632 | ₹379,452 | 224 |
| 2014–2026 continuous | 55% | ₹25.09L | +150.94% | 7.60% | -19.32% | ₹17,389 | ₹411,802 | 225 |
| 2014–2026 continuous | 60% | ₹26.13L | +161.28% | 7.94% | -20.60% | ₹18,173 | ₹449,373 | 225 |
| 2014–2026 continuous | 65% | ₹27.12L | +171.17% | 8.26% | -21.95% | ₹19,095 | ₹489,918 | 225 |
| 2014–2026 continuous | 70% | ₹28.11L | +181.10% | 8.57% | -23.27% | ₹20,056 | ₹532,171 | 225 |
| 2014–2026 continuous | 75% | ₹29.12L | +191.22% | 8.88% | -24.57% | ₹21,034 | ₹575,189 | 225 |
| 2014–2026 continuous | 100% | ₹34.67L | +246.72% | 10.40% | -30.66% | ₹25,168 | ₹797,802 | 203 |

At 50 bps on the continuous account, the 50% solo setting returned +139.85% / -18.11% close drawdown and 55% returned +150.94% / -19.32%. The next tested setting, 60%, reached -20.60%; every higher tested weight also breached 20%. The 50% and 55% quarterly paths were then checked against daily OHLC ranges. Their simultaneous same-day OHLC drawdown bounds were -25.55% and -25.55%, respectively, from the 2020-08-27 peak to the 2020-09-04 trough; both fail the requested 20% screen despite close-only passes. The 50% path ended at ₹23.98 lakh with ₹16,632 fees and ₹3,79,452 modeled slippage; 55% ended at ₹25.09 lakh with ₹17,389 fees and ₹4,11,802 slippage. The audit reconciled each daily close NAV to its order ledger within ₹0.03. These are conservative daily-range bounds, not an observed intraday path. Other solo weights have not received this OHLC audit and remain unqualified. This remains a retrospective sizing screen, not a risk-qualified live rule.

The audit rows are in [`etf_intraday_drawdown_audit.csv`](etf_intraday_drawdown_audit.csv), reproduced by `work/audit_etf_intraday_drawdown.py`. The consolidated ledger marks the two audited full-history 50-bps cases as failing its 20% risk screen.
## Corporate actions and audit

NIFTYBEES has known cash distributions with ex-dates 2014-03-10 and 2015-02-18; the ETF cash/split audit records the source and inferred post-split unit basis. I checked the order ledgers for all 28 continuous 2014–2026 cases (seven solo weights × two schedules × two cost levels). Every path held zero NIFTYBEES units at the prior close on both ex-dates, so those events do not change this strategy family’s historical returns. The saved price series’ split convention remains an empirical inference, not an Upstox guarantee. No GOLDBEES cash distribution was found in the opened AMC action history.

## Limits and prospective follow-up

This is an in-sample exposure sweep across already inspected history. Drawdown estimates are close-marked and future losses can exceed 20%. Current transaction charges are applied uniformly, slippage is modeled rather than observed, cash earns 0%, and investor tax is excluded. The 65% quarterly path remains in the historical revision-3 freeze only for lineage; its current continuous close drawdown is -21.95%, so it is not risk-qualified for the requested 20% limit.

Reproduce with `python work/sensitivity_single_sleeve_deployment.py`. It saves all 140 metric rows in `outputs/single_sleeve_deployment_sensitivity.csv`, daily equity and order files under `work/backtests/single_sleeve_deployment/`, and the rule and source paths in `work/backtests/single_sleeve_deployment/strategy.json`. Fee details and primary rate links are in [`volatility_weighted_blend_method.md`](volatility_weighted_blend_method.md); the ETF event ledger is [`etf_corporate_action_audit.csv`](etf_corporate_action_audit.csv).
