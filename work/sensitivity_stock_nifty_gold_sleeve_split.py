"""Train-select stock/ETF capital splits with exact sleeve-sized order replays."""

from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "work"))

import backtest_stock_nifty_gold_blend as blend_run

stock = blend_run.stock
stock_ohlc = blend_run.stock_ohlc
blend = blend_run.blend
q = blend_run.q

CAPITAL = blend_run.CAPITAL
START = blend_run.START
END = blend_run.END
SLIPPAGE_BPS = blend_run.SLIPPAGE_BPS
STOCK_CAP = blend_run.STOCK_CAP
ETF_CAP = blend_run.ETF_CAP
STOCK_RULE = blend_run.STOCK_RULE
WEIGHTS = tuple(i / 10 for i in range(11))
OUT = ROOT / "work" / "backtests" / "stock_nifty_gold_sleeve_split"
RESULTS = ROOT / "outputs" / "stock_nifty_gold_sleeve_split.csv"
SELECTION = ROOT / "outputs" / "stock_nifty_gold_sleeve_split_selection.json"


def period_metrics(dates: pd.DatetimeIndex, close: np.ndarray, high: np.ndarray, low: np.ndarray,
                   start: pd.Timestamp, end: pd.Timestamp) -> dict:
    positions = np.flatnonzero((dates >= start) & (dates <= end))
    if not len(positions):
        raise ValueError(f"No bars in requested period {start.date()} to {end.date()}")
    first, last = int(positions[0]), int(positions[-1])
    start_nav = CAPITAL if first == 0 else float(close[first - 1])
    funding_date = dates[first] if first == 0 else dates[first - 1]
    prior_close_peak = CAPITAL if first == 0 else max(CAPITAL, float(close[:first].max()))
    prior_ohlc_peak = CAPITAL if first == 0 else max(CAPITAL, float(high[:first].max()))
    close_peak, ohlc_peak = prior_close_peak, prior_ohlc_peak
    close_dd = ohlc_dd = 0.0
    bound_peak_date = "starting_capital"
    if first and prior_ohlc_peak > CAPITAL:
        bound_peak_date = dates[int(np.argmax(high[:first]))].date().isoformat()
    for i in positions:
        if close[i] > close_peak:
            close_peak = float(close[i])
        close_dd = min(close_dd, float(close[i]) / close_peak - 1)
        if high[i] > ohlc_peak:
            ohlc_peak = float(high[i])
            bound_peak_date = dates[i].date().isoformat()
        ohlc_dd = min(ohlc_dd, float(low[i]) / ohlc_peak - 1)
    end_nav = float(close[last])
    total_return = end_nav / start_nav - 1
    return {
        "period_start": dates[first].date().isoformat(), "period_end": dates[last].date().isoformat(),
        "starting_balance_inr": start_nav, "ending_balance_inr": end_nav,
        "total_return_pct": total_return * 100,
        "funding_date": funding_date.date().isoformat(),
        "funding_date_basis": "initial_capital" if first == 0 else "prior_close",
        "cagr_pct": stock.q._calendar_cagr_pct(start_nav, end_nav, funding_date, dates[last]),
        "close_max_drawdown_pct": close_dd * 100,
        "ohlc_drawdown_bound_pct": ohlc_dd * 100,
        "bound_peak_date": bound_peak_date,
        "within_20pct_ohlc": ohlc_dd >= -0.20,
    }


def _self_check_period_boundary() -> None:
    dates = pd.DatetimeIndex(["2023-12-29", "2024-01-02", "2024-12-31"])
    values = np.array([1_000.0, 1_000.0, 1_200.0])
    result = period_metrics(dates, values, values, values, dates[1], dates[-1])
    assert result["funding_date"] == "2023-12-29"
    assert result["funding_date_basis"] == "prior_close"
    assert np.isclose(result["cagr_pct"], 19.836616, atol=1e-5), result


