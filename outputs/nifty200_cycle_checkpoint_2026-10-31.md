# NIFTY 200 research checkpoint — 2026-10-31

## Frozen strategy set: no leader; all four remain untested

| Rule | Signal and schedule | Portfolio / execution | Status |
|---|---|---|---|
| A-M | Positive 12–1 total-return momentum, omit most recent 21 sessions; monthly | Equal-weight top 20, retain ranks 1–25; next-session open, integer shares | NOT RUN — data gate |
| A-Q | Same signal; quarterly | Same portfolio and execution | NOT RUN — data gate |
| B-M | Positive average of 6–1 and 12–1 total returns divided by trailing 252-session annualized volatility; both legs omit latest 21 sessions; require 252 observations; monthly | Same portfolio and execution | NOT RUN — data gate |
| B-Q | Same signal; quarterly | Same portfolio and execution | NOT RUN — data gate |

No performance result or ranking exists for this frozen set. The target remains 20% net CAGR on ₹10 lakh, unlevered, before personal tax. The prior 20% drawdown ceiling remains removed.

## Coverage acquired and verified

- Downloaded 34 Parquet files from the public TejHQ indian-markets dataset at pinned revision 2d6629d656fcb715a03b859f7cff8fbd53a7f420: 11 raw NSE daily-price files, 11 adjusted-price files, 11 action files and one symbol-history file. Total raw payload: 305,712,150 bytes. File sizes, SHA-256 hashes, schemas, row counts and date coverage are recorded in the local manifest and the aggregate [TejHQ source manifest](tejhq_public_source_manifest_2026-10-31.csv).
- Raw and adjusted price files each contain 5,114,880 rows from 2016-01-01 through 2026-10-30. The 23,564 action rows range from 2016-01-05 to 2026-11-06; dates after the as-of date are future records and were not eligible for simulation. Symbol history contains 4,934 rows. This is market-wide source coverage, not proof that every NIFTY 200 name has an executable continuous series.
- Retrieved the official NIFTY 200 constituent CSV (200 unique symbols and ISINs; inferred as-of 2026-09-30), the official IndexInclExcl.xls file (464 deduplicated NIFTY 200 events through 2020-07-31), and cached official notices. Of 79 notices mentioning NIFTY 200, the strict parser extracted 498 membership rows from 38; 41 still lack a parsed numbered membership table.
- On the overlapping 2018–2020 event history, 110 rows match exactly. The remaining comparison is one company-name alias in the XLS and 12 PDF rows from the proposed March 2020 change later deferred. The deferred rows must not be replayed as executed events.
- The membership audit now has one unmapped parsed symbol, PIPAVAVDOC, dated outside the 2018–2026 evaluation. This does not resolve the 41 unparsed notices or prove point-in-time membership completeness.

## Gate and result

**Data gate: NOT PASSED.** The dated membership transition set has not been reconstructed and replayed in both directions; 41 notices, amendments/contingencies and successor entitlements remain unresolved. TejHQ's adjustment documentation excludes rights, mergers and demergers from its split/bonus/dividend price adjustment, so the action file alone is insufficient for those cases. No dataset/evaluation fingerprint was frozen for outcome analysis and none of A-M, A-Q, B-M or B-Q ran. No 20% result can be claimed for the frozen rules.

The pre-existing NIFTY 50 stock-momentum diagnostic remains context only: 11.90% continuous net CAGR at the 50 bps per-side slippage assumption, versus 9.66% matched NIFTY 50 TRI and 9.69% price-only NIFTYBEES under the same modeled trading-cost convention. It is below the 20% target. The modeled 50 bps is uncalibrated; costs materially reduced the strategy's gross return. A separate 20.72% NIFTY/Gold result is limited to 2020 onward and did not qualify on the full-history target.

## Single next research action

Resolve the 41 unparsed notices and exceptional/amended membership events, then produce a dated ISIN-level event ledger and forward/reverse replay against the 2026-09-30 anchor. Keep the 2020 deferred proposals out of operative history and join successor entitlements to source-backed corporate-action records. Re-run the gate before freezing evaluation dates and costs; do not start another parameter search.

## Reproduction and source-use note

The resumable collectors and membership parser are work/collect_tejhq_public_data.py, work/collect_nifty200_notices.py and work/reconstruct_nifty200_membership.py. Their raw inputs and row-level event cache remain outside Git. The report and published manifest contain source metadata and aggregates, not raw price observations or constituent-level event rows.

TejHQ's published terms state personal research/backtesting is allowed and raw data may not be redistributed. NSE's website terms separately restrict storage and use of website content for simulation. The source terms therefore conflict; this report records the conflict and does not claim it is resolved by public accessibility or user authorization. No supplier was contacted, no paid data was acquired, no Upstox request was made, and no live order, leverage or paper-path change occurred.

