# Quant research checkpoint: first 24 hours

- **As of:** 2026-10-30
- **Reference capital:** ₹10,00,000
- **Risk objective:** keep peak-to-trough drawdown within 20%; this is an objective for research and sizing, not a guarantee.
- **Repository:** `AryanFelix/QuantBacktest`, branch `main`
- **Status:** broad retrospective screening complete; no strategy qualifies as a proven winner. Continue with prospective paper evidence before considering live use.

## What the research established

The strongest current **paper candidate** in the tested quarterly static grid is a 55% total cap with a 40/60 NIFTY/Gold risky sleeve: rebalance targets are 22% NIFTYBEES, 33% GOLDBEES, and 45% zero-yield cash. At 200 bps per-side assumed slippage, it returned +115.29% (6.84% CAGR) across 2015–2026, with a -15.33% historical daily OHLC envelope; the already-inspected 2023–2026 pseudo-holdout returned +40.66%. A 5,000-path, 10-year close-return bootstrap using 126-session blocks estimated a 0.56% probability of crossing -20% (±0.11 percentage-point Monte Carlo error), with a -16.16% p05 drawdown. The candidate is post-hoc and selected under a researcher-chosen bootstrap screen after inspecting the full history; it is not a proven winner or a hard 20% loss cap. Exposure is reset only quarterly and can drift between rebalances.

| Quarterly target, 200 bps/side | 2015–2026 return / CAGR | Historical OHLC | 10-year 126-block bootstrap: p05 / breach |
|---:|---:|---:|---:|
| 45% | +84.77% / 5.44% | -12.92% | -13.58% / 0.04% |
| 50% | +97.51% / 6.05% | -14.20% | -14.96% / 0.16% |
| 55% cap, equal 50/50 sleeve | +111.05% / 6.66% | -15.46% | -16.33% / 0.66% |
| 60% higher-return challenger | +125.42% / 7.26% | -16.69% | -17.69% / 1.86% |
| 65% | +140.68% / 7.87% | -17.89% | -19.03% / 3.48% |

At the 55% cap, the 40/60 sleeve mix improved return and reduced the estimated breach rate relative to equal sleeves (0.56% ± 0.11 pp versus 0.66% ± 0.11 pp). Its breach estimate plus 1.96 Monte Carlo standard errors is about 0.78%, below the researcher-set 1% triage threshold; 30/70 is higher-return but about 1.19% on that calculation. The targeted 60% mixes exceed the threshold. This threshold only reflects bootstrap sampling error, not model uncertainty. See the [cap/mix/cost method and reproduction files](quarterly_static_mix_cost_method.md).

### Cash-yield sensitivity extension

A normalized 91-day RBI DBIE-derived rate history was checked against four values in official RBI Table 213 (606 auctions in the study interval, five missing yields). The zero-yield 55% cap / 40/60 sleeve remains the direct-cash baseline. If the whole cash sleeve is instead credited at the previous session’s latest known auction yield on actual/365, the highest-return tested mix passing the same bootstrap triage screen is 65% cap / 30/70 NIFTY/Gold: +219.46% (+10.54% CAGR), -17.57% historical OHLC bound, +68.81% in the already-inspected 2023–2026 segment, and 0.60% ± 0.11 pp 10-year 126-block close-drawdown breaches (p05 -16.35%; point plus 1.96 MCSE = 0.81%). A 65% / 20/80 mix returned more (+226.35%) but failed the 1% screen at 1.64%; nearby 60% / 10/90 and 70% mixes also failed. The 65% comparison was targeted, not a full cap/ratio search. This is an optimistic synthetic cash opportunity-return proxy, not Upstox cash interest or an executed bill ladder. It assumes free continuous reinvestment and excludes taxes and cash-instrument execution. Details, source audit, and all outputs are in the [quarterly method](quarterly_static_mix_cost_method.md), [cash-yield source audit](../work/research/rbi_cash_yield_proxy_2026-10-30.md), and [data manifest](data_manifest.csv).

Other passive NIFTY/Gold allocations remain comparative references. The 20% initial 30/70 mix is a lower-risk return/risk reference; 30% initial 40/60 produced more historical return with a tighter but still sub-20% fifth-percentile envelope than the equal-ratio mix. These are initial weights that drift as the assets move.

