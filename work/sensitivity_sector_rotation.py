"""Screen monthly 12–1 momentum rotation across saved NSE sector ETF histories."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pandas as pd

import replay_volatility_weighted_blend as blend
import upstox_quant as q


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "work" / "data" / "etf_daily"
OUT = ROOT / "work" / "backtests" / "sector_rotation"
SUMMARY = ROOT / "outputs" / "sector_rotation_sensitivity.csv"
SELECTION = ROOT / "outputs" / "sector_rotation_training_selection.json"
CAPITAL = 1_000_000
DD_LIMIT = 20.0
EXPOSURES = (0.50, 0.75, 0.95, 1.00)
SLIPPAGE = (10, 25, 50, 100)
SECTORS = ("BANKBEES", "ITBEES", "AUTOBEES", "PHARMABEES", "PSUBNKBEES")
ASSETS = {
    "NIFTYBEES": "NSE_EQ_INF204KB14I2-days-1-2014-01-01-2026-10-23.csv",
    "GOLDBEES": "GOLDBEES-days-1-2014-01-01-2026-10-23.csv",
    "BANKBEES": "NSE_EQ_INF204KB15I9-days-1-2014-01-01-2026-10-23.csv",
    "ITBEES": "NSE_EQ_INF204KB15V2-days-1-2014-01-01-2026-10-23.csv",
    "AUTOBEES": "NSE_EQ_INF204KC1337-days-1-2014-01-01-2026-10-23.csv",
    "PHARMABEES": "NSE_EQ_INF204KC1089-days-1-2014-01-01-2026-10-23.csv",
    "PSUBNKBEES": "NSE_EQ_INF204KB16I7-days-1-2014-01-01-2026-10-23.csv",
}
PERIODS = (
    ("train_2022_2023", date(2022, 1, 3), date(2023, 12, 29)),
    ("validation_2024", date(2024, 1, 1), date(2024, 12, 31)),
    ("holdout_2025_plus", date(2025, 1, 1), date(2026, 10, 23)),
    ("continuous_2022_plus", date(2022, 1, 3), date(2026, 10, 23)),
)


def _control_targets(panels: dict[str, pd.DataFrame]) -> tuple[pd.DataFrame, pd.Series]:
    nifty_panels = {name: frame[["NIFTYBEES"]] for name, frame in panels.items()}
    gold_panels = {name: frame[["GOLDBEES"]] for name, frame in panels.items()}
    nifty, nifty_events = q.make_targets(nifty_panels, "donchian55_20")
    gold, gold_events = q.make_targets(gold_panels, "trend200")
    targets = pd.concat([nifty * 0.5, gold * 0.5], axis=1).reindex(columns=panels["close"].columns).fillna(0.0)
    events = nifty_events | gold_events
    month_ends = pd.Series(targets.index, index=targets.index).groupby(targets.index.strftime("%Y-%m")).last()
    events.loc[pd.DatetimeIndex(month_ends.to_list())] = True
    return targets, events


def _equal_weight_targets(panels: dict[str, pd.DataFrame]) -> tuple[pd.DataFrame, pd.Series]:
    targets = pd.DataFrame(0.0, index=panels["close"].index, columns=panels["close"].columns)
    targets[list(SECTORS)] = 1.0 / len(SECTORS)
    events = pd.Series(False, index=targets.index)
    month_ends = pd.Series(targets.index, index=targets.index).groupby(targets.index.strftime("%Y-%m")).last()
    events.loc[pd.DatetimeIndex(month_ends.to_list())] = True
    return targets, events


def _sector_targets(panels: dict[str, pd.DataFrame], top_n: int) -> tuple[pd.DataFrame, pd.Series]:
    sector_panels = {name: frame[list(SECTORS)] for name, frame in panels.items()}
    targets, events = q.make_targets(sector_panels, "momentum12_1", top_n=top_n)
    targets = targets.reindex(columns=panels["close"].columns).fillna(0.0)
    assert (targets >= 0).all().all()
    assert (targets.sum(axis=1) <= 1.0 + 1e-12).all()
    month_ends = pd.Series(targets.index, index=targets.index).groupby(targets.index.strftime("%Y-%m")).last()
    assert events.loc[pd.DatetimeIndex(month_ends.to_list())].all()
    return targets, events


def _validate_targets(targets: pd.DataFrame, events: pd.Series, panels: dict[str, pd.DataFrame]) -> None:
    index = panels["close"].index
    assert targets.index.equals(index) and events.index.equals(index)
    assert targets.columns.equals(panels["close"].columns)
    assert (targets >= 0).all().all()
    assert (targets.sum(axis=1) <= 1.0 + 1e-12).all()


def main() -> None:
    q._self_check()
    files, panels = q._read_prices([f"{name}={DATA / path}" for name, path in ASSETS.items()])
    assert set(files) == set(ASSETS)
    common_sectors = panels["close"].dropna(subset=list(SECTORS))
    first_common = common_sectors.index[0].date()
    last_date = panels["close"].index[-1].date()
    assert first_common == date(2022, 1, 25) and last_date == date(2026, 10, 23)

    portfolios = []
    first_active = {}
    for top_n in (1, 2, 3):
        targets, events = _sector_targets(panels, top_n)
        _validate_targets(targets, events, panels)
        active = targets[list(SECTORS)].sum(axis=1).gt(0)
        first_active[f"sector_momentum12_1_top{top_n}"] = active[active].index[0].date().isoformat() if active.any() else ""
        portfolios.append((f"sector_momentum12_1_top{top_n}", top_n, targets, events))

    control_targets, control_events = _control_targets(panels)
    _validate_targets(control_targets, control_events, panels)
    first_active["nifty_gold_50_50_control"] = ""
    portfolios.append(("nifty_gold_50_50_control", None, control_targets, control_events))

    sector_equal_targets, sector_equal_events = _equal_weight_targets(panels)
    _validate_targets(sector_equal_targets, sector_equal_events, panels)
    first_active["sector_equal_weight_control"] = common_sectors.index[0].date().isoformat()
    portfolios.append(("sector_equal_weight_control", None, sector_equal_targets, sector_equal_events))

    targets = control_targets * 0.5 + sector_equal_targets * 0.5
    events = control_events | sector_equal_events
    _validate_targets(targets, events, panels)
    first_active["sector50_nifty25_gold25_equalweight"] = common_sectors.index[0].date().isoformat()
    portfolios.append(("sector50_nifty25_gold25_equalweight", None, targets, events))

    rows = []
    for strategy, top_n, targets, events in portfolios:
        for period, start, end in PERIODS:
            for exposure in EXPOSURES:
                for slippage in SLIPPAGE:
                    equity, orders, stats = q._simulate(
                        panels, targets, events, CAPITAL, exposure, slippage,
                        "equity_delivery", start, end, DD_LIMIT,
                    )
                    stats["total_slippage_inr"] = blend.modeled_slippage(orders, panels)
                    run = OUT / f"{strategy}__{period}__{int(exposure * 100)}cap__{slippage}bps"
                    run.mkdir(parents=True, exist_ok=True)
                    equity.reset_index(names="time").to_csv(run / "equity.csv", index=False)
                    orders.to_csv(run / "orders.csv", index=False)
                    run_summary = {
                        "strategy": strategy,
                        "top_n": top_n,
                        "period": period,
                        "period_start": start.isoformat(),
                        "period_end": end.isoformat(),
                        "exposure_cap_pct": exposure * 100,
                        "slippage_bps_per_side": slippage,
                        "first_active_date": first_active[strategy],
                        **stats,
                    }
                    (run / "summary.json").write_text(json.dumps(run_summary, indent=2), encoding="utf-8")
                    rows.append({
                        "strategy": strategy,
                        "top_n": "" if top_n is None else top_n,
                        "period": period,
                        "period_start": start.isoformat(),
                        "period_end": end.isoformat(),
                        "first_active_date": first_active[strategy],
                        "exposure_cap_pct": exposure * 100,
                        "slippage_bps_per_side": slippage,
                        "starting_balance_inr": stats["starting_balance_inr"],
                        "ending_balance_inr": stats["ending_balance_inr"],
                        "total_return_pct": stats["total_return_pct"],
                        "cagr_pct": stats["cagr_pct"],
                        "max_drawdown_pct": stats["max_drawdown_pct"],
                        "sharpe_zero_rf": stats["sharpe_zero_rf"],
                        "average_gross_exposure_pct": stats["average_gross_exposure_pct"],
                        "order_count": stats["order_count"],
                        "fees_inr": stats["total_fees_inr"],
                        "slippage_cost_inr": stats["total_slippage_inr"],
                        "within_20pct": stats["within_drawdown_limit"],
                        "source_artifact": f"{run.relative_to(ROOT).as_posix()}/summary.json",
                    })

    expected = (3 + 3) * len(PERIODS) * len(EXPOSURES) * len(SLIPPAGE)
    assert len(rows) == expected == 384
    keys = [(r["strategy"], r["period"], r["exposure_cap_pct"], r["slippage_bps_per_side"]) for r in rows]
    assert len(keys) == len(set(keys))
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    result = pd.DataFrame(rows)
    result.to_csv(SUMMARY, index=False)

    train = result[(result.period == "train_2022_2023") & (result.slippage_bps_per_side == 50)]
    feasible = train[train.max_drawdown_pct >= -DD_LIMIT]
    assert not feasible.empty
    selected = feasible.sort_values("cagr_pct", ascending=False).iloc[0]
    selection = {
        "selection_cost_bps_per_side": 50,
        "training_period": "train_2022_2023",
        "criterion": "highest training CAGR among the fixed candidate grid with training maximum drawdown no worse than 20%",
        "selected_strategy": selected.strategy,
        "selected_top_n": int(selected.top_n) if pd.notna(selected.top_n) else None,
        "selected_exposure_cap_pct": float(selected.exposure_cap_pct),
        "training_result": selected.to_dict(),
        "same_rule_validation_holdout_full": result[
            (result.strategy == selected.strategy)
            & (result.exposure_cap_pct == selected.exposure_cap_pct)
            & (result.slippage_bps_per_side == 50)
            & result.period.isin(["validation_2024", "holdout_2025_plus", "continuous_2022_plus"])
        ].to_dict("records"),
        "caveat": "All later-period history was previously inspected; these results are not a strict lockbox or live-performance evidence.",
    }
    SELECTION.write_text(json.dumps(selection, indent=2, default=str), encoding="utf-8")
    print(f"cases={len(rows)} common_sector_sessions={len(common_sectors)} first_common={first_common} selected={selected.strategy} cap={selected.exposure_cap_pct:g}%")


if __name__ == "__main__":
    main()
