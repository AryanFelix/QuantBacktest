"""Compare fixed and trailing-volatility weights for the NIFTY/Gold trend blend."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pandas as pd

import upstox_quant as q


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "work" / "data" / "etf_daily"
OUT = ROOT / "work" / "backtests" / "volatility_weighted_blend"
CAPITAL = 1_000_000
SLIPPAGE = (10, 50)


def make_portfolios(data_specs: list[str] | None = None):
    specs = data_specs if data_specs is not None else [
        f"NIFTYBEES={DATA / 'NSE_EQ_INF204KB14I2-days-1-2014-01-01-2026-10-23.csv'}",
        f"GOLDBEES={DATA / 'GOLDBEES-days-1-2014-01-01-2026-10-23.csv'}",
    ]
    files, panels = q._read_prices(specs)
    nifty, nifty_events = q.make_targets(
        {key: value[["NIFTYBEES"]] for key, value in panels.items()}, "donchian55_20"
    )
    gold, gold_events = q.make_targets(
        {key: value[["GOLDBEES"]] for key, value in panels.items()}, "trend200"
    )
    active = pd.concat([
        nifty.rename(columns={"NIFTYBEES": "NIFTYBEES"}),
        gold.rename(columns={"GOLDBEES": "GOLDBEES"}),
    ], axis=1).reindex(columns=["NIFTYBEES", "GOLDBEES"]).fillna(0.0)
    signal_events = nifty_events.reindex(active.index).fillna(False) | gold_events.reindex(active.index).fillna(False)
    month_ends = pd.Series(active.index, index=active.index).groupby(active.index.strftime("%Y-%m")).last()
    quarter_ends = pd.Series(active.index, index=active.index).groupby(active.index.tz_localize(None).to_period("Q")).last()
    monthly_events = signal_events.copy()
    monthly_events.loc[pd.DatetimeIndex(month_ends.to_list())] = True
    quarterly_events = signal_events.copy()
    quarterly_events.loc[pd.DatetimeIndex(quarter_ends.to_list())] = True
    event_sets = {"monthly": monthly_events, "quarterly": quarterly_events}
    fixed = active * 0.5
    volatility = pd.DataFrame({
        name: series.dropna().pct_change().rolling(63, min_periods=63).std() * (252 ** 0.5)
        for name, series in panels["close"].items()
    }).reindex(active.index)
    portfolios, portfolio_events = {}, {}
    for frequency, events in event_sets.items():
        suffix = "" if frequency == "monthly" else "_quarterly"
        portfolios[f"fixed_50_50{suffix}"] = fixed
        portfolio_events[f"fixed_50_50{suffix}"] = events
        weighted = pd.DataFrame(0.0, index=active.index, columns=active.columns)
        state = pd.Series(0.0, index=active.columns)
        for i, timestamp in enumerate(active.index):
            if events.iloc[i]:
                on = active.iloc[i] > 0
                names = list(active.columns[on])
                state[:] = 0.0
                if len(names) == 1:
                    state.loc[names[0]] = 0.5
                elif len(names) == 2:
                    vols = volatility.loc[timestamp, names]
                    if vols.isna().any() or (vols <= 0).any():
                        weights = pd.Series(0.5, index=names)
                    else:
                        inverse = 1.0 / vols
                        weights = inverse / inverse.sum()
                    state.loc[names] = weights
            weighted.iloc[i] = state
        name = f"inverse_vol_63d{suffix}"
        portfolios[name] = weighted
        portfolio_events[name] = events

    assert list(fixed.columns) == ["NIFTYBEES", "GOLDBEES"]
    assert (fixed.sum(axis=1) <= 1.0 + 1e-12).all()
    for frequency, events in event_sets.items():
        suffix = "" if frequency == "monthly" else "_quarterly"
        weighted = portfolios[f"inverse_vol_63d{suffix}"]
        assert (weighted.sum(axis=1) <= 1.0 + 1e-12).all()
        both = active.gt(0).all(axis=1) & events
        if both.any():
            probe = volatility.loc[active.index[both][0]]
            if probe.notna().all() and (probe > 0).all():
                assert abs(float(weighted.loc[probe.name].sum()) - 1.0) < 1e-12
        one = active.gt(0).sum(axis=1).eq(1) & events
        assert (weighted.loc[one].sum(axis=1) == 0.5).all()
    assert monthly_events.loc[pd.DatetimeIndex(month_ends.to_list())].all()
    assert quarterly_events.loc[pd.DatetimeIndex(quarter_ends.to_list())].all()
    return files, panels, portfolios, portfolio_events


def single_sleeve_weight_targets(targets: pd.DataFrame, weight: float) -> pd.DataFrame:
    if not 0.0 <= weight <= 1.0:
        raise ValueError("single-sleeve weight must be between 0 and 1")
    adjusted = targets.copy()
    solo = targets.gt(0).sum(axis=1).eq(1) & targets.sum(axis=1).between(0.5 - 1e-12, 0.5 + 1e-12)
    for timestamp in targets.index[solo]:
        name = targets.loc[timestamp].idxmax()
        adjusted.loc[timestamp, name] = weight
    assert (adjusted.sum(axis=1) <= 1.0 + 1e-12).all()
    assert (adjusted.loc[~solo].sub(targets.loc[~solo]).abs().to_numpy() < 1e-12).all()
    assert (adjusted.loc[solo].sum(axis=1) - weight).abs().lt(1e-12).all()
    return adjusted


def trailing_volatility_throttle_targets(
    targets: pd.DataFrame, events: pd.Series, base_returns: pd.Series, target_volatility: float
) -> pd.DataFrame:
    if not 0.0 < target_volatility <= 1.0:
        raise ValueError("target volatility must be between 0 and 1")
    realized_vol = base_returns.rolling(63, min_periods=63).std(ddof=1) * (252**0.5)
    adjusted = targets.copy()
    scale = 1.0
    for i, timestamp in enumerate(targets.index):
        if bool(events.iloc[i]):
            volatility = realized_vol.loc[timestamp]
            if pd.notna(volatility) and volatility > 0:
                scale = min(1.0, target_volatility / float(volatility))
        adjusted.iloc[i] = targets.iloc[i] * scale
    assert (adjusted.sum(axis=1) <= targets.sum(axis=1) + 1e-12).all()
    return adjusted


def modeled_slippage(orders: pd.DataFrame, panels: dict[str, pd.DataFrame]) -> float:
    total = 0.0
    for order in orders.itertuples(index=False):
        terminal = getattr(order, "terminal_liquidation", False)
        source = panels["close"] if pd.notna(terminal) and bool(terminal) else panels["open"]
        raw = source.loc[order.time, order.symbol]
        if pd.notna(raw):
            total += int(order.quantity) * abs(float(order.fill_price) - float(raw))
    return total


def main():
    files, panels, portfolios, portfolio_events = make_portfolios()
    OUT.mkdir(parents=True, exist_ok=True)
    end = panels["close"].index[-1].date()
    periods = [
        ("train_2014_2019", date(2014, 1, 1), date(2019, 12, 31)),
        ("validation_2020_2022", date(2020, 1, 1), date(2022, 12, 31)),
        ("holdout_2023_plus", date(2023, 1, 1), end),
        ("full_2020_plus", date(2020, 1, 1), end),
        ("full_2014_plus", date(2014, 1, 1), end),
    ]
    rows = []
    for name, targets in portfolios.items():
        events = portfolio_events[name]
        for period, start, finish in periods:
            for slip in SLIPPAGE:
                equity, orders, stats = q._simulate(
                    panels, targets, events, CAPITAL, 1.0, slip,
                    "equity_delivery", start, finish, 20,
                )
                stats["total_slippage_inr"] = modeled_slippage(orders, panels)
                key = f"{name}__{period}__{slip}bps"
                run = OUT / key
                run.mkdir(exist_ok=True)
                equity.to_csv(run / "equity.csv", index_label="time")
                orders.to_csv(run / "orders.csv", index=False)
                rows.append({
                    "portfolio": name, "period": period,
                    "period_start": start.isoformat(), "period_end": finish.isoformat(),
                    "slippage_bps_per_side": slip, "exposure_cap_pct": 100,
                    **stats,
                })
    pd.DataFrame(rows).to_csv(OUT / "summary.csv", index=False)
    pd.DataFrame(rows).to_csv(ROOT / "outputs" / "volatility_weighted_blend_screen.csv", index=False)
    for frequency in ("monthly", "quarterly"):
        suffix = "" if frequency == "monthly" else "_quarterly"
        name = f"inverse_vol_63d{suffix}"
        weights = portfolios[name].copy()
        weights.insert(0, "rebalance", portfolio_events[name])
        weights.to_csv(OUT / f"daily_weights_inverse_vol_63d_{frequency}.csv", index_label="time")
    (OUT / "strategy.json").write_text(json.dumps({
        "capital_inr": CAPITAL,
        "baseline": "50% NIFTYBEES Donchian 55/20 + 50% GOLDBEES 200DMA while their signals are active",
        "challenger": "63-session inverse-volatility split when both sleeves are active; 50% gross when only one is active; otherwise cash",
        "volatility_input": "trailing 63-session sample standard deviation of daily close-to-close returns, annualized by sqrt(252)",
        "rebalances": "compare monthly and quarterly schedules, each with immediate signal changes; weights use data through signal close; next-session-open fills",
        "slippage_bps_per_side": list(SLIPPAGE),
        "current_fee_schedule_applied_uniformly": True,
        "cash_return_pct": 0,
        "data_end": end.isoformat(),
        "source_data": {name: f"{frame.index[0].date()} to {frame.index[-1].date()}" for name, frame in files.items()},
    }, indent=2), encoding="utf-8")
    print(json.dumps({"output": str(OUT), "scenarios": len(rows), "portfolio_schedules": len(portfolios)}, indent=2))


if __name__ == "__main__":
    main()
