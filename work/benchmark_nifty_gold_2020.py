"""Compare the rolling NIFTY/Gold rule with passive allocations on the same test dates."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pandas as pd

import audit_etf_intraday_drawdown as audit
import replay_volatility_weighted_blend as blend
import upstox_quant as q


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "work" / "backtests" / "nifty_gold_2020_benchmarks"
SUMMARY = ROOT / "outputs" / "nifty_gold_2020_benchmarks.csv"
FULL_OUT = ROOT / "work" / "backtests" / "nifty_gold_full_history_benchmarks"
FULL_SUMMARY = ROOT / "outputs" / "nifty_gold_full_history_benchmarks.csv"
COMMON_OUT = ROOT / "work" / "backtests" / "nifty_gold_common_history_benchmarks"
COMMON_SUMMARY = ROOT / "outputs" / "nifty_gold_common_history_benchmarks.csv"
WALK_FORWARD = ROOT / "outputs" / "nifty_gold_walk_forward.csv"
CAPITAL = 1_000_000.0
EXPOSURE_CAP = 0.45
SLIPPAGE_BPS = 50.0
START = date(2020, 1, 1)
NIFTYBEES_DISTRIBUTIONS = [
    ("NIFTYBEES", date(2014, 3, 10), 0.70),
    ("NIFTYBEES", date(2015, 2, 18), 0.80),
]


def _save_run(path: Path, equity: pd.DataFrame, orders: pd.DataFrame) -> str:
    path.mkdir(parents=True, exist_ok=True)
    equity.to_csv(path / "equity.csv", index_label="time")
    orders.to_csv(path / "orders.csv", index=False)
    return str(path.relative_to(ROOT))


def _passive_targets(panels: dict[str, pd.DataFrame], weights: dict[str, float]):
    targets = pd.DataFrame(0.0, index=panels["close"].index, columns=panels["close"].columns)
    events = pd.Series(False, index=targets.index)
    for symbol, weight in weights.items():
        targets[symbol] = weight
        valid = panels["open"][symbol].notna() & panels["close"][symbol].notna()
        assert valid.any(), f"No executable history for passive benchmark: {symbol}"
        first_bar = valid[valid].index[0]
        events.loc[first_bar] = True
    assert (targets.sum(axis=1) <= 1.0 + 1e-12).all()
    assert 0 < int(events.sum()) <= len(weights)
    return targets, events


def _quarterly_static_targets(panels: dict[str, pd.DataFrame]):
    index = panels["close"].index
    quarter_ends = pd.Series(index, index=index).groupby(index.tz_localize(None).to_period("Q")).last()
    targets = pd.DataFrame(0.5, index=index, columns=panels["close"].columns)
    events = pd.Series(False, index=index)
    events.loc[pd.DatetimeIndex(quarter_ends.to_list())] = True
    for symbol in targets.columns:
        events.loc[panels["open"][symbol].dropna().index[0]] = True
    assert events.any() and (targets.sum(axis=1) == 1.0).all()
    return targets, events


def _run(
    name: str,
    targets: pd.DataFrame,
    events: pd.Series,
    panels: dict[str, pd.DataFrame],
    end: date,
    start: date = START,
    run_dir: Path = OUT,
    cash_distributions: list[tuple[str, date, float]] | None = None,
    exposure_cap: float = EXPOSURE_CAP,
    slippage_bps: float = SLIPPAGE_BPS,
) -> dict:
    equity, orders, stats = q._simulate(
        panels, targets, events, CAPITAL, exposure_cap, slippage_bps,
        "equity_delivery", start, end, 20.0, cash_distributions=cash_distributions,
    )
    stats["total_slippage_inr"] = blend.modeled_slippage(orders, panels)
    relative = _save_run(run_dir / name, equity, orders)
    risk = audit.run_case(name, relative)
    assert risk["max_close_replay_error_inr"] <= 0.03
    return {
        "strategy": name,
        "period_start": stats["first_bar"][:10],
        "period_end": stats["last_bar"][:10],
        "sessions": len(equity),
        "starting_balance_inr": CAPITAL,
        "ending_balance_inr": stats["ending_balance_inr"],
        "total_return_pct": stats["total_return_pct"],
        "cagr_pct": stats["cagr_pct"],
        "close_mdd_pct": risk["close_max_drawdown_pct"],
        "ohlc_drawdown_bound_pct": risk["simultaneous_ohlc_drawdown_bound_pct"],
        "within_20pct_ohlc": risk["within_20pct_under_bound"],
        "total_fees_inr": stats["total_fees_inr"],
        "total_slippage_inr": stats["total_slippage_inr"],
        "cash_distributions_inr": stats["cash_distributions_inr"],
        "order_count": stats["order_count"],
        "max_close_replay_error_inr": risk["max_close_replay_error_inr"],
        "gross_exposure_cap_pct": exposure_cap * 100,
        "slippage_bps_per_side": slippage_bps,
    }


def _annual_sequence_row(role: str, sequence: pd.DataFrame) -> dict:
    sequence = sequence.sort_values("test_year")
    final = sequence.iloc[-1]
    sessions = int(sequence["sessions"].sum())
    years = max(sessions / 252, 1 / 252)
    return {
        "strategy": role,
        "period_start": sequence.iloc[0]["test_start"],
        "period_end": final["test_end"],
        "sessions": sessions,
        "starting_balance_inr": CAPITAL,
        "ending_balance_inr": final["ending_balance_inr"],
        "total_return_pct": (float(final["ending_balance_inr"]) / CAPITAL - 1) * 100,
        "cagr_pct": (float(final["ending_balance_inr"]) / CAPITAL) ** (1 / years) * 100 - 100,
        "close_mdd_pct": final["stitched_close_mdd_pct"],
        "ohlc_drawdown_bound_pct": final["ohlc_bound_pct"],
        "within_20pct_ohlc": bool(final["within_20pct_ohlc"]),
        "total_fees_inr": float(sequence["total_fees_inr"].sum()),
        "total_slippage_inr": float(sequence["total_slippage_inr"].sum()),
        "order_count": int(sequence["order_count"].sum()),
        "max_close_replay_error_inr": float(sequence["max_close_replay_error_inr"].max()),
        "gross_exposure_cap_pct": EXPOSURE_CAP * 100,
        "slippage_bps_per_side": SLIPPAGE_BPS,
    }


def main() -> None:
    _, panels, portfolios, events = blend.make_portfolios()
    data_end = panels["close"].index[-1].date()
    static_targets, static_events = _quarterly_static_targets(panels)
    walk_forward = pd.read_csv(WALK_FORWARD)
    assert walk_forward["test_end"].max() == data_end.isoformat()
    rows = [
        _annual_sequence_row(role, group)
        for role, group in walk_forward.groupby("role", sort=False)
    ]

    for name, weights in (
        ("passive_NIFTYBEES_45pct", {"NIFTYBEES": 1.0}),
        ("passive_GOLDBEES_45pct", {"GOLDBEES": 1.0}),
        ("passive_NIFTY_Gold_22_5pct_each", {"NIFTYBEES": 0.5, "GOLDBEES": 0.5}),
    ):
        targets, rebalance = _passive_targets(panels, weights)
        rows.append(_run(name, targets, rebalance, panels, data_end))

    rows.append(_run(
        "quarterly_D55_20_fixed_45pct",
        portfolios["fixed_50_50_quarterly"],
        events["fixed_50_50_quarterly"],
        panels,
        data_end,
    ))
    rows.append(_run(
        "quarterly_static_50_50_45pct",
        static_targets,
        static_events,
        panels,
        data_end,
    ))
    result = pd.DataFrame(rows)
    assert len(result) == 7 and result["strategy"].is_unique
    assert result["period_end"].eq(data_end.isoformat()).all()
    assert result["max_close_replay_error_inr"].max() <= 0.03
    result.to_csv(SUMMARY, index=False)

    full_start = panels["close"].index[0].date()
    assert full_start == date(2014, 1, 1)
    full_rows = []
    for name, weights in (
        ("passive_NIFTYBEES_45pct", {"NIFTYBEES": 1.0}),
        ("passive_GOLDBEES_45pct", {"GOLDBEES": 1.0}),
        ("passive_NIFTY_Gold_22_5pct_each", {"NIFTYBEES": 0.5, "GOLDBEES": 0.5}),
    ):
        targets, rebalance = _passive_targets(panels, weights)
        full_rows.append(_run(
            name, targets, rebalance, panels, data_end,
            start=full_start, run_dir=FULL_OUT,
            cash_distributions=NIFTYBEES_DISTRIBUTIONS,
        ))
    full_rows.append(_run(
        "quarterly_D55_20_fixed_45pct",
        portfolios["fixed_50_50_quarterly"],
        events["fixed_50_50_quarterly"],
        panels,
        data_end,
        start=full_start,
        run_dir=FULL_OUT,
        cash_distributions=NIFTYBEES_DISTRIBUTIONS,
    ))
    full_rows.append(_run(
        "quarterly_static_50_50_45pct",
        static_targets,
        static_events,
        panels,
        data_end,
        start=full_start,
        run_dir=FULL_OUT,
        cash_distributions=NIFTYBEES_DISTRIBUTIONS,
    ))
    full_result = pd.DataFrame(full_rows)
    assert len(full_result) == 5 and full_result["strategy"].is_unique
    assert full_result["period_start"].eq(full_start.isoformat()).all()
    assert full_result["period_end"].eq(data_end.isoformat()).all()
    assert full_result["max_close_replay_error_inr"].max() <= 0.03
    active = full_result.loc[full_result.strategy == "quarterly_D55_20_fixed_45pct"].iloc[0]
    assert float(active["cash_distributions_inr"]) == 0.0, "active rule unexpectedly held NIFTYBEES on a known ex-date"
    static = full_result.loc[full_result.strategy == "quarterly_static_50_50_45pct"].iloc[0]
    assert float(static["cash_distributions_inr"]) > 0
    assert full_result.loc[
        full_result.strategy.isin(["passive_NIFTYBEES_45pct", "passive_NIFTY_Gold_22_5pct_each"]),
        "cash_distributions_inr",
    ].gt(0).all()
    full_result.to_csv(FULL_SUMMARY, index=False)

    common_start = date(2015, 1, 2)
    common_rows = []
    for name, weights in (
        ("passive_NIFTYBEES_45pct", {"NIFTYBEES": 1.0}),
        ("passive_GOLDBEES_45pct", {"GOLDBEES": 1.0}),
        ("passive_NIFTY_Gold_22_5pct_each", {"NIFTYBEES": 0.5, "GOLDBEES": 0.5}),
    ):
        targets, rebalance = _passive_targets(panels, weights)
        common_rows.append(_run(
            name, targets, rebalance, panels, data_end,
            start=common_start, run_dir=COMMON_OUT,
            cash_distributions=NIFTYBEES_DISTRIBUTIONS,
        ))
    common_rows.append(_run(
        "quarterly_D55_20_fixed_45pct",
        portfolios["fixed_50_50_quarterly"],
        events["fixed_50_50_quarterly"],
        panels,
        data_end,
        start=common_start,
        run_dir=COMMON_OUT,
        cash_distributions=NIFTYBEES_DISTRIBUTIONS,
    ))
    common_rows.append(_run(
        "quarterly_static_50_50_45pct",
        static_targets,
        static_events,
        panels,
        data_end,
        start=common_start,
        run_dir=COMMON_OUT,
        cash_distributions=NIFTYBEES_DISTRIBUTIONS,
    ))
    common_result = pd.DataFrame(common_rows)
    assert len(common_result) == 5 and common_result["strategy"].is_unique
    assert common_result["period_start"].eq(common_start.isoformat()).all()
    assert common_result["period_end"].eq(data_end.isoformat()).all()
    assert common_result["max_close_replay_error_inr"].max() <= 0.03
    assert common_result.loc[
        common_result.strategy.isin(["passive_NIFTYBEES_45pct", "passive_NIFTY_Gold_22_5pct_each"]),
        "cash_distributions_inr",
    ].gt(0).all()
    common_result.to_csv(COMMON_SUMMARY, index=False)
    print(json.dumps({
        "period": [result["period_start"].min(), data_end.isoformat()],
        "initial_capital_inr": CAPITAL,
        "exposure_cap_pct": EXPOSURE_CAP * 100,
        "slippage_bps_per_side": SLIPPAGE_BPS,
        "results": result[["strategy", "ending_balance_inr", "total_return_pct", "close_mdd_pct", "ohlc_drawdown_bound_pct"]].to_dict("records"),
        "summary": str(SUMMARY.relative_to(ROOT)),
        "full_history_period": [full_start.isoformat(), data_end.isoformat()],
        "full_history_results": full_result[["strategy", "ending_balance_inr", "total_return_pct", "close_mdd_pct", "ohlc_drawdown_bound_pct", "cash_distributions_inr"]].to_dict("records"),
        "full_history_summary": str(FULL_SUMMARY.relative_to(ROOT)),
        "common_history_period": [common_start.isoformat(), data_end.isoformat()],
        "common_history_results": common_result[["strategy", "ending_balance_inr", "total_return_pct", "close_mdd_pct", "ohlc_drawdown_bound_pct", "cash_distributions_inr"]].to_dict("records"),
        "common_history_summary": str(COMMON_SUMMARY.relative_to(ROOT)),
    }, indent=2))


if __name__ == "__main__":
    main()
