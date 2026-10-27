# Quarterly inverse-volatility NIFTY/Gold ETF blend challenger

**Run date:** 2026-10-27  
**Data:** saved Upstox daily ETF candles through 2026-10-23  
**Capital:** ₹10,00,000  
**Risk screen:** maximum historical drawdown 20%  
**Status:** fee-corrected retrospective challenger; at 50 bps it adds 2.21 pp to the fixed quarterly control, with a -18.11% close drawdown; its -25.55% OHLC envelope fails the requested screen.

## Frozen rules and comparison

The fixed control uses NIFTYBEES Donchian 55/20 and GOLDBEES 200DMA with 50% target weight per active sleeve. The monthly schedule rebalances at signal changes and month-end; the quarterly schedule uses the same signal-change events and calendar quarter-end instead. When both sleeves are active, the inverse-vol challenger allocates in proportion to the inverse of each ETF's trailing 63-session realized volatility. When one sleeve is active it keeps that sleeve at 50% of NAV; with neither active it holds cash. Weights use data through the signal close and trade at the next session open. Gross exposure never exceeds 100%; there is no leverage.

The 63-session window was fixed before the prior monthly weighting replay; the quarterly frequency was added as a retrospective schedule comparison and was not selected on an untouched sample. The run covers four portfolio/schedule variants, five windows (2014–2019 train, 2020–2022 validation, 2023–2026 holdout slice, 2020–2026 full period, and one continuous 2014–2026 account), and 10/50 bps per-side slippage: 40 scenarios total. Each window starts from ₹10 lakh; the 2014–2026 case compounds continuously without resetting at the split dates. The 2023 slice starts from a fresh ₹10 lakh balance but is not independent because this history was already inspected.

