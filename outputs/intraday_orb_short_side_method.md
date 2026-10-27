# NIFTY 30-minute opening-range breakout: symmetric short-side screen

**Frozen:** 2026-10-27
**Capital:** ₹10 lakh per period and cost case
**Data:** Upstox 30-minute NIFTY 50 signal and NIFTYBEES execution bars, 2022-01-03–2026-10-23

## Rule

Use the first NIFTY 50 30-minute bar as the opening range. If the second bar closes above the first-bar high, enter long at the third bar's open. If it closes below the first-bar low, enter short at the third bar's open. The stop is the opposite edge of the first NIFTYBEES 30-minute bar. Fill a stop crossed through a bar's open at that open; otherwise fill at the stop. Close any remaining position at the last bar's close and hold no overnight positions.

Size each trade to risk 0.5% of current account equity at the modeled stop, subject to a 95% gross-exposure cap and whole-share quantities. Charge the existing Upstox/NSE intraday fee model for equity-fund units. Apply 10, 25, 50, and 100 bps adverse slippage per side; 10 bps is the base scenario, not a measured spread. No additional range, trend, or day-of-week filter is tested.

## Evaluation

Reset to ₹10 lakh for train (2022–2023), validation (2024), the previously inspected 2025–2026 segment, and continuous 2022–2026. Report both the original long-only rule and its symmetric long/short extension across all four fixed slippage assumptions. The existing long-only sensitivity is an assert-based reproduction control: with zero minimum opening-range width, 10 bps slippage, and each period, returns must match exactly within floating-point tolerance.

This extension is a screen, not a fresh holdout: all periods were already inspected in the long-only ORB and related intraday studies. No parameter will be selected from the 2025–2026 segment. If the short side creates a plausible net edge, require a separate 1-minute execution-path replay before considering it further.

## Limits

Signals, entries, stops, and terminal exits use 30-minute OHLC. Stop gaps within a 30-minute bar, bid/ask spread, queue priority, and partial fills are not observable here. Slippage values are stress inputs, not historical fills. Current fees are applied to old data; investor taxes and market impact are not modeled. Even a drawdown pass does not guarantee a future 20% maximum loss.

The strategy uses the shared simulator in `work/upstox_quant.py`. Runner and row-level results: `work/sensitivity_intraday_orb_short_side.py` and `outputs/intraday_orb_short_side_sensitivity.csv`.
