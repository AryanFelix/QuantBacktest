# Stock dividend amounts in Upstox candle share units

**Checked:** 2026-10-26

## Method

The dividend-event input is the corrected `outputs/stock_dividend_parse_audit.csv`; its earlier broad `div` filter matched `Sub-Division` split labels, and the first strict filter missed the feed typo `Dividned`. For each parsed dividend, the script finds later bonus/split factors for that symbol from `outputs/upstox_split_bonus_adjustment_audit.csv` and divides the nominal per-historical-share cash amount by their product. SEBI defines a bonus ratio A:B as A new shares for each B held and the share-count factor as (A+B)/B; it also describes split price/share changes as proportional. This supports the arithmetic, not Upstox's history convention.

The saved feed contains 21 ever-member bonus/split symbol-date candidates in 2020-2026; every candidate is present in the 21-row price-adjustment audit. 120 parsed dividend rows have a later parsed share factor; 525 have no later factor in this saved feed. No parsed dividend ex-date coincides with one of these split/bonus dates. Examples: Bajaj Finance ₹44 divided by factor 10 becomes ₹4.40; Nestlé ₹140 divided by factor 20 becomes ₹7; Reliance ₹9 divided by factor 2 becomes ₹4.50. `outputs/stock_dividend_share_unit_alignment.csv` lists each event, the nominal amount, factor, candidate candle-unit amount, and action terms.

## Interpretation and limits

The conversion is an inference: the project's 21-row Upstox audit found observed ex-date close factors near 1.0 for bonus/split events that would otherwise imply large price changes, consistent with the cached history already reflecting new share units. Upstox's Historical Candle V3 documentation defines OHLC, volume, and open interest but does not specify corporate-action adjustment. Therefore the adjusted cash values are candidate research inputs, not verified Upstox accounting. The NSE corporate-actions page feed is not a completeness-guaranteed API; a missing later event would understate the conversion factor. Cash-flow timing, withholding/personal tax, same-date event aggregation, rights issues, and merger/demerger entitlements are outside this calculation. Do not use this alone to claim stock strategy P&L.

Sources: [SEBI Investor Education: Corporate Actions (Feb 2025)](https://investor.sebi.gov.in/pdf/reference-material/ppt/PT-5%20Corporate%20Action%20-%20Dividends%2C%20Bonus%2C%20Splits%20etc-%20Feb%202025.pdf); [SEBI valuation circular on split adjustment](https://www.sebi.gov.in/sebi_data/mutualfundfile/jul-2018/1530853780625.pdf); [Upstox Historical Candle V3 documentation](https://upstox.com/developer/api-documentation/v3/get-historical-candle-data/).
