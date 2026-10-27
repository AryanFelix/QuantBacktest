# Preliminary NIFTY 50 stock momentum screen

**Run date:** 2026-10-27  
**Evaluation:** 2021-02-01 to 2026-10-23  
**Capital:** ₹10,00,000; 95% exposure ceiling; 20% historical drawdown screen; 10 bps per-side slippage.

## Frozen comparisons and time split

- Monthly equal-weight top 5 positive 12-1 total-return momentum.
- Same top-5 rank with close above its 200-session total-return average.
- Same 200-session filter with top 10 holdings.
- Same top 10 with both stock and NIFTYBEES closes above their respective 200-session averages.
Signals use the month-end point-in-time NIFTY 50 snapshot and execute at the next session open. Each rule is run at 50%, 60%, 70%, 80%, and 95% exposure. The exposure and rule with the highest train CAGR among train-period cases inside the 20% drawdown screen is selected; its 2024 and 2025+ rows are reported separately. Orders are integer-share NSE cash delivery with Upstox's current published fee schedule applied uniformly, 10 bps baseline slippage per side, and no cash interest. The unfiltered and market-filtered top-10 95% variants are stressed at 20 and 50 bps per side. All positions are liquidated at the end and charged.

## Return and corporate-action treatment

Dividend cash is credited on ex-date to positions held through the previous close. Parsed dividend amounts are converted to the observed Upstox candle share unit using later split/bonus factors where available; Upstox's adjustment convention and the NSE page feed's completeness are not guaranteed. The event feed records separate same-date notices and the script sums their parsed amounts.

The following 13 source symbols are excluded for the entire sample because their rights, merger, or demerger position path is not reconciled: ADANIENT, BHARTIARTL, GRASIM, HDFC, HINDUNILVR, ITC, RELIANCE, SHRIRAMFIN, SIEMENS, TATACONSUM, TMPV, UPL, VEDL. This materially narrows the historical NIFTY 50 universe and can bias results. Other unrecognized corporate actions, point-in-time membership archive incompleteness, taxes, and historical fee changes remain risks. NIFTYBEES is an investable price benchmark; ETF distributions are not separately reconstructed.

The screen's `max_drawdown_pct` carries the account high-water mark from the start of the simulation through each window; `period_max_drawdown_pct` resets at the window boundary. The NIFTYBEES market 200DMA gate was added after the first stock-rule results were inspected, so all gated results are explicitly post-hoc comparisons and need fresh forward validation. These runs are not untouched out-of-sample evidence: the underlying data and several other strategy results have already been inspected. A 20% historical drawdown pass is not a future loss bound. See `stock_momentum_screen.csv`, `stock_momentum_monthly_picks.csv`, `stock_momentum_daily_equity.csv`, and `stock_momentum_orders.csv` for reproducible details.
