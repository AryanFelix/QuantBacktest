"""Replay saved stock-momentum orders against daily OHLC to bound drawdown."""

from __future__ import annotations

import csv
import json
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs"
CAPITAL = 1_000_000.0
LIMIT_PCT = 20.0
WINDOWS = (
    ("train_2021_2023", "2021-02-01", "2023-12-29"),
    ("validation_2024", "2024-01-01", "2024-12-31"),
    ("holdout_2025_plus", "2025-01-01", "2026-10-23"),
    ("full_2021_2026", "2021-02-01", "2026-10-23"),
)

sys.path.insert(0, str(ROOT / "work"))
import backtest_stock_momentum as stock


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def load_runs() -> dict[str, tuple[pd.DataFrame, pd.DataFrame, int, str]]:
    equity = pd.read_csv(OUT / "stock_momentum_daily_equity.csv", parse_dates=["date"])
    orders = pd.read_csv(OUT / "stock_momentum_orders.csv")
    screen = read_csv(OUT / "stock_momentum_screen.csv")
    bps = {row["strategy"]: int(float(row["slippage_bps_per_side"])) for row in screen if row["period"] == "full_2021_2026"}
    runs: dict[str, tuple[pd.DataFrame, pd.DataFrame, int, str]] = {}
    for name, group in equity.groupby("strategy", sort=False):
        e = group.set_index("date").sort_index()
        o = orders.loc[orders["strategy"] == name].copy()
        assert name in bps
        source_group = "benchmark" if name == "NIFTYBEES buy-and-hold benchmark" else "diagnostic_stress" if bps[name] != 10 else "restricted_baseline"
        runs[name] = (e, o, bps[name], source_group)

    action_dir = ROOT / "work" / "backtests" / "stock_momentum_action_aware"
    for slip in (10, 20, 50):
        folder = action_dir / f"slippage_{slip}bps"
        e = pd.read_csv(folder / "daily_equity.csv", parse_dates=["date"]).set_index("date").sort_index()
        o = pd.read_csv(folder / "orders.csv")
        name = f"stock_top10_mom12_1_trend200_market200@95%_full_universe" + (f"_slip{slip}" if slip != 10 else "")
        runs[name] = (e, o, slip, "restored_universe")

    assert len(runs) == 28, f"Expected 25 restricted/benchmark plus 3 restored-universe paths, found {len(runs)}"
    assert sum(group == "restricted_baseline" and bps == 10
               for name, (_, _, bps, group) in runs.items()) == 20
    return runs


def price_panels(index: pd.DatetimeIndex, bars: dict[str, pd.DataFrame], etf: pd.DataFrame) -> dict[str, np.ndarray]:
    all_bars = {**bars, "NIFTYBEES": etf}
    panels = {}
    for symbol, frame in all_bars.items():
        raw = frame.reindex(index)
        prior_close = raw["close"].ffill().shift(1)
        panel = raw.loc[:, ["open", "high", "low", "close"]].copy()
        panel["close"] = panel["close"].ffill()
        for field in ("open", "high", "low"):
            panel[field] = panel[field].fillna(prior_close)
        panels[symbol] = panel.to_numpy(dtype=float)
    return panels


