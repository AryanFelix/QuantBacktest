# Stock momentum + NIFTY/Gold sleeve blend

- **Run date:** 2026-10-27
- **Data:** saved Upstox daily candles through 2026-10-23
- **Capital:** ₹10,00,000, split into two independent ₹5,00,000 sleeves
- **Execution cost:** current modeled Upstox/NSE delivery fees plus 50 bps slippage per side
- **Status:** fixed 50/50 blend diagnostic; retrospective, not a validated winner or untouched holdout.

The replay reuses saved local Upstox histories; `/work/data/` caches and generated `/work/backtests/` ledgers are ignored by Git and are not part of the public repository. The API key is not written to research artifacts.

## Frozen rules

The stock sleeve uses the previously examined monthly top-10 positive 12–1 total-return momentum rule with both a stock 200-session trend filter and a NIFTYBEES 200-session market gate. It restores the 13 previously excluded action-source names, equal-weights eligible names, caps gross exposure at 95%, uses integer shares, and executes at the next session open.

The ETF sleeve holds NIFTYBEES and GOLDBEES in a quarterly static 50/50 mix, with a 45% sleeve exposure cap. Its target is therefore 22.5% of sleeve NAV per ETF at each rebalance. The two sleeves retain their own cash and reinvest their own profits; there is no transfer or rebalancing between sleeves. Both use 50 bps per-side slippage and terminal liquidation.

The total account starts at ₹10 lakh. Each sleeve starts at ₹5 lakh, so the initial gross exposure targets are 47.5% in stocks plus 22.5% in ETFs. All values are after modeled fees and slippage; cash earns 0%.

## Results

| Window | End value | Net return | Close drawdown | Combined OHLC bound | 20% screen |
|---|---:|---:|---:|---:|---|
| Feb 2021–Dec 2023, training slice | ₹13.90L | +39.03% | -10.86% | -13.56% | Pass |
| 2024, validation slice | ₹15.70L | +12.94% | -11.02% | -12.27% | Pass |
| 2025–Oct 2026, holdout slice | ₹17.66L | +12.47% | -9.72% | -10.56% | Pass |
| Feb 2021–Oct 2026, continuous | ₹17.66L | +76.59% | -11.02% | -13.56% | Pass |

The continuous path has a 10.45% CAGR. Its total modeled fees were ₹55,264 and slippage was ₹1,86,804 across 733 orders. The component sleeves ended at ₹9.59 lakh (+91.80%) for stock momentum and ₹8.07 lakh (+61.38%) for the NIFTY/Gold mix. Their separate OHLC bounds were -19.79% and -15.36%; the combined bound was -13.56%.

The combined OHLC envelope sums each sleeve's daily high and low portfolio marks, then tracks drawdown from the combined high-water mark. This assumes the independent sleeve extremes can coincide, which is conservative; it is not an observed intraday portfolio path. Close-NAV replay error was below ₹0.000001 for the stock sleeve and zero for the ETF sleeve.

## Interpretation and limits

The equal starting allocation reduced the historical drawdown bound relative to either sleeve alone while retaining a positive return in all three chronological slices. This is one fixed blend, not an allocation optimum. The stock market gate was added after earlier results were inspected, and the historical dates have all been examined; the 2024 and 2025+ slices are retrospective pseudo-out-of-sample comparisons.

The stock selection still depends on a provisional point-in-time NIFTY 50 universe and incomplete corporate-action/dividend evidence. NIFTYBEES and GOLDBEES exchange candles do not establish complete total returns; ETF distributions, especially for Gold, remain a source limit. Taxes, cash yield, live spread, market impact, partial fills, and operational constraints are not included. Passing this historical 20% screen cannot guarantee a future maximum drawdown.

## Reproduction

Run `python work/backtest_stock_nifty_gold_blend.py`. The runner rebuilds both sleeves at ₹5 lakh, audits both OHLC ledgers, asserts daily close-NAV reconciliation, and writes the combined ledger and summary under `work/backtests/stock_nifty_gold_blend/`. The four window rows are in [`stock_nifty_gold_blend.csv`](stock_nifty_gold_blend.csv). Stock source and universe caveats are in the [restored-universe stock review](stock_momentum_action_aware_method.md); ETF history and corporate-action caveats are in the [extended NIFTY/Gold review](nifty_gold_history_benchmarks_method.md).
