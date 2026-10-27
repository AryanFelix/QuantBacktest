# ETF daily timestamp and drawdown audit

**Reviewed:** 2026-10-27  
**Capital:** ₹10 lakh  
**Cost case:** current modeled NSE/Upstox delivery charges plus 50 bps per-side slippage  
**Reference risk limit:** 20% peak-to-trough

## Daily candle session-date correction

The saved Upstox daily ETF bars did not all use midnight timestamps. For example, on 2016-01-15 NIFTYBEES is timestamped 09:15 IST and GOLDBEES 09:16 IST. The old simulator joined bars by exact timestamp, so these two bars became separate rows even though both represented the same daily session. The old quarterly control ledger had 3,232 rows for 3,166 NIFTYBEES session dates, including 66 extra same-date rows in the NIFTY/Gold panel.

Upstox's [Historical Candle V3 documentation](https://upstox.com/developer/api-documentation/v3/get-historical-candle-data/) describes the timestamp as the start of the candle timeframe and shows daily candles at 00:00 IST. This cache has non-midnight session stamps, so the daily simulator now normalizes files named `-days-1-` to their local calendar session before joining instruments. It collapses repeated same-day bars only when every OHLCV field matches; conflicting same-day records raise an error. Intraday inputs retain their original timestamps. A targeted exact-key request for 2016-01-15 failed at DNS resolution before an API response, so this pass did not freshly retrieve that candle.

The cache scan covered 95 `days-1` CSV paths: 94 contain OHLC fields and one is an NSE TRI file with a different schema. Eleven OHLC paths contain non-midnight timestamps and repeated session dates. Ten ETF cache paths contain same-day duplicates with identical candle fields. The original India VIX cache has three duplicate session dates with conflicting values, so the shared loader correctly fails closed on that raw file. The overlay research now uses a separate reconciled file: NSE official daily OHLC replaces those three dates while the raw Upstox cache remains unchanged. The source responses and 90-case rerun are documented in [the VIX method](india_vix_overlay_method.md).

This issue affected previous multi-asset daily results that relied on exact timestamp joins. The 2026-10-27 ETF-unit STT correction then required a second replay of each affected ETF screen; all listed CSVs and run-level paths below are now current. The ETF fee correction and its source rates are described in [the fee-model audit](../work/research/fee_model_audit.md). The India VIX raw cache still fails closed; its overlay uses the separate NSE-reconciled input. Stock momentum aligns dates within its own daily reader; its separate constituent and corporate-action limitations remain.

## Corrected NIFTY/Gold results

All results below use daily session-date alignment, next-session-open entries/exits, integer ETF units, modeled fees, 0% interest on cash, and ₹10 lakh initial capital. The listed rules were chosen from previously inspected history; the 2023+ slice and bootstrap do not create an untouched lockbox.

| Rule | Gross cap | Ending value | Net return | Close MDD | OHLC bound | Fees | Orders |
|---|---:|---:|---:|---:|---:|---:|---:|
| Quarterly fixed 50/50 trend sleeves | 100% | ₹23.76L | +137.64% | -17.86% | -25.66% | ₹16,110 | 220 |
| Quarterly 63-session inverse-vol NIFTY/Gold | 100% | ₹23.98L | +139.85% | -18.11% | -25.55% | ₹16,632 | 224 |
| Quarterly fixed sleeves, risk-scaled | 45% | ₹17.78L | +77.77% | -15.23% | -16.15% | ₹14,647 | 225 |
| Quarterly fixed sleeves, risk-scaled | 70% | ₹20.77L | +107.75% | -17.18% | -19.07% | ₹15,647 | 225 |
| Quarterly fixed sleeves, risk-scaled | 74% | ₹21.16L | +111.65% | -17.27% | -19.99% | ₹15,643 | 225 |
| Quarterly inverse-vol; 65% solo sleeve / 16% vol target | 100% overall | ₹27.44L | +174.43% | -21.95% | -25.55% | ₹19,093 | 225 |
| Quarterly inverse-vol; 80% solo sleeve / 16% vol target | 100% overall | ₹29.80L | +197.98% | -25.85% | -26.84% | ₹21,631 | 225 |

The two highest-return continuous rows from the seven-setting local parameter sweep were also replayed through this OHLC check. Both are post-hoc challengers selected by their full-sample returns, and both fail the requested drawdown limit:

| Post-hoc challenger | Ending value | Net return | Close MDD | OHLC bound | Fees | 20% OHLC screen |
|---|---:|---:|---:|---:|---:|---|
| Donchian 55/30 + Gold SMA200 | ₹25.55L | +155.50% | -14.85% | -25.53% | ₹20,334 | Fail |
| Donchian 40/20 + Gold SMA200 | ₹25.46L | +154.61% | -15.18% | -25.53% | ₹21,142 | Fail |

