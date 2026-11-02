# Archived checkpoint

Superseded by the registered AGEL claim-mark and cash-account protocol in `outputs/nifty200_agel_valuation_protocol_2026-11-02.md`. This file preserves the prior 2018-04-04 stop as a dated finding.

---

# NIFTY 200 sequential account checkpoint — 2026-11-02

## Four frozen configurations

Each row is an actual ₹10 lakh cash-account prefix using the frozen signal and rebalance schedule, integer shares, next-session raw opens, 50 bp slippage per side, the existing fee schedule, and zero cash yield. NAV and drawdown end at the last supported close before the first held-position claim could no longer be valued.

| Configuration | Valid through | Actual orders (buy / sell) | NAV at last valid close | Max drawdown | First material blocker | State |
|---|---:|---:|---:|---:|---|---|
| A-M | 2018-04-04 | 66 (43 / 23) | ₹901,978.73 | −11.48% | ADANIENT demerger claim, 2018-04-05 | Stopped prefix |
| B-M | 2018-04-04 | 62 (39 / 23) | ₹921,478.80 | −9.76% | ADANIENT demerger claim, 2018-04-05 | Stopped prefix |
| A-Q | 2018-04-04 | 20 (20 / 0) | ₹990,565.07 | −2.28% | ADANIENT demerger claim, 2018-04-05 | Stopped prefix |
| B-Q | 2018-04-04 | 20 (20 / 0) | ₹996,957.85 | −1.19% | ADANIENT demerger claim, 2018-04-05 | Stopped prefix |

**No full-period CAGR is reported or ranked.** Monthly accounts executed the 2018-02-01, 2018-03-01, and 2018-04-02 orders; quarterly accounts executed their first orders on 2018-04-02. The 20% CAGR objective remains unproven.

## First targets and fixed-rule eligibility

The 2018-01-31 A-M target is **certified under the registered source-correction protocol**. Of the eight named first-signal cases, HUDCO and DMART are `RULE_INELIGIBLE` because they were not listed for the complete lagged window; the six remaining cases were resolved from the registered rights, dividend, and IDFC evidence. HUDCO listed 2017-05-19 and DMART 2017-03-21, both after the 2017-01-25 lookback start. The wider clarification also records AUBANK's 2017-07-10 listing date. See the [listing evidence ledger](nifty200_listing_evidence_2026-11-02.csv) and [operational eligibility rule](nifty200_operational_eligibility_clarification_2026-11-02.md).

The positive twentieth score is **0.75471643**. All three rights cases remain below that boundary even under the conservative free-right sensitivity: KARURVYSYA 0.71284584, INDHOTEL 0.30347423, and CANBK 0.41220446. Their source-corrected scores use full subscription prices, not premiums alone. COLPAL's ₹4 dividend and ENGINERSIN's ₹0.50 dividend are incorporated. The IDFCBANK “Interest Payment” is retained as an evidence-supported debt-event inference: the vendor row points to equity ISIN INE092T01019, while issuer/debt records identify NCD ISIN INE092T08352. The exact original vendor notice was not found, so this classification remains an inference.

The same predeclared correction model certifies the monthly February and March targets and both quarterly March targets. B scores were recalculated from corrected daily prices so the volatility denominator changes with rights corrections. The B configurations retain an unknown RELCAPITAL score where RHFL prelisting daily marks are absent; the supported return numerator is nonpositive, so the candidate cannot rank positive under the fixed positive-score rule. For A-Q, Tata Steel's free-right sensitivity crosses the 0.57142754 boundary, but the source-confirmed full terms—4:25 at ₹510 and 2:25 at ₹615—produce corrected score 0.4825976, below the boundary. This is a terms-based correction, not a return-selected adjustment.

The [registered correction protocol](nifty200_first_signal_correction_protocol_2026-11-02.md) contains the event terms and primary citations. The machine-readable [score certificates and account evidence](nifty200_sequential_prefix_evidence_2026-11-02.json) preserve each boundary, selected set, corrected scores, uncertainty treatment, and exact blocker.