def replay(name: str, run: tuple[pd.DataFrame, pd.DataFrame, int, str], panels: dict[str, np.ndarray],
           dividends: dict[tuple[str, pd.Timestamp], float]) -> dict:
    equity, orders, slippage_bps, group = run
    index = equity.index
    orders = orders.copy()
    orders["date"] = pd.to_datetime(orders["date"]).dt.normalize()
    terminal_flag = orders.get("terminal_liquidation", pd.Series(False, index=orders.index))
    terminal = orders.loc[terminal_flag.astype(str).str.lower().eq("true")].copy()
    ordinary = orders.drop(index=terminal.index)
    order_groups = {dt: rows for dt, rows in ordinary.groupby("date", sort=False)}
    quantity: dict[str, int] = {}
    cash = CAPITAL
    close_path = []
    high_path = []
    low_path = []
    max_error = 0.0
    dividends_by_date: dict[pd.Timestamp, dict[str, float]] = defaultdict(dict)
    for (symbol, exdate), amount in dividends.items():
        dividends_by_date[exdate][symbol] = amount

    def nav_at(prices: dict[str, float]) -> float:
        return cash + sum(qty * prices[symbol] for symbol, qty in quantity.items() if qty)

    saved_navs = equity["nav"].to_numpy(dtype=float)
    for position, dt in enumerate(index):
        day_orders = order_groups.get(dt)
        needed = {symbol for symbol, qty in quantity.items() if qty}
        if day_orders is not None:
            needed.update(day_orders["symbol"].tolist())
        if dt == index[-1] and not terminal.empty:
            needed.update(terminal["symbol"].tolist())
        day = {symbol: panels[symbol][position] for symbol in needed}
        cash += sum(quantity.get(symbol, 0) * amount for symbol, amount in dividends_by_date.get(dt, {}).items())
        held = [symbol for symbol, qty in quantity.items() if qty]
        for symbol in held:
            if symbol not in day or (day[symbol] <= 0).any() or not np.isfinite(day[symbol]).all():
                raise AssertionError(f"Held {symbol} lacks a valid OHLC mark on {dt.date()} in {name}")
        opening = {symbol: row[0] for symbol, row in day.items() if np.isfinite(row[0]) and row[0] > 0}
        pretrade_open = nav_at(opening)
        for order in day_orders.itertuples(index=False) if day_orders is not None else ():
            symbol, side = order.symbol, order.side
            amount, fee, notional = int(order.quantity), float(order.total), float(order.notional)
            if amount <= 0 or symbol not in opening:
                raise ValueError(f"Invalid or unpriced ordinary order in {name} on {dt.date()}: {order}")
            if side == "buy":
                quantity[symbol] = quantity.get(symbol, 0) + amount
                cash -= notional + fee
            elif side == "sell":
                if amount > quantity.get(symbol, 0):
                    raise ValueError(f"Sell exceeds reconstructed position in {name}: {order}")
                quantity[symbol] -= amount
                cash += notional - fee
            else:
                raise ValueError(f"Unknown order side in {name}: {side}")
        held = [symbol for symbol, qty in quantity.items() if qty]
        for symbol in held:
            if symbol not in day or (day[symbol][1:] <= 0).any() or not np.isfinite(day[symbol][1:]).all():
                raise AssertionError(f"Post-trade holding {symbol} lacks a valid OHLC mark on {dt.date()} in {name}")
        post_open = nav_at(opening)
        highs = {symbol: row[1] for symbol, row in day.items() if np.isfinite(row[1]) and row[1] > 0}
        lows = {symbol: row[2] for symbol, row in day.items() if np.isfinite(row[2]) and row[2] > 0}
        high_nav = max(pretrade_open, post_open, nav_at(highs))
        low_nav = min(pretrade_open, post_open, nav_at(lows))

        closes = {symbol: row[3] for symbol, row in day.items() if np.isfinite(row[3]) and row[3] > 0}
        close_nav = nav_at(closes)
        if dt == index[-1] and not terminal.empty:
            for order in terminal.itertuples(index=False):
                symbol, amount = order.symbol, int(order.quantity)
                if amount != quantity.get(symbol, 0):
                    raise ValueError(f"Terminal quantity does not close the position in {name}: {order}")
                quantity[symbol] = 0
                cash += float(order.notional) - float(order.total)
            close_nav = cash
            high_nav = max(high_nav, close_nav)
            low_nav = min(low_nav, close_nav)

        error = abs(close_nav - saved_navs[position])
        max_error = max(max_error, error)
        if error > 0.03:
            raise AssertionError(f"Close NAV replay mismatch in {name} on {dt.date()}: {close_nav} vs {saved_navs[position]}")
        close_path.append(close_nav)
        high_path.append(high_nav)
        low_path.append(low_nav)

    if any(quantity.values()):
        raise AssertionError(f"Terminal position remains in {name}: {quantity}")
    highs = np.asarray(high_path)
    lows = np.asarray(low_path)
    closes = np.asarray(close_path)
    running_peak = CAPITAL
    running_peak_date = "starting_capital"
    worst_dd = 0.0
    worst_peak_date = worst_trough_date = "starting_capital"
    dd_rows = []
    for dt, high, low, close in zip(index, highs, lows, closes):
        if high > running_peak:
            running_peak, running_peak_date = high, dt.date().isoformat()
        drawdown = low / running_peak - 1
        if drawdown < worst_dd:
            worst_dd, worst_peak_date, worst_trough_date = drawdown, running_peak_date, dt.date().isoformat()
        dd_rows.append({"date": dt, "close_nav": close, "ohlc_high_nav": high, "ohlc_low_nav": low,
                        "running_highwater_nav": running_peak, "running_highwater_date": running_peak_date,
                        "running_drawdown_pct": drawdown * 100})
    close_curve = np.maximum.accumulate(np.r_[CAPITAL, closes])[1:]
    close_dd = closes / close_curve - 1
    drawdowns = np.asarray([row["running_drawdown_pct"] for row in dd_rows]) / 100
    path_orders = orders
    fees_all = float(path_orders["total"].sum()) if not path_orders.empty else 0.0
    slip_all = float((path_orders["quantity"] * (path_orders["fill_price"] - path_orders["raw_price"]).abs()).sum()) if not path_orders.empty else 0.0
    details = {
        "strategy": name, "source_group": group, "slippage_bps_per_side": slippage_bps,
        "start_date": index[0].date().isoformat(), "end_date": index[-1].date().isoformat(),
        "starting_capital_inr": CAPITAL, "ending_balance_inr": float(closes[-1]),
        "total_return_pct": float((closes[-1] / CAPITAL - 1) * 100),
        "close_max_drawdown_pct": float(close_dd.min() * 100),
        "ohlc_drawdown_bound_pct": float(worst_dd * 100), "bound_peak_date": worst_peak_date,
        "bound_trough_date": worst_trough_date, "total_fees_inr": fees_all,
        "total_slippage_inr": slip_all, "order_count": int(len(orders)),
        "max_close_replay_error_inr": max_error,
    }
    return {"details": details, "daily": dd_rows, "ohlc_dd": drawdowns, "close_dd": close_dd,
            "highs": highs, "lows": lows, "closes": closes}


