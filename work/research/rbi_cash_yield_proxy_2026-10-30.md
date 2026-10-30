# RBI 91-day Treasury-bill cash proxy: source and modeling audit

- **Checked:** 2026-10-30
- **Purpose:** determine whether historical cash yield can be credited to the quarterly NIFTY/Gold allocation study.

## Finding

The official RBI source is DBIE report 307, **Auctions of 91-Day Government of India Treasury Bills**. RBI describes T-bills as discount instruments redeemed at face value, says 91-day auctions are usually weekly with T+1 settlement, and specifies actual/365 for money-market day count. The RBI Handbook’s Table 213 publishes auction date, issue date, cut-off price, and implicit yield. [RBI Table 213](https://rbi.org.in/scripts/PublicationsView.aspx?id=22019) and the [RBI T-bill FAQ](https://m.rbi.org.in/commonman/english/scripts/FAQs.aspx?Id=711) are the source references.

The first read-only mirror API export of report 307 flattened columns ambiguously and was not suitable for direct normalization. A separately normalized [91-day rate history](https://measure.thisindianlife.today/data/rates-tbill-91/) is compiled from RBI DBIE and provides auction date, issue date, cut-off price, and implicit yield. It is CC BY 4.0 and identifies RBI DBIE as its source. The saved 2026-10-08 vintage has 606 auction rows in the 2015-01-02–2026-10-23 research window, including five missing yields; the normalized output also retains five Dec-2014 seed rows for prior-rate alignment. Four rows were checked against RBI's official Table 213: 2022-08-03 (5.5586%), 2022-08-10 (5.5949%), 2023-08-17 (6.8781%), and 2023-08-30 (6.8225%). The corresponding rounded prices also agree. The raw mirror and normalized input remain local and ignored; the cleaned series and preparation code are versioned.

**Decision:** use the validated normalized series only for a clearly labeled opportunity-return sensitivity. The direct zero-yield baseline remains. In the sensitivity, the last auction yield whose issue date is no later than a session is credited to cash on actual/365 calendar days, and the last available rate is carried across missing auctions. This is an optimistic synthetic proxy: it credits the whole cash balance continuously and does not model buying, holding, maturing, or reinvesting a 91-day bill ladder, auction access, liquidity, whole-lot constraints, tax, or premature-sale prices. It must not be represented as an executed investment or as Upstox cash interest.

## Reproduction and caveats

Run `python work/prepare_rbi_91d_tbill_yields.py` to normalize the cached inputs and reproduce the four official spot checks. Run `python work/stress_quarterly_static_mix_cash_yield.py` and the targeted challenger runners to regenerate the cash-yield comparison. The simulator uses only an issue-date rate available by the session being accrued, so the sensitivity has no look-ahead from later auctions. Its yield accrual increases expected return, not ETF-price drawdown protection; the 20% objective is still not guaranteed.

## Re-entry criteria

For an investable cash-return estimate, replace this broad-rate proxy with a specified instrument actually available to the account (for example, a quoted liquid fund or executable bill ladder), verify its total-return series and transaction/tax treatment, and measure observed cash sweep terms. Keep the zero-yield control for comparability. Yield accrual is an expected-return adjustment; it does not reduce ETF price drawdown or create a guaranteed daily cash return.
