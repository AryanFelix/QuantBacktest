# QuantBacktest 24-hour checkpoint — 2026-11-01

## Strategy lead

**No strategy is in the lead.** The four frozen L500-v2 configurations received dependency-only runs; no configuration passed the pre-outcome checks, so no strategy return, CAGR, drawdown, fee-adjusted ranking, or 20% CAGR claim was produced.

| Frozen configuration | Schedule | Eligible identities per decision, min–max* | Dependency result |
|---|---:|---:|---|
| L500v2-A-M | Monthly | 1,346–2,236 | Conditional at all 105 decisions; NOT RUN for P&L |
| L500v2-A-Q | Quarterly | 1,346–2,236 | Conditional at all 35 decisions; NOT RUN for P&L |
| L500v2-B-M | Monthly | 1,339–2,208 | Conditional at all 105 decisions; NOT RUN for P&L |
| L500v2-B-Q | Quarterly | 1,339–2,208 | Conditional at all 35 decisions; NOT RUN for P&L |

\* Counts are conditional feasibility diagnostics under the corrected working calendar. They are not certified universe coverage. The ₹10 lakh objective remains at least 20% annual CAGR after costs, before personal tax. The former 20% drawdown ceiling remains removed.

## Decision and study scope

The repaired NIFTY 200 membership replay passed, but candidate signal, identity, action, order, and holding-mark dependencies did not. Per the preregistered protocol, L500-v2 was then selected for the one fallback dependency study. Both audits remained non-P&L. No additional universe, indicator, threshold, schedule, or favorable evaluation window was introduced.

The full evaluation remains 2018-01-01 through 2026-10-23, with the fixed A/B signals, monthly/quarterly schedules, top-20 portfolio, rank-25 retention, and next-session raw-price integer-share execution. The ₹10 lakh continuous-capital model, 50 bp base cost, 10/100/200 bp sensitivities, zero cash yield, and matched TRI/passive comparisons were not applied because no path passed dependency review.

## Source and replay corrections

- The 29-page `ind_prs23082021.pdf` was visually reviewed after pypdf returned no usable text. Page 14 contains six NIFTY 200 exclusions and six inclusions effective 2021-09-30. SHA-256: `c9b9feef248ca89f7d8c8f12009e3d5c409eb4d6c793eee061fb93bf0af1231e`.
- The three-page `ind_prs24092018.pdf` had 12 stripped characters. Visual review classified it as CPSE-only with no NIFTY 200 parent change. The 213-document extraction coverage ledger records text/page coverage and review disposition; the 12 restored event rows remain local.
- Corporate actions are counted once by symbol, ISIN, ex-date, and type. Exact duplicate feed rows are collapsed; 21 event keys contain multiple distinct term rows and remain flagged for primary-source reconciliation rather than counted as separate entitlements.
- Replay residuals changed after each correction:

| Step | Failed batches | Direction checks | Replay certified |
|---|---:|---:|---|
| Governor baseline at `650fbaa` | 11 | 22 | No |
| August 2021 source recovered | 8 | 16 | No |
| VBL bridge reviewed | 5 | 10 | No |
| IRCTC bridge reviewed | 5 | 10 | No |
| IPCALAB bridge reviewed | 5 | 10 | No |
| CESC bridge reviewed | 0 | 0 | Yes |

The remaining failures cascaded from shared state preconditions; the batches were not independent missing archives. Final replay contains 391 operative events, 24 identity bridges, 412 intervals, a 200-member 2026-09-30 anchor, and 111 exact official XLS/PDF event matches with zero one-sided rows. The forward and reverse replay round trip is certified.

Economic dates remain separate from identifier observations: IRCTC split entitlement 2021-10-28 and new ID first observed 2021-10-29; IPCALAB entitlement 2022-01-10 and official EOD first new ID 2022-01-11; CESC entitlement 2021-09-17 and NSE EOD first new ID 2021-09-20 while the issuer audit says 2021-09-21; VBL’s 2024 action feed uses stale ISIN `INE200M01013` while adjacent identity history shows `INE200M01021`→`INE200M01039`; E2E’s official EOD uses the new ID on 2026-06-05 while TejHQ first observes it on 2026-06-08. Source PDFs, raw EOD rows, file hashes, ratios, raw-price behavior, and conflicts are retained in the local reviewed bridge register.

## Calendar reconciliation

