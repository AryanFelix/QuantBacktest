# Upstox corporate-actions API: research note

**Checked:** 2026-10-26  
**Source policy:** Upstox first-party developer documentation only for API behavior.

## Documented contract

- `GET https://api.upstox.com/v2/fundamentals/{isin}/corporate-actions` retrieves events for one company by ISIN. The request example uses `Accept: application/json` and a bearer token. The documented required path parameter is `isin`; the endpoint page lists no query parameters, date filters, pagination controls, or time-range/retention guarantee. [Endpoint reference](https://upstox.com/developer/api-documentation/get-corporate-actions/)
- The documented examples of event types are dividends, bonus issues, stock splits, and rights issues. The response schema has `status`, a `data` event list, and for each event `name`, `expiry_date` (described as ex-date or effective date), `amount`, `ratio`, and `event_details` key/value entries. The example details include announcement date, ex-dividend date, record date, dividend type, amount, percentage, and text details. [Endpoint reference](https://upstox.com/developer/api-documentation/get-corporate-actions/)
- The endpoint reference lists invalid ISIN (`UDAPI1206`) as an error. It does not document mergers, demergers, spin-offs, delistings, symbol changes, event corrections, or a historical completeness guarantee. Absence from this page is a documentation gap, not proof that the service can never return such events. [Endpoint reference](https://upstox.com/developer/api-documentation/get-corporate-actions/)
- Upstox announced the Company Fundamentals suite effective May 11, 2026. That is the documented launch date, not a statement about the earliest corporate-action date returned for any particular security. [Launch announcement](https://upstox.com/developer/api-documentation/announcements/company-fundamentals-api/)

## Backtest implications

The documented interface alone does not provide a way to request a specified historic interval or establish that the returned list is complete. The response schema is also a generic event-details array, so a backtest should normalize and validate event labels and dates rather than assume a fixed detail ordering. For a stock total-return ledger, this API is useful as a dividend/bonus/split probe, but it cannot be treated as the sole authoritative historical source based on the public contract. In particular, merger and demerger share entitlements need issuer/exchange filings and explicit position accounting.

In the project’s saved sample calls for VEDL, ITC, HINDUNILVR, RELIANCE, and HDFCBANK, responses contained eight records total (one or two per ISIN), all dividends, dated 2025-11-07 through 2026-10-14. These are observations from this project’s samples, not an Upstox coverage guarantee. Raw responses are in `work/data/universe_sources/upstox_actions_*.json`.

## Sources

1. Upstox, [Get Corporate Actions](https://upstox.com/developer/api-documentation/get-corporate-actions/), accessed 2026-10-26.
2. Upstox, [Company Fundamentals API Launch](https://upstox.com/developer/api-documentation/announcements/company-fundamentals-api/), effective 2026-05-11, accessed 2026-10-26.
