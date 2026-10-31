# Broad-stock point-in-time data gate — 2026-10-31

## Decision: FAIL

The local stock cache cannot support a survivorship-safe NIFTY 200 or NIFTY 500 test. No broad-universe strategy configurations were run, and no data was purchased.

## Coverage available now

| Input | Local coverage | Gap for this study |
|---|---|---|
| Daily stock prices | 70 Upstox symbol histories; 2020-01-01 to 2026-10-23; 169–1,692 bars each | The histories cover a sampled NIFTY 50 list, not the historical NIFTY 200/500 membership set or all deleted instruments. Most names have no pre-2020 warm-up. |
| Point-in-time membership | 82 monthly snapshots from 2020-01 through 2026-10; 50 or 51 names per snapshot; 69 unique symbols | Reconstructed NIFTY 50 sample only. Six records need explicit transition reconciliation: 2023-07 (JIOFIN lacks a price), 2023-08 (JIOFIN has insufficient warm-up), 2025-01 (ITCHOTELS has insufficient warm-up), 2025-10 (TMCV lacks a price), 2025-12 (KWIL lacks a price), and 2026-01 (KWIL lacks a price). |
| Signal warm-up | First January 2020 snapshot has 50 names with fewer than 252 cached sessions | A 12–1 signal needs a complete 252-session history; older/delisted members and entrants need their own pre-entry prices. |
| Corporate actions | NSE notices and Upstox action/price checks exist for a subset | Thirteen names are marked unresolved for rights, merger, demerger or successor accounting in the restricted diagnostic. The selected all-saved stock run has four action overlaps, including BPCL bonus, BAJFINANCE bonus/split and HDFCBANK bonus. This does not prove every share-unit path or payout complete. |
| Quality inputs | None with point-in-time publication timestamps was assembled | Current/restated financial statements cannot be backfilled into historical signals. The quality branch is therefore omitted. |

The exact local coverage tables are `work/data/universe_sources/stock_history_coverage.csv`, `stock_monthly_universe_coverage.csv`, and `nifty50_monthly_universe_2020_2026.csv`. Their audit does not establish complete NIFTY 50 action accounting, much less broad-index coverage.

## Viable source and acquisition requirements

1. Obtain a licensed, effective-dated historical NIFTY 200 and/or NIFTY 500 constituent file from [NSE Indices Data Subscription](https://www.niftyindices.com/offerings/data-subscription). NSE Indices describes constituent data containing company names, identifiers, market capitalization, weights and prices, and directs users to contact it for subscription. The [current NIFTY 200 page](https://www.niftyindices.com/indices/equity/broad-based-indices/nifty-200) is not a complete historical member ledger. Freeze the broadest index only after the licensed archive’s start/end dates and change coverage are verified.
2. Require effective dates, stable security identifiers/ISINs, weights, additions and removals, and records for suspension, delisting and exceptional replacements. Reconcile every month boundary and all non-scheduled changes against the [index rebalancing calendar](https://www.niftyindices.com/resources/index-rebalancing-schedule).
3. Backfill daily OHLCV for every constituent and every exit/delisting/successor through its economic end date, with at least 252 trading sessions before each signal. Upstox V3 documentation lists daily candles from January 2000, but requests require a recognized instrument key and are limited to one decade per request; it does not provide missing membership or old/delisted identifier coverage. See [Historical Candle Data V3](https://upstox.com/developer/api-documentation/v3/get-historical-candle-data/).
4. Obtain event-level cash dividends, splits, bonuses, rights entitlements, mergers, demergers, cash-outs and successor-share ratios. Retain the full economic value in the simulated account; never remove an inconvenient historical name based on an event learned later.
5. If a quality signal is later considered, require point-in-time filing/publication timestamps, period end, restatement history, and a reproducible rule for delayed or missing reports.
6. Keep licensing and purchase authorization separate from the research gate. No data should be bought until the user authorizes the quoted source and terms.

## Frozen consequence for this cycle

The preregistered broad-universe momentum grid did not run. With quality inputs unavailable, the planned set would have been four configurations: positive 12–1 momentum and volatility-adjusted 6/12 momentum, each at monthly and quarterly rebalance frequency, using the fixed top-20 basket and five-rank retention buffer. Those rules remain a next-cycle specification only; no results were observed and no replacement filters were improvised.
