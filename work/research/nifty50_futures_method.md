# NIFTY 50 futures 200-day trend test — frozen method

**Registered:** 2026-10-26, before calculating strategy P&L

## Rule

Use one NIFTY 50 monthly futures lot when the prior session's NIFTY 50 cash-index close is above its trailing 200-session simple moving average; otherwise hold cash. Compute the indicator on the index close, then act at the next session's futures open. This is a fixed, established trend rule; no futures parameters or position sizes will be selected from these results.

## Trading and accounting

- Continuous sample: 2024-10-01 through 2026-09-25. The final date is before the next roll into the October 2026 future, for which no expired-contract history exists yet.
- Separate recent sample: 2026-01-02 through 2026-09-25, initialized flat and using the 200-day signal history available before its first order. It is a short, provisional holdout.
- Roll at the open one NSE trading session before the expiring near-month future's expiry. Close the old lot and open the next monthly contract at that day's opens when the signal is long. If the signal is flat, only close.
- Mark the futures position to each day's close; daily OHLC close is a proxy for settlement. Use the individual expiry contracts, not a synthetic continuous price series.
- Charge each executed side on its reference open notional. Use 10 bps per side of slippage as baseline, with 20 and 50 bps reported as fixed sensitivities. Brokerage is ₹10/order for API orders through 2025-12-31 and ₹20/order from 2026-01-01; NSE futures turnover charge is 0.00173% through 2026-02-28 and 0.00183% from 2026-03-01; futures STT is 0.02% on sells through 2026-03-31 and 0.05% from 2026-04-01. Add 0.002% buy stamp duty, SEBI ₹10/crore, IPFT ₹0.01/crore, and 18% GST on brokerage, exchange, and IPFT charges. SEBI is computed at `notional × 0.000001`; fees follow the published Upstox schedule and dates.
- Start each run with ₹10,00,000. Buy one lot regardless of capital, and report notional leverage. A 30% of notional margin reserve is a stress assumption only; it is not a historical SPAN/ELM reconstruction. Returns use futures P&L on cash capital and do not accrue interest on idle cash.
- Report net return, CAGR, close-marked maximum drawdown, fees, slippage, round trips, number of orders, exposure, and whether the observed drawdown stayed within 20%. The 20% figure screens observed history; it is not a live stop or loss guarantee.

## Data limits

Upstox expired monthly-futures contracts/candles are cached under `work/data/expired/nifty50_monthly_futures/`. December 2024's missing Upstox daily candles were replaced with official NSE UDiFF daily bhavcopy rows; one January 2025 overlap matched OHLC and open interest, while NSE volume was converted from lots to units using the contract lot size. Contract history starts in October 2024, so both futures samples are too short to establish robustness across market regimes. Spot-index signal history uses the existing Upstox NIFTY 50 daily cache.

Five cached futures files contained multiple timestamped bars for the same session. Their open/high/low values agree, but some closes differ slightly. The backtest keeps the earliest local timestamp for each duplicated session; the 00:00 row for the 2025-01-30 contract on 2024-12-02 exactly matches the official NSE UDiFF row. The duplicate candidates and selection are preserved in `outputs/upstox_futures_daily_duplicate_audit.csv`; the remaining duplicate dates were not individually cross-checked to NSE.

## Sources checked

- Upstox charges: https://upstox.com/brokerage-charges/
- NSE NIFTY 50 expiry schedule: https://www.nseindia.com/static/products-services/equity-derivatives-nifty50
- NSE UDiFF F&O daily archive filename pattern, documented in `work/fetch_nifty50_monthly_futures.py` and individual data-manifest rows.
