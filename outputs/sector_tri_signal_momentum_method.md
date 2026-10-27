# Sector momentum with official TRI signals

**Run date:** 2026-10-27
**Execution data:** Upstox daily ETF OHLC through 2026-10-23
**Signal data:** NSE Indices gross sector TRI, 2014-01-01 through 2026-10-23
**Capital / risk screen:** ₹10 lakh; 20% maximum drawdown

## Rule and implementation

For BANKBEES, ITBEES, AUTOBEES, PHARMABEES, and PSUBNKBEES, rank the corresponding official Nifty sector gross TRI series by 12–1 momentum (252-session return ending 21 sessions before month-end). Hold only positive-score indices above their own 200-session TRI average, equally weight the top 1/2/3, and rebalance at month-end signals for next-session ETF opens. ETF market prices determine quantities, fills, NAV, fees, and slippage; TRI is signal data only. Four official special-session dates in 2015–2018 have no common Upstox execution-panel date and are omitted from the aligned signal grid. The price-signal baseline is the matching row in `outputs/sector_rotation_sensitivity.csv`.

Costs use current modeled equity-fund delivery charges uniformly across historical trades and 10/50/100 bps adverse slippage per side. Base results credit no ETF cash distributions because the sector ETF event ledger is incomplete; the disputed 2026 AUTOBEES/PHARMABEES claims remain a separate source-only lead. The official TRI is not an ETF fill price and does not supply ETF market impact or distribution dates.

## Walk-forward-style selection result

Selected sector_tri_momentum12_1_top2 at 75% exposure. Training return was +42.37% and its conservative OHLC bound was -17.22%. The selected rule, its 2024 validation, 2025+ holdout, continuous replay, and OHLC bounds are in `outputs/sector_tri_signal_momentum_selection.json`; all 144 strategy/cost/period rows are in `outputs/sector_tri_signal_momentum_sensitivity.csv`. The 48 50-bps paths have conservative same-day high-before-low replays in `outputs/sector_tri_signal_momentum_ohlc_audit.csv`; every order ledger reconciled to saved close NAV within ₹0.03.

## Limits

This is a signal-source challenger, not a cash-distribution-adjusted ETF total-return backtest. The five-ETF universe has unequal inception dates and survivor bias; although index TRI supplies pre-launch signal warm-up, ETF P&L begins only when traded ETF bars exist. The 2025+ and full histories were inspected repeatedly and are not untouched holdouts. The OHLC envelope assumes held positions hit daily highs before lows; it is conservative but is not an enforceable future loss limit. A passing historical bound does not guarantee future drawdown stays below 20%.

The source capture script is `work/capture_sector_tri_signal_history.py`; raw rows are in `work/data/index_daily/sector_tri_raw_2014_2026.json`. NSE Indices describes TRI as price performance plus dividends indexed on ex-date and reinvested; its historical-data page's POST route was observed in official page JavaScript and is not a documented public API. See [NSE TRI methodology](https://www.niftyindices.com/resources/index-concepts/total-return-index) and [historical-data report](https://www.niftyindices.com/reports/historical-data).
