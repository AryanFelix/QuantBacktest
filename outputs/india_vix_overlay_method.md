# India VIX exposure-overlay sensitivity

**2026-10-27 fee-model correction:** This static result snapshot predates the instrument-specific ETF STT replay. Use the current sensitivity CSV and consolidated ledger for numeric results; older figures below are superseded where they differ. See the [fee-model audit](../work/research/fee_model_audit.md).


**Status:** tested and rejected as a useful return/risk improvement. No VIX overlay was added to the forward-paper freeze.

## Rule and data handling

The base account is the quarterly NIFTYBEES Donchian 55/20 plus GOLDBEES 200-session SMA portfolio. It uses the 63-session inverse-volatility split when both sleeves are active and 65% exposure when only one is active. At signal-change and quarter-end closes, the overlay checks the latest confirmed India VIX close. At thresholds of 15, 20, 25, or 30, it retains either 0% or 50% of the base NIFTYBEES weight and leaves Gold unchanged until the next scheduled event. The resulting target trades at the following session's open; the VIX contract itself is never traded.

## Source reconciliation

The original Upstox daily cache remains unchanged at `work/data/index_daily/IndiaVIX-days-1-2014-01-01-2026-10-23.csv`. It contains 3,172 rows across 3,169 session dates, including conflicting duplicate rows on 2015-06-29, 2015-07-02, and 2015-08-10. NSE's [official historical India VIX page](https://www.nseindia.com/reports-indices-historical-vix) returned one daily bar for each disputed date. The complete responses, request paths, and HTTP statuses are preserved in [india_vix_nse_conflict_reconciliation.json](india_vix_nse_conflict_reconciliation.json).

| Session | Conflicting Upstox closes | NSE official OHLC | NSE close used |
|---|---:|---|---:|
| 2015-06-29 | 18.17, 17.30 | 15.7600 / 18.7750 / 15.7600 / 17.2975 | 17.2975 |
| 2015-07-02 | 15.63, 15.56 | 15.8450 / 16.0775 / 15.1625 / 15.5575 | 15.5575 |
| 2015-08-10 | 15.47, 15.44 | 14.9100 / 15.6225 / 14.2425 / 15.4650 | 15.4650 |

`work/sensitivity_india_vix_overlay.py` validates these are the three and only three duplicate dates, checks that one Upstox close on each date matches the NSE close to the cache's two-decimal precision, and generates a separate daily research file at `work/data/index_daily/IndiaVIX-NSE-reconciled-days-1-2014-01-01-2026-10-23.csv`. It replaces all four OHLC values on those dates with NSE's official daily bar; all other sessions remain from Upstox. The one ETF session missing a VIX bar (2019-07-02) uses the previous confirmed close. Its row-level treatment is in [india_vix_daily_quality.csv](india_vix_daily_quality.csv).

## Backtest design

The 90 runs cover nine rules (no overlay plus eight threshold/retention combinations), five chronological windows, and 10/50 bps per-side slippage. Windows are 2014–2019, 2020–2022, 2023 onward, 2020 onward, and continuous 2014 onward. Each run starts with ₹10 lakh, uses integer ETF units, current delivery charges applied uniformly, zero cash interest, and terminal liquidation. Signals use the close known at the event close; fills occur at the next session's open. Results use close-marked portfolio equity.

## Results

At 50 bps per side over full 2014–2026, no tested VIX setting satisfies the 20% close-drawdown limit. The no-overlay baseline returns +152.55% with -23.80% drawdown. The best drawdown among overlay settings is -22.68% for VIX ≥20 with 0% NIFTY retention, but that rule returns +113.66% and still breaches the limit. The VIX ≥30 / 50% retention rule nearly preserves baseline return (+152.14%) but has the same -23.80% drawdown.

At 10 bps per side, the no-overlay baseline returns +235.70% / -17.40% drawdown. All tested VIX overlays have the same -17.40% drawdown and lower full-history returns, ranging from +110.12% to +235.15%. In the 2023+ holdout at 50 bps, the no-overlay return is +79.19% / -18.32%; every overlay has the same drawdown and none improves the return. This screen does not support adding VIX to the candidate rule.

## Reproduction and limits

Run `python work/sensitivity_india_vix_overlay.py` from the workspace root. It regenerates the reconciled input, all 90 equity/order paths, the summary CSV, and the missing/ambiguous-session audit. A seven-field assertion checks that its no-overlay full-history result matches the corrected 65% single-sleeve benchmark.

These are retrospective comparisons on inspected history, not independent validation or forward results. The 20% screen is based on daily closes; intraday adverse paths can be worse. The historical close series does not establish future slippage, fills, or the completeness of all other Upstox observations.
