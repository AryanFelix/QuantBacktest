# Stock momentum and NIFTY/Gold exact sleeve-split sensitivity

- **Run date:** 2026-10-27
- **Input history:** saved Upstox daily bars through 2026-10-23; 1,420 common sessions from 2021-02-01
- **Account size:** ₹10,00,000
- **Costs:** current modeled fees plus 50 bps adverse slippage per side
- **Status:** retrospective allocation sensitivity; no allocation is validated for live trading.

## Question and frozen rules

This run checks whether changing the initial capital split between the previously evaluated stock and ETF sleeves changes the risk/return result. It replays eleven splits from 0% to 100% stock in 10-point steps. Each candidate is re-simulated at its actual sleeve capital, including integer share sizing, sleeve-level fees and slippage; the paths are not scaled from a ₹5 lakh result. The sleeves stay independent and do not transfer or rebalance capital between one another.

The stock sleeve is monthly top-10 positive 12–1 total-return momentum, with stock and NIFTYBEES 200-session trend gates, a 95% sleeve gross cap, next-session-open orders, and integer shares. The ETF sleeve is quarterly static 50/50 NIFTYBEES/GOLDBEES at a 45% gross cap. Both sleeves use 50 bps per-side slippage and terminal liquidation. Cash yield is 0%. The strategy definitions and source caveats are in [the fixed-blend note](stock_nifty_gold_blend_method.md) and [the restored-universe stock review](stock_momentum_action_aware_method.md).

No Upstox API request was made for this sensitivity; it reuses the saved histories. The cost model and price data were not changed. The repository intentionally ignores `/work/data/` caches and generated `/work/backtests/` ledgers, so the committed source/results do not include the local candles or detailed daily/order files; those are recreated locally when the required caches are present. The API key is not written to the repository.

## Selection and measurement

The 2021-02-01 through 2023-12-29 training slice selects the highest net return among tested splits whose combined daily OHLC drawdown envelope is no worse than -20%. Ties prefer more training drawdown headroom, then the split nearest 50/50. The selected capital weight is descriptive because the underlying stock signal and all later historical dates were already inspected.

The validation slice is 2024-01-01 through 2024-12-31; the later comparison slice is 2025-01-01 through 2026-10-23. Returns compound continuously: each slice starts at the prior session's account NAV. Drawdown high-water marks also carry through the full account path; the reported peak date follows a high inherited from an earlier slice. Period CAGR uses elapsed calendar days between its first and last session.

For each day, the combined upper and lower marks sum the stock sleeve and ETF sleeve OHLC values. The envelope therefore allows both sleeves' highs or lows to coincide, a conservative bound rather than a synchronized intraday portfolio path. Close and OHLC results are based on the exact order-ledger replays. The 50/50 full-history result must reconcile to the earlier fixed-blend run within ₹0.000001 for account NAV and the recorded cost fields; the script asserts that reconciliation.

## Results

| Stock / ETF initial capital | Training return / OHLC bound | 2024 return | 2025–Oct 2026 return | Full return / OHLC bound | Full end NAV |
|---:|---:|---:|---:|---:|---:|
| 0% / 100% | +17.99% / -14.37% | +6.43% | +28.96% | +61.94% / -15.36% | ₹16.19L |
| 50% / 50% | +39.03% / -13.56% | +12.94% | +12.47% | +76.59% / -13.56% | ₹17.66L |
| 100% / 0% | +61.97% / -19.66% | +18.26% | +1.84% | +95.08% / -19.66% | ₹19.51L |

The training-only rule picks 100% stock. Its training envelope leaves only 0.34 percentage points below the requested 20% screen; it then earns only 1.84% in the later slice, versus 28.96% for the ETF-only sleeve and 12.47% for 50/50. That reversal is evidence that the apparent full-period return leader is allocation- and regime-sensitive, not a winner. All eleven exact weights and all four periods are in the [44-row CSV](stock_nifty_gold_sleeve_split.csv).

The selected 100% stock path ended at ₹19,50,820, with +12.39% CAGR, -17.32% close drawdown, -19.66% OHLC envelope, ₹78,957 fees, ₹2,52,689 modeled slippage, and 642 orders. The exact 50/50 control ended at ₹17,65,921, with +10.45% CAGR, -11.02% close drawdown, -13.56% OHLC envelope, ₹55,264 fees, ₹1,86,804 modeled slippage, and 733 orders. Costs are included in the net NAV; slippage is also itemized separately.

## Limits

The sensitivity grid is coarse at ten percentage points, and its top weight is at a boundary. The 100% stock allocation was selected after repeated inspection of the training dates; later dates were already inspected too, so the later slice is not a pristine lockbox. The split does not repair the stock universe's provisional membership, merger/demerger/dividend evidence, or ETF distribution gaps. It also excludes tax beyond modeled charges, market impact beyond 50 bps, cash yield, partial fills, and live execution. Passing a historical OHLC screen does not enforce a 20% future drawdown limit.

## Reproduction and artifacts

Run `python work/sensitivity_stock_nifty_gold_sleeve_split.py` from a checkout with the saved data caches. The runner recreates all eleven exact-capital simulations, checks session alignment and OHLC containment, reconciles 50/50 to the fixed-blend baseline, updates the consolidated metric ledger and data manifest idempotently, and saves detailed combined ledgers plus sleeve equity/orders for 50/50 and the training-selected split under local `work/backtests/stock_nifty_gold_sleeve_split/`. The selection and carried-forward period rows are in [the JSON record](stock_nifty_gold_sleeve_split_selection.json); the rule definitions are in [the fixed-blend note](stock_nifty_gold_blend_method.md).
