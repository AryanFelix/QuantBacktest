# Demerger ex-date valuation and data availability

**Checked:** 2026-10-27

## Official valuation method

NSE's June 2026 Nifty equity-index methodology sets a temporary dummy successor value to the prior close of the parent minus the parent's ex-date SPOS-discovered price, floored at zero. That is an index valuation rule, not a separately traded successor price. When one new company is issued, dividing this residual by the shareholder's entitlement ratio gives a per-new-share proxy. When several companies are issued, the parent price alone gives only their aggregate residual.

NSE SPOS guidance says the equilibrium price is the opening price. The official Security-wise Archives page contains the daily OHLC and `Open Price` field, so the parent ex-date `Open` is the price input to this residual calculation when the event is confirmed as SPOS. The archive is a daily price record, not a separate SPOS order/trade tape. Event-specific scheduling circulars are now located for ITC ([CMTR/65845](https://nsearchives.nseindia.com/content/circulars/CMTR65845.pdf)) and HINDUNILVR ([CMTR/71508](https://nsearchives.nseindia.com/content/circulars/CMTR71508.pdf)); they establish the SPOS scheduling and process but do not publish a numeric final auction result. Their official archive opens are therefore the best supported daily inputs to the index residual, not standalone auction-result records. See the [ITC/HUL source audit](spos_itc_hul_auction_result_audit_2026-10-27.md) for the caveat and entitlement ratios.

## Retrieved parent opens and residuals

The NSE archive page was read in the browser and its historical data endpoint returned six `EQ` parent rows (HTTP 200). The saved raw responses are `work/data/nse_spos_parent_open_raw.json`. Residuals below follow the NSE index formula; the per-new-share column is blank for Vedanta because four successor companies share the residual.

| Event | Ex-date | Prior close | Parent open | Residual per old share | Entitlement(s) | Single-recipient proxy | Days to first cached successor quote |
|---|---:|---:|---:|---:|---|---:|---:|
| RELIANCE / JIOFIN | 2023-07-20 | ₹2,841.85 | ₹2,580.00 | ₹261.85 | 1:1 | ₹261.85 | 32 |
| ITC / ITC Hotels | 2025-01-06 | ₹481.60 | ₹455.60 | ₹26.00 | 1:10 | ₹260.00 | 23 |
| SIEMENS / Siemens Energy India | 2025-04-07 | ₹4,928.15 | ₹2,450.00 | ₹2,478.15 | 1:1 | ₹2,478.15 | 73 |
| TATAMOTORS / TMCV | 2025-10-14 | ₹660.75 | ₹400.00 | ₹260.75 | 1:1 | ₹260.75 | 29 |
| HINDUNILVR / Kwality Wall's | 2025-12-05 | ₹2,462.20 | ₹2,422.00 | ₹40.20 | 1:1 | ₹40.20 | 73 |
| VEDL / four successors | 2026-04-30 | ₹773.60 | ₹289.50 | ₹484.10 | 1:1 each to four companies | — | 45 |

The complete event-level bridge, including successor archive checks and quote-gap dates, is `outputs/corporate_action_spos_value_bridge.csv`. A separate query across all series returned no successor rows for nine event-symbol pairs; raw responses are in `work/data/nse_spos_successor_probes_raw.json`. This means there is no successor transaction price in that daily archive on the event dates. It does not prove there was no SPOS or no off-archive indicative price.

## Use and limits

The residual and single-recipient values are valuation proxies, not recorded successor fills and not yet stock strategy P&L. A shareholder return ledger must book the entitled shares, preserve the proxy through the interval, and switch to actual market marks when the successor begins trading; otherwise the long quote gaps can create an artificial loss or gain. The VEDL aggregate cannot be allocated across VAML, VOGL, VISL, and VEDPOWER without separate valuation evidence. Upstox parent candles are not substituted for nominal NSE prices because their share-unit behavior around bonus/split events is only empirically inferred.

HDFC/HDFCBANK was a merger rather than a demerger SPOS case. HDFC Bank remained continuously traded, and the exchange ratio was 42:25; that action needs merger-aware position accounting.

The reproducible builder is `work/build_spos_parent_value_bridge.py`. It checks the raw response status, event coverage, residual arithmetic, and the ITC/VEDL ratio handling before writing the bridge and updating the manifest.

## Sources

- NSE, [Methodology Document for Equity Indices, June 2026](https://archives.nseindia.com/content/indices/Method_NIFTY_Equity_Indices.pdf), demerger handling and dummy-price calculation, pp. 299–301.
- NSE, [Special Pre-Open session](https://www.nseindia.com/static/products-services/equity-market-special-pre-open-session), SPOS scope and equilibrium-price guidance.
- NSE, [Security-wise Archives (Equities)](https://www.nseindia.com/report-detail/eq_security), historical daily price archive and source page for the saved responses.
- NSE, [Tata Motors SPOS circular](https://nsearchives.nseindia.com/content/circulars/CMTR70614.pdf), [Siemens Energy SPOS circular](https://nsearchives.nseindia.com/content/circulars/CMTR67392.pdf), and [Vedanta SPOS circular](https://nsearchives.nseindia.com/content/circulars/CMTR73856.pdf).
- NSE Indices, [Reliance demerger press release](https://www.niftyindices.com/Press_Release/ind_prs17072023.pdf).
- NSE, [ITC Hotels entitlement filing](https://nsearchives.nseindia.com/corporate/ITC_27012025211253_SE_COA_.pdf), and [HUL FAQ on Kwality Wall's entitlement](https://nsearchives.nseindia.com/corporate/HINDUNILVR_29112025134344_SEIntimationFAQs.pdf).
- NSE, [HDFC Bank merger filing](https://nsearchives.nseindia.com/corporate/HDFCBANK_19072023144457_SEintimation_Reg34.pdf).
