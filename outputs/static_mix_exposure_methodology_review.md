# Static NIFTY/Gold exposure-selection review

## Verdict

The 2015–2019 selection followed by a frozen 2020–2026 replay is a useful **chronological pseudo-out-of-sample check**, but it is not a genuinely untouched out-of-sample test. The 45% benchmark was chosen after inspecting full-history risk, and the later sample has already been analyzed in this project. Label it accordingly; only new future sessions can provide prospective evidence.

## Execution and drawdown details

- The simulator enters/rebalances at the next session open using the preceding close. A quarter-end event is therefore executed on the next trading day. The first 2020 test entry can use the 2019-12-31 close as its signal, with execution at the first 2020 session open; this is causal. Keep all selection and tie-breaking confined to 2015–2019.
- The stated exposure cap is applied when sizing at a rebalance. Between quarterly rebalances, price drift can take actual exposure above or below that target; do not describe it as a continuous leverage ceiling. The mix is 50/50 between risky sleeves at the target, with the unused fraction left in zero-yield cash.
- The OHLC audit replays orders and checks daily high/low portfolio marks, assuming holdings can experience the day’s high before its low. This is a conservative same-day bound under that path assumption, not a guarantee or a market-risk limit. Include opening exposure and the terminal liquidation in the screen.
- Each period run starts with ₹10 lakh and liquidates at its end. The 2020 replay is therefore a fresh-account experiment, not continuous compounding from the training account. Its train-period terminal sale and test-period first-open purchase also add boundary costs.
- If the fixed 5-point grid has no cap passing the 20% OHLC screen, report that no candidate qualifies. If several candidates tie on training return, prefer the lower cap; otherwise a tie-break can accidentally choose more risk without more return.

## Data and accounting risks

- The 2015–2019 training window includes the known NIFTYBEES 2015 payout. The replay credits cash to eligible units on its ex-date; the ₹0.80 per saved unit conversion is inferred from Nippon’s pre-split payout and later 1:10 split. The earlier 2014 payout is outside this training window.
- GoldBeES’ AMC page lists a 2019 1:100 split but does not certify a complete no-distribution history. Upstox daily candles are not documented as dividend-adjusted; observed continuity around the split does not prove how every historical price was adjusted. Missing GoldBeES distributions or incorrect unit continuity could change returns and the selected exposure. See the [ETF total-return source audit](../work/research/etf_total_return_source_audit.md), [Nippon GoldBeES corporate actions](https://investeasy.nipponindiaim.com/rmfGsamnew/Products/GoldBeES/CorporateAction.aspx), and [Upstox historical-candle documentation](https://upstox.com/developer/api-documentation/v3/get-historical-candle-data/).
- “Net” means modeled exchange/broker charges plus 50 bps slippage per side, with zero cash yield and terminal liquidation. Current fee rates are applied uniformly to historical trades. Investor income/capital-gains taxes and variable live spreads/market impact are not modeled.

## Selection rule to freeze

Evaluate only the predetermined 20%–100% exposure grid in 5-point steps on 2015-01-02 through 2019-12-31. Retain candidates with OHLC drawdown bound no worse than −20%; among those, choose the highest training net total return, breaking exact ties toward lower exposure. Freeze that cap before producing the 2020-01-02 through 2026-10-23 result. Do not call the later result independent validation; continue the paper comparison prospectively on new Upstox sessions.