def window_rows(name: str, run: tuple[pd.DataFrame, pd.DataFrame, int, str], result: dict,
                selected: bool) -> list[dict]:
    equity, orders, bps, group = run
    dates = equity.index
    rows = []
    order_dates = pd.to_datetime(orders["date"]).dt.normalize() if not orders.empty else pd.Series(dtype="datetime64[ns]")
    for label, start_str, end_str in WINDOWS:
        start, end = pd.Timestamp(start_str), pd.Timestamp(end_str)
        mask = (dates >= start) & (dates <= end)
        positions = np.flatnonzero(mask)
        if not len(positions):
            continue
        first, last = int(positions[0]), int(positions[-1])
        baseline = CAPITAL if first == 0 else float(equity.iloc[first - 1]["nav"])
        ending = float(result["closes"][last])
        years = max((dates[last] - start).days / 365.25, 1 / 252)
        total = ending / baseline - 1
        cagr = ((1 + total) ** (1 / years) - 1) * 100 if total > -1 else -100.0
        fee_mask = (order_dates >= start) & (order_dates <= dates[last]) if len(order_dates) else []
        period_orders = orders.loc[fee_mask] if len(order_dates) else orders
        window_dd = result["ohlc_dd"][first:last + 1]
        dd_pos = first + int(np.argmin(window_dd))
        close_dd = result["close_dd"][first:last + 1]
        rows.append({
            "simulation_type": "stock_ohlc_intraday_drawdown_audit", "strategy": name,
            "source_group": group, "period": label, "period_start": start.date().isoformat(),
            "period_end": dates[last].date().isoformat(), "starting_balance_inr": baseline,
            "ending_balance_inr": ending, "total_return_pct": total * 100, "cagr_pct": cagr,
            "max_drawdown_pct": float(window_dd.min() * 100),
            "close_max_drawdown_pct": float(close_dd.min() * 100),
            "bound_peak_date": result["daily"][dd_pos]["running_highwater_date"],
            "bound_trough_date": result["daily"][dd_pos]["date"].date().isoformat(),
            "fees_inr": float(period_orders["total"].sum()) if not period_orders.empty else 0.0,
            "slippage_cost_inr": float((period_orders["quantity"] * (period_orders["fill_price"] - period_orders["raw_price"]).abs()).sum()) if not period_orders.empty else 0.0,
            "slippage_bps_per_side": bps, "order_count": len(period_orders),
            "within_20pct": bool(window_dd.min() >= -LIMIT_PCT / 100),
            "selected_on_ohlc_training_only": selected,
            "max_close_replay_error_inr": result["details"]["max_close_replay_error_inr"],
            "selection_or_sizing": "Same saved strategy; OHLC audit only. Candidate selection uses train window only." if selected else "Saved strategy replay; diagnostic, not selected.",
            "source_artifact": "work/audit_stock_momentum_ohlc.py;outputs/stock_momentum_ohlc_audit.csv;outputs/stock_momentum_ohlc_selection.json;outputs/stock_momentum_ohlc_audit_method.md",
            "notes": "Conservative same-day portfolio OHLC envelope (all held highs before lows); closes reconciled to saved ledger. Historical estimate, not a future loss limit." + (" NIFTYBEES has isolated 2022 open prices 11.8–13.0% from the prior close; benchmark OHLC bound needs an independent exchange-price check." if group == "benchmark" else ""),
            "ohlc_data_quality_flag": "NIFTYBEES has isolated 2022 open prices 11.8–13.0% from the prior close; benchmark OHLC bound needs an independent exchange-price check." if group == "benchmark" else "",
        })
    return rows


