# ITC and HUL demerger SPOS source audit

**Checked:** 2026-10-27
**Question:** Are the ex-date parent opens used in the two demerger residuals confirmed SPOS prices, and what exact values can first-party sources support?

## Finding

The earlier [demerger price-discovery note](reorganization_price_discovery.md) said event-specific SPOS circulars were not found for ITC and HUL. That was incomplete: NSE published scheduling circulars for both events. The circulars establish that the SPOS was scheduled and define what happens if equilibrium is not immediately found; they do **not** print the final numeric auction result.

The event-date values are available in NSE's Security-wise Archives `EQ` daily rows as the parent **Open**: ₹455.60 for ITC on 2025-01-06 and ₹2,422.00 for HINDUNILVR on 2025-12-05. NSE's pre-open guidance states that an equilibrium price determined in a pre-open session is the opening price, and that the first normal-market trade becomes the open only if the pre-open session does not discover a price. Thus these official opening prices are the best sourceable inputs for the NSE index residual formula and are consistent with the SPOS results. The daily archive does not label its `Open` field as an SPOS auction-result record, so keep that distinction in any strategy ledger.

## Primary-source evidence and arithmetic

| Event | SPOS scheduling evidence | NSE archive prior close → open | NSE index residual proxy | Issuer entitlement | Per-new-share proxy |
|---|---|---:|---:|---:|---:|
| ITC / ITC Hotels, 2025-01-06 | [NSE CMTR/65845](https://nsearchives.nseindia.com/content/circulars/CMTR65845.pdf) schedules 09:00–10:00 IST and says the call auction continues if no equilibrium price is found. | ₹481.60 → ₹455.60 | ₹26.00 per ITC share | ITC filing confirms 1 ITC Hotels share per 10 ITC shares. | ₹260.00 per ITC Hotels share |
| HINDUNILVR / Kwality Wall's, 2025-12-05 | [NSE CMTR/71508](https://nsearchives.nseindia.com/content/circulars/CMTR71508.pdf) schedules 09:00–10:00 IST and describes the process for no equilibrium price; its block-deal provision applies only subject to successful price discovery. | ₹2,462.20 → ₹2,422.00 | ₹40.20 per HUL share | HUL FAQ confirms 1 KWIL share per HUL share. | ₹40.20 per KWIL share |

The residuals are `max(0, prior close − ex-date parent open)`, following the [NSE equity-index demerger methodology](https://archives.nseindia.com/content/indices/Method_NIFTY_Equity_Indices.pdf), pp. 299–301. The ITC 1:10 entitlement and Jan 6 record date are in [ITC's exchange filing](https://nsearchives.nseindia.com/corporate/ITC_28012025004206_SE_COA_.pdf). HUL's effective date, Dec 5 record date, and 1:1 ratio are in its [NSE-filed FAQ](https://nsearchives.nseindia.com/corporate/HINDUNILVR_29112025134344_SEIntimationFAQs.pdf).

The matching NSE Indices releases for [ITC](https://www.niftyindices.com/Press_Release/ind_prs30122024.pdf) and [HUL](https://www.niftyindices.com/Press_Release/ind_prs28112025.pdf) confirm the demerger treatment and zero-price dummy inclusion in index baskets. They do not publish the specific SPOS price. The NSE [pre-open rules](https://www.nseindia.com/static/products-services/equity-market-pre-open) define the relationship between discovered price and the day's open. The official [Security-wise Archives](https://www.nseindia.com/report-detail/eq_security) supplies the parent daily `EQ` OHLC fields.

## Saved values and practical limit

The retrieved official archive payloads are preserved in `work/data/nse_spos_parent_open_raw.json`; the reproducible residual calculation is in `work/build_spos_parent_value_bridge.py`, and the six-event output is `outputs/corporate_action_spos_value_bridge.csv`. The ITC row records previous close ₹481.60, open ₹455.60, and residual ₹26.00. HINDUNILVR records previous close ₹2,462.20, open ₹2,422.00, and residual ₹40.20.

The corresponding successor archive probes had no event-date rows. The first cached ITCHOTELS quote is 2025-01-29 (23 calendar days later); the first cached KWIL quote is 2026-02-16 (73 calendar days later). NSE Indices later reports confirm those listing dates: [ITC Hotels](https://www.niftyindices.com/Press_Release/ind_prs06022025_1.pdf) and [Kwality Wall's](https://nsearchives.nseindia.com/corporate/KWIL_16022026115750_SEIntimationPressRelease_signed.pdf). Therefore ₹260.00 and ₹40.20 are methodology-based, single-recipient valuation proxies for the entitlement bridge—not recorded successor fills or stand-alone auction prints. Do not treat issuer tax-cost apportionment as market value.

## Conclusion for stock accounting

For a transparent index-style bridge, use the official parent opens above to derive the implied residuals, book the issuer-confirmed entitlement quantities, and mark the values as proxies until successor market prices are available. Retain the missing numeric SPOS result-sheet caveat. No corporate-action strategy P&L was changed by this source audit.
