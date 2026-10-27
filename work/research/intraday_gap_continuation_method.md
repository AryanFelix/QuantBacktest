# NIFTY opening-gap continuation test

**Specification frozen:** 2026-10-27, before running this family<br>
**Data:** saved Upstox 30-minute NIFTY 50 and NIFTYBEES candles, 2022-01-03–2026-10-23<br>
**Capital:** ₹10 lakh per run<br>
**Drawdown screen:** 20%
**Primary case:** 0.50% minimum gap, 1R target, 50 bps adverse slippage per side

## Rule

This is a cash-only, long-only continuation hypothesis. Compare the first NIFTY 50 30-minute bar's open with the prior common session close. A signal requires a gap up of at least 0.30%, 0.50%, or 0.75%, a green first bar, and a first-bar close above the prior close. Enter NIFTYBEES at the second 30-minute bar's open. Place the stop at the first NIFTYBEES bar's low and the target at 1R above entry, where 1R is the raw entry-to-stop distance. Exit on the first stop or target touch, or at the final bar close. Never carry a position overnight; at most one trade can occur per session.

Size each trade so modeled loss at the stop, including adverse entry/stop slippage and current Upstox/NSE equity-intraday fees, is at most 0.5% of current NAV. Cap gross exposure at 100% of NAV. Costs are 10/25/50/100 bps adverse slippage per side; 50 bps is the primary case. No leverage, shorting, options, or parameter selection on validation/later periods.

If a 30-minute bar reaches both stop and target, assume the stop first. A level crossed at the bar open fills at that open with adverse slippage. The same shared simulator marks intrabar NAV from raw OHLC and realizes exit fees; it cannot reconstruct tick order or actual queue execution.

## Sample and comparison

Require 13 timestamps in both feeds with exact timestamp alignment. Prior-session close references use the previous common date. Each period starts afresh with ₹10 lakh: training 2022–2023, validation 2024, later 2025-01-01–2026-10-23, and continuous 2022-01-03–2026-10-23. The later period was already inspected during the larger research project, so it is retrospective pseudo-out-of-sample evidence, not a pristine holdout. The three gap thresholds and four cost levels are sensitivities, not a search for a later-period winner.

## Hypothesis and limits

Published work reports that some positive opening gaps continue as information is absorbed, while other evidence finds overnight-to-intraday reversal. These findings motivate a narrow, India-specific test; they do not establish that the signal survives Indian ETF trading costs. See [Stocks Opening Price Gaps and Adjustments to New Information](https://doi.org/10.1007/s10614-023-10363-w) and [Overnight Returns and Intraday Reversals: Evidence from U.S. Equities](https://www.utupub.fi/items/094ffc24-ca98-482d-bd18-a469ca028791/full).

The data are price bars, not order-book quotes. Fixed slippage is a sensitivity, not observed spread or market impact. The NIFTY index supplies signals and NIFTYBEES is the execution proxy; tracking error, intraday ETF distributions, tax, and broker/exchange fee changes are not fully reconstructed. Current intraday fees are applied historically. No return should be treated as a forecast or deployment recommendation.

## Reproduction

Run `python work/backtest_intraday_gap_continuation.py`. It writes 48 per-run equity/trade/summary triplets under `work/backtests/intraday_gap_continuation/` and `outputs/intraday_gap_continuation_sensitivity.csv`. Its assert-based self-check covers signal direction, threshold boundary, and the fixed 1R target.