All 18 dates lacking TejHQ rows for every security were checked against primary exchange evidence. All are real sessions: 14 special sessions and four regular sessions. Official NSE EOD backfill adds 37,576 EQ/BE rows across 3,481 identities. All 18 NIFTY 50 TRI and NTR marks match the local reference exactly. The working session calendar grows from 2,665 to 2,683 dates. The 2024-05-18 special session uses the official daily aggregate; intraday venue paths are not reconstructed.

Across those backfill rows, 37,460 adjusted factors resolved and 116 remain unresolved: 54 action-term, 47 nearby-history, 11 factor-ratio, three unexplained-jump, and one identity-bridge row. The detailed residuals and source files remain local. These finite calendar/factor checks do not certify every security’s historical trading status.

## Measured candidate dependencies

### NIFTY 200

Each of the four schedules has unresolved member signals at every decision. Across the four configurations, the audit found 3,255 missing adjusted-price signal-window incidences (1,256 distinct entity/date windows), 2,653 distinct unreviewed action event keys across 69,299 signal-action path incidences, and 35 distinct unreviewed identity transition event keys across 932 signal-window incidences. The action counts group by event identity; repeated signal windows are reported separately as path incidences.

The provisional holdings also have 191 missing daily-close path incidences across 75 entity/date pairs, 15 missing order-open incidences across six order-date/entity pairs, and five unreviewed held identity-transition roots. Fifty-six entity/date pairs have at least one gap in a detected transition window; 19 have at least one candidate-specific gap with no matching transition in local history. These sets can overlap across configurations. Example residuals include `NIITTECH|INE591G01017` with 19 missing marks from 2025-06-04 through 2025-06-30, and the January 2018 `HDFCBANK|INE040A01034` A signal whose 232 required adjusted closes are missing from 2017-01-25 through 2018-01-01. No path was priced using a stale mark, zero, assumed fill, or unreviewed identity stitch.

### L500-v2

The amended contemporaneous rule requires positive, finite, valid EQ/BE OHLC and turnover over the preceding 63 completed sessions and the full applicable signal window. It uses no ISIN stitching or future survival/cleanliness. Between 1,339 and 2,236 identities meet those recorded windows per decision under the working calendar; this remains conditional on the calendar’s archive coverage.

All monthly and quarterly decision sets remain conditional because selected candidates’ adjusted-price signal windows intersect 6,401 distinct unreviewed action event keys (139,010 path incidences). The audit also found 34 held-transition path incidences across 13 distinct transition roots, 995 missing-close incidences across 430 entity/date pairs, and 49 missing-open incidences across 24 order-date/entity pairs. Two hundred sixty-seven entity/date pairs have at least one path gap in a detected transition window; 184 have at least one candidate-specific gap with no matching transition. These sets can overlap across configurations. All remain invalid paths, with no assumed no-trade session or execution.

For a concrete source dependency, L500v2-A-M includes the 2017-03-09 HDFC dividend while its selected identity is `INE001A01036` and the action feed identifies `INE001A01028`. The local reviewed-source register has no exact primary-backed bridge for that event. The audit kept the event unresolved and used no nearest-ISIN match. The local rows also identify each affected rule/date/entity, the exact vendor action ISIN, the missing order/mark date, and the lookup performed.

## Reproduction and evidence

- Protocol: `L500-v2`, preregistered before candidate counts or outcomes; `L500-v1` remains preserved and unrun.
- Replay summary: `nifty200_membership_replay_summary_2026-10-31.json`.
- Stepwise residual deltas: `nifty200_replay_residual_delta_2026-11-01.json` and the five intermediate replay summaries.
- Notice extraction coverage: `nifty200_source_extraction_coverage_2026-10-31.csv`.
- Calendar aggregate: `nse_calendar_backfill_aggregate_2026-10-31.csv` and `nse_calendar_backfill_summary_2026-10-31.json`.
- Candidate dependency aggregates: `nifty200_candidate_dependency_audit_2026-10-31.json` and `l500_data_gate_2026-10-31.json`.
- Detailed entity/date dependency ledgers, raw prices/actions, downloaded notices, and row-level source documents remain in the ignored local `work/data/public_research/` cache.
- Parser, replay, calendar, NIFTY 200 dependency, and L500-v2 dependency self-checks passed. The scripts compile. No Upstox request, exposed token, paid source, outreach, leverage, live order, or raw-data push was used.

## Cycle decision

This cycle stops with no certified strategy performance result. The 20% net-CAGR objective remains unchanged and unproven. When research resumes, the next finite work is to resolve the listed adjusted-price action/identity inputs and the actual post-entry mark/open gaps, then rerun the same four L500-v2 configurations’ dependency audit before authorizing any P&L.
