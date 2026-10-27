# Sector ETF secondary-claim cash-flow sensitivity

**Run date:** 2026-10-27
**Starting capital:** ₹10 lakh
**Slippage:** 50 bps per side
**Scope:** 144 conditional simulations with order-level OHLC risk replays

## Questions and source status

The source memo records two secondary-source event claims: AUTOBEES ₹10.50 per unit ex 2026-06-09 and PHARMABEES ₹6.50 per unit ex 2026-06-11. Neither amount/date pair was verified by a primary issuer, exchange, or AMFI notice. See the [source review](../work/research/sector_distribution_primary_source_update_2026-10-27.md) for the checks and retrieval gaps. The results below are hypothetical accounting sensitivities, not confirmed distributions or accepted base-case cash flows.

The run tests each claim separately and both together for price-signal and official-TRI-signal top-one, top-two, and top-three sector momentum. The four gross exposure caps are 50%, 75%, 95%, and 100%. It covers the 2025-01-01–2026-10-23 holdout slice and the 2022-01-03–2026-10-23 continuous path at 50 bps. Each path starts with ₹10 lakh. Signals are unchanged; ETF prices set executions, and cash is credited to the shares held at the prior close on each claimed ex-date before that day's next-open rebalance. Cash can fund subsequent orders. Current modeled ETF charges and adverse slippage apply to those orders. No tax or cash interest is modeled.

## Results

No tested momentum path held AUTOBEES at its claimed ex-date, so the AUTOBEES-only case credited ₹0 and matched the price-only baseline. Every improvement below comes from assuming the PHARMABEES claim is true. The claim-only sensitivity credited ₹1,20,659.50–₹2,35,040 in 2025+ paths and ₹1,62,701.50–₹4,58,172 in continuous paths, depending on the prior-close PHARMABEES units held. These are large potential return differences and show why the missing event record cannot be treated as a minor data caveat.

| Rule and cap | Window | Price-only return / OHLC bound | With PHARMABEES claim / OHLC bound | Cash credited |
|---|---|---:|---:|---:|
| Official-TRI top-two, 75% | 2025+ | -15.49% / -19.23% | +0.38% / -17.66% | ₹1,74,245.50 |
| Official-TRI top-two, 75% | Continuous | +36.87% / -22.86% | +62.56% / -22.86% | ₹2,82,139.00 |
| Official-TRI top-three, 50% | 2025+ | -10.16% / -13.57% | +1.23% / -11.55% | ₹1,22,317.00 |
| Official-TRI top-three, 50% | Continuous | +29.80% / -13.54% | +46.25% / -13.26% | ₹1,76,683.00 |
| Official-TRI top-three, 75% | 2025+ | -15.37% / -19.93% | +0.53% / -16.98% | ₹1,77,112.00 |
| Official-TRI top-three, 75% | Continuous | +45.96% / -19.90% | +73.36% / -19.38% | ₹3,05,363.50 |

The official-TRI top-two/75% rule still breaches the continuous 20% OHLC screen even when the claim is credited: its worst bound remains -22.86%. The top-three/75% case remains close to the risk limit, with only 0.62 percentage points of bound headroom after crediting the claim. Across the grid, the number of continuous and holdout paths that pass the 20% OHLC screen did not change when the claim was included. The claim can materially change returns but did not turn the selected rule into a risk-qualified candidate.

## Execution, checks, and limits

The runner asserts that its no-distribution baseline reproduces the published 50-bps return, close drawdown, fees, and slippage for all 48 source/strategy/cap/window combinations. It uses the shared simulator's prior-close share eligibility and cash-credit logic, and audits all 144 conditional order ledgers against daily OHLC. Maximum close-NAV reconciliation error was less than ₹0.000001. The 144-row output records eligible units, cash per event, base and conditional returns, close MDD, OHLC bounds, risk classification, fees, and slippage.

The amounts and dates are unverified, the current retrieved AMFI/Upstox event responses were empty and do not establish completeness, and no primary event notice was found in the review. The included scenarios assume the secondary claims are accurate and payable to the prior-close units; they do not prove either fact. Actual ETF total returns also require a complete event ledger and correct tax treatment. Price histories, surviving-fund selection, and previously inspected periods remain material limits. Do not promote a cash-sensitive path from this scenario to expected performance until an official event record is obtained.

## Reproduction

- Runner: `work/sensitivity_sector_distribution_cashflow.py`.
- Result table: `outputs/sector_distribution_cashflow_sensitivity.csv`.
- Per-run equity curves, orders, summaries, and OHLC audit details: ignored local paths under `work/backtests/sector_distribution_cashflow_sensitivity/`.
- Baseline comparisons: `outputs/sector_rotation_sensitivity.csv`, `outputs/sector_rotation_ohlc_audit.csv`, `outputs/sector_tri_signal_momentum_sensitivity.csv`, and `outputs/sector_tri_signal_momentum_ohlc_audit.csv`.