def register_outputs(rows: list[dict], selected_pct: float) -> None:
    summary_path = ROOT / "outputs" / "backtest_summary.csv"
    ledger = stock.read_csv(summary_path)
    fields = list(ledger[0])
    ledger = [row for row in ledger if row["simulation_type"] != "stock_nifty_gold_split_sensitivity"]
    for row in rows:
        ledger_row = {field: "" for field in fields}
        ledger_row.update({
            "simulation_type": "stock_nifty_gold_split_sensitivity",
            "strategy": "Stock momentum + NIFTY/Gold exact capital split",
            "universe": "Restored-provisional NIFTY 50 stocks; NIFTYBEES; GOLDBEES",
            "period": row["period"], "period_start": row["period_start"], "period_end": row["period_end"],
            "starting_balance_inr": row["starting_balance_inr"], "ending_balance_inr": row["ending_balance_inr"],
            "total_return_pct": row["total_return_pct"], "cagr_pct": row["cagr_pct"],
            "max_drawdown_pct": row["close_max_drawdown_pct"],
            "slippage_bps_per_side": SLIPPAGE_BPS, "fees_inr": row["fees_inr"],
            "slippage_cost_inr": row["slippage_cost_inr"], "order_count": row["order_count"],
            "within_20pct": row["within_20pct_ohlc"],
            "selection_or_sizing": f"Exact sleeve replay: {row['stock_initial_capital_pct']:.0f}% stock / {row['etf_initial_capital_pct']:.0f}% ETF; selected on training only={row['selected_on_training_only']}",
            "source_artifact": "outputs/stock_nifty_gold_sleeve_split.csv;outputs/stock_nifty_gold_sleeve_split_selection.json;outputs/stock_nifty_gold_sleeve_split_method.md;work/sensitivity_stock_nifty_gold_sleeve_split.py;work/backtests/stock_nifty_gold_sleeve_split/",
            "notes": f"Combined OHLC bound {row['ohlc_drawdown_bound_pct']:.4f}%; initial gross target {row['initial_gross_target_pct']:.1f}%; 50 bps/side; current modeled fees; 0% cash yield. All dates inspected; retrospective split sensitivity, not validated allocation. ETF distributions and stock actions/universe remain incomplete.",
        })
        ledger.append(ledger_row)
    stock.atomic_csv(summary_path, ledger, fields)

    manifest_path = ROOT / "outputs" / "data_manifest.csv"
    manifest = stock.read_csv(manifest_path)
    manifest_fields = list(manifest[0])
    dataset = "Stock + NIFTY/Gold exact capital-split sensitivity"
    manifest = [row for row in manifest if row["dataset"] != dataset]
    manifest.append({
        "dataset": dataset, "ticker": "Restored-universe NIFTY 50 stocks; NIFTYBEES; GOLDBEES",
        "instrument_key": "", "bar_interval": "daily marks; monthly and quarterly trades",
        "first_bar": START.date().isoformat(), "last_bar": END.date().isoformat(),
        "bar_count": "1420", "file_count": "11 exact capital splits; 44 metric rows",
        "empty_files": "0",
        "cache_paths": "work/sensitivity_stock_nifty_gold_sleeve_split.py;outputs/stock_nifty_gold_sleeve_split.csv;outputs/stock_nifty_gold_sleeve_split_selection.json;outputs/stock_nifty_gold_sleeve_split_method.md;work/backtests/stock_nifty_gold_sleeve_split/",
        "purpose": "Compare exact ₹10 lakh stock/ETF sleeve allocations against the 20% historical drawdown screen",
        "notes": f"Training-only selected weight {selected_pct:.0f}% stock; 50 bps/side; 0% cash yield; all dates previously inspected; not an investable winner.",
    })
    for row in manifest:
        if row["dataset"] == "Consolidated backtest metric ledger":
            row["bar_count"] = str(len(ledger))
            phrase = "Forty-four exact stock/NIFTY/Gold capital-split sensitivity rows added."
            if phrase not in row["notes"]:
                row["notes"] = row["notes"].rstrip() + " " + phrase
    stock.atomic_csv(manifest_path, manifest, manifest_fields)


