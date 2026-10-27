"""Replay fixed-weight NIFTY/Gold and NIFTY/sector/Gold ETF composites."""

from __future__ import annotations

import csv
import json
import os
import tempfile
from datetime import date
from pathlib import Path

import pandas as pd

import upstox_quant as q


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "work" / "data" / "etf_daily"
OUT = ROOT / "work" / "backtests" / "nifty_sector_gold_composites"
CAPITAL = 1_000_000
SLIPPAGE = (10, 20, 50)
EXPOSURES = (0.50, 0.75, 0.95, 1.00)
PERIODS = (("2020_plus", date(2020, 1, 1)), ("recent", date(2023, 1, 1)))
ASSETS = {
    "NIFTYBEES": "NSE_EQ_INF204KB14I2-days-1-2014-01-01-2026-10-23.csv",
    "BANKBEES": "NSE_EQ_INF204KB15I9-days-1-2014-01-01-2026-10-23.csv",
    "ITBEES": "NSE_EQ_INF204KB15V2-days-1-2014-01-01-2026-10-23.csv",
    "AUTOBEES": "NSE_EQ_INF204KC1337-days-1-2014-01-01-2026-10-23.csv",
    "PHARMABEES": "NSE_EQ_INF204KC1089-days-1-2014-01-01-2026-10-23.csv",
    "PSUBNKBEES": "NSE_EQ_INF204KB16I7-days-1-2014-01-01-2026-10-23.csv",
    "JUNIORBEES": "NSE_EQ_INF732E01045-days-1-2014-01-01-2026-10-23.csv",
    "GOLDBEES": "GOLDBEES-days-1-2014-01-01-2026-10-23.csv",
}


