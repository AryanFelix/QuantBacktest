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

The NIFTYBEES buy-and-hold close path has -15.82% drawdown, but its OHLC replay gives -30.76%. The saved Upstox series contains isolated 2022 opens 11.8–13.0% from the prior close (for example, 2022-01-17 at ₹223 versus ₹197.36 and 2022-05-11 at ₹153.30 versus ₹176.16), while the closes remain near the prior close. Treat this benchmark's OHLC bound as a data-quality flag pending an exchange-price cross-check, not a reliable intraday loss estimate.

## Limits

The histories and strategy variants were already inspected, so the split is chronological but not a fresh lockbox. This audit does not repair the provisional NIFTY 50 membership archive or the incomplete corporate-action event feed; the restored-universe path has only been checked against actions currently saved. Dividend share-unit conversion is inferred. NIFTYBEES benchmark OHLC has the 2022 opening-price flags above. Daily OHLC cannot capture spread, queue position, partial fills, market impact, taxes, or future losses. A historical envelope passing 20% is not a future loss cap.

## Reproduction

- Runner: `work/audit_stock_momentum_ohlc.py`.
- Results: `outputs/stock_momentum_ohlc_audit.csv` and `outputs/stock_momentum_ohlc_selection.json`.
- Inputs: `outputs/stock_momentum_daily_equity.csv`, `outputs/stock_momentum_orders.csv`, and `work/backtests/stock_momentum_action_aware/`.
