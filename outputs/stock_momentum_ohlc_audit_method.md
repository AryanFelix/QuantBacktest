# NIFTY 50 stock-momentum OHLC drawdown audit

**Specification frozen before this audit:** 2026-10-27
**Capital:** ₹10 lakh
**Primary slippage:** 10 bps per side; saved 20/50-bps stress paths also audited

## Objective and cases

The stock screen currently measures close-to-close drawdown. This audit replays each saved order ledger against daily OHLC bars to check whether an account that passes the close screen breaches the user's 20% peak-to-trough budget intraday.

Audit all 20 restricted-universe monthly momentum/trend candidates (four rules × five exposure caps) at 10 bps, the four saved 20/50-bps top-10 stress paths, the NIFTYBEES benchmark, and the three restored-universe top-10/200DMA paths at 10/20/50 bps. This is 28 paths. Report training (2021-02-01 to 2023-12-29), 2024 validation, 2025+ holdout, and continuous 2021-02-01 to 2026-10-23 windows. The first 20 paths at 10 bps alone determine a training-only candidate by highest net CAGR among rules passing the training OHLC screen; all other cases are diagnostic.

## Accounting and envelope

Reconstruct holdings from saved integer-share orders and fees. Credit the same candidate cash dividends on ex-date to prior-close holdings as the portfolio simulator. Apply ordinary orders at recorded next-open fills; apply terminal liquidation only after the last close. Reconcile reconstructed close NAV against saved equity every session to within ₹0.03.

For each session, mark the pre-trade and post-trade portfolio at open, then at the combined portfolio's daily highs and lows. Update the running peak using the day's maximum NAV and calculate drawdown from that peak to the day's minimum NAV. This assumes every held asset reaches its high before the portfolio reaches its low on the same session; it is a conservative historical envelope, not the observed intraday portfolio path. Carry the all-time peak across validation and holdout windows.

## Results

The per-session close replay reconciled for all 28 paths; the maximum absolute difference from saved NAV was less than ₹0.000001. Fourteen of the 20 restricted-universe 10-bps candidates passed the training OHLC bound. The training-only screen selected top ten 12–1 momentum with stock 200DMA and NIFTYBEES 200DMA gates at a 95% cap. Training return was +76.34% (21.56% CAGR) with a -15.57% OHLC bound. The 2024 return was +25.65%; the 2025–October 2026 return was +4.27%. The continuous return was +131.04%, with a -15.89% OHLC bound versus -13.96% close drawdown. Fees were ₹82,879 and modeled slippage ₹54,296.

Restoring all 13 previously excluded action-source names changed the same rule to +122.63% continuous return and -17.07% OHLC bound at 10 bps; at 50 bps it returned +95.08% with a -19.66% bound, leaving only 0.34 percentage points of historical room to the limit. No result establishes a winner: the NIFTYBEES gate was chosen after earlier results were inspected, the corporate-action feed remains incomplete, and recent-period returns were modest.

The NIFTYBEES buy-and-hold close path has -15.82% drawdown; its conservative OHLC envelope is -30.76%. On 2026-10-27, NSE's official [Security-wise Archives (Equities)](https://www.nseindia.com/report-detail/eq_security) returned the Jan 17 and May 11, 2022 `EQ` rows. Both dates' previous close, open, high, low, close, and volume match the saved Upstox bars exactly. The large openings are exchange-confirmed: Jan 17 opened/high ₹223 versus ₹197.36 prior close, then traded as low as ₹195.70; May 11 opened/low ₹153.30 versus ₹176.16 prior close and later reached ₹181.90. The two-date comparison is in [`niftybees_2022_ohlc_source_crosscheck.csv`](niftybees_2022_ohlc_source_crosscheck.csv). This resolves the source-mismatch concern for those bars, but does not make -30.76% an observed intraday portfolio drawdown: the envelope assumes every daily high precedes every low, and OHLC data does not reveal the complete path.

## Limits

The histories and strategy variants were already inspected, so the split is chronological but not a fresh lockbox. This audit does not repair the provisional NIFTY 50 membership archive or the incomplete corporate-action event feed; the restored-universe path has only been checked against actions currently saved. Dividend share-unit conversion is inferred. The two flagged NIFTYBEES bars are exchange-verified, but this is not a full-history independent source audit. Daily OHLC cannot capture spread, queue position, partial fills, market impact, taxes, or the high/low sequence on every day. A historical envelope passing 20% is not a future loss cap.

## Reproduction

- Runner: `work/audit_stock_momentum_ohlc.py`.
- Two flagged benchmark bars cross-checked against the NSE `EQ` archive: [`niftybees_2022_ohlc_source_crosscheck.csv`](niftybees_2022_ohlc_source_crosscheck.csv).
- Results: `outputs/stock_momentum_ohlc_audit.csv` and `outputs/stock_momentum_ohlc_selection.json`.
- Inputs: `outputs/stock_momentum_daily_equity.csv`, `outputs/stock_momentum_orders.csv`, and `work/backtests/stock_momentum_action_aware/`.
