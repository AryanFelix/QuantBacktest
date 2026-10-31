# Selected stock-momentum rule attribution — 2026-10-31

## Result

Rule: monthly NIFTY 50 12–1 total-return momentum, equal-weight top 15, full exposure, two-rank retention buffer. It was chosen from a 36-rule grid on 2021–2023 training CAGR. The selected rule is not a winner: its net calendar CAGR falls from 23.88% in training to 11.87% in 2024 and -4.94% in 2025–October 2026. The continuous 2021–October 2026 account returns 11.90% net, below the 20% objective.

## Gross, net, benchmark and costs

“Gross same shares” replays the selected rule’s actual integer-share order quantities at raw prices, with dividends but with modeled fees and slippage removed. This isolates cost drag while holding the executed share path fixed; it is not a separate no-cost strategy optimization. Net values use 50 bps assumed slippage per side and current modeled fees. Benchmark CAGRs use NIFTY 50 TRI; validation and 2025+ include the prior continuous account mark at the window boundary.

| Window | Gross same-share CAGR | Net CAGR | Matched NIFTY 50 TRI | Net excess | Beta to TRI | Fees | Assumed slippage | Traded notional | Orders |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Training 2021–2023 | 27.16% | 23.88% | 16.95% | +6.93 pp | 0.97 | ₹43,238 | ₹103,703 | ₹2.07 crore | 574 |
| Validation 2024 | 13.53% | 11.87% | 10.01% | +1.86 pp | 1.25 | ₹14,767 | ₹36,447 | ₹72.89 lakh | 187 |
| 2025–2026-10-23 | -1.14% | -4.94% | -1.27% | -3.67 pp | 1.09 | ₹35,439 | ₹1,00,146 | ₹2.00 crore | 376 |
| Continuous 2021–2026-10-23 | 15.11% | 11.90% | 9.66% | +2.24 pp | 1.05 | ₹93,443 | ₹2,40,296 | ₹4.81 crore | 1,137 |

For the full account, ₹10 lakh grew to about ₹22.37 lakh on the same-share gross replay and ₹19.03 lakh net. The ₹3.34 lakh difference equals the saved ledger’s ₹93,443 modeled fees plus ₹2,40,296 assumed slippage. The run traded about 48.05 times starting capital in total, or 8.40 times per year. In 2025 onward, gross same-share return was close to the matched index; modeled trading costs turned that near-match into net underperformance. At 10 bps/side, the full-period net CAGR rises to 14.15%, but the 2025+ result is still -2.79% versus -1.27% for NIFTY 50 TRI.

The full-strategy zero-slippage rerun returns **14.72% CAGR** and ends at **₹21.94 lakh**. It retains current modeled fees and reruns integer quantities and affordability at raw-price fills, so this is a zero-assumed-slippage strategy result, not the same-share gross attribution above. The existing frozen signal remains below the 20% objective at every tested cost level:

| Assumed slippage per side | Full-strategy net CAGR | 2025–2026-10 net CAGR | Modeled fees, full period | Modeled slippage, full period |
|---:|---:|---:|---:|---:|
| 0 bps | 14.72% | -2.32% | ₹98,234 | ₹0 |
| 10 bps | 14.15% | -2.79% | ₹96,657 | ₹51,107 |
| 50 bps | 11.90% | -4.94% | ₹93,443 | ₹2,40,296 |

The matched official NIFTY 50 TRI CAGR is 9.66%. An investable NIFTYBEES buy-and-hold comparator, simulated with next-session entry, integer units, terminal liquidation, current modeled charges, and the same 50 bps per-side slippage, returned 9.69% calendar CAGR and ended at ₹16,97,241. Its close drawdown was -16.11%, fees ₹339, and modeled slippage is recorded in [`stock_momentum_passive_comparison_2026-10-31.csv`](stock_momentum_passive_comparison_2026-10-31.csv). This ETF result is price-only; it is not a substitute for total return. The independent ETF order replay reconciled to NAV with zero rupee error.

With the current fee model and this fixed signal, a root search implies about **90.2 bps per side** would erase the full-period CAGR edge over NIFTY 50 TRI. This is a model-implied break-even, not an observed spread or capacity estimate. No timestamped spread/order-size evidence was available to calibrate the 50-bps base assumption.

## Exposure diagnosis

- **Market and style:** the rule holds only positive 12–1 momentum names from a reconstructed NIFTY 50 universe, at a 100% exposure cap. Its daily net beta to NIFTY 50 TRI is about 1.05 over the full period, 1.25 in 2024 and 1.09 in 2025+. The momentum tilt does not have a comparable point-in-time value, quality or size factor series in this dataset, so a multi-factor style regression is not available.
- **Sector:** the average portfolio exposure is concentrated in Financial Services (16.0% of NAV), Automobile and Auto Components (12.7%), and Metals & Mining (10.2%). About 8.7% of average NAV is unclassified. These labels come from the 2026-09-30 constituent file applied retrospectively; they are descriptive only, not historical sector attribution. The full sector table is in [`stock_momentum_sector_exposure_2026-10-31.csv`](stock_momentum_sector_exposure_2026-10-31.csv).
- **Universe and corporate actions:** 70 saved price histories support a sampled point-in-time NIFTY 50 universe, not NIFTY 200/500. Four known action overlaps occur in the selected run, including BPCL bonus, BAJFINANCE bonus/split and HDFCBANK bonus. Thirteen names with unresolved rights/merger/demerger or successor paths are excluded only in a separate restricted diagnostic; the chosen all-saved rule includes its 70-symbol histories. Corporate-action completeness is not established.
- **Passive comparator:** NIFTY 50 TRI is the matched total-return index comparator. NIFTYBEES buy-and-hold at 100% unlevered exposure returned 9.69% after the same 50 bps/side model, close to TRI’s 9.66%; the ETF series is price-only and has incomplete distribution evidence. The rule’s 2.24-point full-period excess over TRI is not robust across folds and does not remove the universe and event-data limitations.

## Reconciliation and reproduction

`work/attribute_stock_momentum_leader.py` rebuilds only the selected rule, the NIFTYBEES passive comparison, and the existing 0/10/50-bps stock cost sensitivities. It asserts every displayed net-excess value equals net CAGR minus matched TRI CAGR. Independent order replays reconcile to the simulator’s daily NAV within ₹0.05 for stock and exactly ₹0.00 for NIFTYBEES. The full input fingerprint is [`research_data_fingerprint_2026-10-31.json`](research_data_fingerprint_2026-10-31.json), combined SHA-256 `180972b026b3f2ebb87302bfa3f7dc30e87c044cf3f7b0bc4c2f33e2df7aca68`.

The 2025+ period and full history have been viewed repeatedly; this is a diagnostic, not a fresh holdout. The 50-bps cost assumption is uncalibrated, current fees are applied uniformly over history, and stock actions, distributions, delisted names, historical sector classifications and realized capacity remain incomplete.
