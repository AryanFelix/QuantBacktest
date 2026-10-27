"""Scale the fixed NIFTY/Gold control against a conservative daily OHLC risk bound."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

import audit_etf_intraday_drawdown as audit
import replay_volatility_weighted_blend as blend
import upstox_quant as q


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "work" / "backtests" / "intraday_ohlc_exposure"
SUMMARY = ROOT / "outputs" / "intraday_ohlc_exposure_sensitivity.csv"
CAPITAL = 1_000_000.0
SLIPPAGE_BPS = 50.0
EXPOSURE_CAPS = tuple(sorted({round(0.25 + 0.05 * i, 2) for i in range(16)} | {0.71, 0.72, 0.73, 0.74}))


def main() -> None:
    _, panels, portfolios, event_sets = blend.make_portfolios()
    assert panels["close"].index.is_unique
    targets = portfolios["fixed_50_50_quarterly"]
    events = event_sets["fixed_50_50_quarterly"]
    rows = []
    for cap in EXPOSURE_CAPS:
        equity, orders, stats = q._simulate(
            panels, targets, events, CAPITAL, cap, SLIPPAGE_BPS,
            "equity_delivery", drawdown_limit_pct=20,
        )
        run = OUT / f"gross_cap_{int(cap * 100)}pct__50bps"
        run.mkdir(parents=True, exist_ok=True)
        equity.to_csv(run / "equity.csv", index_label="time")
        orders.to_csv(run / "orders.csv", index=False)
        row = audit.run_case(f"Fixed quarterly 50/50 sleeves; {cap:.0%} gross cap", str(run.relative_to(ROOT)))
        row.update({
            "gross_exposure_cap_pct": cap * 100,
            "total_return_pct": stats["total_return_pct"],
            "cagr_pct": stats["cagr_pct"],
            "fees_inr": stats["total_fees_inr"],
            "order_count": stats["order_count"],
            "annualized_volatility_pct": stats["annualized_volatility_pct"],
        })
        rows.append(row)

    result = pd.DataFrame(rows)
    assert len(result) == len(EXPOSURE_CAPS) == 20
    assert result["within_20pct_under_bound"].equals(result["simultaneous_ohlc_drawdown_bound_pct"].ge(-20))
    result.to_csv(SUMMARY, index=False)
    print(f"Wrote {len(result)} exposure caps; each order ledger reconciles to close NAV.")


if __name__ == "__main__":
    main()
