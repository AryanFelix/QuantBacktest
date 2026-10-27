# Stock momentum and NIFTY/Gold sleeve-split execution-cost stress

- **Run date:** 2026-10-27
- **Input history:** saved Upstox daily bars through 2026-10-23; 1,420 common sessions from 2021-02-01
- **Account size:** ₹10,00,000
- **Fee model:** current modeled charges, held fixed across cases
- **Status:** retrospective execution-cost sensitivity; slippage inputs are scenarios, not measured spreads.

## Experiment

This extends the [exact sleeve-split replay](stock_nifty_gold_sleeve_split_method.md) across adverse slippage of 10, 50, 100, and 200 bps per side. At each cost level, all eleven initial stock/ETF weights from 0% to 100% in 10-point steps are re-simulated at their exact sleeve capital, including integer-share sizing, fees, and the specified slippage. The stock and quarterly NIFTY/Gold rules, rebalancing, exposure caps, and 0% cash yield are unchanged. The 50-bps, 50/50 path is reconciled against the earlier fixed-blend result.

The 10/50/100/200-bps values are deliberate execution-cost scenarios, not observations of current bid/ask spreads or market impact. No Upstox request was made; this run reuses the same local cached prices. As described in the base split note, raw caches and generated daily/order ledgers are excluded from Git.

## Selection rule and results

At each slippage level, the training-only selector chooses the highest net return from 2021-02-01 through 2023-12-29 among allocations with a combined OHLC drawdown envelope no worse than -20%. Ties prefer more training drawdown headroom, then a weight closer to 50/50. Validation is 2024; the later comparison slice is 2025-01-01 through 2026-10-23. Account NAV and drawdown high-water marks carry continuously across these periods. All dates have already been inspected, so the later slice is not a pristine lockbox.

| Slippage per side | Training-selected stock / ETF | Training return / OHLC bound | 2025–Oct 2026 return | Full return / OHLC bound | Selection status |
|---:|---:|---:|---:|---:|---|
| 10 bps | 100% / 0% | +74.56% / -17.03% | +5.74% | +122.63% / -17.07% | Pass; 2.97 pp training headroom |
| 50 bps | 100% / 0% | +61.97% / -19.66% | +1.84% | +95.08% / -19.66% | Pass; 0.34 pp training headroom |
| 100 bps | 70% / 30% | +35.56% / -18.94% | +3.55% | +58.74% / -18.94% | Pass; 1.06 pp training headroom |
| 200 bps | None | No tested weight passed | Not selected | No qualifying path | Reject under training OHLC screen |

The 50/50 reference full-path return and OHLC bound were +97.01% / -12.00% at 10 bps, +76.59% / -13.56% at 50 bps, and +54.20% / -16.27% at 100 bps; it failed the 200-bps training screen. At 100 bps, 30% stock / 70% ETF returned +50.30% full-path with -14.61% OHLC bound and +14.75% in the later slice, exceeding the training-selected 70% stock path's +3.55% later return. This is a useful sign that training return selection can choose a poor later allocation, not evidence that 30/70 is the right forward weight.

The top stock weight remains the full-history return leader at 10 and 50 bps, but its later returns are weak and its 50-bps training bound nearly touches the user's limit. At 100 bps the training choice drops to 70% stock; by 200 bps, every tested allocation breaches the training OHLC screen. The return leader therefore depends on a cost assumption that is not measured. Do not use this grid to claim an execution-ready winner.

## Limits and reproduction

This is a deterministic slippage stress on historical order simulations, not a spread study. It omits observed quotes, market impact beyond the scenario, partial fills, tax outside modeled charges, cash yield, and future drawdowns. The common price histories omit or incompletely reconstruct some ETF distributions and corporate actions; the stock universe is provisional. A historical OHLC pass is not an enforceable 20% future loss bound.

Run `python work/sensitivity_stock_nifty_gold_split_cost.py` from a checkout with the local data caches. The runner reuses the exact-split simulator, writes the [176-row cost/allocation/period ledger](stock_nifty_gold_sleeve_split_cost.csv), stores training-selected rows by cost in the [selection JSON](stock_nifty_gold_sleeve_split_cost_selection.json), and appends all cases idempotently to the consolidated backtest ledger. The fixed strategy definitions and base 50-bps results remain in [the split method](stock_nifty_gold_sleeve_split_method.md).
