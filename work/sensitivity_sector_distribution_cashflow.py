"""Stress sector ETF results against two unverified secondary-source cash claims."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pandas as pd

import audit_etf_intraday_drawdown as ohlc_audit
import replay_volatility_weighted_blend as blend
import sensitivity_sector_rotation as price_signal
import sensitivity_sector_tri_signal as tri_signal
import upstox_quant as q


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "work" / "backtests" / "sector_distribution_cashflow_sensitivity"
SUMMARY = ROOT / "outputs" / "sector_distribution_cashflow_sensitivity.csv"
CAPITAL = 1_000_000
DD_LIMIT = 20.0
SLIPPAGE_BPS = 50
PERIOD_NAMES = {"holdout_2025_plus", "continuous_2022_plus"}
EVENTS = {
    "AUTOBEES": (date(2026, 6, 9), 10.50),
    "PHARMABEES": (date(2026, 6, 11), 6.50),
}
SCENARIOS = {
    "autobees_only_secondary": [("AUTOBEES", *EVENTS["AUTOBEES"])],
    "pharmabees_only_secondary": [("PHARMABEES", *EVENTS["PHARMABEES"])],
    "both_secondary_claims": [
        ("AUTOBEES", *EVENTS["AUTOBEES"]),
        ("PHARMABEES", *EVENTS["PHARMABEES"]),
    ],
}


def _published_baselines() -> tuple[dict, dict]:
    price = pd.read_csv(ROOT / "outputs" / "sector_rotation_sensitivity.csv")
    price = price.loc[price["slippage_bps_per_side"] == SLIPPAGE_BPS]
    price_risk = pd.read_csv(ROOT / "outputs" / "sector_rotation_ohlc_audit.csv")
    price_risk = price_risk.loc[price_risk["slippage_bps_per_side"] == SLIPPAGE_BPS]
    tri = pd.read_csv(ROOT / "outputs" / "sector_tri_signal_momentum_sensitivity.csv")
    tri = tri.loc[tri["slippage_bps_per_side"] == SLIPPAGE_BPS]
    tri_risk = pd.read_csv(ROOT / "outputs" / "sector_tri_signal_momentum_ohlc_audit.csv")
    tri_risk = tri_risk.loc[tri_risk["slippage_bps_per_side"] == SLIPPAGE_BPS]

    def indexed(metrics: pd.DataFrame, risk: pd.DataFrame, strategy_prefix: str) -> dict:
        audit = {
            (row.strategy, row.period, float(row.exposure_cap_pct)): row._asdict()
            for row in risk.itertuples(index=False)
        }
        result = {}
        for row in metrics.itertuples(index=False):
            if row.period not in PERIOD_NAMES or not str(row.strategy).startswith(strategy_prefix):
                continue
            key = (row.strategy, row.period, float(row.exposure_cap_pct))
            if key not in audit:
                raise AssertionError(f"Missing published OHLC baseline for {key}")
            result[key] = {**row._asdict(), **audit[key]}
        return result

    return indexed(price, price_risk, "sector_momentum12_1_top"), indexed(
        tri, tri_risk, "sector_tri_momentum12_1_top"
    )


def _same(actual: float, expected: float, tolerance: float = 1e-5) -> bool:
    return abs(float(actual) - float(expected)) <= tolerance


def main() -> None:
    q._self_check()
    files, panels = q._read_prices(
        [f"{name}={price_signal.DATA / path}" for name, path in price_signal.ASSETS.items()]
    )
    assert set(files) == set(price_signal.ASSETS)
    assert panels["close"].index.min().date() == date(2014, 1, 1)
    assert panels["close"].index.max().date() == date(2026, 10, 23)
    tri_closes, _ = tri_signal._read_tri(panels["close"].index)
    price_baseline, tri_baseline = _published_baselines()

    run_specs = []
    for top_n in (1, 2, 3):
        price_targets, price_events = price_signal._sector_targets(panels, top_n)
        tri_targets, tri_events = tri_signal._targets(tri_closes, panels, top_n)
        run_specs.extend([
            ("price", f"sector_momentum12_1_top{top_n}", top_n, price_targets, price_events, price_baseline),
            ("official_tri", f"sector_tri_momentum12_1_top{top_n}", top_n, tri_targets, tri_events, tri_baseline),
        ])

    rows = []
    for signal_source, strategy, top_n, targets, rebalance, baselines in run_specs:
        for period_name, start, end in price_signal.PERIODS:
            if period_name not in PERIOD_NAMES:
                continue
            for exposure in price_signal.EXPOSURES:
                key = (strategy, period_name, exposure * 100)
                baseline = baselines[key]
                _, base_orders, base_stats = q._simulate(
                    panels, targets, rebalance, CAPITAL, exposure, SLIPPAGE_BPS,
                    "equity_delivery", start, end, DD_LIMIT,
                )
                base_slippage = blend.modeled_slippage(base_orders, panels)
                assert _same(base_stats["total_return_pct"], baseline["total_return_pct"])
                assert _same(base_stats["max_drawdown_pct"], baseline["max_drawdown_pct"])
                assert _same(base_stats["total_fees_inr"], baseline["fees_inr"], 0.01)
                assert _same(base_slippage, baseline["slippage_cost_inr"], 0.01)

                for scenario, distributions in SCENARIOS.items():
                    equity, orders, stats = q._simulate(
                        panels, targets, rebalance, CAPITAL, exposure, SLIPPAGE_BPS,
                        "equity_delivery", start, end, DD_LIMIT,
                        cash_distributions=distributions,
                    )
                    stats["total_slippage_inr"] = blend.modeled_slippage(orders, panels)
                    run_name = f"{signal_source}__top{top_n}__{period_name}__{int(exposure * 100)}cap__{scenario}"
                    run = OUT / run_name
                    run.mkdir(parents=True, exist_ok=True)
                    equity.reset_index(names="time").to_csv(run / "equity.csv", index=False)
                    orders.to_csv(run / "orders.csv", index=False)
                    risk = ohlc_audit.run_case(
                        run_name, run.relative_to(ROOT).as_posix(), CAPITAL
                    )
                    assert risk["max_close_replay_error_inr"] <= 0.03
                    (run / "summary.json").write_text(json.dumps({
                        "signal_source": signal_source,
                        "strategy": strategy,
                        "top_n": top_n,
                        "period": period_name,
                        "exposure_cap_pct": exposure * 100,
                        "cashflow_scenario": scenario,
                        "claim_status": "unverified secondary-source-only sensitivity",
                        "distribution_claims": [
                            {"symbol": symbol, "ex_date": ex_date.isoformat(), "cash_per_share_inr": amount}
                            for symbol, ex_date, amount in distributions
                        ],
                        "ohlc_audit": risk,
                        **stats,
                    }, indent=2), encoding="utf-8")
                    event_qty = {event["symbol"]: event["eligible_quantity"] for event in stats["cash_distribution_events"]}
                    event_cash = {event["symbol"]: event["cash_inr"] for event in stats["cash_distribution_events"]}
                    credited = float(stats["cash_distributions_inr"])
                    expected_credited = sum(
                        event_qty.get(symbol, 0) * amount for symbol, _, amount in distributions
                    )
                    assert _same(credited, expected_credited, 0.01)
                    assert risk["cash_distributions_credited_inr"] == round(credited, 2)
                    rows.append({
                        "signal_source": signal_source,
                        "strategy": strategy,
                        "top_n": top_n,
                        "period": period_name,
                        "period_start": start.isoformat(),
                        "period_end": end.isoformat(),
                        "exposure_cap_pct": exposure * 100,
                        "slippage_bps_per_side": SLIPPAGE_BPS,
                        "cashflow_scenario": scenario,
                        "claim_status": "unverified secondary-source-only sensitivity",
                        "autobees_claim_per_unit_inr": EVENTS["AUTOBEES"][1],
                        "autobees_claim_ex_date": EVENTS["AUTOBEES"][0].isoformat(),
                        "autobees_eligible_quantity": event_qty.get("AUTOBEES", 0),
                        "autobees_cash_credited_inr": event_cash.get("AUTOBEES", 0.0),
                        "pharmabees_claim_per_unit_inr": EVENTS["PHARMABEES"][1],
                        "pharmabees_claim_ex_date": EVENTS["PHARMABEES"][0].isoformat(),
                        "pharmabees_eligible_quantity": event_qty.get("PHARMABEES", 0),
                        "pharmabees_cash_credited_inr": event_cash.get("PHARMABEES", 0.0),
                        "total_cash_credited_inr": credited,
                        "base_total_return_pct": baseline["total_return_pct"],
                        "scenario_total_return_pct": stats["total_return_pct"],
                        "return_delta_pp": stats["total_return_pct"] - baseline["total_return_pct"],
                        "base_close_mdd_pct": baseline["max_drawdown_pct"],
                        "scenario_close_mdd_pct": stats["max_drawdown_pct"],
                        "close_mdd_delta_pp": stats["max_drawdown_pct"] - baseline["max_drawdown_pct"],
                        "base_ohlc_bound_pct": baseline["simultaneous_ohlc_drawdown_bound_pct"],
                        "scenario_ohlc_bound_pct": risk["simultaneous_ohlc_drawdown_bound_pct"],
                        "ohlc_bound_delta_pp": risk["simultaneous_ohlc_drawdown_bound_pct"] - baseline["simultaneous_ohlc_drawdown_bound_pct"],
                        "within_20pct_under_ohlc": risk["within_20pct_under_bound"],
                        "base_within_20pct_under_ohlc": baseline["within_20pct_under_bound"],
                        "fees_inr": stats["total_fees_inr"],
                        "slippage_cost_inr": stats["total_slippage_inr"],
                        "order_count": stats["order_count"],
                        "max_close_replay_error_inr": risk["max_close_replay_error_inr"],
                        "source_artifact": f"{run.relative_to(ROOT).as_posix()}/summary.json;outputs/sector_distribution_cashflow_sensitivity.csv;work/sensitivity_sector_distribution_cashflow.py",
                    })

    result = pd.DataFrame(rows)
    assert len(result) == 144, f"Expected 144 secondary-only sensitivities; got {len(result)}"
    assert not result.duplicated(["signal_source", "strategy", "period", "exposure_cap_pct", "cashflow_scenario"]).any()
    assert result[["total_cash_credited_inr", "fees_inr", "slippage_cost_inr"]].ge(0).all().all()
    result.to_csv(SUMMARY, index=False)
    print(f"Wrote {len(result)} secondary-only distribution sensitivities with OHLC audits; max replay error={result['max_close_replay_error_inr'].max():.4f}")


if __name__ == "__main__":
    main()
