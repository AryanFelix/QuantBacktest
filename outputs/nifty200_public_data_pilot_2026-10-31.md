# NIFTY 200 data-unlock decision — 2026-10-31

## Decision: do not use the public website files for backtesting without written permission

An exploratory, narrow file-format check showed that official public source files are technically accessible and parseable. The access route did not require authentication and no access control was bypassed. Review of the current official terms then exposed a use restriction: NSE's [Terms of Use](https://www.nseindia.com/static/nse-terms-of-use) restrict copying and storage without prior written permission and prohibit systematic or automated data collection; the same terms prohibit using site content for simulation. NSE Indices' [disclaimer](https://www.niftyindices.com/disclaimer) says site information may not be reproduced or stored without prior written permission and requires a license for use or distribution of index data.

Because the requested work is strategy backtesting, public accessibility alone is not authorization. The source-file pilot is stopped before strategy-performance analysis. No supplier was contacted, and no market-data observations or constituent records are included in the public repository. The source-data payloads and derived row-level pilot files are excluded from the GitHub push. The [source-hash manifest](nifty200_public_source_hashes_2026-10-31.csv) is retained as a retrieval audit record, not as a substitute for licensed data.

The complete historical-universe gate remains **NOT PASSED**. The four frozen cases remain **NOT RUN**. Do not rerun the pilot against public NSE/NSE Indices pages for simulation until written permission or an applicable data license covers collection, local storage, internal backtesting and any sharing of derived results.

## Acquisition request — prepared, not sent

Ask NSE Indices for a written sample and quote for NIFTY 200 point-in-time membership history covering 2018-01-01 through 2026-10-23, or the maximum contiguous period available through 2026-10-23. Request dated snapshots and a complete additions/removals ledger with announcement date, effective date, reference close, notice ID, symbol, company name, constituent status and stable identifiers such as ISIN/exchange security ID. Ask them to identify coverage of amendments, deferments, event-driven changes, delisted/exited/suspended/renamed/relisted names, mergers, demergers and successor securities.

For prices and events, ask whether the package includes unadjusted daily OHLCV for active and exited securities; the adjustment convention; rights, successor-share and cash-in-lieu records; effective-dated security-master history; corrections/version policy; delivery cadence and format; total cost; and the license terms for local retention, internal strategy simulation, and sharing derived summary results in a public GitHub repository. Ask for representative records around a scheduled replacement, a deferred change, an event-driven successor case and the July 2024 file-format transition. Do not purchase until the sample reconciles to official notices and demonstrates the stated coverage.

## Official sources

- [NSE Data Sharing and Usage Policy](https://www.nseindia.com/static/market-data/nse-data-policy)
- [NSE Terms of Use](https://www.nseindia.com/static/nse-terms-of-use)
- [NSE Indices disclaimer](https://www.niftyindices.com/disclaimer)
- [NSE Indices data-subscription page](https://www.niftyindices.com/offerings/data-subscription)
- [NSE All Reports page](https://www.nseindia.com/all-reports)

**Next action:** obtain written authorization and the sample/quote described above, or provide an equivalent licensed sample locally. Then reconcile source coverage and license scope before deciding whether to run the four frozen cases.
