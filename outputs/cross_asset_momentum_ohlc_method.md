# Cross-asset ETF momentum OHLC audit

## Result

The 50-bps-per-side case is the conservative primary result. On ₹10 lakh, the rule selected a 45% gross exposure cap from the development data and returned 20.85% (ending at ₹12,08,542; 5.19% CAGR) from 2023-01-01 through 2026-10-23. Close-to-close maximum drawdown was -12.93%; the conservative daily OHLC envelope was -13.56%, leaving 6.44 percentage points under the historical 20% screen. Modeled fees were ₹7,567 over 161 orders. This is a retrospective pseudo-holdout: every historical window has already been inspected.

At 10 bps per side, the same risk-gated selector chose 50% exposure. Its pseudo-holdout return was 29.68% (₹12,96,777 ending value; 7.18% CAGR), with -12.81% close drawdown, -13.69% OHLC envelope, ₹7,734 modeled fees, and 161 orders. The low-friction result is secondary because 10 bps may understate real execution costs.

## Rule and selection

At each monthly rebalance, rank the available NIFTY, Gold, and sector/index ETFs by 12-minus-1-month price momentum, keep the top three with closing price above the 200-session moving average, and execute target changes at the next session's open. The eight instruments are NIFTYBEES, GOLDBEES, BANKBEES, ITBEES, AUTOBEES, PHARMABEES, PSUBNKBEES, and JUNIORBEES. The portfolio starts with ₹10 lakh, has no leverage, and is tested at gross exposure caps from 25% to 95% in five-point increments.

For each slippage assumption, a cap is eligible only when the OHLC envelope is within 20% in the 2014–2019 training, 2020–2022 selection, and continuous 2014–2022 development windows. Among eligible caps, the highest 2020–2022 CAGR is selected. The 2020–2022 period is selection data, not an independent validation set. The 2023+ window is a chronological pseudo-holdout, but it has been reviewed during this research and is not a lockbox.

The cap screen is sensitive to execution assumptions. At 50 bps per side, only 25% through 45% passed all development risk gates; 45% had the highest selected-period CAGR (6.01%). At 10 bps, the selected cap was 50%. A 75% cap at 10 bps looked attractive in the 2023+ slice (+46.64%), but its OHLC bound there was -19.98%, leaving only 0.02 percentage points of historical room, and it did not pass all development windows. It is not the selected case.

## Data, fees, and risk interpretation

Daily Upstox ETF candles are frozen through 2026-10-23. The simulator uses the shared current fee model, whole ETF units, next-open fills, and adverse slippage of 10 or 50 bps per side. ETF fund-unit STT is applied according to the corrected fund classification; the previous cross-asset outputs charged equity-share STT to ETF units and are superseded. The legacy cross-asset rows remain visible in `outputs/backtest_summary.csv` for traceability; use this corrected frontier and selection JSON for current figures. The current fee schedule is applied uniformly to historical trades, not reconstructed from dated contract notes.

Only the verified NIFTYBEES distributions of ₹0.70 on 2014-03-11 and ₹0.80 on 2015-02-20 are credited. Gold and sector ETF distributions are not completely reconciled; cash earns zero. The 2023+ slices therefore should not be read as fully distribution-adjusted total returns.

The daily OHLC bound assumes each held asset can reach its session high before its session low. It is a conservative path envelope, not a realized intraday portfolio path, executable stop, or future loss limit. The 20% screen is a historical filter only.

## Reproduction

- Runner: `work/audit_cross_asset_momentum_ohlc.py`
- 150-case metric and risk grid: [`cross_asset_momentum_ohlc_risk_frontier.csv`](cross_asset_momentum_ohlc_risk_frontier.csv)
- Cost-specific selection and selected pseudo-holdout rows: [`cross_asset_momentum_ohlc_selection.json`](cross_asset_momentum_ohlc_selection.json)
- Per-run close-NAV and order replay files are generated under the gitignored `work/backtests/cross_asset_momentum_risk_frontier/` directory. Each OHLC replay asserts close-NAV reconciliation within ₹0.03.