Current Upstox/NSE charges and stated slippage are applied. The simulator includes ₹20 per executed order, instrument-specific STT, stamp duty, NSE transaction/IPFT, SEBI turnover, DP sell charges, and GST. NIFTYBEES uses equity-oriented-fund STT (nil on buys and 0.001% on delivery sells); GOLDBEES uses no STT. Current rates are applied uniformly to history as a cost stress, not as historical contract-note reconstruction. [Upstox charges](https://upstox.com/brokerage-charges/), [NSE levies](https://www.nseindia.com/static/invest/first-time-investor-sebi-turnover-fees-stt-other-levies), and [AMFI guidance](https://www.amfiindia.com/investor/knowledge-center-info?zoneName=TaxRegimeForMutualFunds) support the instrument distinction. See the [fee audit](../work/research/fee_model_audit.md).

A live one-day API probe fetched NIFTYBEES (`NSE_EQ|INF204KB14I2`) for 2026-10-23. Its OHLCV row matched the saved candle exactly. The runner authenticated through the current user's `HKCU\Environment` registry fallback while the process environment was unset; no token was written to artifacts. A query through 2026-10-26 returned no bars; the saved response is `work/data/api_probes/NIFTYBEES_2026-10-24_to_2026-10-26_empty.csv`. This verifies current API access and one-row cache agreement, not a fresh re-download of all historical inputs.

## Corrected results

Returns and end balances are net of modeled fees and slippage; cash earns 0%. The 20% screen uses daily close-marked NAV. The table highlights the 2020+ and 2023+ windows at both friction levels; the full 40-case ledger contains all training and validation scenarios.

| Window | Portfolio | Slip bps/side | End value | Return | CAGR | Max close drawdown | Fees | Slippage | Orders | 20% screen |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| 2020-01–2026-10 | Fixed monthly 50/50 control | 10 | ₹25.71L | +157.14% | 15.10% | -13.60% | ₹12,333 | ₹44,040 | 199 | Pass |
| 2020-01–2026-10 | Fixed monthly 50/50 control | 50 | ₹23.07L | +130.74% | 13.26% | -14.21% | ₹12,051 | ₹206,965 | 197 | Pass |
| 2020-01–2026-10 | Inverse-vol monthly | 10 | ₹26.45L | +164.50% | 15.59% | -13.60% | ₹12,963 | ₹51,666 | 201 | Pass |
| 2020-01–2026-10 | Inverse-vol monthly | 50 | ₹23.29L | +132.92% | 13.42% | -14.21% | ₹12,624 | ₹240,319 | 200 | Pass |
| 2020-01–2026-10 | Fixed quarterly 50/50 control | 10 | ₹25.91L | +159.13% | 15.24% | -13.95% | ₹9,712 | ₹43,423 | 129 | Pass |
| 2020-01–2026-10 | Fixed quarterly 50/50 control | 50 | ₹23.30L | +132.98% | 13.42% | -14.23% | ₹9,416 | ₹204,282 | 127 | Pass |
| 2020-01–2026-10 | Inverse-vol quarterly | 10 | ₹26.58L | +165.82% | 15.67% | -13.95% | ₹10,226 | ₹49,811 | 131 | Pass |
| 2020-01–2026-10 | Inverse-vol quarterly | 50 | ₹23.54L | +135.41% | 13.60% | -14.23% | ₹9,870 | ₹232,420 | 130 | Pass |
| 2023-01–2026-10 | Fixed monthly 50/50 control | 10 | ₹17.25L | +72.55% | 15.68% | -13.60% | ₹5,038 | ₹14,882 | 89 | Pass |
| 2023-01–2026-10 | Fixed monthly 50/50 control | 50 | ₹16.54L | +65.41% | 14.38% | -14.22% | ₹5,028 | ₹72,709 | 89 | Pass |
| 2023-01–2026-10 | Inverse-vol monthly | 10 | ₹17.59L | +75.90% | 16.27% | -13.60% | ₹5,194 | ₹16,885 | 89 | Pass |
| 2023-01–2026-10 | Inverse-vol monthly | 50 | ₹16.76L | +67.62% | 14.78% | -14.22% | ₹5,174 | ₹82,267 | 89 | Pass |
| 2023-01–2026-10 | Fixed quarterly 50/50 control | 10 | ₹17.31L | +73.14% | 15.78% | -13.95% | ₹3,523 | ₹14,640 | 49 | Pass |
| 2023-01–2026-10 | Fixed quarterly 50/50 control | 50 | ₹16.61L | +66.15% | 14.51% | -14.24% | ₹3,491 | ₹71,576 | 49 | Pass |
| 2023-01–2026-10 | Inverse-vol quarterly | 10 | ₹17.48L | +74.79% | 16.08% | -13.95% | ₹3,582 | ₹15,778 | 49 | Pass |
| 2023-01–2026-10 | Inverse-vol quarterly | 50 | ₹16.72L | +67.20% | 14.71% | -14.24% | ₹3,545 | ₹77,041 | 49 | Pass |

### Corrected continuous 2014–2026 compounding check

This account starts with ₹10 lakh in January 2014 and carries NAV, positions, fees, and cash through 2026-10-23. Results are net of current modeled delivery charges and stated slippage.

| Portfolio | Slip bps/side | End value | Return | CAGR | Max close drawdown | Fees | Slippage | Orders |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Fixed monthly 50/50 control | 10 | ₹29.15L | +191.52% | 8.89% | -13.60% | ₹21,374 | ₹79,583 | 332 |
| Fixed monthly 50/50 control | 50 | ₹23.52L | +135.19% | 7.04% | -17.83% | ₹20,294 | ₹351,665 | 327 |
| Inverse-vol monthly | 10 | ₹29.96L | +199.64% | 9.13% | -13.60% | ₹22,125 | ₹89,094 | 334 |
| Inverse-vol monthly | 50 | ₹23.65L | +136.45% | 7.09% | -18.15% | ₹20,954 | ₹388,789 | 333 |
| Fixed quarterly 50/50 control | 10 | ₹29.38L | +193.77% | 8.96% | -13.95% | ₹17,144 | ₹78,715 | 222 |
| Fixed quarterly 50/50 control | 50 | ₹23.76L | +137.64% | 7.13% | -17.86% | ₹16,110 | ₹348,327 | 219 |
| Inverse-vol quarterly | 10 | ₹30.16L | +201.62% | 9.18% | -13.95% | ₹17,778 | ₹86,584 | 224 |
| Inverse-vol quarterly | 50 | ₹23.98L | +139.85% | 7.21% | -18.11% | ₹16,632 | ₹379,452 | 224 |

At 50 bps, quarterly inverse-vol ended at ₹23.98L (+139.85%, 7.21% CAGR, -18.11% close drawdown), versus ₹23.76L (+137.64%, 7.13%, -17.86%) for the fixed quarterly control. The return advantage is 2.21 percentage points; inverse-vol paid ₹16,632 in fees versus ₹16,110. Their same-day OHLC envelopes are -25.55% and -25.66%, so both fail the conservative 20% limit. See the [timestamp and risk audit](etf_daily_timestamp_and_intraday_risk_audit.md).

For the quarterly inverse-vol 50 bps path, the updated 10-year stationary-bootstrap 20% close-drawdown breach estimate is 9.94% at 63-session blocks, with a -22.11% fifth-percentile maximum drawdown. These are conditional resampling estimates, not forecasts. At 10 bps the fixed and inverse quarterly close drawdowns were -13.95%; those friction cases do not establish a live executable spread.

There was no dual-active quarterly rebalance in the 2014–2019 training slice, so inverse-vol allocation has no evidence from that regime. The 2020–2026 and 2023+ windows have also been inspected. The extension tests compounding sensitivity; it does not establish a winner. Annual net returns and continuous-path statistics in the linked CSVs were rebuilt after date normalization.

### Cash distributions and split-unit audit

Nippon’s published NIFTYBEES history lists ₹7 and ₹8 distributions per old ₹10-face-value unit, with record dates 2014-03-11 and 2015-02-20. NSE lists the corresponding ex-dates as 2014-03-10 and 2015-02-18. NIFTYBEES later split 1:10 in December 2019; the saved Upstox price series is continuous across the split and appears normalized to post-split units. The historical distribution rates therefore map to ₹0.70 and ₹0.80 per saved-price unit, an empirical unit-basis inference. [Nippon NIFTYBEES corporate-action history](https://investeasy.nipponindiaim.com/rmfGsamnew/Products/NiftyBeES/CorporateAction.aspx), [NSE NIFTYBEES security page](https://www.nseindia.com/get-quote/equity/NIFTYBEES/Nippon-India-ETF-Nifty-50-BeES).

The order ledger shows zero NIFTYBEES units held at the prior close on both ex-dates in all eight continuous candidate paths. Those known distributions therefore add ₹0 to this strategy’s P&L; no backtest rerun is needed for them. Nippon’s published GOLDBEES corporate-action history lists a 1:100 split and no cash distributions; the saved price is continuous across the split, again suggesting post-split normalization rather than providing an Upstox guarantee. [Nippon GOLDBEES corporate-action history](https://investeasy.nipponindiaim.com/rmfGsamnew/Products/GoldBeES/CorporateAction.aspx), [NSE GOLDBEES security page](https://www.nseindia.com/get-quote/equity/GOLDBEES/NIPPON-INDIA-ETF-GOLD-BEES?series=EQ).

The saved ticker-named Upstox action-cache files were empty without request metadata. A direct follow-up through `fetch_corporate_actions` queried both exact ISINs and returned API success with zero records; the requests and results are captured in `work/data/api_probes/ETF_corporate_actions_2026-10-26.json`. Re-query with `python work/upstox_quant.py corporate-actions --isin INF204KB14I2` and `--isin INF204KB17I5`. The NIFTYBEES API response is empty despite two source-confirmed distributions, so it does not provide complete history for this sample. The event-level source, unit conversion, position check, and split-date price check are recorded in `outputs/etf_corporate_action_audit.csv`, generated by `work/audit_etf_corporate_actions.py`.

## Limits

The quarterly inverse-vol uplift is modest under 50 bps slippage and follows an exploratory schedule comparison on already-inspected history. It is a paper challenger, not a proven or guaranteed winner. The 20% drawdown limit is an observed historical screen, not a future loss bound. For this NIFTYBEES/GOLDBEES candidate, the published cash distributions are reconciled against holdings, while split-unit normalization remains empirical; sector-ETF distributions in the separate composite are not fully reconciled. Current charges are applied across the past, and next-open OHLC fills plus fixed slippage do not establish live execution quality. There is no independent untouched lockbox. The source candles currently end at 2026-10-23.
