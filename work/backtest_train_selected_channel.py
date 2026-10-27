"""Select one NIFTY/Gold channel rule on training history and replay later windows."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pandas as pd

import audit_etf_intraday_drawdown as audit
import replay_volatility_weighted_blend as blend
import sensitivity_nifty_gold_parameters as sensitivity
import upstox_quant as q


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "work" / "backtests" / "train_selected_channel"
SUMMARY = ROOT / "outputs" / "train_selected_channel_validation.csv"
CAPITAL = 1_000_000.0
SLIPPAGE_BPS = 50.0
EXPOSURE_CAPS = (0.45, 0.70, 1.00)
WINDOWS = (
    ("train_2014_2019", date(2014, 1, 1), date(2019, 12, 31)),
    ("validation_2020_2022", date(2020, 1, 1), date(2022, 12, 31)),
    ("recent_2023_plus", date(2023, 1, 1), None),
    ("full_2014_plus", date(2014, 1, 1), None),
)


def main() -> None:
    sensitivity_rows = pd.read_csv(ROOT / "outputs" / "etf_parameter_sensitivity.csv")
    training = sensitivity_rows[
        sensitivity_rows["period"].eq("train_2014_2019")
        & sensitivity_rows["slippage_bps_per_side"].eq(SLIPPAGE_BPS)
        & sensitivity_rows["within_drawdown_limit"]
    ]
    selected = training.sort_values("total_return_pct", ascending=False).iloc[0]
    assert selected["variant"] == "channel_exit_D55_30_SMA200"

    _, panels, _, _ = blend.make_portfolios()
    data_end = panels["close"].index[-1].date()
    rules = (
        ("training_selected_D55_30_SMA200", 55, 30, 200),
        ("fixed_reference_D55_20_SMA200", 55, 20, 200),
    )
    rows = []
    OUT.mkdir(parents=True, exist_ok=True)
    for rule_name, entry_n, exit_n, trend_n in rules:
        targets, events = sensitivity._portfolio(panels, entry_n, exit_n, trend_n)
        for window, start, requested_end in WINDOWS:
            end = requested_end or data_end
            slips = (10.0, SLIPPAGE_BPS, 100.0) if window == "full_2014_plus" else (SLIPPAGE_BPS,)
            for cap in EXPOSURE_CAPS:
                for slip in slips:
                    equity, orders, stats = q._simulate(
                        panels, targets, events, CAPITAL, cap, slip,
                        "equity_delivery", start, end, 20.0,
                    )
                    stats["total_slippage_inr"] = blend.modeled_slippage(orders, panels)
                    run = OUT / f"{rule_name}__{window}__cap{int(cap * 100)}__{int(slip)}bps"
                    run.mkdir(parents=True, exist_ok=True)
                    equity.to_csv(run / "equity.csv", index_label="time")
                    orders.to_csv(run / "orders.csv", index=False)
                    risk = audit.run_case(rule_name, str(run.relative_to(ROOT)))
                    rows.append({
                        "strategy": rule_name,
                        "selection_basis": "Highest net return among seven parameter settings in 2014–2019 at 50 bps, subject to 20% close drawdown",
                        "period": window,
                        "exposure_cap_pct": cap * 100,
                        "slippage_bps_per_side": slip,
                        "period_start": stats["first_bar"][:10],
                        "period_end": stats["last_bar"][:10],
                        "sessions": len(equity),
                        "starting_balance_inr": CAPITAL,
                        "ending_balance_inr": stats["ending_balance_inr"],
                        "total_return_pct": stats["total_return_pct"],
                        "cagr_pct": stats["cagr_pct"],
                        "close_max_drawdown_pct": stats["max_drawdown_pct"],
                        "ohlc_drawdown_bound_pct": risk["simultaneous_ohlc_drawdown_bound_pct"],
                        "within_20pct_close": stats["within_drawdown_limit"],
                        "within_20pct_ohlc": risk["within_20pct_under_bound"],
                        "within_20pct": risk["within_20pct_under_bound"],
                        "total_fees_inr": stats["total_fees_inr"],
                        "total_slippage_inr": stats["total_slippage_inr"],
                        "order_count": stats["order_count"],
                        "max_close_replay_error_inr": risk["max_close_replay_error_inr"],
                        "ohlc_bound_peak_date": risk["bound_peak_date"],
                        "ohlc_bound_trough_date": risk["bound_trough_date"],
                    })

    result = pd.DataFrame(rows)
    assert len(result) == 36
    assert result["max_close_replay_error_inr"].max() <= 0.03
    assert set(result["strategy"]) == {"training_selected_D55_30_SMA200", "fixed_reference_D55_20_SMA200"}
    result.to_csv(SUMMARY, index=False)
    print(f"Wrote {len(result)} train-selected/control replays with OHLC bounds through {data_end}.")


if __name__ == "__main__":
    main()
