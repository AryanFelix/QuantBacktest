# NIFTY 50 Press-Release Archive Coverage Audit

**Audit date:** 2026-10-26  
**Purpose:** Check whether the provisional point-in-time NIFTY 50 membership reconstruction is missing public NSE Indices replacement notices, with special attention to a scanned release that text extraction could not read.

## Finding

The 29-page image-only release `ind_prs23082021.pdf` does **not** contain a missed NIFTY 50 membership change. Visual review of all pages shows its replacement tables cover NIFTY Next 50, NIFTY 500, NIFTY 100, NIFTY Midcap and small-cap indices, sector/thematic indices, and other products. Page 28 explicitly states: “No changes are being made in NIFTY 50” (along with named related indices). The release is dated August 23, 2021, and says the reviewed changes take effect September 30, 2021. It adds no NIFTY 50 add/drop event, so the event ledger, monthly universe, and backtest results did not need a correction from this source.

## Archive cross-check

The saved NSE Indices archive index contains 1,243 rows representing **1,236 unique PDF filenames** dated 2014–2026. The selected PDF audit contains 198 unique releases. A title scan found **107** unique releases titled “Replacement(s) in indices”; every one is included among the 198 selected PDFs. This is a useful coverage check for the generic replacement-release family, not a proof that every archive item has been read.

A separate literal title scan for `NIFTY 50`, `NIFTY50`, or `CNX Nifty` found 10 releases, none selected for membership parsing. These are the exact title hits:

| PDF | Archive title |
|---|---|
| `ind_prs02112018.pdf` | Change in the reference rate for computation of NIFTY 1D Rate, NIFTY50 Inverse and NIFTY50 Leverage indices |
| `ind_prs05122023.pdf` | NSE Indices launches new variant of the Nifty 50 index - the Nifty 50 Net Total Return (NTR) index |
| `ind_prs06032017_1.pdf` | Change in forex rate for computation of NIFTY50 USD index. |
| `ind_prs11092026_1.pdf` | Higher frequency for real time index dissemination of Nifty 50 |
| `ind_prs13052016.pdf` | Mirae Launches NIFTY 50 based Leveraged ETF in Korea |
| `ind_prs16062016.pdf` | IISL Launches Nifty 50 Futures Index |
| `ind_prs18042017.pdf` | IISL Launches NIFTY50 Equal Weight Index |
| `ind_prs19072016.pdf` | NIFTY 50 based Leverage & Inverse Products to be launched in Hong Kong |
| `ind_prs22042026.pdf` | Higher frequency for real time index dissemination of Nifty 50 w.e.f. May 11, 2026 |
| `ind_prs27062014.pdf` | CNX Nifty linked ETF listed on Korea Exchange. |

These titles concern an index variant, equal-weight/leverage/inverse/futures products, a forex or reference-rate calculation, dissemination frequency, or an ETF listing; none describes a constituent review. Other title-only hits that mention “50” refer to different indices (for example, Nifty Midcap 50 or fixed-income 50:50 indices) and were not treated as NIFTY 50 constituent evidence.

The six selected PDFs for which the text audit has no extracted NIFTY 50 page text were reviewed as follows:

| PDF | Coverage note |
|---|---|
| `ind_prs18032015_2.pdf` | Extracted tables concern other indices (including CNX 200/500); no NIFTY 50 change identified. |
| `ind_prs21022014.pdf` | Extracted tables concern CNX 200/500 and mid-cap indices; no NIFTY 50 change identified. |
| `ind_prs23012015.pdf` | Extracted tables concern CNX 200/500, CNX Midcap and Nifty Midcap 50; no NIFTY 50 change identified. |
| `ind_prs24092018.pdf` | Release concerns the NIFTY CPSE index. |
| `ind_prs26082014.pdf` | Extracted tables concern other CNX indices; no NIFTY 50 change identified. |
| `ind_prs23082021.pdf` | 29-page scanned release; visually inspected page-by-page. Page 28 explicitly says no NIFTY 50 changes. |

The reconstructed ledger contains 76 add/drop rows (40 with effective dates from 2020 onward), sourced from 28 distinct releases (20 releases for 2020 onward). It produces 82 monthly membership snapshots from January 2020 through October 2026; the October snapshot is as of October 23. These numbers describe the current reconstruction; they do not make the source archive complete.

## Why coverage remains provisional

- Only 198 of 1,236 unique archive PDFs were selected for parsing. The generic replacement-title family is covered, but not every unselected PDF body has been inspected; relevant notices could use a different title.
- NSE Indices' paid historical constituent dataset has not been obtained, so the release-derived event ledger has not been reconciled against a complete official point-in-time history.
- The current constituent CSV is a seed for backward reconstruction, and public releases may not document every index maintenance detail needed to establish a complete historical universe.

Accordingly, this review resolves the specific scanned-release blind spot and strengthens confidence in the selected replacement notices; it does not upgrade the stock universe to complete or independently validated. Stock momentum results remain exploratory, with previously documented corporate-action and universe limitations.

## Reproduction sources

- Archive index: `work/data/universe_sources/full_release_archive_index.json`
- Selected-release audit: `work/data/universe_sources/nifty50_release_audit.json` and `.csv`
- Event ledger: `work/data/universe_sources/nifty50_member_events.json` and `.csv`
- Monthly snapshots: `work/data/universe_sources/nifty50_monthly_universe_2020_2026.csv`
- Archive parser: `work/parse_nifty50_release_archive.py`
- Membership reconstruction: `work/reconstruct_nifty50_membership.py`
- Scanned NSE release: [`ind_prs23082021.pdf`](../work/data/universe_sources/pdfs/ind_prs23082021.pdf); [official NSE Indices copy](https://www.niftyindices.com/Press_Release/ind_prs23082021.pdf)
