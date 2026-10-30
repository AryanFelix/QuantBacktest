# Quarterly static NIFTY/Gold: cap, mix, and cost stress

- **Run date:** 2026-10-30
- **Reference capital:** ₹10,00,000 per replay
- **Universe:** NIFTYBEES and GOLDBEES
- **Exposure caps:** 45%, 50%, 55%, 60%, and 65% aggregate gross exposure; selected mix checks at 55% and 60%
- **Per-side slippage assumptions:** 10, 50, 100, and 200 bps
- **Market history:** 2015-01-02 through 2026-10-23

## Design

The experiment runs 176 separate replays: 80 equal-weight cases across five caps, four slippage assumptions, and four periods; 80 sleeve-ratio cases at a 55% cap across ten NIFTY/Gold mixes and 50/200-bps costs; and 16 cases at a 60% cap for 30/70 and 40/60 mixes at 50/200 bps. The periods are continuous 2015–2026, training 2015–2019, validation 2020–2022, and the already-inspected 2023–2026 pseudo-holdout. Each replay begins with a fresh ₹10 lakh; proceeds are not compounded from one period into another.

At each quarterly event, the portfolio resets total exposure to the selected cap, then assigns the risky sleeve by its stated NIFTY/Gold ratio. Unused capital stays in zero-yield cash. Signals use the prior close and trades execute at the next open; positions use whole units and are liquidated at the end. NIFTYBEES distributions available in the local dataset are credited. Gold distributions are not reconstructed. The target exposure is applied at quarterly sizing events; asset moves can take exposure above or below the target until the next rebalance.

Each run uses the shared product-specific fee model, including GST on SEBI turnover fees, plus the selected slippage on both sides of every trade. The daily OHLC risk envelope marks held positions through the day’s high and then the day’s low. This is a conservative historical envelope, not an executable stop or a guarantee of maximum loss.

## Results at 200 bps per side

| Quarterly target cap | 2015–2026 net return | CAGR | Historical OHLC bound | 10-year bootstrap p05 drawdown | 10-year bootstrap breach estimate |
|---:|---:|---:|---:|---:|---:|
| 45% | +84.77% | 5.44% | -12.92% | -13.58% | 0.04% |
| 50% | +97.51% | 6.05% | -14.20% | -14.96% | 0.16% |
| **55%** | **+111.05%** | **6.66%** | **-15.46%** | **-16.33%** | **0.66%** |
| 60% | +125.42% | 7.26% | -16.69% | -17.69% | 1.86% |
| 65% | +140.68% | 7.87% | -17.89% | -19.03% | 3.48% |

The equal-weight frontier shows the return/risk cost of increasing the quarterly target. The conditional 10-year block bootstrap estimates rise from 0.04% at 45% cap to 3.48% at 65% cap.

### 55% cap sleeve-ratio stress at 200 bps per side

| NIFTY/Gold share of risky sleeve | 2015–2026 net return | Historical OHLC bound | 10-year 126-block p05 | Breach estimate ± MCSE |
|---:|---:|---:|---:|---:|
| 0/100 | +131.50% | -18.36% | -20.83% | 6.98% ± 0.36 pp |
| 10/90 | +127.39% | -16.90% | -18.76% | 3.00% ± 0.24 pp |
| 20/80 | +123.47% | -15.51% | -17.25% | 1.32% ± 0.16 pp |
| 30/70 | +119.45% | -15.21% | -16.38% | 0.92% ± 0.14 pp |
| **40/60** | **+115.29%** | **-15.33%** | **-16.16%** | **0.56% ± 0.11 pp** |
| 50/50 | +111.05% | -15.46% | -16.33% | 0.66% ± 0.11 pp |
| 60/40 | +106.72% | -17.04% | -17.25% | 1.52% ± 0.17 pp |
| 70/30 | +102.27% | -19.01% | -18.91% | 3.16% ± 0.25 pp |
| 80/20 | +97.75% | -20.98% | -21.26% | 8.54% ± 0.40 pp |
| 90/10 | +93.16% | -22.95% | -24.43% | 19.06% ± 0.56 pp |
| 100/0 | +88.72% | -24.92% | -28.31% | 56.74% ± 0.70 pp |

The 40/60 sleeve maps to a 22% NIFTYBEES / 33% GOLDBEES quarterly target, leaving 45% in cash. It ends at about ₹21.53 lakh from ₹10 lakh, with modeled fees of ₹4,090 and slippage of ₹70,165. Its already-inspected 2023–2026 pseudo-holdout returned +40.66% with a -13.32% OHLC bound. The 30/70 mix earned more but its 0.92% point breach estimate plus Monte Carlo uncertainty does not stay below the conservative 1% screen.

### Targeted 60% cap checks at 200 bps per side

| NIFTY/Gold share | Net return | Historical OHLC bound | 10-year 126-block p05 | Breach estimate ± MCSE |
|---:|---:|---:|---:|---:|
| 30/70 | +135.24% | -16.42% | -17.69% | 1.44% ± 0.17 pp |
| 40/60 | +130.39% | -16.56% | -17.46% | 1.46% ± 0.17 pp |
| 50/50 | +125.42% | -16.69% | -17.69% | 1.86% ± 0.19 pp |