def run_weight(stock_weight: float, context: dict, slippage_bps: int = SLIPPAGE_BPS) -> dict:
    stock_capital = CAPITAL * stock_weight
    etf_capital = CAPITAL - stock_capital
    stock_equity = stock_orders = stock_stats = stock_result = None
    etf_equity = etf_orders = etf_stats = etf_result = None
    if stock_capital > 0:
        stock.CAPITAL = stock_capital
        stock_ohlc.CAPITAL = stock_capital
        stock_equity, stock_orders, stock_stats = stock.simulate(
            STOCK_RULE, context["stock_bars"], context["dividends"], context["scheduled"][STOCK_RULE],
            STOCK_CAP, slippage_bps, start=START, end=END,
        )
        stock_equity = stock_equity.copy()
        stock_equity.index = blend_run.daily_index(stock_equity.index)
        stock_panels = stock_ohlc.price_panels(stock_equity.index, context["stock_bars"], context["etf_bars"])
        stock_result = stock_ohlc.replay(
            "stock sleeve", (stock_equity, stock_orders, slippage_bps, "restored_universe"),
            stock_panels, context["dividends"],
        )
        dates = stock_equity.index
        stock_close, stock_high, stock_low = stock_result["closes"], stock_result["highs"], stock_result["lows"]
    else:
        stock_close = stock_high = stock_low = None

    if etf_capital > 0:
        etf_equity, etf_orders, etf_stats = q._simulate(
            context["panels"], context["portfolios"]["fixed_50_50_quarterly"],
            context["events"]["fixed_50_50_quarterly"], etf_capital, ETF_CAP,
            slippage_bps, "equity_delivery", START.date(), END.date(), 20.0,
        )
        etf_result = blend_run.replay_etf_ohlc(etf_equity, etf_orders, context["files"], etf_capital)
        dates = etf_result["dates"]
        etf_close, etf_high, etf_low = etf_result["closes"], etf_result["highs"], etf_result["lows"]
    else:
        etf_close = etf_high = etf_low = None

    if stock_capital > 0 and etf_capital > 0 and not stock_equity.index.equals(etf_result["dates"]):
        raise AssertionError("Stock and ETF sleeves do not share the same daily session index")
    zeros = np.zeros(len(dates))
    close = (stock_close if stock_capital > 0 else zeros) + (etf_close if etf_capital > 0 else zeros)
    high = (stock_high if stock_capital > 0 else zeros) + (etf_high if etf_capital > 0 else zeros)
    low = (stock_low if stock_capital > 0 else zeros) + (etf_low if etf_capital > 0 else zeros)
    assert len(dates) > 1 and dates[0] == START and dates[-1] == END
    assert np.all(high + 0.03 >= close) and np.all(low - 0.03 <= close)

    windows = (
        ("train_2021_2023", START, pd.Timestamp("2023-12-29")),
        ("validation_2024", pd.Timestamp("2024-01-01"), pd.Timestamp("2024-12-31")),
        ("holdout_2025_plus", pd.Timestamp("2025-01-01"), END),
        ("full_2021_2026", START, END),
    )
    rows = []
    for label, start, end in windows:
        metrics = period_metrics(dates, close, high, low, start, end)
        metrics.update({
            "strategy": "stock_nifty_gold_sleeve_split",
            "stock_initial_capital_pct": stock_weight * 100,
            "etf_initial_capital_pct": (1 - stock_weight) * 100,
            "initial_gross_target_pct": (stock_weight * STOCK_CAP + (1 - stock_weight) * ETF_CAP) * 100,
            "period": label, "slippage_bps_per_side": slippage_bps,
            "fees_inr": "", "slippage_cost_inr": "", "order_count": "",
        })
        if label == "full_2021_2026":
            stock_fee = float(stock_stats["fees_inr"]) if stock_capital > 0 else 0.0
            stock_slippage = float(stock_stats["slippage_cost_inr"]) if stock_capital > 0 else 0.0
            etf_fee = float(etf_stats["total_fees_inr"]) if etf_capital > 0 else 0.0
            etf_slippage = float(blend.modeled_slippage(etf_orders, context["panels"])) if etf_capital > 0 else 0.0
            metrics.update({
                "fees_inr": stock_fee + etf_fee,
                "slippage_cost_inr": stock_slippage + etf_slippage,
                "order_count": (len(stock_orders) if stock_capital > 0 else 0) + (len(etf_orders) if etf_capital > 0 else 0),
            })
        rows.append(metrics)

    return {
        "stock_weight": stock_weight, "stock_capital": stock_capital, "etf_capital": etf_capital,
        "dates": dates, "close": close, "high": high, "low": low,
        "rows": rows, "stock_equity": stock_equity, "stock_orders": stock_orders,
        "etf_equity": etf_equity, "etf_orders": etf_orders,
        "stock_result": stock_result, "etf_result": etf_result,
    }


def load_context() -> dict:
    stock.ACTION_EXCLUSIONS = set()
    stock.START, stock.END = START, END
    stock_bars, tri, dividends = stock.load_prices()
    etf_bars = pd.read_csv(
        stock.DATA / "etf_daily" / "NSE_EQ_INF204KB14I2-days-1-2014-01-01-2026-10-23.csv",
        parse_dates=["time"],
    )
    etf_bars["date"] = pd.to_datetime(etf_bars["time"]).dt.tz_localize(None).dt.normalize()
    etf_bars = etf_bars.drop_duplicates("date").set_index("date").sort_index()
    scheduled, _ = stock.build_targets(stock_bars, tri, etf_bars["close"])
    if STOCK_RULE not in scheduled:
        raise ValueError(f"Frozen stock rule is missing: {STOCK_RULE}")
    files, panels, portfolios, events = blend.make_portfolios()
    return {
        "stock_bars": stock_bars, "dividends": dividends, "etf_bars": etf_bars,
        "scheduled": scheduled, "files": files, "panels": panels,
        "portfolios": portfolios, "events": events,
    }


