# CAGR reanalysis — 2026-10-30

## Decision

The old opening leaderboard ranked five nearby variants of one quarterly NIFTY/Gold allocation family. A researcher-selected 1% bootstrap breach screen pushed it toward low exposure and synthetic cash yield. That screen was not the same as the requested 20% peak-to-trough constraint, and it did not compare stock, sector, ETF, intraday, or derivatives families.

The new screen ranks net CAGR after modeled fees and 50 bps per-side slippage, then checks the account against the historical daily high-before-low OHLC envelope. It uses ₹10 lakh, zero cash yield, and requires an observed envelope no worse than -20%. Bootstrap results remain a secondary diagnostic. This is a historical screen, not a forward loss limit.

## Reanalysis results

| Candidate | Window | Net CAGR / return | OHLC drawdown bound | Recent slice |
|---|---|---:|---:|---:|
| Equal-weight five-sector ETF control, 95% cap | 2022-01-03–2026-10-23 | 12.79% / +76.68% | -19.69% | +3.50% in 2025–Oct 2026 |
| Restored-universe top-10 stock momentum, 95% cap | 2021-02-01–2026-10-23 | 12.39% / +95.08% | -19.66% | +1.84% in 2025–Oct 2026 |
| 25% NIFTY trend / 50% sectors / 25% Gold trend | 2022-01-03–2026-10-23 | 11.92% / +72.92% | -14.72% | +17.05% in 2025–Oct 2026 |
| 50/50 initial-capital stock-momentum + NIFTY/Gold blend | 2021-02-01–2026-10-23 | 10.45% / +76.59% | -13.56% | +12.47% in 2025–Oct 2026 |
| Quarterly 50/50 active NIFTY/Gold, 70% exposure cap | 2015-01-02–2026-10-23 | 5.85% / +93.31% | -19.06% | — |

All rows use saved Upstox daily data through 2026-10-23. ETF and stock rules use modeled delivery fees plus 50 bps adverse slippage per side. The stock and sector sweeps and the 50/50 stock/ETF blend were rerun with the current shared fee helper. The two-ratio NIFTY/Gold frontier was rerun directly with that helper and full-period OHLC re-marking; its reproducible run is [`audit_nifty_gold_cagr_frontier.py`](../../work/audit_nifty_gold_cagr_frontier.py), with results in [`nifty_gold_ohlc_cagr_frontier.csv`](../../outputs/nifty_gold_ohlc_cagr_frontier.csv).

The two fast leaders have almost no historical risk headroom and weak latest slices. The sector/NIFTY/Gold blend is a higher-growth challenger with 5.28 percentage points of envelope headroom, but only starts in 2022 and sector ETF distributions remain incomplete. The 50/50 stock/ETF blend has 6.44 points of headroom and a positive 2025–October 2026 segment; it still depends on a provisional stock universe and incomplete ETF total-return inputs.

### The apparent NIFTY/Gold leader fails the risk screen

The quarterly 30% NIFTY / 70% Gold active mix at a 100% cap showed 14.35% CAGR from 2020 to October 2026 and -18.96% close drawdown. Full high/low replay puts its OHLC envelope at -25.34%. The 50/50 mix at a 100% cap showed 13.42% CAGR and -14.23% close drawdown, but its OHLC bound is -25.66%. Both fail the 20% screen.

A targeted 2015–October 2026 frontier tested 30/70 and 50/50 sleeves at exposure caps from 60% to 100%, all at 50 bps per side. Among these 16 cases, the highest-CAGR screen survivor was 50/50 at a 70% cap: 5.85% CAGR with -19.06% OHLC. The 30/70 mix passed only at a 60% cap, with 5.45% CAGR and -19.60% OHLC. These survivors have less than one percentage point of risk headroom. This is a two-ratio experiment, not a complete composition search.

## What the result says about the approach

The low CAGR is not explained only by the old bootstrap threshold. The user’s 20% drawdown ceiling is binding when the actual daily high/low envelope is used: the higher-return NIFTY/Gold variants breach, while the versions that pass across the longer 2015–2026 path reduce exposure enough to fall below 6% CAGR.

The higher short-history returns come from equity concentration and recent sector leadership. Sector equal weight and stock momentum both pass the historical envelope narrowly, but both earned less than 4% in the latest inspected segment. Their CAGRs do not establish a persistent edge. The mixed sector/NIFTY/Gold rule and the 50/50 stock/ETF blend have more historical room under the limit and positive recent returns, but their histories and return inputs are still incomplete.

## Next research work

1. Prioritize the stock sleeve as the new source of growth, but rebuild it on a point-in-time broad universe with delisted names, corporate actions, and dividend-inclusive returns. The current top-10 NIFTY 50 result is provisional.
2. Compare the official [Nifty200 Momentum 30](https://www.niftyindices.com/indices/equity/strategy-indices/nifty200-momentum-30) and [Nifty500 Multicap Momentum Quality 50](https://www.niftyindices.com/indices/equity/strategy-indices/nifty500-multicap-momentum-quality50) rule sets with a small frozen 12–1 momentum / quality-filter set. Treat pre-inception index history as backfilled.
3. On the frozen stock candidate, compare 50/50, 60/40, and 70/30 stock/ETF sleeve weights, then a lagged volatility exposure overlay. Select weights only in training and keep an untouched chronological holdout.
4. Reconcile sector ETF distributions against official sector total-return indexes before promoting the sector basket. Keep options and intraday ideas outside the return leaderboard until long enough underlying data and instrument-specific fees are available.

The research-backed experiment list and primary references are in [`cagr_reanalysis_hypotheses_2026-10-30.md`](cagr_reanalysis_hypotheses_2026-10-30.md).

## Limits

All dates have been inspected during this research; none is an untouched lockbox. OHLC bounds assume each held asset reaches its high before its low within the session and can miss overnight gaps, market impact, and fill failures. ETF cash distributions, stock point-in-time membership, and some corporate actions are incomplete. Modeled fees apply the current schedule uniformly to historical trades, and the 50 bps slippage is a stress assumption rather than measured historical spread. No backtest can guarantee a future maximum drawdown.
