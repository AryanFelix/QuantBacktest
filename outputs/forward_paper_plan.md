# Forward paper test: NIFTY/Gold ETF controls

**Rules frozen:** 2026-10-27, revision 8<br>
**Backtest selection cutoff:** 2026-10-23  
**Paper warm-up available at freeze:** 2026-10-26  
**Paper start:** first completed common NIFTYBEES/GOLDBEES session on or after 2026-10-28  
**Starting capital:** ₹10,00,000 per path  
**Exposure ceiling:** 100%; no leverage  
**Historical drawdown alert:** 20%

Revision 1 froze three paths. Revision 2 added the 95% monthly cash-buffer control; revision 3 added the 65% solo-sleeve path after the 140-case deployment screen; revision 4 added its 16% trailing-volatility throttle; revision 5 added an 80% solo-sleeve / 16% throttle challenger after the 130-case joint sizing screen. Revision 6 added the passive NIFTY/Gold 22.5%/22.5% initial allocation. Revision 7 preserved all eight revision-6 paths and added three passive drawdown-control thresholds. Revision 8 preserves those eleven paths and adds the 70% gross cap selected under the user 20% training OHLC screen plus the 40% cap selected with a 15% safety buffer. The 2023+ backtest was already inspected, so these are historical pseudo-out-of-sample results; the new paths are included for genuinely prospective observation after the freeze. Revision 8 was frozen before the first post-freeze paper session, and paper observation starts 2026-10-28. Earlier immutable configurations remain available for lineage.

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
| Quarterly fixed control, training-selected 70% cap | Same quarterly fixed 50/50 sleeves; 70% cap chosen on 2014–2022 training under the 20% OHLC screen | Same |
| Quarterly fixed control, 40% risk-buffer cap | Same quarterly fixed 50/50 sleeves; 40% cap chosen on 2014–2022 training under a 15% OHLC buffer | Same |
| Quarterly inverse-vol control, 50% solo sleeve | 63-session inverse-volatility split when both sleeves are active; 50% NAV when one is active; quarter-end and signal-change rebalances | Same |
| Quarterly inverse-vol challenger, 65% solo sleeve | Same inverse-vol split when both sleeves are active; 65% NAV when one is active; quarter-end and signal-change rebalances | Same |
| Quarterly inverse-vol, 65% solo plus 16% volatility throttle | Same 65% solo rule; at signal-change or quarter-end, scale base exposure by min(1, 16% / trailing 63-session annualized base-portfolio volatility); hold scale until next rebalance | Same |
| Quarterly inverse-vol, 80% solo plus 16% volatility throttle | Same inverse-vol split when both sleeves are active; 80% NAV when one is active; at each signal-change or quarter-end event scale by min(1, 16% / trailing 63-session annualized volatility of the unthrottled 80% portfolio); hold scale until next rebalance | Same |

Signals use completed daily candles; modeled entries and exits use the next available session open with the stated slippage. Cash earns 0%. For the Oct 28 start, any completed Oct 26–27 bars are signal warm-up only and are excluded from paper NAV/return rows. The paths are shadow calculations only: the runner reads market candles and never places broker orders. Each account starts in cash on the paper start date; historical positions are not carried forward.

## Historical basis and current state

The immutable revision-3/4/5 configurations were frozen before the daily session-date correction and remain only to preserve prospective experiment lineage. The corrected 50 bps continuous results are: 65% solo without throttle +152.55% / -23.80% close drawdown; 65%/16% +155.58% / -23.80%; and 80%/16% +173.28% / -28.03%. They breach the requested 20% historical close-drawdown screen and are not risk-qualified candidates. The 130-case grid's prior claim that 80%/16% passed all ten period/cost cases is superseded. See the corrected [interaction method](joint_exposure_volatility_method.md) and [ledger](joint_exposure_volatility_sensitivity.csv).

The corrected 125-case cost stress likewise finds no 65% or 80% rule within 20% on the continuous path at 50 or 100 bps. Only the 10 bps cases for the 65% and 80% variants pass all five inspected windows; 10 bps has not been verified against executable spreads. The 100–200 bps levels are deliberate sensitivities, not observed spreads. See the corrected [cost method](cost_stress_method.md) and [ledger](cost_stress_sensitivity.csv).