## Account ledger and execution checks

| Configuration | Turnover | Fees | Slippage | Cash distributions credited | NAV reconciliation residual |
|---|---:|---:|---:|---:|---:|
| A-M | ₹1,774,590.52 | ₹4,149.14 | ₹8,848.28 | ₹905.60 | ₹0.00 |
| B-M | ₹2,036,229.20 | ₹4,344.74 | ₹10,156.86 | ₹411.10 | ₹0.00 |
| A-Q | ₹997,549.99 | ₹1,656.50 | ₹4,962.94 | ₹0.00 | ₹0.00 |
| B-Q | ₹994,608.20 | ₹1,653.00 | ₹4,948.30 | ₹0.00 | ₹0.00 |

The fee totals include brokerage, STT, exchange charges, stamp duty, SEBI, DP charges where applicable, and GST. The monthly cash distributions are credited to the actual prior-close share quantity on each source-feed ex-date; each event and quantity is listed in the JSON certificate. Rights and demerger entitlements are not treated as free cash or free subscriptions.

I independently compared every actual order's reference open to the cached source raw open and recomputed the fill as raw open × 1.005 for buys or × 0.995 for sells; maximum observed discrepancy was below ₹0.00000000001. I also recomputed the integer-share target from prior-close NAV and close for every executed rebalance. All matched except cash affordability after costs left A-M one share and A-Q six shares below the target on 2018-04-02. Orders remained unlevered. At the monthly rebalance, A-M resized 16 of 16 retained names on 2018-03-01 and 16 of 17 on 2018-04-02; B-M resized 11 of 15 at each rebalance. These are actual order rows, not membership-only counts.

## Exact first blocker

The source action identifies ADANIENT's 2018-04-05 scheme event. The BSE information memorandum and NSE issuer filing specify **761 AGEL shares for every 1,000 ADANIENT shares**; AGEL's first listed session was 2018-06-18. The account held 287 ADANIENT shares in A-M, 294 in B-M, and 319 in each quarterly account at the 2018-04-04 close. The corresponding gross formula claims are 218.407, 223.734, and 242.759 AGEL shares before any scheme-specific fractional treatment.

No contemporaneous source-backed fair mark or documented earlier cash settlement was established for those unlisted claims from 2018-04-05 through 2018-06-17. The engine therefore stops before the ex-date, preserves all prior fills, and does not use the later listing quote to backfill the gap. The decisive resolution is a contemporaneous daily fair-value series throughout the interval, or official evidence of earlier cash settlement, including the scheme's fractional-share treatment. Primary evidence: [BSE information memorandum](https://www.bseindia.com/downloads/ipo/20186131279Adani%20Green%20Energy%20Limited%20-%20Information%20Memorandum.pdf) and [NSE issuer outcome and listing notice](https://nsearchives.nseindia.com/corporate/listcontract3_07022019173803_ADANIGREEN_outcome_315.pdf).

## Verification scope and limits

Passed local checks: `work/upstox_quant.py self-check` (calendar CAGR, missing terminal marks, non-liquidated prefixes, summed same-ex-date dividends, and retained-name resizing); `work/audit_strategy_dependencies.py --self-check` (prelisting ineligibility versus missing data, action normalization, and identity continuity); and the sequential runner's asserts (selection bounds, TERP correction, B volatility sensitivity, and the exact ADANIENT stop). The actual four account prefixes were rerun after the blocker and position trace changes.

The account state is only certified through 2018-04-04. No full evaluation, matched-period TRI comparison, 10/100/200 bp sensitivity, capacity study, or full-period independent reproduction was completed. The IDFC classification remains inferential; RHFL's missing prelisting marks remain unresolved for the affected B score. Raw bars, action rows, and order/equity detail stay local; this report and the aggregate certificate contain the curated review evidence.
