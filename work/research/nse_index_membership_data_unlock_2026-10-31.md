# NSE index-membership data unlock: official-source audit

## Follow-up status — 2026-10-31

The original source audit below preceded the user's explicit authorization to acquire publicly accessible data for personal research. After that authorization, a pinned public price/action dataset, the current NIFTY 200 anchor, the official event workbook and additional notices were collected and checksummed. No supplier was contacted and no paid data was acquired. See [the current cycle checkpoint](../../outputs/nifty200_cycle_checkpoint_2026-10-31.md) for verified coverage and the remaining data gate.

The earlier “awaiting sample/quote” recommendation is superseded. The current blocker is incomplete dated membership replay, unparsed notices and corporate-action/successor accounting. This update does not claim that public access resolves the separate source-terms conflict; raw data and row-level event records remain outside Git.

**Research date:** 2026-10-31  
**Scope:** Public, primary-source evidence for reconstructing point-in-time Nifty 200 membership and linked security prices. This is a source audit only; no supplier was contacted, no data was purchased, and no strategy returns were inspected.

## Verified

### Notices establish separate announcement, effective, and reference-close dates

- The [NSE Indices press-release archive](https://www.niftyindices.com/press-release) lists the broad-market replacement release dated **17 February 2023**, titled “Replacements in indices w.e.f March 31, 2023.” The linked [17 February 2023 notice](https://www.niftyindices.com/Press_Release/ind_prs17022023_1.pdf) names **31 March 2023** as the effective date and **29 March 2023 close** as the reference close. Keep these as separate fields; the release date is the announcement date.
- That notice records a Nifty 200 semiannual review with **nine exclusions and nine inclusions**. The exclusions are CLEAN, EMAMILTD, GSPL, ISEC, INDIAMART, IEX, LINDEINDIA, NATIONALUM, and NAM-INDIA. The inclusions are ADANIPOWER, APOLLOTYRE, CGPOWER, DEVYANI, FLUOROCHEM, IRFC, NHPC, NMDC, and PEL. The same notice records **20 exclusions and 20 inclusions** for Nifty 500. It explicitly flags TATACOFFEE's exclusion as arising from a proposed scheme of arrangement for demerger.
- A separate [6 March 2023 notice](https://www.niftyindices.com/Press_Release/ind_prs06032023.pdf) also specifies 31 March 2023 (29 March close), but concerns strategy-index quarterly changes and a Shariah review. It is not a second amendment to the 17 February Nifty 200/500 replacement list. The archive therefore has multiple notices sharing an effective date; index family and notice type must be captured.
- The [17 July 2023 corporate-action notice](https://www.niftyindices.com/Press_Release/ind_prs17072023.pdf) reports that, following the special pre-open session for Reliance Industries Ltd on 20 July, the spun-off entity was to be included in Nifty 200, Nifty 500, and other named indices **effective 20 July 2023 (close of 19 July)**. This is a separate event-driven membership change, not a regular semiannual review. The notice refers to a methodology revision for schemes of arrangement; the event belongs in both the membership-change and corporate-action audit trail.
- The [25 March 2020 notice](https://www.niftyindices.com/Press_Release/ind_prs25032020.pdf) says changes announced on 23 March for implementation on 27 March (26 March close), tied to SEBI concentration norms for ETFs and index funds, were **deferred until further notice**, with a revised date to be communicated with two weeks' notice. This is not evidence of a Nifty 200/500 replacement taking effect. The original planned date is not evidence that the change took effect; a backtest needs the subsequent operative notice or must leave the transition unresolved.
- The [rebalancing schedule](https://www.niftyindices.com/resources/index-rebalancing-schedule) states that Nifty 200 and Nifty 500 are reconstituted semiannually, on the last working day of March and September. It also says NSE Indices may conduct additional reviews for specified events such as schemes of arrangement, suspension, and delisting. A schedule is not a full change ledger.

### Public NSE routes support a validated narrow price sample, not full-universe history

- The [NSE All Reports page](https://www.nseindia.com/all-reports) exposes a “Security-wise Archives (Equities)” route. Public legacy and CM-UDiFF Bhavcopy files were retrieved without authentication and parsed for a fixed, preselected sample. The pilot validates 49 positive finite OHLC rows, including five sessions from 23–27 March 2020 and samples on both sides of the 8 July 2024 format transition. It confirms a sample path, not bulk coverage or permission for unrestricted redistribution.
- NSE states that the old CM Bhavcopy CSV / Common Bhavcopy route was discontinued from **8 July 2024** and points users to **CM-UDiFF Common Bhavcopy Final** archives. The pilot maps and validates both schemas on the sampled symbols; a complete cross-history symbol/adjustment reconciliation remains open.
- The [Nifty Indices historical-data page](https://www.niftyindices.com/reports/historical-data) provides historical index-level OHLC and total-return / net-total-return series. It is not, by itself, a historical constituent-membership archive.

### What the public subscription page promises

The [Nifty Indices data-subscription page](https://www.niftyindices.com/offerings/data-subscription) advertises ongoing and historical data on individual securities. Its constituent-data description names company names, identifiers, market capitalization, weights, and prices, and says to request end-of-day constituent data from its listed contact address or vendors. This is evidence that constituent data is offered for subscription, **not** a defined service-level commitment for the fields or dates required by this research.

## Inferred

- A point-in-time reconstruction should join (1) dated membership snapshots or an inclusion/exclusion ledger, (2) contemporaneous announcement and amendment notices, and (3) security-level daily bars. Current constituent lists and index-level OHLC cannot substitute for that history.
- The release archive provides a concrete event check: the March 2023 Nifty 200 review has nine adds and nine drops. It does not prove the full constituent set immediately before or after the review, nor provide all interim event changes. For a bounded pilot, Nifty 200 is the smaller scope; start/end anchors and all intervening event changes still need to be supplied or independently reconciled.
- Event notices can correct the naive “last working day of March/September” rule. The 2020 deferment shows why the operative effective date must be resolved from the latest notice, and the 2023 Reliance event shows why semiannual files alone are insufficient.

## Unknown / not established by the public pages reviewed

The public pages do not specify or demonstrate:

- Earliest and latest dates, contiguous coverage, frequency, or whether daily constituent snapshots and a dated change ledger are both included.
- Whether “identifiers” means stable ISIN / exchange security identifiers across symbol changes, renames, suspensions, exits, relistings, or successor securities.
- Complete historical membership anchors; treatment of companies that later delisted, merged, demerged, or otherwise disappeared; and whether historical files preserve removed constituents.
- Corporate-action fields or treatment for splits, bonuses, rights entitlements, mergers, demergers, spin-offs, successor shares, and cash-in-lieu. The Reliance notice confirms one index-membership action, not complete corporate-action price/cashflow data.
- Whether “prices” means OHLCV bars, close-only observations, adjusted prices, total-return values, or another series; adjustment methodology; volume and delivery fields; corrections/revisions; and schema/version policy.
- Delivery format, update cadence, license for internal quantitative research, price, and access to a representative sample before purchase.

The [Nifty 200](https://www.niftyindices.com/indices/equity/broad-based-indices/nifty-200) and [Nifty 500](https://www.niftyindices.com/indices/equity/broad-based-indices/nifty-500) descriptions are current index descriptions, not historical constituent files. The [Daily Reports page](https://www.niftyindices.com/reports/daily-reports) links daily snapshots and an archive, but its public description does not establish that those files contain the full historical constituent snapshots needed here.

## One concrete acquisition request (draft only; not sent)

> Please quote and provide a schema/sample for **Nifty 200 end-of-day constituent history**, covering **2018-01-01 through 2026-10-23**, or the maximum available *contiguous* period ending 2026-10-23. We need (a) point-in-time member snapshots at each effective date and (b) a complete dated additions/removals ledger, including announcement date, effective date, reference close, notice/circular identifier, index, constituent status, company name, symbol, and stable identifiers such as ISIN/exchange security ID. Please state explicitly how the files cover delisted, exited, suspended, renamed, relisted, merged, demerged, and successor securities, and include the intervening event-driven changes and amendments/deferments, not just scheduled March/September rebalances.
>
> Please also specify whether the subscription includes daily **unadjusted OHLCV** for every active and historical constituent, including securities no longer listed; the adjustment policy and separately available corporate-action/rights/successor-share/cashflow records; the effective-dated security master and symbol/identifier mapping; data corrections and file-version/update policy; delivery format and cadence; permitted internal research use; and total cost. Please include sample records for the 2023 Nifty 200 March review (CLEAN and one inclusion), the 2020 deferred review with its eventual operative date or an explicit statement if unavailable, and the July 2023 Reliance/Jio Financial event. No purchase or supplier contact has been made.

## Pilot gate

The public-source pilot is documented in [`nifty200_public_data_pilot_2026-10-31.md`](../../outputs/nifty200_public_data_pilot_2026-10-31.md), with raw-input hashes, parsed prices and membership reconciliation. The current 30 September 2026 anchor reverses and reapplies the 7 additions/7 removals announced 10 August, but there is no independent pre-event snapshot. The public `IndexInclExcl.xls` NIFTY 200 sheet contains 467 dated rows from 22 November 2011 through 31 July 2020; it does not bridge the full 2018–2026 period. The pilot validates sampled March 2023 and July 2023 event prices, a recent listing, the 2020 stress interval, and the July 2024 file-format transition. It does not resolve the full March 2020 deferred event chain or establish complete delisted/successor price and action records. The complete-universe gate remains **NOT PASSED**; the four frozen cases remain **NOT RUN**.

## Official source index

1. [NSE Indices press-release archive](https://www.niftyindices.com/press-release)
2. [17 February 2023: Nifty 200 / Nifty 500 replacements](https://www.niftyindices.com/Press_Release/ind_prs17022023_1.pdf)
3. [6 March 2023: strategy and Shariah changes](https://www.niftyindices.com/Press_Release/ind_prs06032023.pdf)
4. [17 July 2023: Reliance demerger event](https://www.niftyindices.com/Press_Release/ind_prs17072023.pdf)
5. [25 March 2020: deferment](https://www.niftyindices.com/Press_Release/ind_prs25032020.pdf)
6. [NSE Indices rebalancing schedule](https://www.niftyindices.com/resources/index-rebalancing-schedule)
7. [Nifty Indices data subscription](https://www.niftyindices.com/offerings/data-subscription)
8. [NSE All Reports / Security-wise Archives](https://www.nseindia.com/all-reports)
9. [Nifty Indices historical index data](https://www.niftyindices.com/reports/historical-data)
10. [Nifty Indices daily reports](https://www.niftyindices.com/reports/daily-reports)