def main() -> None:
    runs = load_runs()
    bars, _, dividends = stock.load_prices()
    etf = pd.read_csv(ROOT / "work" / "data" / "etf_daily" / "NSE_EQ_INF204KB14I2-days-1-2014-01-01-2026-10-23.csv", parse_dates=["time"])
    etf["date"] = pd.to_datetime(etf["time"]).dt.tz_localize(None).dt.normalize()
    etf = etf.drop_duplicates("date").set_index("date").sort_index()
    all_dates = pd.DatetimeIndex(sorted(set().union(*(set(run[0].index) for run in runs.values()))))
    panels = price_panels(all_dates, bars, etf)
    results = {}
    for number, (name, run) in enumerate(runs.items(), 1):
        print(f"Replaying {number}/{len(runs)}: {name}", flush=True)
        results[name] = replay(name, run, panels, dividends)
    primary = [(name, result) for name, result in results.items()
               if run_group(runs[name]) == "restricted_baseline" and runs[name][2] == 10]
    train_scores = []
    for name, result in primary:
        train_index = np.asarray([pd.Timestamp(d["date"]) <= pd.Timestamp("2023-12-29") for d in result["daily"]])
        train_end = float(result["closes"][train_index][-1])
        years = (pd.Timestamp("2023-12-29") - pd.Timestamp("2021-02-01")).days / 365.25
        cagr = ((train_end / CAPITAL) ** (1 / years) - 1) * 100
        dd = float(result["ohlc_dd"][train_index].min() * 100)
        train_scores.append({"strategy": name, "training_cagr_pct": cagr, "training_ohlc_drawdown_pct": dd,
                             "passes_20pct_training_bound": dd >= -LIMIT_PCT})
    eligible = [row for row in train_scores if row["passes_20pct_training_bound"]]
    selected = max(eligible, key=lambda row: (row["training_cagr_pct"], row["strategy"]))["strategy"] if eligible else ""
    rows = [row for name, run in runs.items() for row in window_rows(name, run, results[name], name == selected)]
    assert len(rows) == 112 and len({(r["strategy"], r["period"]) for r in rows}) == 112
    assert max(row["max_close_replay_error_inr"] for row in rows) <= 0.03
    assert all(np.all(result["highs"] + 0.01 >= result["closes"]) and np.all(result["lows"] - 0.01 <= result["closes"])
               for result in results.values())

    audit_path = OUT / "stock_momentum_ohlc_audit.csv"
    pd.DataFrame(rows).to_csv(audit_path, index=False)
    selected_result = results[selected] if selected else None
    selection = {
        "capital_inr": CAPITAL, "drawdown_limit_pct": LIMIT_PCT,
        "case_count": len(runs), "period_row_count": len(rows),
        "selection_scope": "20 restricted-universe stock momentum rules/exposure caps at 10 bps; maximum training CAGR subject to training OHLC drawdown no worse than -20%",
        "selected_strategy": selected,
        "training_candidates_ranked": sorted(train_scores, key=lambda row: row["training_cagr_pct"], reverse=True),
        "selected_full_path": selected_result["details"] if selected_result else None,
        "primary_10bps_full_path_ranked_by_return": sorted(
            [results[name]["details"] for name, _ in primary], key=lambda row: row["total_return_pct"], reverse=True),
        "audit_limitations": [
            "OHLC drawdown is a conservative simultaneous portfolio envelope, not observed intraday sequence.",
            "NIFTYBEES benchmark candles include isolated 11.8–13.0% opening gaps against prior closes in 2022; its -30.76% OHLC bound is diagnostic until exchange-level OHLC is checked.",
            "Point-in-time NIFTY membership and action event feeds remain incomplete; the restored-universe series is still diagnostic.",
            "The histories and strategy variants were inspected already; chronological validation and holdout are not pristine lockboxes.",
            "Historical pass does not guarantee future drawdown stays below 20%.",
        ],
    }
    (OUT / "stock_momentum_ohlc_selection.json").write_text(json.dumps(selection, indent=2), encoding="utf-8")
    register_outputs(rows)
    print(json.dumps({"paths": len(runs), "rows": len(rows), "selected_training_only": selected,
                      "selected_training_cagr_pct": next((r["training_cagr_pct"] for r in train_scores if r["strategy"] == selected), None),
                      "selected_full_return_pct": selected_result["details"]["total_return_pct"] if selected_result else None,
                      "selected_ohlc_drawdown_bound_pct": selected_result["details"]["ohlc_drawdown_bound_pct"] if selected_result else None,
                      "max_replay_error_inr": max(r["max_close_replay_error_inr"] for r in rows)}, indent=2))


