# L500 benchmark-calendar date audit

**As of:** 2026-10-31
**Scope:** Official NSE/BSE evidence for the 18 supplied dates; calendar classification only. No raw market data were downloaded.

## Findings

| Date | Classification | Official evidence |
|---|---|---|
| 2016-10-30 | Special session — Muhurat | NSE’s FY 2016–17 report identifies Oct 30 as a special Muhurat session in its index/futures chart note; BSE’s index release says indices would be calculated on the declared special trading day. [NSE annual report, p. 48](https://nsearchives.nseindia.com/global/content/about_us/annualreport16-17.pdf) · [BSE index release](https://www.bseindia.com/downloads/SPDJ_ANN/MediaReleasePDF/422944_mediarelease-specialtradingsessionoct302016-20161030.pdf) |
| 2017-10-19 | Special session — Muhurat | NSE circular [CMTR35993](https://nsearchives.nseindia.com/content/circulars/CMTR35993.pdf) schedules a special live session. |
| 2018-11-07 | Special session — Muhurat | NSE holiday circular [CMTR36475](https://nsearchives.nseindia.com/content/circulars/CMTR36475.pdf) names Muhurat trading on this date. |
| 2019-10-27 | Special session — Muhurat | NSE holiday circular [CMTR39612](https://nsearchives.nseindia.com/content/circulars/CMTR39612.pdf) names Muhurat trading on this date. |
| 2020-02-01 | Special session — Union Budget | BSE’s [official index release](https://www.bseindia.com/downloads/SPDJ_ANN/MediaReleasePDF/1077559_MediaReleaseSpecialTradingSessionon20200201.pdf) declares the special day and confirms S&P BSE indices would be calculated. The NSE capital-market notice is [CMTR43290](https://nsearchives.nseindia.com/content/circulars/CMTR43290.pdf); the direct PDF did not load in this audit browser. |
| 2020-11-14 | Special session — Muhurat | NSE circular [CMTR46230](https://nsearchives.nseindia.com/content/circulars/CMTR46230.pdf) schedules a special live session. |
| 2021-11-04 | Special session — Muhurat | NSE Clearing circular [CMPT50078](https://nsearchives.nseindia.com/content/circulars/CMPT50078.pdf) identifies the Muhurat session and records Nov 4 as a trade date. |
| 2022-10-24 | Special session — Muhurat | NSE circular [ISC54105](https://nsearchives.nseindia.com/content/circulars/ISC54105.pdf) confirms the special session and trade permission for this date. |
| 2023-11-12 | Special session — Muhurat | NSE circular [ISC59313](https://nsearchives.nseindia.com/content/circulars/ISC59313.pdf) confirms the Sunday session. |
| 2024-03-02 | Special session — DR switchover | NSE Clearing circular [CMPT60709](https://nsearchives.nseindia.com/content/circulars/CMPT60709.pdf) references NSE’s live-session notice for Mar 2 and confirms the primary-to-DR switchover; [CMPT60769](https://nsearchives.nseindia.com/content/circulars/CMPT60769.pdf) records Mar 2 trades and settlement. |
| 2024-05-18 | Special session — DR switchover | NSE public member notice [MSD61893](https://nsearchives.nseindia.com/content/circulars/MSD61893.pdf) specifies Equity and Equity Derivatives sessions, 09:15–10:00 at the primary site and 11:30–12:30 at DR. BSE’s [S&P BSE Indices release](https://www.bseindia.com/downloads/SPDJ_ANN/MediaReleasePDF/1472152_mediareleasespecialtradingsessionfors%26pbseindices20240510.pdf) independently says its indices would be calculated. |
| 2024-11-01 | Special session — Muhurat | NSE circular [CMTR64628](https://nsearchives.nseindia.com/content/circulars/CMTR64628.pdf) schedules a special live session. |
| 2025-10-21 | Special session — Muhurat | NSE circular [CMTR70319](https://nsearchives.nseindia.com/content/circulars/CMTR70319.pdf) schedules a special live session. |
| 2026-02-01 | Special session — Union Budget | NSE capital-market notice [CMTR72349](https://nsearchives.nseindia.com/content/circulars/CMTR72349.pdf) schedules a Sunday live session; NSE Clearing’s [CMPT72389](https://nsearchives.nseindia.com/content/circulars/CMPT72389.pdf) confirms the referenced trade date and settlement. |
| 2026-06-05 | Regular weekday session | Friday; not in NSE’s 2026 equity holiday list. [NSE calendar and regular equity-market rule](https://www.nseindia.com/resources/exchange-communication-holidays) |
| 2026-06-15 | Regular weekday session | Monday; not in NSE’s 2026 equity holiday list. [NSE calendar and regular equity-market rule](https://www.nseindia.com/resources/exchange-communication-holidays) |
| 2026-06-16 | Regular weekday session | Tuesday; not in NSE’s 2026 equity holiday list. [NSE calendar and regular equity-market rule](https://www.nseindia.com/resources/exchange-communication-holidays) |
| 2026-06-22 | Regular weekday session | Monday; not in NSE’s 2026 equity holiday list. [NSE calendar and regular equity-market rule](https://www.nseindia.com/resources/exchange-communication-holidays) |

## Audit notes

- All 18 dates are valid exchange-session dates in the evidence reviewed: 14 special sessions and four regular weekdays. None is established as an erroneous calendar date.
- **2016 discrepancy:** NSE’s annual report chart note and BSE’s contemporaneous index release support Oct 30. A narrative passage in the same NSE annual report says Oct 28, so the report is internally inconsistent; the date classification above follows the chart and the separate BSE session notice. NSE’s later [Muhurat-session history](https://nsearchives.nseindia.com/web/sites/default/files/inline-files/Market%20Pulse_November%202024_FINAL_3.pdf) also lists 30-Oct-2016.
- **2024-05-18 / CMPT61957:** The publicly hosted NSE Clearing [CMPT61957](https://nsearchives.nseindia.com/content/circulars/CMPT61957.pdf) concerns clearing/settlement timings and trade-date settlement, but its PDF is marked **Confidential**. Treat it as corroboration only; the public NSE trading notice and BSE index release above establish the session without relying on it.
- These sources establish exchange-session status, not that every vendor has a valid close or bar for each index on every special session. Check the target benchmark’s own observation and close before treating a missing row as an exchange closure.
