# Passive NIFTY/Gold initial-composition walk-forward

- **Run date:** 2026-10-27
- **Input history:** saved Upstox daily candles through 2026-10-23; 2,921 common sessions from 2015-01-02
- **Starting capital:** ₹10,00,000
- **Initial gross exposure:** 45%, held as uninvested cash otherwise
- **Costs:** current modeled charges plus 50 bps adverse slippage per side
- **Status:** retrospective composition sensitivity; no ratio is validated for live trading.

## Question and construction

The strongest passive NIFTY/Gold benchmark uses 45% initial gross exposure, but prior tests fixed the risky sleeve at 50/50. This screen holds that 45% initial allocation constant and tests eleven NIFTY shares of the risky sleeve, from 0% to 100% in 10-point steps; Gold receives the balance. For example, 30/70 means 13.5% of starting NAV in NIFTYBEES and 31.5% in GOLDBEES. Each allocation is bought at the first available session and held without rebalancing, so its risky exposure drifts with asset prices.

Each path starts with ₹10 lakh and uses integer units, current modeled ETF fees, 50 bps per-side slippage, and terminal liquidation. Known NIFTYBEES cash distributions from 2014/2015 are credited using the existing share-unit conversion. GOLDBEES distribution completeness is unverified and no Gold payouts are credited. Cash earns 0%. The daily OHLC audit uses the saved order ledger and a conservative envelope; it is not an observed synchronized intraday path.

## Training selection and carry-forward

The training segment is 2015-01-02 through 2019-12-31. It selects the highest net return among the eleven ratios whose training OHLC envelope is no worse than -20%. Ties prefer more risk headroom, then the composition nearest equal sleeves. Each candidate is also replayed continuously from 2015-01-02 through 2026-10-23. The post-2019 return is calculated on the training NAV carried forward within that same full-account path.

## Results

The training selector chose **100% NIFTY / 0% Gold** within the risky sleeve (45% NIFTY initial NAV): training return was +24.24% with -14.50% training OHLC bound. That continuous path returned +92.66% over 2015–2026 and +54.62% after 2019, but its full-history OHLC bound breached the screen at -25.20%.

| NIFTY / Gold share of 45% sleeve | Initial NAV weights | 2015–2026 return | Close drawdown | OHLC bound | Post-2019 return on carried NAV | Screen |
|---:|---:|---:|---:|---:|---:|---|
| 0% / 100% | 0% / 45% | +165.39% | -20.35% | -24.45% | +126.49% | Fail |
| 10% / 90% | 4.5% / 40.5% | +158.09% | -19.53% | -23.03% | +118.89% | Fail |
| 20% / 80% | 9% / 36% | +150.82% | -18.66% | -21.50% | +111.39% | Fail |
| 30% / 70% | 13.5% / 31.5% | +143.55% | -17.71% | -19.93% | +103.99% | Pass, 0.07 pp headroom |
| 40% / 60% | 18% / 27% | +136.27% | -16.69% | -18.70% | +96.67% | Pass, 1.30 pp headroom |
| 50% / 50% | 22.5% / 22.5% | +129.00% | -15.58% | -17.37% | +89.45% | Pass, 2.63 pp headroom |
| 60% / 40% | 27% / 18% | +121.73% | -14.38% | -17.47% | +82.31% | Pass, 2.53 pp headroom |
| 70% / 30% | 31.5% / 13.5% | +114.46% | -14.49% | -19.43% | +75.26% | Pass, 0.57 pp headroom |
| 80% / 20% | 36% / 9% | +107.18% | -16.47% | -21.38% | +68.30% | Fail |
| 90% / 10% | 40.5% / 4.5% | +99.91% | -18.43% | -23.30% | +61.41% | Fail |
| 100% / 0% | 45% / 0% | +92.66% | -20.36% | -25.20% | +54.62% | Fail |

The maximum full-history return among tested ratios that passes the 20% OHLC screen is 30/70. Its advantage over the equal 50/50 mix is 14.55 percentage points, but only 0.07 points of historical drawdown headroom remain. The return frontier therefore comes close to the risk boundary. This 30/70 ratio was identified after inspecting the full path; it is descriptive, not an independent selection or a robust drawdown candidate. The lower-return 40/60 path has 1.30 points of historical room, and 50/50 has 2.63 points.

The 50/50, 45%-exposure path reconciles against the existing passive exposure sweep within ₹0.03 for ending NAV, fees, slippage, OHLC bound, and orders. Every run's order-ledger close NAV replay error is below ₹0.03.

## Limits and reproduction

This is a one-time passive allocation with drifting weights, not a maintained exposure cap. The training-selected ratio fails continuous drawdown, while full-history selection among surviving ratios is explicitly post-hoc. All dates have already been inspected and the Gold ETF distribution record is incomplete. A separate 5,000-path stationary bootstrap on composition-specific net close returns estimates ten-year 63-session-block drawdown breaches of 4.76% for 30/70 and 3.40% for 40/60; it does not recreate OHLC paths or holdings, and both ratios were selected after examining this history. ETF bid/ask spreads, market impact beyond 50 bps, cash yield, tax outside modeled charges, and future drawdowns are unmodeled. A historical OHLC pass cannot enforce a 20% future loss limit.

Run `python work/sensitivity_passive_mix_composition.py` from a checkout with local data caches. The runner writes [the 22-row training/continuous ledger](passive_mix_composition_sensitivity.csv), a [selection record](passive_mix_composition_selection.json), exact daily equity and order files under local `work/backtests/passive_mix_composition/`, and the consolidated metrics. The prior [passive exposure sensitivity](passive_mix_exposure_method.md) holds the risky sleeve at equal weights while varying total initial exposure.
