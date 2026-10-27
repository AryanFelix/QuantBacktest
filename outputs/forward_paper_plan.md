# Forward paper test: NIFTY/Gold ETF controls

**Rules frozen:** 2026-10-27, revision 7  
**Backtest selection cutoff:** 2026-10-23  
**Paper warm-up available at freeze:** 2026-10-26  
**Paper start:** first completed common NIFTYBEES/GOLDBEES session on or after 2026-10-28  
**Starting capital:** ₹10,00,000 per path  
**Exposure ceiling:** 100%; no leverage  
**Historical drawdown alert:** 20%

Revision 1 froze three paths. Revision 2 added the 95% monthly cash-buffer control; revision 3 added the 65% solo-sleeve path after the 140-case deployment screen; revision 4 added its 16% trailing-volatility throttle; revision 5 added an 80% solo-sleeve / 16% throttle challenger after the 130-case joint sizing screen. Revision 6 added the passive NIFTY/Gold 22.5%/22.5% initial allocation. Revision 7 preserves all eight revision-6 paths and adds a three-threshold passive drawdown-control frontier. The full 2015–2026 history was inspected before this rule was designed, so no threshold is selected for paper; all three are observed prospectively. Revision 7 is frozen before the 2026-10-27 close, and paper observation starts 2026-10-28. Earlier immutable configurations remain available for lineage.

## Rules under prospective observation

| Path | Frozen rule | Costs |
|---|---|---|
| Passive NIFTY/Gold mix | At the first paper-session next-open fill, buy NIFTYBEES and GOLDBEES to 22.5% of NAV each; hold units without rebalancing. Initial gross exposure is 45%; exposure may drift. | Current Upstox/NSE delivery charges; 10 and 50 bps per side |
| Passive drawdown control, 8% trigger | Start with 30% NAV in each ETF; after close-NAV drawdown reaches 8%, reduce total exposure to 30% at the next open; restore 60% when drawdown recovers to -4%, at the next open. | Same |
| Passive drawdown control, 10% trigger | Same 60% start and 30% reduced exposure; trigger at -10% close drawdown and recover at -5%. | Same |
| Passive drawdown control, 12% trigger | Same 60% start and 30% reduced exposure; trigger at -12% close drawdown and recover at -6%. | Same |
| Monthly fixed control, 100% cap | 50% NIFTYBEES Donchian 55/20 + 50% GOLDBEES SMA200 while each sleeve is active; rebalance on signal changes and month-end | Current Upstox/NSE delivery charges; 10 and 50 bps per side |
| Monthly fixed control, 95% cap | Same monthly targets and signals; 95% gross exposure cap leaves a cash buffer when both sleeves are active | Same |
| Quarterly fixed control, 100% cap | Same sleeves and targets; rebalance on signal changes and quarter-end | Same |
| Quarterly inverse-vol control, 50% solo sleeve | 63-session inverse-volatility split when both sleeves are active; 50% NAV when one is active; quarter-end and signal-change rebalances | Same |
| Quarterly inverse-vol challenger, 65% solo sleeve | Same inverse-vol split when both sleeves are active; 65% NAV when one is active; quarter-end and signal-change rebalances | Same |
| Quarterly inverse-vol, 65% solo plus 16% volatility throttle | Same 65% solo rule; at signal-change or quarter-end, scale base exposure by min(1, 16% / trailing 63-session annualized base-portfolio volatility); hold scale until next rebalance | Same |
| Quarterly inverse-vol, 80% solo plus 16% volatility throttle | Same inverse-vol split when both sleeves are active; 80% NAV when one is active; at each signal-change or quarter-end event scale by min(1, 16% / trailing 63-session annualized volatility of the unthrottled 80% portfolio); hold scale until next rebalance | Same |

Signals use completed daily candles; modeled entries and exits use the next available session open with the stated slippage. Cash earns 0%. For the Oct 28 start, any completed Oct 26–27 bars are signal warm-up only and are excluded from paper NAV/return rows. The paths are shadow calculations only: the runner reads market candles and never places broker orders. Each account starts in cash on the paper start date; historical positions are not carried forward.

## Historical basis and current state

The immutable revision-3/4/5 configurations were frozen before the daily session-date correction and remain only to preserve prospective experiment lineage. The corrected 50 bps continuous results are: 65% solo without throttle +152.55% / -23.80% close drawdown; 65%/16% +155.58% / -23.80%; and 80%/16% +173.28% / -28.03%. They breach the requested 20% historical close-drawdown screen and are not risk-qualified candidates. The 130-case grid's prior claim that 80%/16% passed all ten period/cost cases is superseded. See the corrected [interaction method](joint_exposure_volatility_method.md) and [ledger](joint_exposure_volatility_sensitivity.csv).