The monthly fixed 95% trend path is the same rule as the training-selected NIFTYBEES Donchian 55/20 + GOLDBEES 200DMA blend. At 50 bps, it returned +63.69% on the 2023–2026 fold with a -16.28% daily OHLC envelope, but the separate 2020+ fold breached at -24.41%. Those later periods were inspected; this mixed result is context for paper observation, not qualification as a robust 20% drawdown strategy. The ledgers, costs, and envelope reconciliation are in the [OHLC audit](etf_daily_timestamp_and_intraday_risk_audit.md).

The revision-8 exposure study selects a 70% cap on 2014–2022 under the exact 20% OHLC screen; its training bound is -19.07%, leaving 0.93 points of room. The fresh-capital 2023+ replay returned +55.71% / -16.81% OHLC at 50 bps. A 40% cap selected under a 15% buffer returned +37.80% / -13.86%. Both later periods were previously inspected; the separate 70% control bootstrap estimated a 7.30% ten-year close-drawdown breach frequency at 63-session blocks. These are research candidates, not proven risk caps. See the [selection method and results](etf_exposure_cap_oos_method.md).

At the revision-8 freeze, the latest common completed candle remains 2026-10-26; the 20:06 IST Oct 27 range recheck returned one bar per ETF, both dated Oct 26. NSE's official 2026 calendar lists Oct 26 as an open session ([NSE trading holidays](https://www.nseindia.com/resources/exchange-communication-holidays)). Raw responses are saved under `work/data/api_probes/`. The paper runner requests only through the prior calendar date, so an unfinished current-day candle cannot enter its snapshots or paper NAV. No Oct 27 candle has been used, and the paper ledgers remain empty because the frozen start is Oct 28. No synthetic return or broker order has been recorded. Latest request metadata is in `work/data/api_probes/forward_paper_latest.json`; every runner request attempt is retained in `work/data/api_probes/forward_paper_history.jsonl`.

At 15:20 IST on 2026-10-27, the incremental runner successfully requested through Oct 26 and cached one completed daily bar for each ETF. The first attempt had received the bars but failed while comparing the fetched timezone-aware timestamps with strings read from the incremental CSV; `work/forward_paper_etf_blend.py` now parses the combined timestamp column before deduplication and sorting. The successful retry confirms Oct 26 as the latest common bar. Oct 27 remains excluded until a later completed-session fetch, and no post-freeze session or paper return row exists yet. The runner reads the registered token from HKCU, so this workflow did not require restarting Codex.

At 15:35 IST, exact-date Upstox V3 requests for Oct 27 returned API success with zero daily candles for both ETFs. At 19:49 IST, after a transient DNS failure, an Oct 24–27 range retry succeeded with one bar per ETF, both dated Oct 26. A 20:06 IST follow-up and a 21:15 IST recheck again returned one Oct 26 bar per ETF; no Oct 27 daily candle was available and the common cache still ends on Oct 26. This is a publication-lag observation, not proof that the session was closed or that the endpoint is complete. The credential-free candle-response records are in `work/data/api_probes/market_session_check_2026-10-27.json` and `work/data/api_probes/market_session_check_2026-10-27_afterclose.json`, with attempts retained in `work/data/api_probes/forward_paper_history.jsonl`; the runner has not added an Oct 27 bar to paper snapshots or NAV.

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
- `work/backtests/forward_paper/frozen_config_v7.json`: prior eleven-path freeze, adding the 8/10/12% drawdown-trigger frontier.
- `work/backtests/forward_paper/frozen_config_v8.json`: current thirteen-path freeze, adding the training-selected 70% cap and 40% safety-buffer comparison.
- `work/backtests/forward_paper/latest_status.json`: latest run state and API outcomes.
- `work/data/api_probes/forward_paper_history.jsonl`: append-only, credential-free record of every incremental request attempt.
- `work/data/forward_paper/incremental/`: new candle additions; historical source files remain unchanged.

This becomes prospective evidence only as new sessions arrive after the freeze. It does not validate or promote the historical candidate today.