def main() -> None:
    _self_check_period_boundary()
    context = load_context()
    runs = [run_weight(weight, context) for weight in WEIGHTS]
    all_rows = [row for run in runs for row in run["rows"]]
    base_half = next(row for row in all_rows if row["stock_initial_capital_pct"] == 50 and row["period"] == "full_2021_2026")
    blend_half = next(row for row in stock.read_csv(ROOT / "outputs" / "stock_nifty_gold_blend.csv") if row["period"] == "full_2021_2026")
    for split_key, blend_key in (("ending_balance_inr", "ending_balance_inr"),
                                 ("total_return_pct", "total_return_pct"),
                                 ("ohlc_drawdown_bound_pct", "ohlc_drawdown_bound_pct"),
                                 ("fees_inr", "fees_inr"), ("slippage_cost_inr", "slippage_cost_inr"),
                                 ("order_count", "order_count")):
        assert np.isclose(float(base_half[split_key]), float(blend_half[blend_key]), rtol=0, atol=1e-6), (split_key, base_half[split_key], blend_half[blend_key])
    training_rows = [row for run in runs for row in run["rows"] if row["period"] == "train_2021_2023" and row["within_20pct_ohlc"]]
    selected = max(training_rows, key=lambda row: (
        float(row["total_return_pct"]), float(row["ohlc_drawdown_bound_pct"]),
        -abs(float(row["stock_initial_capital_pct"]) - 50),
    ))
    selected_weight = float(selected["stock_initial_capital_pct"]) / 100
    for row in all_rows:
        row["selected_on_training_only"] = row["stock_initial_capital_pct"] == selected["stock_initial_capital_pct"]
    pd.DataFrame(all_rows).to_csv(RESULTS, index=False)

    selected_run = next(run for run in runs if run["stock_weight"] == selected_weight)
    selection = {
        "selected_stock_initial_capital_pct": selected["stock_initial_capital_pct"],
        "selected_etf_initial_capital_pct": selected["etf_initial_capital_pct"],
        "selection_rule": "Highest 2021-2023 net return among 10-point splits with a training combined OHLC bound no worse than -20%; ties prefer more drawdown headroom, then the split closest to 50/50.",
        "selected_training_row": selected,
        "selected_validation_row": next(row for row in selected_run["rows"] if row["period"] == "validation_2024"),
        "selected_holdout_row": next(row for row in selected_run["rows"] if row["period"] == "holdout_2025_plus"),
        "selected_full_row": next(row for row in selected_run["rows"] if row["period"] == "full_2021_2026"),
        "all_dates_previously_inspected": True,
        "interpretation": "Training-only allocation selection is descriptive; this is not a pristine out-of-sample validation because the stock signal and all later dates were already inspected.",
    }
    SELECTION.write_text(json.dumps(selection, indent=2), encoding="utf-8")

    OUT.mkdir(parents=True, exist_ok=True)
    save_weights = {0.5, selected_weight}
    for run in runs:
        if run["stock_weight"] not in save_weights:
            continue
        pct = int(round(run["stock_weight"] * 100))
        directory = OUT / f"stock_{pct:03d}_etf_{100-pct:03d}"
        directory.mkdir(parents=True, exist_ok=True)
        equity = pd.DataFrame({
            "nav_total_inr": run["close"], "ohlc_high_bound_nav_inr": run["high"],
            "ohlc_low_bound_nav_inr": run["low"],
        }, index=run["dates"])
        equity.index.name = "date"
        equity.to_csv(directory / "combined_equity.csv")
        if run["stock_equity"] is not None:
            run["stock_equity"].to_csv(directory / "stock_equity.csv")
            run["stock_orders"].to_csv(directory / "stock_orders.csv", index=False)
        if run["etf_equity"] is not None:
            run["etf_equity"].to_csv(directory / "etf_equity.csv", index_label="time")
            run["etf_orders"].to_csv(directory / "etf_orders.csv", index=False)
        summary = next(row for row in run["rows"] if row["period"] == "full_2021_2026")
        (directory / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")

    register_outputs(all_rows, selected["stock_initial_capital_pct"])

    selected_full = selection["selected_full_row"]
    print(json.dumps({
        "allocation_grid": "0-100% stock in 10-point steps",
        "metric_rows": len(all_rows),
        "training_only_selected_stock_pct": selected["stock_initial_capital_pct"],
        "selected_training_return_pct": selected["total_return_pct"],
        "selected_training_ohlc_bound_pct": selected["ohlc_drawdown_bound_pct"],
        "selected_2025_plus_return_pct": selection["selected_holdout_row"]["total_return_pct"],
        "selected_full_return_pct": selected_full["total_return_pct"],
        "selected_full_ohlc_bound_pct": selected_full["ohlc_drawdown_bound_pct"],
        "reconciled_50_50_to_fixed_blend": True,
    }, indent=2))


if __name__ == "__main__":
    main()
