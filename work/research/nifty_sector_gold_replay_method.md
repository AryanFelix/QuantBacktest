# Fixed NIFTY / sector momentum / Gold ETF replay

**2026-10-27 fee-model correction:** This static result snapshot predates the instrument-specific ETF STT replay. Use the current linked sensitivity CSV and [consolidated ledger](../../outputs/backtest_summary.csv) for numeric results; older figures below are superseded where they differ. See the [fee-model audit](fee_model_audit.md).


**Registered:** 2026-10-26, before this replay; prior exploratory results for this same mix were already visible in the research workspace.

## Purpose

The report identified the 50% NIFTYBEES Donchian + 25% sector momentum + 25% GOLDBEES trend mix as needing a clean composite replay. This run checks its complete event schedule, orders, fees, and equity path in the established daily simulator. It is a reproducibility audit of an already explored portfolio, **not** fresh out-of-sample evidence.

## Frozen portfolio rules

- Comparator: allocate 50% to NIFTYBEES Donchian 55/20 and 50% to GOLDBEES 200DMA.
- Allocate sleeve targets at 50% to NIFTYBEES Donchian 55/20, 25% to a sector-ETF 12–1 momentum sleeve, and 25% to GOLDBEES 200DMA.
- The sector sleeve ranks BANKBEES, ITBEES, AUTOBEES, PHARMABEES, PSUBNKBEES, and JUNIORBEES by 12-month return excluding the latest month; only positive-return instruments above their 200DMA qualify; equal-weight the top three qualifying ETFs.
- Trade after signal changes and at each month-end, using next-session open fills. Use overall gross exposure caps of 50%, 75%, 95%, and 100% for both mixes; 100% allows the strategy to deploy full NAV but does not use leverage.
- Start with ₹10,00,000, use no cash yield, and charge current Upstox/NSE equity-delivery fees uniformly over the historical sample. Report 10 bps per-side slippage as baseline and 20/50 bps as stress cases.
- Evaluate 2020-01-01 through 2026-10-23 and 2023-01-01 through 2026-10-23. Both windows have been inspected previously and remain retrospective. No sleeve weights or exposure caps are selected from these outputs.

## Data and limitations

Daily OHLCV is from the saved Upstox ETF histories listed in `outputs/data_manifest.csv`. The sector universe consists of currently surviving ETFs with unequal inception dates, so the sector ranking has survivorship and availability bias. ETF market-price histories are not treated as official total-return series. The six sector sleeve ETFs now have a documented corporate-action review in `outputs/sector_etf_corporate_action_audit.csv`; identified BANKBEES, JUNIORBEES, and PSUBNKBEES cash events predate the tested period. Direct AMFI scheme-dividend queries for all five Nippon sector ETFs across 2022–2026 returned empty records; this negative result does not prove that no distributions occurred. A third-party page's 2026 AUTOBEES/PHARMABEES distribution claims therefore remain unverified. AMFI NAV history is saved only from 2023-04-03 onward and has five unmatched market dates per ETF; it is a fund-valuation cross-check, not a total-return adjustment. On 2026-10-26, all six exact-ISIN Upstox requests succeeded with empty event lists. The [Upstox API documentation](https://upstox.com/developer/api-documentation/get-corporate-actions/) describes event records, but empty responses do not establish provider completeness; in particular, Upstox also returned no NIFTYBEES events despite two known historic distributions. See `outputs/sector_rotation_primary_sources.md` and `outputs/sector_etf_corporate_action_audit.csv`. The current fee schedule applied uniformly is a cost stress, not a dated historical contract-note reconstruction. This comparison cannot validate live fills or future drawdown.

## ETF action audit follow-up — 2026-10-26

