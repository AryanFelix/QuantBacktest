# NIFTY intraday ORB with prior-day trend gate

**Run date:** 2026-10-27

- **Capital:** ₹10 lakh per fresh period
- **Risk:** 0.5% of account NAV at the modeled stop; 95% gross exposure ceiling
- **Data:** Upstox 30-minute NIFTY 50 and NIFTYBEES candles, 2022-01-03–2026-10-23; daily Upstox NIFTY 50 closes for the 200-session filter
- **Costs:** current modeled NSE/Upstox equity-fund intraday fees; 10/25/50/100 bps adverse slippage per side

## Rule and comparison

The baseline is the existing long-only NIFTY 30-minute opening-range breakout. The first index candle sets the range. A close above that range on the second candle signals entry at the third candle's open; the stop is the traded ETF's first-candle low. Exit at the first stop touch, with gap-through stops filled at the bar open, or at the last 30-minute close. Positions are flat overnight. The established filter under study permits a trade only when the **previous completed NIFTY daily close** was above its then-known 200-session simple moving average. The rule adds no same-day information and uses no fitted thresholds.

Both baseline and filtered paths use the same intraday signals, fills, stop sizing, exposure cap, fees, and costs. Each segment starts with ₹10 lakh: training 2022-01-03–2023-12-29, validation 2024, inspected 2025-01-01–2026-10-23 holdout, and continuous 2022-01-03–2026-10-23. The 30-minute data merge requires matching timestamps between index signal and ETF execution bars.

## Results

| Path | Segment | Return at 10 bps | Maximum drawdown | Trades |
|---|---|---:|---:|---:|
| Ungated baseline | Training | -10.65% | -11.79% | 112 |
| Prior-close SMA200 gate | Training | -11.40% | -12.40% | 87 |
| Ungated baseline | Validation | -2.81% | -3.40% | 52 |
| Prior-close SMA200 gate | Validation | -2.62% | -3.22% | 49 |
| Ungated baseline | 2025+ replay | -13.79% | -14.08% | 78 |
| Prior-close SMA200 gate | 2025+ replay | -8.51% | -8.51% | 35 |
| Ungated baseline | Continuous | -25.20% | -25.98% | 242 |
| Prior-close SMA200 gate | Continuous | -21.11% | -21.56% | 171 |

The gate reduced continuous turnover and costs (10-bps slippage case: fees ₹49,533 and slippage ₹234,048, versus ₹69,267 and ₹326,503 ungated), but both continuous paths lost money and breached the 20% maximum-drawdown screen. At 50 bps per side the continuous returns were -72.38% gated and -83.00% ungated. No path in the tested cost range establishes a profitable intraday edge; reject this ORB family on current evidence.

## Limits and reproduction

The later sample and ORB family were already examined in earlier research; the 2025+ comparison is retrospective pseudo-OOS, not an untouched lockbox. Stop execution is inferred from 30-minute OHLC, so within-bar order, bid/ask spread, queue priority, and partial fills are unknown. Fixed slippage is a stress input rather than observed market impact. Current charges are applied uniformly, taxes and financing are excluded, and this gate does not guarantee a 20% loss limit.

- Runner: [`work/sensitivity_intraday_orb_daily_regime.py`](../work/sensitivity_intraday_orb_daily_regime.py)
- Shared ORB simulator and filter self-check: [`work/upstox_quant.py`](../work/upstox_quant.py)
- All 32 cost/period rows: [`intraday_orb_daily_regime.csv`](intraday_orb_daily_regime.csv)
- Local run-level NAV and trade outputs: `work/backtests/intraday_orb_daily_regime/`
