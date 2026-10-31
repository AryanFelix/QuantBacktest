# QuantBacktest governor checkpoint — 2026-10-31

## Decision

**No strategy met the 20% after-cost calendar CAGR objective over its full predefined evaluation. Pause for governor review.** The cycle used the unlevered cash mandate, ₹10 lakh reference capital, history through 2026-10-23, and no personal tax. It ended early after the broad-stock data gate failed; there is no value in spending the remaining window on another ETF ratio sweep.

## What changed the assessment

- Shared and stock simulators now reject terminal liquidation when a held security lacks a raw close on the account’s last date. A valid terminal sale uses that last date’s close and ends with zero exposure. Calendar CAGR uses elapsed days divided by 365.25. The four-session regression passed.
- The saved-ledger audit scanned 3,168 order files: 2,495 had terminal orders and 4,932 terminal sale rows; none was backdated or missing a terminal quote. It checked 7,293,564 held symbol-days. The 438 stale marks are one GOLDBEES cache gap on 2019-05-07, repeated across overlapping runs. The exact day’s NAV/rebalance effect is unknowable from cached prices; this does not imply all old ledgers are corrupt.
- The selected monthly NIFTY 50 12–1 top-15 rule remains a diagnostic leader, not a winner: 23.88% training, 11.87% in 2024, -4.94% in 2025–October 2026, and 11.90% continuously after modeled costs. Matched NIFTY 50 TRI returned 9.66%; a 100% NIFTYBEES passive path returned 9.69% after the same 50 bps/side model, but is price-only. In 2025 onward the rule lagged TRI by 3.67 percentage points. Its full close/OHLC drawdowns were -26.63%/-29.66%.
- Full-account attribution reconciles the selected stock rule to its order ledger within ₹0.05. Same-share gross CAGR was 15.11%; modeled fees were ₹93,443, modeled slippage ₹240,296, and annual turnover 8.40 times starting capital. The 50 bps execution assumption is uncalibrated; a modeled break-even is about 90.2 bps per side versus TRI. This is not a measured spread/capacity result.
- Calendar-time remeasurement supersedes the recent Donchian/Gold 14.0592% with 13.8245% from 2023-01-02 to 2026-10-23. The corrected 2020+ CAGR is 12.7457%, superseding 12.9368%. This change is a measurement/cost correction, not a new edge.
- NIFTY/Gold’s 20.72% result is limited to 2020 onward; it is 10.40% over 2014–2026, -0.51% in 2014–2019, and 13.60% at the training-selected 50% exposure since 2020. No losing-period regime gate was added.

## What failed or remains unrun

- The broad-universe gate failed. Available data is 70 stock histories and 82 reconstructed monthly NIFTY 50 snapshots, not a survivorship-safe NIFTY 200/500 panel. Membership transitions, warm-up, delisted/successor names, corporate actions and point-in-time quality inputs are incomplete. No broad-stock configurations ran and no data was purchased.
- The four frozen broad-universe candidates are A-M, A-Q, B-M and B-Q in the [next-cycle specification](next_cycle_spec_2026-10-31.md). Quality variants were omitted because publication-timestamped historical fundamentals are unavailable. They remain NOT RUN, not failed strategies.
- Existing intraday ORB remains rejected: at 10 bps/side its continuous result was -25.20% ungated and -21.11% with the prior-close SMA200 gate. All 36 continuous gap-fade cases lost. The 198-case NIFTY/Gold allocation-ratio search had no positive 2015–2019 training result; its mechanically selected 30% cap lagged the fixed reference later. Do not reopen these without corrected evidence or new inputs.
- The synthetic 2× Smallcap 250 proxy is excluded from the unlevered leaderboard: its 32.06% headline fell to 15.71% under the modeled financing-rate sensitivity before trading costs, with -70.50% close drawdown.
- A local scan of the existing historical summary found at least 4,409 result rows, 1,534 distinct strategy/universe/selection-or-sizing/cost tuples, 58 simulation types and 876 strategy labels. Windows, cost stresses, audits and parameter cases overlap; these are not independent trials. The aggregate file’s legacy rows lack complete code/data hashes and trial dependence, so a Deflated Sharpe diagnostic is not supportable. The artifact snapshot SHA-256 and cycle register are in the [experiment register](experiment_register_2026-10-31.csv).

## Assumptions and risk still open

The 50 bps/side stock and ETF execution base is not calibrated from timestamped spreads and order sizes. Current fee rates are applied across historical periods. ETF distribution history is incomplete; point-in-time stock membership and action/successor treatment are incomplete; historical sector labels are applied retrospectively; capacity, partial fills, personal tax, and live stop behavior are not established. The holdout history has been viewed repeatedly and is not untouched evidence. The absence of a hard drawdown ceiling does not limit future loss.

The Upstox token remains unrotated after prior exposure. **No Upstox API request was made in this cycle.** Rotate it before any future request. No live broker order, leverage or paper-path change was made.

## One next action and one future challenger

The justified next action is to obtain a quote or user-provided licensed archive for effective-dated NIFTY 200/500 membership, identifiers, exits/delistings and complete corporate-action/successor entitlements, then pass the data gate before any strategy run. Do not buy data without authorization. If the four preregistered momentum cases still fail to meet 20% over their frozen evaluation, the single materially different hypothesis to consider is point-in-time post-earnings announcement drift using timestamped filing and earnings-surprise data. It is not specified tightly enough to run and is not a paper candidate yet.

## Review artifacts and reproduction

Start with the [top-five report](quant_research_report.md), [data gate](broad_stock_data_gate_2026-10-31.md), [experiment register](experiment_register_2026-10-31.csv), [terminal audit](terminal_liquidation_audit_2026-10-31.md), and [stock attribution](stock_momentum_attribution_2026-10-31.md). Data fingerprint: `180972b026b3f2ebb87302bfa3f7dc30e87c044cf3f7b0bc4c2f33e2df7aca68`. Code fingerprint: `bda1cc218c635071f8580d5c6f0b7c7c0bb56595dcf85a2901fcb60ab5290cb1`.

From the repository root, reproduce the checks and highlighted runs with:

```powershell
python work/check_terminal_liquidation.py
python work/audit_stored_position_gaps.py
python work/attribute_stock_momentum_leader.py
python work/replay_donchian_gold_blend.py
python work/write_research_data_fingerprint.py
python work/write_research_code_fingerprint.py
```