| ₹10 lakh policy, 200 bps assumed slippage per side | End value | Net return / CAGR | Modeled fees / slippage | Historical daily OHLC bound | 10-year paired-OHLC estimate |
|---|---:|---:|---:|---:|---|
| 20% initial exposure, 30/70 NIFTY/Gold | ₹16.22 lakh | +62.21% / 4.26% | ₹213 / ₹20,938 | -13.96% | 0.92% breach at 126-session blocks; p05 -16.80% |
| 20% initial exposure, 50/50 NIFTY/Gold | ₹15.59 lakh | +55.86% / 3.90% | ₹212 / ₹19,608 | -11.86% | 0.22% breach at 126-session blocks; p05 -15.42% |
| 30% initial exposure, 40/60 NIFTY/Gold | ₹18.86 lakh | +88.56% / 5.62% | ₹248 / ₹30,409 | -15.89% | 3.34% breach at 126-session blocks; p05 -19.13% |
| 30% initial exposure, 50/50 NIFTY/Gold | ₹18.38 lakh | +83.78% / 5.39% | ₹247 / ₹29,407 | -14.66% | 2.68% breach at 126-session blocks; p05 -18.98% |
| 45% initial exposure, 40/60 NIFTY/Gold | ₹23.29 lakh | +132.85% / 7.56% | ₹301 / ₹45,618 | -18.75% | 19.68% breach at 126-session blocks; p05 -22.76% |

Across the 10/50/100/200-bps cost grid, 30% 40/60 continuous return declined from +91.44% to +88.56%; its already-inspected 2023+ pseudo-holdout return declined from +29.63% to +27.91%. The 30/70 mix returned more at each cost but fails the 200-bps 126-session p05 screen. The 64-row ledger covers four sleeve ratios and four chronological periods; see the [method and results](passive_mix_composition_cost_method.md) and [cost ledger](passive_mix_30pct_composition_cost.csv).

The matched 50/200-bps bootstrap confirms the 30% risk ordering: at 126-session blocks, 40/60 had 3.32%/3.34% estimated breaches and p05 -19.09%/-19.13%; 50/50 had slightly lower 2.60%/2.68% estimates and p05 -18.93%/-18.98%. The same block paths were used at both costs. The 30/70 and 70/30 mixes crossed the p05 risk screen at both costs. See the [paired-cost bootstrap ledger](passive_mix_30pct_composition_cost_bootstrap.csv).

At 30% initial exposure, 40/60 returned more historically than 50/50 (+88.56% versus +83.78%). Their 126-session breach estimates were 3.34% versus 2.68%, with p05 envelopes -19.13% versus -18.98%; the 40/60 mix had lower estimated breach at 63 sessions (2.70% versus 3.06%). The 30/70 mix returned +93.33% but its 126-session p05 was -20.27%, crossing the coarse tail screen. The 30% initial paths can drift materially as asset prices move; the equal-sleeve strategy reached about 67% gross exposure. The 20% 30/70 and 50/50 paths reached about 56.72% and 54.16%. A maintained exposure ceiling requires a separately simulated and costed rebalancing policy.

The 45% initial 40/60 variant is a high-return counterexample, not a risk-screen pass. Its historically observed OHLC bound is -18.75%, but the stateful bootstrap estimated 20.00% and 19.68% breach rates at 63/126-session mean blocks, with p05 envelopes of -22.54% and -22.76%. The 30/70, 50/50, and 70/30 45% mixes also fail the sampled tail screen. The expanded ledger includes 80 historical replay rows and 42 stateful bootstrap summaries.

An 8%/4% drawdown trigger that cut the 20% 30/70 policy to 10% returned +66.12% with a -11.46% historical OHLC bound. It had zero breaches among 5,000 paths at each tested bootstrap block length, but median 126-block CAGR was lower than fixed exposure (3.54% versus 4.06%). It triggered once, only in the already-inspected post-2019 period, and never recovered in the historical replay. This post-hoc rule is not independent validation.

## Other strategy families screened