- The six exact-ISIN Upstox corporate-action requests succeeded on 2026-10-26 and returned zero events. The response ledger is saved in `work/data/api_probes/sector_etf_corporate_actions_2026-10-26.json`; no token value was saved. The empty feed is not treated as evidence that the events do not exist.
- The opened official AMC/NSE evidence shows the known BANKBEES, JUNIORBEES, and PSUBNKBEES cash events predate the 2020+ composite window. It does not prove those action histories are complete for every provider.
- ATS lists a 1:1 AUTOBEES bonus on 2025-07-14 and ₹10.50 distribution on 2026-06-09, and a ₹6.50 PHARMABEES distribution on 2026-06-11. Direct first-party AMFI scheme/year queries for 2022–2026 returned HTTP 200 with empty data arrays for both schemes; this does not prove complete event coverage. The raw query record and scheme mapping are in `work/data/api_probes/amfi_sector_etf_scheme_dividends_2022_2026.json` and `work/data/api_probes/amfi_nippon_sector_scheme_ids.json`. ATS's PHARMABEES page also pairs ₹6.50/unit with a 1.20% yield although the quoted ETF price is ₹26.65; the arithmetic does not reconcile. Treat these ATS records as unverified leads.
- The saved composite order ledger contains four relevant paths (2020_plus/recent × 95%/100% exposure). It records no AUTOBEES units before either flagged date. It records 7,616–11,552 PHARMABEES units before 2026-06-11. If that unverified ₹6.50 claim were true, the nominal cash sensitivity would be ₹49,504–₹75,088 across these paths; this amount is diagnostic only and is excluded from the reported backtest because the AMFI-sourced record shows zero declarations.
- No backtest result was changed. If a primary AMC, AMFI, or exchange record later confirms a distribution that conflicts with the current evidence, add the entitlement cash and rerun every affected portfolio path. The official AMFI NAV history cross-check is saved from 2023-04-03 onward in `work/data/index_daily/sector_etf_nav_price_tri_panel_2023_2026.csv`; it does not cover 2022, omits five market sessions, and includes three NAV-only quarter ends. The exact-ISIN Upstox requests returned empty lists, not completeness evidence.

## Post-run fee audit

After the fee formula audit, the shared SEBI turnover fee was corrected from ₹1/crore to the published ₹10/crore and the 48-scenario replay was rerun. Headline returns and drawdowns are unchanged at two decimals. The current rates remain a cost stress applied uniformly to historical dates; see `work/research/fee_model_audit.md` for source and limitations.

## Session-date alignment rerun — 2026-10-27

The 48-case composite replay was regenerated after the shared reader normalized Upstox daily bars to local session dates. The current `scenario_summary.csv` reports, at 95% exposure and 10 bps per side, +145.27% / -13.61% for the 2020–2026 NIFTY/Gold control and +117.77% / -11.53% for the fixed 50/25/25 sector mix; from 2023 onward those returns are +68.88% and +44.65%. At 100% exposure and 50 bps, the control returned +124.58% / -14.61% and the sector mix +98.22% / -12.90% over 2020–2026. This confirms the mix's lower drawdown and lower return in this same sample; it is still post-hoc, price-only, and not total-return evidence. The complete corrected rows and per-run ledgers are in `work/backtests/nifty_sector_gold_composites/scenario_summary.csv` and `outputs/backtest_summary.csv`.

## BANKBEES source correction — 2026-10-27

A primary-source recheck found that the BANKBEES row in `outputs/sector_etf_corporate_action_audit.csv` had copied NIFTYBEES's ₹7/₹8 cash amounts. The [official NSE BANKBEES quote page](https://www.nseindia.com/get-quote/equity/BANKBEES/Nippon-India-ETF-Nifty-Bank-BeES) lists ₹11/unit (ex-date 2014-03-10) and ₹13/unit (ex-date 2015-02-18), plus the 1:10 face-value split effective 2019-12-19. The [NIFTYBEES NSE page](https://www.nseindia.com/get-quote/equity/NIFTYBEES/Nippon-India-ETF-Nifty-50-BeES) is the source for the ₹7/₹8 amounts. The action matrix is corrected; all BANKBEES events still predate the 2020+ composite replay, so no strategy metrics changed. The primary-source evidence and remaining limits are recorded in `outputs/sector_rotation_primary_sources.md`.
