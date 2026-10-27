# NSE stock dividend terms: parse and price-date audit

**Checked:** 2026-10-27

This audit filters the saved NSE corporate-actions page feed to dividend-labelled events for symbols appearing in at least one reconstructed monthly NIFTY 50 snapshot, with ex-dates from 2020-01-01 through 2026-10-23. This is an ever-member symbol filter, not proof that a symbol belonged to NIFTY 50 on that event date. It parses explicit Rs/Re/₹ amounts as rupees per share; percent-only announcements are converted using the feed's stated face value. Multiple explicit amounts in one subject are summed. A verified VEDL event override is keyed by ex-date, record date, face value, and exact subject; its primary-source URLs are stored on that event row. Other unparsed labels and same-symbol/ex-date multi-row groups remain visible for review; separate notices are not silently deduplicated or aggregated.

## Primary-source reconciliation

The NSE page feed labels VEDL's 2022-03-09 ex-date and 10-Mar-2022 record date only as Interim Dividend. Vedanta's shareholder dividend history identifies a third interim dividend of ₹13 per ₹1 share paid on 23-Mar-2022; the BSE-hosted FY2021-22 annual report matches the 10-Mar record date and ₹13 amount. The event-level amount_source_urls field retains both documents. This resolves the amount for this row only; it does not establish completeness of the NSE event feed.

Revision note (2026-10-26): the earlier broad `div` filter also matched `Sub-Division` split notices; the first strict filter then missed the NSE feed typo `Dividned`. The current rule excludes the split labels and retains that dividend spelling. Earlier counts are superseded.

The event-level output is `outputs/stock_dividend_parse_audit.csv`; counts by parse status and year are in `outputs/stock_dividend_parse_summary.csv`. In this run, 646 event rows were found, 646 amounts parsed, 0 amounts remained unstated, 646 ex-dates matched a cached price bar, and 10 rows belonged to 5 same-symbol/ex-date multi-row groups. The join checks price-date coverage only. This is not proof that the NSE page feed is complete. It also does not reconcile revised notices, same-day cash aggregation, taxes, rights, or merger/demerger entitlements.

Amounts are nominal at the historical share unit. Upstox price history appears adjusted for some later bonus/split events; dividend amounts must be converted into the same share units before adding cash to a simulated position. No stock total-return backtest is authorized by this parser audit alone.

Source: `work/data/universe_sources/nse_corporate_actions_2000_2026.json`; source-contract limits are in `work/research/nse_corporate_actions_api.md`.