The corrected 125-case cost stress likewise finds no 65% or 80% rule within 20% on the continuous path at 50 or 100 bps. Only the 10 bps cases for the 65% and 80% variants pass all five inspected windows; 10 bps has not been verified against executable spreads. The 100–200 bps levels are deliberate sensitivities, not observed spreads. See the corrected [cost method](cost_stress_method.md) and [ledger](cost_stress_sensitivity.csv).

The monthly fixed 95% trend path is the same rule as the training-selected NIFTYBEES Donchian 55/20 + GOLDBEES 200DMA blend. At 50 bps, it returned +63.69% on the 2023–2026 fold with a -16.28% daily OHLC envelope, but the separate 2020+ fold breached at -24.41%. Those later periods were inspected; this mixed result is context for paper observation, not qualification as a robust 20% drawdown strategy. The ledgers, costs, and envelope reconciliation are in the [OHLC audit](etf_daily_timestamp_and_intraday_risk_audit.md).

At the revision-7 freeze, the latest common completed candle is 2026-10-26. The 00:29 IST Upstox retry for 2026-10-24 through 2026-10-27 returned success with no bars before the Oct 27 session opened. After the scheduled Oct 26 session completed, an exact-key retry on Oct 27 returned one daily candle each for NIFTYBEES and GOLDBEES; NSE's official 2026 calendar lists Oct 26 as an open session ([NSE trading holidays](https://www.nseindia.com/resources/exchange-communication-holidays)). Raw responses are saved under `work/data/api_probes/market_session_check_2026-10-26/`. The paper runner requests only through the prior calendar date, so an unfinished current-day candle cannot enter its snapshots or paper NAV. No Oct 27 candle has been used, and the paper ledgers remain empty because the frozen start is Oct 28. No synthetic return or broker order has been recorded. Latest request metadata is in `work/data/api_probes/forward_paper_latest.json`; every runner request attempt is retained in `work/data/api_probes/forward_paper_history.jsonl`; the wider coverage check is in `work/data/api_probes/recent_daily_candle_coverage_2026-10-26.json`.

Daily candles do not provide a realized spread ledger. Fixed 10/50 bps slippage is a sensitivity, not a measured bid/ask spread. Next-open fills are modeled and can differ from executable fills. The 20% drawdown limit is an alert threshold, not a guarantee or automatic stop.

## Reproduction and files

Run `python work/forward_paper_etf_blend.py` after the Upstox feed publishes common post-freeze candles. The runner reads the registered token directly from HKCU; it excludes the current calendar date and fetches through yesterday to avoid partial daily bars. It records credential-free request metadata in the latest-probe file and append-only history, merges source snapshots without editing historical caches, and recomputes each frozen path from the first paper session. The three drawdown policies use their close-NAV high-water signal and next-open rebalance in the same runner. Paper ledger rows are idempotent by as-of date, strategy, and slippage case.

- `outputs/forward_paper_ledger.csv`: one summary row per as-of date, portfolio, and slippage case.
- `outputs/forward_paper_equity.csv`: daily NAV and exposure paths since the paper start.
- `outputs/forward_paper_orders.csv`: modeled order ledger for the latest replay.
- `work/backtests/forward_paper/frozen_config.json`: revision 1 freeze.
- `work/backtests/forward_paper/frozen_config_v2.json`: revision 2 freeze, including the 95% cash-buffer control.
- `work/backtests/forward_paper/frozen_config_v3.json`: revision 3 freeze, including the 65% solo-sleeve challenger.
- `work/backtests/forward_paper/frozen_config_v4.json`: prior six-path freeze, including the 65% / 16% throttle.
- `work/backtests/forward_paper/frozen_config_v5.json`: prior seven-path freeze, including the 80% / 16% challenger.
- `work/backtests/forward_paper/frozen_config_v6.json`: prior eight-path freeze, including the passive NIFTY/Gold mix.
- `work/backtests/forward_paper/frozen_config_v7.json`: current eleven-path freeze, adding the 8/10/12% drawdown-trigger frontier.
- `work/backtests/forward_paper/latest_status.json`: latest run state and API outcomes.
- `work/data/api_probes/forward_paper_history.jsonl`: append-only, credential-free record of every incremental request attempt.
- `work/data/forward_paper/incremental/`: new candle additions; historical source files remain unchanged.

This becomes prospective evidence only as new sessions arrive after the freeze. It does not validate or promote the historical candidate today.
