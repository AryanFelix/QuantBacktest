# Upstox historical candle adjustment behavior

**Checked:** 2026-10-26  
**Instrument sample:** current and historical NIFTY 50 equities with cached Upstox daily candles

## Question

Do Upstox historical prices include the share-count adjustment for stock bonus issues and splits? The answer matters because applying the same factor again would distort historical returns.

## Method and observation

Joined the NSE corporate-actions page feed to cached Upstox stock candles by symbol and ex-date. Included bonus and face-value split/sub-division subjects; excluded debenture distributions. Compared the prior traded close and ex-date close. The reproducible script is `work/audit_upstox_adjustment_behavior.py`; the 21 event rows, parsed share factors, theoretical unadjusted price factors, and observed prices are in `outputs/upstox_split_bonus_adjustment_audit.csv`.

Across all 21 events, the ex-date close factor ranged from 0.947 to 1.050. This includes RELIANCE's 1:1 bonus on 2024-10-28 and HDFCBANK's 1:1 bonus on 2025-08-26: their observed close factors were approximately 1.005 and 0.991, while an unadjusted share-unit price would theoretically be near half the prior close. In the sample, prices therefore behave as if the historical series already reflects the changed share count.

## Interpretation limits

This is an empirical inference from price continuity, not a published Upstox guarantee. The [Historical Candle V3 documentation](https://upstox.com/developer/api-documentation/v3/get-historical-candle-data/) defines timestamp, OHLC, volume, and open-interest fields but does not state whether corporate-action factors are applied. The [Corporate Actions API](https://upstox.com/developer/api-documentation/get-corporate-actions/) documents event information for dividends, bonus, split, and rights issues, but does not establish that candle history is adjusted from this feed.

Do not apply another bonus/split share factor to the same Upstox-returned stock history unless a source-specific check shows the series uses nominal pre-event share units. This finding does not establish dividend reinvestment or total returns, the behavior of ETF candles, or handling of rights, mergers, and demergers. The major demerger-date discontinuities documented in the research report remain visible in the cached stock histories and need explicit entitlement accounting.