def _atomic_csv(path: Path, rows: list[dict], fields: list[str] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = fields or list(dict.fromkeys(key for row in rows for key in row))
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", newline="", delete=False, dir=path.parent, suffix=".tmp") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
        temporary = Path(handle.name)
    os.replace(temporary, path)


def _build_portfolios():
    specifications = [f"{symbol}={DATA / filename}" for symbol, filename in ASSETS.items()]
    files, panels = q._read_prices(specifications)
    index_panels = {field: frame[["NIFTYBEES"]] for field, frame in panels.items()}
    gold_panels = {field: frame[["GOLDBEES"]] for field, frame in panels.items()}
    sectors = ["BANKBEES", "ITBEES", "AUTOBEES", "PHARMABEES", "PSUBNKBEES", "JUNIORBEES"]
    sector_panels = {field: frame[sectors] for field, frame in panels.items()}
    index_targets, index_events = q.make_targets(index_panels, "donchian55_20")
    gold_targets, gold_events = q.make_targets(gold_panels, "trend200")
    sector_targets, sector_events = q.make_targets(sector_panels, "momentum12_1", top_n=3)

    portfolios = {}
    for name, weights in (("nifty_gold_50_50", {"NIFTYBEES": 0.5, "GOLDBEES": 0.5}),
                          ("nifty_sector_gold_50_25_25", {"NIFTYBEES": 0.5, "SECTOR": 0.25, "GOLDBEES": 0.25})):
        parts = [index_targets.mul(weights["NIFTYBEES"])]
        if "SECTOR" in weights:
            parts.append(sector_targets.mul(weights["SECTOR"]))
        parts.append(gold_targets.mul(weights["GOLDBEES"]))
        targets = pd.concat(parts, axis=1).reindex(columns=list(ASSETS)).fillna(0.0)
        events = index_events.reindex(targets.index).fillna(False) | gold_events.reindex(targets.index).fillna(False)
        if "SECTOR" in weights:
            events |= sector_events.reindex(targets.index).fillna(False)
        month_ends = pd.Series(targets.index, index=targets.index).groupby(targets.index.strftime("%Y-%m")).last()
        month_end_dates = pd.DatetimeIndex(month_ends.to_list())
        events.loc[month_end_dates] = True
        assert targets.columns.tolist() == list(ASSETS)
        assert (targets >= 0).all().all() and (targets.sum(axis=1) <= 1.0 + 1e-12).all()
        assert events.loc[month_end_dates].all()
        portfolios[name] = (targets, events)
    return files, panels, portfolios


def _modeled_slippage(orders: pd.DataFrame, panels: dict[str, pd.DataFrame]) -> float:
    total = 0.0
    for order in orders.itertuples(index=False):
        terminal = getattr(order, "terminal_liquidation", False)
        source = panels["close"] if pd.notna(terminal) and bool(terminal) else panels["open"]
        raw = source.loc[order.time, order.symbol]
        if pd.notna(raw):
            total += int(order.quantity) * abs(float(order.fill_price) - float(raw))
    return total


def _write_manifest() -> None:
    path = ROOT / "outputs" / "data_manifest.csv"
    with path.open(encoding="utf-8-sig", newline="") as handle:
        manifest = list(csv.DictReader(handle))
    fields = list(manifest[0])
    descriptions = [
        ("Fixed ETF composite replay summary", "NIFTYBEES/GOLDBEES/sector ETFs", "scenario summary", "work/backtests/nifty_sector_gold_composites/scenario_summary.csv", "Fixed weights and 50/75/95/100% exposure caps; 10/20/50 bps per-side slippage."),
        ("Fixed ETF composite daily equity", "NIFTYBEES/GOLDBEES/sector ETFs", "daily marks", "work/backtests/nifty_sector_gold_composites/equity.csv", "Detailed close-marked NAV for 95% and 100% exposure at baseline slippage."),
        ("Fixed ETF composite orders", "NIFTYBEES/GOLDBEES/sector ETFs", "order ledger", "work/backtests/nifty_sector_gold_composites/orders.csv", "Signal and month-end rebalances with modeled fill and fee components."),
        ("Fixed ETF composite assumptions", "NIFTYBEES/GOLDBEES/sector ETFs", "method and data", "work/backtests/nifty_sector_gold_composites/summary.json", "Run parameters, data ranges, and all fixed scenarios."),
        ("Fixed ETF composite replay method", "NIFTYBEES/GOLDBEES/sector ETFs", "method note", "work/research/nifty_sector_gold_replay_method.md", "Fixed-weight replay specification and data limitations."),
    ]
    rows = [{"dataset": dataset, "ticker": ticker, "instrument_key": "", "bar_interval": interval,
             "first_bar": "2020-01-01", "last_bar": "2026-10-23", "bar_count": "", "file_count": "1",
             "empty_files": "0", "cache_paths": cache_path, "purpose": "Compare fixed ETF composite strategies under the 20% drawdown screen", "notes": notes}
            for dataset, ticker, interval, cache_path, notes in descriptions]
    row_paths = {row["cache_paths"] for row in rows}
    manifest = [row for row in manifest if row["cache_paths"] not in row_paths]
    _atomic_csv(path, manifest + rows, fields)


def _write_backtest_summary(rows: list[dict]) -> None:
    path = ROOT / "outputs" / "backtest_summary.csv"
    with path.open(encoding="utf-8-sig", newline="") as handle:
        existing = list(csv.DictReader(handle))
    fields = list(existing[0])
    strategy_ids = {"nifty_gold_50_50_clean_replay", "nifty_sector_gold_50_25_25_clean_replay"}
    existing = [row for row in existing if row["strategy"] not in strategy_ids]
    for row in rows:
        if row["slippage_bps_per_side"] != 10 or row["exposure_cap_pct"] not in {95.0, 100.0}:
            continue
        stats = row["stats"]
        strategy = f"{row['portfolio']}_clean_replay"
        existing.append({
            "simulation_type": "fixed_rule_composite_replay", "strategy": strategy, "universe": row["universe"],
            "period": row["period"], "period_start": row["period_start"], "period_end": row["period_end"],
            "starting_balance_inr": CAPITAL, "ending_balance_inr": stats["ending_balance_inr"],
            "total_return_pct": stats["total_return_pct"], "cagr_pct": stats["cagr_pct"],
            "max_drawdown_pct": stats["max_drawdown_pct"], "sharpe_zero_rf": stats["sharpe_zero_rf"],
            "gross_exposure_cap_pct": row["exposure_cap_pct"], "slippage_bps_per_side": row["slippage_bps_per_side"],
            "fees_inr": stats["total_fees_inr"], "slippage_cost_inr": row["slippage_inr"],
            "trade_count": "", "order_count": stats["order_count"], "within_20pct": stats["within_drawdown_limit"],
            "selection_or_sizing": "Fixed sleeve weights and fixed exposure cap; no cap chosen from this screen.",
            "source_artifact": "work/backtests/nifty_sector_gold_composites/scenario_summary.csv",
            "notes": "Current Upstox charges applied uniformly; surviving sector ETF universe; ETF distributions and total return not reconciled.",
        })
    _atomic_csv(path, existing, fields)


def main() -> None:
    q._self_check()
    files, panels, portfolios = _build_portfolios()
    last_date = panels["close"].index[-1].date()
    scenarios = []
    equity_rows = []
    order_rows = []
    for portfolio, (targets, events) in portfolios.items():
        for period, start in PERIODS:
            for exposure in EXPOSURES:
                for slippage in SLIPPAGE:
                    equity, orders, stats = q._simulate(
                        panels, targets, events, CAPITAL, exposure, slippage,
                        "equity_delivery", start, last_date, 20,
                    )
                    slip_cost = _modeled_slippage(orders, panels)
                    scenario = {
                        "portfolio": portfolio, "period": period, "period_start": start.isoformat(),
                        "period_end": last_date.isoformat(), "exposure_cap_pct": exposure * 100,
                        "slippage_bps_per_side": slippage, "slippage_inr": slip_cost,
                        "universe": ",".join(ASSETS), "stats": stats,
                    }
                    scenarios.append(scenario)
                    if slippage == 10 and exposure in {0.95, 1.0}:
                        equity_rows.extend({"portfolio": portfolio, "period": period, "exposure_cap_pct": exposure * 100,
                                            **record} for record in equity.reset_index().rename(columns={"index": "time"}).to_dict("records"))
                        order_rows.extend({"portfolio": portfolio, "period": period, "exposure_cap_pct": exposure * 100,
                                           **record} for record in orders.to_dict("records"))
    assert len(scenarios) == len(portfolios) * len(PERIODS) * len(EXPOSURES) * len(SLIPPAGE) == 48
    rows = []
    for scenario in scenarios:
        row = {key: value for key, value in scenario.items() if key != "stats"}
        row.update(scenario["stats"])
        row["fees_by_component_inr"] = json.dumps(row["fees_by_component_inr"], sort_keys=True)
        rows.append(row)
    OUT.mkdir(parents=True, exist_ok=True)
    _atomic_csv(OUT / "scenario_summary.csv", rows)
    _atomic_csv(OUT / "equity.csv", equity_rows)
    _atomic_csv(OUT / "orders.csv", order_rows)
    summary = {
        "registered_method": "work/research/nifty_sector_gold_replay_method.md",
        "capital_inr": CAPITAL, "data_end": last_date.isoformat(), "exposure_caps_pct": [x * 100 for x in EXPOSURES],
        "slippage_bps_per_side": list(SLIPPAGE),
        "data_ranges": {symbol: {"first": str(frame.index[0].date()), "last": str(frame.index[-1].date()), "rows": len(frame)} for symbol, frame in files.items()},
        "sector_universe": ["BANKBEES", "ITBEES", "AUTOBEES", "PHARMABEES", "PSUBNKBEES", "JUNIORBEES"],
        "scenarios": scenarios,
        "limits": ["Both periods were inspected in prior research and are retrospective.", "The sector ETF universe has survivor and unequal-inception bias.", "ETF cash distributions are not fully reconciled.", "Current Upstox equity fees are applied uniformly over history; slippage is modeled."],
    }
    (OUT / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    _write_manifest()
    _write_backtest_summary(scenarios)
    for row in scenarios:
        if row["slippage_bps_per_side"] == 10 and row["exposure_cap_pct"] in {95.0, 100.0}:
            stats = row["stats"]
            print(f"{row['portfolio']} {row['period']} cap={row['exposure_cap_pct']:.0f}% return={stats['total_return_pct']:.2f}% cagr={stats['cagr_pct']:.2f}% mdd={stats['max_drawdown_pct']:.2f}% fees={stats['total_fees_inr']:.0f} slip={row['slippage_inr']:.0f} dd20={stats['within_drawdown_limit']}")
    print(f"scenarios={len(scenarios)} output={OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