The bootstrap summaries use 5,000 stationary-block paths, 1/3/5/10-year horizons, and 21/63/126-session mean blocks. The p05 value is the lower 5th percentile of path close-to-close maximum drawdown; the breach estimate is the share of paths below -20%. The MCSE is Monte Carlo sampling error only. These resample already-seen daily net returns, including modeled costs; they do not rebuild holdings or daily OHLC paths.

For research triage, I use a conservative screen requiring the estimated 10-year breach rate plus 1.96 times its MCSE to stay below 1%. The 55% 40/60 mix passes this Monte Carlo-only hurdle at approximately 0.78%; the 30/70 mix is about 1.19%, and the targeted 60% mixes exceed it. This 1% research threshold is not the user’s 20% drawdown objective and is not a future-loss guarantee. The 55% 40/60 mix is the highest-return candidate in this tested grid under that screen, not a global optimum.

## Interpretation and limits

Treat the 55% cap, 40/60 sleeve as a paper-trading candidate, the 50/50 sleeve as a control, and 60%/30/70 as a higher-return risk challenger. This is a post-hoc comparison: every date and the pseudo-holdout were already examined during the broader search, so no fresh lockbox remains. Block resampling assumes future returns resemble the limited inspected history. A low estimated breach rate does not establish that actual peak-to-trough loss will stay within 20%.

The zero-yield grid remains the direct-cash baseline. A separate opportunity-return sensitivity uses a normalized 91-day RBI T-bill auction-yield series; source validation and the synthetic accrual method are documented below. Under that proxy, the highest-return tested mix passing the 1% bootstrap-only triage screen is a 65% cap with a 30/70 NIFTY/Gold sleeve (19.5%/45.5% target ETF weights and 35% proxy cash): +219.46%, 10.54% CAGR, and -17.57% historical OHLC bound. Its 10-year 126-session close-return bootstrap estimated a 0.60% breach rate (±0.11 pp MCSE), -16.35% p05, and 0.81% point-plus-1.96-MCSE screen. The 2023–2026 already-inspected pseudo-holdout returned +68.81%. The higher-return 65% 20/80 variant (+226.35%) fails that screen at 1.64%; neighboring 60% 10/90 and 70% variants fail as well. This nearby test is not a complete cap/mix search, and its conditional ranking depends on the assumed cash opportunity return.

The T-bill series is a cash-yield proxy, not an executed 91-day bill ladder or broker cash return. Missing GOLDBEES distributions may understate Gold total return. Modeled fees use a generic current schedule; taxes, measured live spreads, market impact, partial fills, and capacity are excluded. The slippage range is assumed, not observed. The account does not use leverage or broker orders.

## RBI T-bill cash-yield opportunity sensitivity

`work/prepare_rbi_91d_tbill_yields.py` creates `outputs/rbi_91d_tbill_yields_2015_2026.csv` from the normalized RBI DBIE-derived source, preserving auction and issue dates and four checks against official RBI Table 213. The 2015–2026 window contains 606 auction rows with five missing yields; the output retains five 2014 seed rows. In the optional simulator input, each holding interval uses the yield known by the previous session’s issue date and accrues simple interest on cash over calendar days using actual/365. The default simulator and all older runs still use zero yield.

The primary frontier has 64 paired-period sensitivity rows and 180 5,000-path bootstrap summaries. Targeted 65% cap challengers add eight paired-period rows and 48 bootstrap summaries; five neighboring cap/mix cases add 20 paired-period rows and 120 summaries. Bootstraps resample the combined daily close-return series, including the proxy accrual; they do not reconstruct T-bill purchases, cash flows, or OHLC paths. Crediting the whole cash balance continuously at the latest known auction yield assumes uninterrupted, cost-free reinvestment. The proxy omits a 91-day maturity ladder, auction execution/access, liquidity, lot size, taxes, reinvestment costs, and premature-sale prices. It raises expected return but offers no guarantee of cash availability or a 20% peak-to-trough limit. See the [source and modeling audit](../work/research/rbi_cash_yield_proxy_2026-10-30.md).

The next step is a frozen, read-only forward-paper ledger with daily feed-completeness checks and observed spread capture. Before any live consideration, implement and separately cost a continuously monitored exposure/drawdown policy; a quarterly target is not a hard 20% loss limit.

## Reproduction

Run `python work/stress_quarterly_static_mix_cost.py` for the 176 zero-yield historical replays and `python work/bootstrap_quarterly_static_mix_cost.py` for the 408 return-block summaries. Reproduce the RBI yield series with `python work/prepare_rbi_91d_tbill_yields.py`, the 64-row cash-yield frontier with `python work/stress_quarterly_static_mix_cash_yield.py`, and its targeted additions with `python work/stress_quarterly_cash_yield_65pct_challengers.py` and `python work/stress_quarterly_cash_yield_neighbors.py`. The cash-yield replays and summaries are linked above; shared cost and OHLC methods are documented in [`passive_mix_composition_cost_method.md`](passive_mix_composition_cost_method.md).