Both envelopes span the same 2020-08-27 high to 2020-09-04 low. The 2020–2022 and 2023+ close-return slices were positive for both variants, but they are not untouched holdouts because these variants were selected after inspecting the full sweep. Bootstrap results were not run for these candidates because the OHLC envelope already breaches the 20% constraint.

## Chronological NIFTY/Gold blend holdout OHLC audit

The monthly NIFTYBEES Donchian 55/20 + GOLDBEES 200DMA rule selected a 95% exposure cap from a fixed 10/25/50/75/95% grid at 10 bps per side, using only the preceding training and validation windows. I rebuilt both later windows at 50 bps per-side slippage and replayed their saved orders against daily OHLC. The selection windows were 2014–2017 / 2018–2019 for the 2020+ fold, and 2014–2019 / 2020–2022 for the 2023+ fold.

| Test fold | Ending value | Net return | Close MDD | Daily OHLC bound | Fees | Slippage | Orders | 20% envelope screen |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| 2020-01–2026-10-23 | ₹22.63L | +126.34% | -14.21% | -24.41% | ₹11,889 | ₹2,02,682 | 201 | Fail |
| 2023-01–2026-10-23 | ₹16.37L | +63.69% | -14.22% | -16.28% | ₹4,924 | ₹71,210 | 89 | Pass, 3.72 pp headroom |

The 2020+ envelope breaches from the 2020-08-27 high through the 2020-09-04 low. The 2023+ fold is the stronger risk-qualified historical holdout and is the same monthly 95% path already frozen in forward-paper revision 7. Its 2023–2026 history has nevertheless been inspected during this research; it is not a pristine lockbox. Both folds use zero cash yield and credit no cash distributions. The close drawdown and daily OHLC envelope are different measures; the latter assumes all held assets hit their highs before their lows on each day.

The OHLC bound raises the running peak using each held ETF's daily high, then measures the trough using each held ETF's daily low. It assumes all held assets hit their highs before all hit their lows on the same session. It is a conservative envelope, not a synchronized or observed intraday portfolio path. The positions and cash are reconstructed from orders; reconstructed daily closes match the saved ledgers within ₹0.000001.

The 100% quarterly inverse-vol candidate returns +139.85% with -18.11% close drawdown, but its simultaneous-high/low OHLC envelope is -25.55%. It therefore fails the requested 20% limit under this conservative risk check; its 10-year block-bootstrap 20% breach estimate is 7.58%–10.66% across 21/63/126-session blocks.

A coarse-to-fine gross-cap screen tested 25%–100%, with additional 71%–74% cases. The highest tested cap that stayed inside -20% was 74%, but it had just 0.009 percentage points of bound headroom and is not a practical risk margin. At 70%, the bound leaves 0.935 points. At 45%, it leaves 3.849 points and the 10-year stationary-bootstrap breach frequency is lower. These remain retrospective sizing comparisons, not a promise to contain future losses.

| Fixed-rule gross cap | OHLC bound headroom | 10-year close-return bootstrap breach rate (63-session mean block) | Median max drawdown | 5th-percentile max drawdown |
|---:|---:|---:|---:|---:|
| 45% | 3.849 pp | 3.54% | -12.74% | -19.08% |
| 70% | 0.935 pp | 7.30% | -13.95% | -21.19% |

The bootstrap resamples historical net daily returns; it does not rebuild indicators, orders, costs, or risk caps on synthetic price paths. The three block lengths and four horizons are saved in [`etf_drawdown_bootstrap.csv`](etf_drawdown_bootstrap.csv). The full exposure curve and reproducible runner are in [`intraday_ohlc_exposure_sensitivity.csv`](intraday_ohlc_exposure_sensitivity.csv) and `work/sensitivity_intraday_ohlc_exposure.py`.

## Reproduction and limitations

Run from the `work` directory:

```powershell
python replay_volatility_weighted_blend.py
python sensitivity_single_sleeve_deployment.py
python sensitivity_joint_exposure_volatility.py
python sensitivity_cost_stress.py
python sensitivity_intraday_ohlc_exposure.py
python bootstrap_etf_drawdown_risk.py
```

Then run `python audit_etf_intraday_drawdown.py` to reconcile ten control/challenger order ledgers to close NAV and recompute their daily OHLC bounds. The two selected 95% holdout replays are generated by `python replay_donchian_gold_blend.py`. No live orders were placed. Actual spreads, partial fills, taxes, ETF cash distributions outside the known unheld ex-dates, and live operational stops are not modeled. Paper revision 7 is frozen before the 2026-10-27 close; 2026-10-26 is the latest common completed candle, and the 2026-10-28 prospective start has not produced a post-freeze return. The 74% result is a historical grid maximum, not an established winner.
