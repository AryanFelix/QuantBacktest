# Monthly NIFTY trend credit spread — preregistered replay

**Specification frozen:** 2026-10-27, before batch option-leg histories are fetched or strategy P&L is calculated. A single September 2026 pair was queried earlier only to confirm API availability; it is excluded from the study calculations.

## Rule

Use the existing daily NIFTY 50 close and 200-session SMA rule. Twenty underlying sessions before each cached monthly expiry, use the completed close to select direction; enter at the next session's option open and exit at the close five sessions before expiry. In an uptrend, sell a monthly put 200 NIFTY points below spot and buy a same-expiry put exactly 200 points farther OTM. In a downtrend, sell a monthly call 200 points above spot and buy a same-expiry call exactly 200 points farther OTM. Select the nearest listed strike satisfying the OTM constraint; skip the expiry if the exact 200-point wing is unavailable. This is one directional defined-risk vertical credit spread per expiry, one lot maximum, with no parameter selection.

The strategy skips an expiry when its monthly chain is unavailable, a contract or required candle is missing, entry/exit volume is zero, the net entry credit after fees/slippage is non-positive, a vertical mark violates its no-arbitrage width bounds, or the gross spread-width loss for one lot exceeds 2% of current account NAV. The option pair must have matching expiry and lot size. Intermediate missing daily option closes are forward-filled and counted as stale marks; entries and exits require fresh positive-volume bars.

## Execution and accounting

- Start with ₹10 lakh. Use the cached monthly expiry snapshots from 2024-10 through 2026-09 and the Upstox NIFTY 50 daily series. Signals use only the prior completed close; fills use option-leg daily opens/closes.
- Charge both option legs on entry and exit with the shared current Upstox/NSE options fee schedule. Apply 25/50/100 bps adverse slippage per leg per side. Cash earns 0%; no investor tax or financing charge is added.
- Credit received, open spread marks, realized P&L, fees, and slippage are accounted in the portfolio NAV. Report close-marked drawdown and a daily option-OHLC adverse envelope: mark the long leg at its low and short leg at its high for the adverse side, clamp the vertical value to its defined payoff width, and allow the favorable daily extremes to precede adverse extremes. This is a stress envelope, not the observed intraday path.
- Use 2024-10-01–2025-06-30 as training, 2025-07-01–2025-12-31 as validation, 2026-01-01–2026-09-30 as the chronological later segment, and the continuous 2024-10-01–2026-09-30 account. Each split starts with a fresh ₹10 lakh; the continuous account carries cash and NAV across all eligible trades.

## Risk and evidence limits

The contractual maximum loss at expiry before transaction costs is spread width times lot size, less the opening credit. One-lot exposure and a 2% gross-width risk screen do not cap net loss after costs, margin requirements, settlement risk, overnight gaps, or market disruption. Broker SPAN/ELM margin is not reconstructed. The later segment and related monthly debit-spread strategy were already inspected; it is retrospective pseudo-OOS evidence, not a pristine lockbox. The sample contains at most 24 monthly expiries and can be reduced by missing or illiquid option history. Daily close marks can be stale when a leg has no trade; the run will report mark coverage and skips.

No conclusion about profitability is registered here. The selection rule is fixed and will not be changed after seeing the resulting P&L.

## Reproduction

- Runner: [`work/backtest_monthly_nifty_credit_spread.py`](../backtest_monthly_nifty_credit_spread.py)
- Primary API and fee source review: [`monthly_nifty_credit_spread_sources.md`](monthly_nifty_credit_spread_sources.md)
- Data and fee implementation: [`work/upstox_quant.py`](../upstox_quant.py)
- Run ledger: `work/backtests/monthly_nifty_credit_spread/`
