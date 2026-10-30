# Passive NIFTY/Gold composition execution-cost stress

- **Run date:** 2026-10-27
- **History:** 2015-01-02 through 2026-10-23
- **Capital:** ₹10,00,000 per replay
- **Initial exposure:** 45%, with the balance in zero-yield cash
- **Status:** retrospective cost sensitivity; no allocation is independently validated.

## Design

All eleven NIFTY/Gold risky-sleeve compositions (NIFTY share 0–100% in 10-point steps) were replayed at 10, 50, 100, and 200 bps adverse slippage per side. Each of the 88 period/cost/composition cases has an independent integer-unit simulation, current modeled delivery fees, next-open initial purchase, and terminal liquidation. NIFTYBEES cash distributions in the existing event ledger are credited; GOLDBEES cash distributions remain unverified. Daily OHLC risk uses the same high-before-low envelope as the base composition study.

The fee model includes the standard Upstox ₹20 per executed delivery order and ₹20 DP charge per scrip on a delivery sale, plus modeled NSE transaction, STT, stamp duty, SEBI, IPFT, and GST charges. Upstox publishes its brokerage and DP schedule on its [brokerage charges page](https://upstox.com/brokerage-charges/); statutory rates and effective-date tables are on [NSE's levy schedule](https://www.nseindia.com/static/invest/first-time-investor-sebi-turnover-fees-stt-other-levies). The project-specific rates and fund classifications are audited in the [fee-model review](../work/research/fee_model_audit.md). User-specific tariff plans and tax outside exchange charges are not modeled.

At each slippage level, the training selector chooses the highest-return composition from 2015-01-02 through 2019-12-31 that passes a -20% conservative OHLC bound. The chosen share is then observed on a continuously compounded ₹10 lakh path through 2026-10-23. That later history has been examined in prior work and is not a lockbox. The best full-history return passing the same bound is shown only as a descriptive frontier, not as a selection rule.

The 50-bps rows reconcile against the base 22-row composition study within ₹0.03 for ending value, return, close drawdown, OHLC bound, fees, slippage, and order count. `benchmark_nifty_gold_2020._run` accepts a slippage override; all existing callers retain its 50-bps default.

## Results

At every tested cost, the training selector picked NIFTY-only within the 45% risky sleeve. Its continuous path failed the historical risk screen at every cost. The highest-return full-history ratio that passed the -20% OHLC screen was 30% NIFTY / 70% Gold in every row, but its bound approached the threshold as costs rose.

| Slippage per side | Training pick | Training return / OHLC | Continuous training-pick return / OHLC | Highest-return full-history passing mix | Return / OHLC |
|---:|---:|---:|---:|---:|---:|
| 10 bps | 100% NIFTY | +24.70% / -14.48% | +93.39% / -25.16% | 30/70 | +144.49% / -19.92% |
| 50 bps | 100% NIFTY | +24.24% / -14.50% | +92.66% / -25.20% | 30/70 | +143.55% / -19.93% |
| 100 bps | 100% NIFTY | +23.67% / -14.53% | +91.74% / -25.24% | 30/70 | +142.37% / -19.94% |
| 200 bps | 100% NIFTY | +22.53% / -14.59% | +89.91% / -25.33% | 30/70 | +140.01% / -19.98% |

| NIFTY / Gold within risky sleeve | 10 bps return / OHLC | 50 bps return / OHLC | 100 bps return / OHLC | 200 bps return / OHLC |
|---:|---:|---:|---:|---:|
| 30 / 70 | +144.49% / -19.92% | +143.55% / -19.93% | +142.37% / -19.94% | +140.01% / -19.98% |
| 40 / 60 | +137.19% / -18.69% | +136.27% / -18.70% | +135.13% / -18.72% | +132.85% / -18.75% |
| 50 / 50 | +129.88% / -17.35% | +129.00% / -17.37% | +127.90% / -17.38% | +125.69% / -17.41% |

For the 30/70 path, modeled fees are approximately ₹302 at each cost level; modeled slippage rises from ₹2,356 at 10 bps to ₹47,120 at 200 bps. The 200-bps full-history bound has only about 0.02 percentage points of room, which is not a meaningful safety margin. The 40/60 mix leaves 1.25 points of OHLC room even at 200 bps, with lower returns. The 50/50 mix has more historical room and lower return.

## Limits and reproduction

These are assumed slippage levels, not measured bid/ask spreads. Costs apply only to the initial purchase and terminal sale because the strategy holds units without rebalancing; actual spread, market impact, partial fills, dividend reinvestment, cash interest, capital-gains tax, and future drawdowns can change results. The cost grid does not make the full-history frontier independent. The historical OHLC envelope is a conservative bound, not a future loss guarantee.

Reproduce with `python work/sensitivity_passive_mix_composition_cost.py`. It writes the [88-row cost ledger](passive_mix_composition_cost_sensitivity.csv), per-cost training and descriptive full-history choices ([selection JSON](passive_mix_composition_cost_selection.json)), and local equity/order ledgers under `work/backtests/passive_mix_composition_cost/`. The base [composition study](passive_mix_composition_method.md) describes the 50-bps construction and known event coverage.

## 30% initial-exposure cost extension

The four 30% initial NIFTY/Gold compositions (30/70, 40/60, 50/50, and 70/30) were replayed at 10/50/100/200 bps per-side slippage across training, validation, the already-inspected 2023+ pseudo-holdout, and continuous 2015–2026 history. This adds 64 exact-fee replays; 200-bps rows reconcile against the expanded 80-row ledger within ₹0.03. `work/sensitivity_passive_mix_30pct_composition_cost.py` adds these rows to the consolidated backtest ledger and data manifest.

| Slippage per side | 30/70 continuous return / OHLC | 40/60 continuous return / OHLC | 50/50 continuous return / OHLC | 40/60 inspected 2023+ return / OHLC |
|---:|---:|---:|---:|---:|
| 10 bps | +96.31% / -17.00% | +91.44% / -15.85% | +86.58% / -14.62% | +29.63% / -12.35% |
| 50 bps | +95.68% / -17.01% | +90.84% / -15.86% | +85.99% / -14.63% | +29.26% / -12.36% |
| 100 bps | +94.90% / -17.02% | +90.08% / -15.87% | +85.25% / -14.64% | +28.81% / -12.37% |
| 200 bps | +93.33% / -17.04% | +88.56% / -15.89% | +83.78% / -14.66% | +27.91% / -12.40% |

The return ranking is unchanged across the cost grid, but the 30/70 mix's 126-session bootstrap p05 envelope is -20.27% at 200 bps and crosses the coarse risk screen. The 40/60 30% mix remains inside that p05 screen at -19.13% (3.34% estimated breach), while the 50/50 mix has a slightly lower 126-session breach estimate of 2.68% and p05 of -18.98%. These probability estimates come from the 200-bps conditional bootstrap; the cost sweep does not independently validate the strategy. The 2023+ segment has already been inspected and is not a fresh holdout.

## Lower initial exposure extension at 200 bps

The extension replays 10%, 15%, 20%, 25%, and 30% initial exposure at 30/70, 50/50, and 70/30 NIFTY/Gold weights; it adds 30% 40/60 and, at 45%, 30/70, 40/60, 50/50, and 70/30. Training, validation, the already-inspected pseudo-holdout, and continuous history produce 80 rows via `work/stress_passive_composition_lower_exposure_200bps.py`. A separate 5,000-path stateful paired-OHLC bootstrap covers each exposure's 30/70 case, the 20% 50/50 and 70/30 alternatives, all four 30% mixes, and all four 45% mixes across 21/63/126-session mean blocks (42 summaries). Deterministic historical replays are asserted against the canonical simulator.

| Initial exposure and sleeve mix | Continuous 2015–2026 return / OHLC | 63-block 10-year breach estimate | Fifth-percentile OHLC envelope |
|---|---:|---:|---:|
| 10%, 30/70 NIFTY/Gold | +31.09% / -9.05% | 0 of 5,000 paths | -10.85% |
| 15%, 30/70 NIFTY/Gold | +46.64% / -11.82% | 0.14% | -13.96% |
| 20%, 30/70 NIFTY/Gold | +62.21% / -13.96% | 0.56% | -16.35% |
| 20%, 50/50 NIFTY/Gold | +55.86% / -11.86% | 0.28% | -15.40% |
| 20%, 70/30 NIFTY/Gold | +49.48% / -9.92% | 1.92% | -17.60% |
| 25%, 30/70 NIFTY/Gold | +77.77% / -15.66% | 1.94% | -18.22% |
| 30%, 30/70 NIFTY/Gold | +93.33% / -17.04% | 4.34% | -19.78% |
| 30%, 40/60 NIFTY/Gold | +88.56% / -15.89% | 2.70% | -18.94% |
| 30%, 50/50 NIFTY/Gold | +83.78% / -14.66% | 3.06% | -19.15% |
| 45%, 30/70 NIFTY/Gold comparison anchor | +140.01% / -19.98% | 23.72% | -23.32% |
| 45%, 40/60 NIFTY/Gold | +132.85% / -18.75% | 20.00% | -22.54% |
| 45%, 50/50 NIFTY/Gold | +125.69% / -17.41% | 21.28% | -23.24% |
| 45%, 70/30 NIFTY/Gold | +111.37% / -19.54% | 40.30% | -27.64% |

At 126-session blocks, the 20% 30/70 case had a -16.80% fifth-percentile envelope and 0.92% estimated breach probability; the 20% 50/50 alternative had -15.42% and 0.22%, trading some return for more modeled cushion. The 25% 30/70 case had -18.69% / 2.78%. At 30%, the 40/60 mix returned more than 50/50 (+88.56% versus +83.78%); in the same paired bootstrap, its 126-session breach estimate/p05 were 3.34% / -19.13%, compared with 2.68% / -18.98% for 50/50. The 30% 30/70 case's fifth percentile was -20.27% with a 5.60% breach estimate, so it fails that coarse tail screen. Zero breaches for 10% at 63/126 sessions means zero events among 5,000 paths, not zero true risk; the rule-of-three 95% upper bound is about 0.06%. The 45% 30/70 historical OHLC bound leaves only 0.02 percentage points of headroom; its 63-session bootstrap breach estimate is 23.72%, with a -23.32% fifth-percentile envelope. The 45% 40/60 mix raises the historical cushion to 1.25 points, but its 63/126-session breach estimates are 20.00%/19.68% and p05 envelopes are -22.54%/-22.76%. The 50/50 and 70/30 alternatives also have 63-session breach estimates above 20%. These high-return 45% mixes therefore fail the coarse 20% risk screen under this conditional resampling. Initial holdings drift rather than maintain exposure caps: the 20% 30/70 path reached 56.72% peak gross exposure, and 20% 50/50 reached 54.16%. This composition grid was formed after examining the full history; resampling cannot promise a future loss ceiling. See the [replay ledger](passive_mix_composition_lower_exposure_200bps.csv), [bootstrap summary](passive_mix_composition_lower_exposure_200bps_bootstrap.csv), and both reproduction scripts.
