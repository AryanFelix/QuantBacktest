# Terminal liquidation and saved-mark audit — 2026-10-31

## Shared simulator correction

Both `work/upstox_quant.py::_simulate` and `work/backtest_stock_momentum.py::simulate` previously used a held position’s last available close for a terminal sale even if the account ran later. They now require a raw close for every held position on the account’s final date, raise `ValueError` with the symbol/date when it is missing, sell at that final date’s close, and record zero final exposure after liquidation. No stale quote is treated as an executable terminal fill.

All callers of the shared `_simulate` were reviewed. No caller was found that catches and discards the validity error. Annualization now uses elapsed calendar days divided by 365.25 across the shared engine and affected stock, intraday, spread and benchmark callers. A zero-day interval returns no CAGR rather than manufacturing a one-session year.

## Saved-ledger audit

`python work/audit_stored_position_gaps.py` mapped all traded symbols and checked the order files against paired daily equity histories and raw price calendars.

| Check | Result |
|---|---:|
| Order CSV files scanned | 3,168 |
| Unpaired/skipped order/equity cases | 0 |
| Files with terminal orders | 2,495 |
| Terminal sale rows | 4,932 |
| Terminal sales dated before the account’s final equity date | 0 |
| Terminal sales without a raw close on their order date | 0 |
| Held symbol-day observations checked | 7,293,564 |
| Held observations missing a raw close | 438, across 438 saved files |
| Unmapped symbols | 0 |

All 438 held-position gaps are the same event: GOLDBEES has no raw daily candle on 2019-05-07. Other traded ETF and index histories do contain that session; the gap is instrument-specific. The adjacent GOLDBEES closes are ₹28.00 on May 6 and ₹28.05 on May 8. The saved runs carried the previous close on May 7. The missing day’s actual price is not in the cache, so its precise NAV and rebalance effect cannot be reconstructed or corrected from these files. These 438 rows are overlapping parameter runs, not 438 independent strategy failures.

The audit found no stored terminal backdated sale and no terminal sale missing a raw quote. Therefore the terminal fix does not invalidate all prior stored ledgers. The GOLDBEES mid-run mark remains a disclosed source-data exception in the affected NIFTY/Gold runs.

## Remeasurement and superseded values

The Donchian/Gold account was funded on 2023-01-02 and marked through 2026-10-23. The corrected recent result is ₹16,36,860.36 ending NAV, 13.8245% calendar CAGR, ₹4,926.52 fees and ₹71,209.84 modeled slippage. The earlier 14.0592% CAGR is superseded. The ₹2.56 ending-NAV change matches the GST-on-SEBI-fees correction.

For the 2020+ Donchian/Gold run, CAGR changes from 12.9368% to 12.7457%. Fees rise by ₹7.27 after GST on SEBI fees; four GOLDBEES fills change by one share each under integer-share affordability, lowering modeled slippage by ₹0.93. The new ending NAV is ₹22,63,342.15. See [`measurement_correction_2026-10-31.csv`](measurement_correction_2026-10-31.csv); the prior aggregate rows remain in historical files and are superseded there by the correction ledger.

The selected stock leader’s continuous account was rerun and independently replayed from its order ledger. Its selected rows in the frontier CSV now use the corrected elapsed-calendar windows; other historical grid rows were not regenerated in this bounded cycle. See [`stock_momentum_attribution_2026-10-31.md`](stock_momentum_attribution_2026-10-31.md).

## Minimal checks

`python work/check_terminal_liquidation.py` passed the four-session synthetic stale-terminal-quote case for both simulator paths and verified final-date sales and calendar-time CAGR when the quote exists. `q._self_check()` and Python compilation of the edited modules also passed. Reproduce the stored audit with `python work/audit_stored_position_gaps.py`.