- **ETF trend/swing:** monthly NIFTYBEES Donchian 55/20 with a GOLDBEES 200-day filter returned +63.69% on the already-inspected 2023+ segment at 50 bps with a -16.28% OHLC bound; its 2020+ bound was -24.41%. Keep as a paper challenger, not a winner.
- **Cross-asset ETF momentum:** the strength-weighted version returned +22.51% on the inspected pseudo-holdout at 50 bps, but its 63-session conditional bootstrap estimated a 41.98% 10-year 20% drawdown-breach rate. Higher assumed costs reduced pseudo-holdout returns sharply.
- **Sectors:** rotation results varied by construction and period; stronger full-history results did not persist in the later pseudo-holdout. ETF distribution history and survivorship limit confidence.
- **Stocks:** price-only momentum blends looked competitive, but point-in-time membership and corporate-action/total-return coverage remain incomplete. Do not rank these against cleaner ETF studies as if data quality were equal.
- **Intraday:** NIFTY 30-minute opening-range breakouts and opening-gap fades lost after modeled costs across the tested screens.
- **Options/futures:** index-options evidence is blocked by missing expired-contract coverage in sampled historical expiries. The small monthly option samples were negative after costs. Futures screens did not support a robust, margin-aware candidate.

## Data, cost, and validation limits

- Local daily market history used here ends on 2026-10-23. Upstox Analytics authentication was read from the configured Windows registry fallback; the API key was not written to research files. A restart was not required for the successful calls already observed.
- The latest paper cache has two common post-freeze sessions through 2026-10-29. Exact-date Oct 30 requests at 18:54 and 19:54 IST returned no daily candles for NIFTYBEES and GOLDBEES. That does not prove a holiday or a complete feed. The paper replay placed no broker orders.
- Fee tables include modeled delivery levies and the recent GST correction, but use a generic current schedule rather than a verified personal tariff. Slippage grids (including 200 bps per side) are assumptions, not observed spreads or market impact. Income tax and realistic capacity/partial-fill effects are not modeled.
- Known NIFTYBEES distributions are credited in selected replays; GOLDBEES total-return/distribution reconciliation is incomplete. The primary cap/mix grid still uses zero-yield cash; the separately reported RBI T-bill opportunity proxy is not an investable cash-return series.
- LIQUIDBEES’ official AMFI NAVs stay near ₹1,000 because they record daily IDCW payouts, not a reinvested total-return path. The observed issuer dividend feed is stale and its reconstruction misses reported performance at the 3-year horizon; the Nifty 1D Rate benchmark history has a material 2020 retrieval gap. No LIQUIDBEES return is credited. See the [cash-proxy audit](liquidbees_cash_proxy_audit.md) and [NAV source review](../work/research/liquidbees_nav_source_review.md).
- The paired-OHLC bootstrap reruns exposure sizing and the OHLC envelope over 5,000 conditional 10-year paths with mean block lengths 21, 63, and 126 sessions. Resampling already-seen history cannot create an unseen regime; zero observed breaches does not mean zero risk.
- All historical dates and pseudo-holdouts have been examined during the search. None is a fresh lockbox. The strongest numbers are subject to selection bias, data gaps, and regime dependence; a historical or bootstrap -20% screen cannot cap future losses.

## Recommended next research phase

1. Continue the frozen revision-9 forward-paper ledger. If the 55% quarterly target cap is added, freeze it as a new, forward-only paper path after the amendment; do not count the two earlier Oct 28–29 sessions as prospective evidence. Keep the 20% initial 30/70 and 30% initial 40/60 mixes as passive references, with 20% 50/50 and 30% 50/50 as lower-tail comparisons.
2. Verify each paper session's candle completeness, and record observed bid/ask, fills, and actual personal fees when available. Reconcile total-return series and distributions before comparing stock and ETF candidates.
3. Test a maintained gross-exposure cap and operational drawdown stop with next-open execution and fees. Track cash yield, spreads, sizing drift, missing sessions, and monitor failures.
4. Revisit derivatives only after a continuous, point-in-time expired-contract source is available; revisit individual stocks after point-in-time membership and corporate actions are audited.
5. Promote nothing to live trading on this checkpoint alone. A live decision needs fresh out-of-sample paper evidence and explicit execution/risk controls.

## Reproduction

The latest composition extensions are documented in [the method note](passive_mix_composition_cost_method.md). Reproduce the 10/50/100/200-bps sweep with `python work/sensitivity_passive_mix_30pct_composition_cost.py`, the matched 50/200-bps paired bootstrap with `python work/bootstrap_passive_mix_30pct_composition_cost.py`, the 200-bps deterministic ledger with `python work/stress_passive_composition_lower_exposure_200bps.py`, and the broader paired-OHLC bootstrap with `python work/bootstrap_passive_composition_lower_exposure_200bps.py`. The full research catalog and earlier methods are indexed in the [quant research report](quant_research_report.md) and [data manifest](data_manifest.csv).