def register_outputs(rows: list[dict]) -> None:
    ledger_path = OUT / "backtest_summary.csv"
    ledger = read_csv(ledger_path)
    fields = list(ledger[0])
    ledger = [row for row in ledger if row["simulation_type"] != "stock_ohlc_intraday_drawdown_audit"]
    for row in rows:
        selected = str(row["selected_on_ohlc_training_only"]).lower() == "true"
        out = {field: "" for field in fields}
        for field in fields:
            if field in row:
                out[field] = str(row[field])
        out["universe"] = {
            "benchmark": "NIFTYBEES price-only benchmark; distribution and OHLC source issues remain",
            "restored_universe": "Point-in-time NIFTY 50; 13 prior action-source exclusions restored; exploratory accounting",
            "restricted_baseline": "Provisional point-in-time NIFTY 50 with 13 action-source exclusions",
            "diagnostic_stress": "Restricted-universe top-10 stress path",
        }[row["source_group"]]
        out["gross_exposure_cap_pct"] = row["strategy"].split("@", 1)[1].split("%", 1)[0] if "@" in row["strategy"] else ""
        out["selection_or_sizing"] = ("Selected using training OHLC drawdown and CAGR; " if selected else "Diagnostic replay; ") + row["selection_or_sizing"]
        out["notes"] = (
            f"Close MDD {float(row['close_max_drawdown_pct']):.2f}%; conservative simultaneous OHLC bound "
            f"{float(row['max_drawdown_pct']):.2f}% (peak {row['bound_peak_date']}, trough {row['bound_trough_date']}); "
            f"maximum NAV replay error ₹{float(row['max_close_replay_error_inr']):.6f}. {row['notes']}"
        )
        ledger.append(out)
    stock.atomic_csv(ledger_path, ledger, fields)

    manifest_path = OUT / "data_manifest.csv"
    manifest = read_csv(manifest_path)
    manifest_fields = list(manifest[0])
    name = "Stock momentum order-ledger OHLC drawdown audit"
    manifest = [row for row in manifest if row["dataset"] != name]
    for row in manifest:
        if row["dataset"] == "Consolidated backtest metric ledger":
            row["bar_count"] = str(len(ledger))
            if "112 stock OHLC audit rows" not in row["notes"]:
                row["notes"] += "; includes 112 stock order-ledger OHLC audit window rows"
            row["notes"] = row["notes"].replace("report.; includes 112 stock", "report; includes 112 stock")
        if row["dataset"] == "Demerger ex-date price-discovery method":
            source_note = "work/research/spos_itc_hul_auction_result_audit_2026-10-27.md"
            if source_note not in row["cache_paths"].split(";"):
                row["cache_paths"] += ";" + source_note
            row["notes"] = "Official NSE parent OHLC recovered for six events; ITC/HUL scheduling circulars found but numeric final SPOS prices remain unpublished in those circulars. Residuals are index/entitlement proxies, not booked stock P&L."
    manifest.append({
        "dataset": name, "ticker": "NIFTY 50 stocks and NIFTYBEES benchmark", "instrument_key": "",
        "bar_interval": "daily OHLC; monthly trades", "first_bar": "2021-02-01", "last_bar": "2026-10-23",
        "bar_count": str(len(rows)), "file_count": "28 strategy paths; 4 windows each", "empty_files": "0",
        "cache_paths": "work/audit_stock_momentum_ohlc.py;outputs/stock_momentum_ohlc_audit.csv;outputs/stock_momentum_ohlc_selection.json;outputs/stock_momentum_ohlc_audit_method.md",
        "purpose": "Replay saved stock-momentum orders against daily OHLC and select a candidate using the training OHLC drawdown bound",
        "notes": "Orders and fees reconcile to saved close NAV within ₹0.03. Envelope assumes all holdings reach daily highs before lows; NIFTYBEES benchmark has isolated open-price quality flags.",
    })
    stock.atomic_csv(manifest_path, manifest, manifest_fields)


def run_group(run: tuple[pd.DataFrame, pd.DataFrame, int, str]) -> str:
    return run[3]


if __name__ == "__main__":
    main()
