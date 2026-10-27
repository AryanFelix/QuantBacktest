"""Backtest a fixed-capital blend of restored-universe stock momentum and NIFTY/Gold ETFs."""

from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "work"))

import audit_stock_momentum_ohlc as stock_ohlc
import backtest_stock_momentum as stock
import replay_volatility_weighted_blend as blend
import upstox_quant as q

START = pd.Timestamp("2021-02-01")
END = pd.Timestamp("2026-10-23")
CAPITAL = 1_000_000.0
SLEEVE_CAPITAL = CAPITAL / 2
SLIPPAGE_BPS = 50
STOCK_CAP = 0.95
ETF_CAP = 0.45
STOCK_RULE = "stock_top10_mom12_1_trend200_market200@95%"
OUT = ROOT / "work" / "backtests" / "stock_nifty_gold_blend"
SUMMARY_CSV = ROOT / "outputs" / "stock_nifty_gold_blend.csv"


def daily_index(index: pd.Index) -> pd.DatetimeIndex:
    result = pd.DatetimeIndex(index)
    if result.tz is not None:
        result = result.tz_localize(None)
    return result.normalize()


def replay_etf_ohlc(
    equity: pd.DataFrame,
    orders: pd.DataFrame,
    files: dict[str, pd.DataFrame],
    starting_capital: float,
) -> dict:
    index = daily_index(equity.index)
    if not index.is_unique or not index.is_monotonic_increasing:
        raise ValueError("ETF daily equity dates must be unique and increasing")
    prices = {}
    for symbol, frame in files.items():
        daily = frame.loc[:, ["open", "high", "low", "close"]].copy()
        daily.index = daily_index(daily.index)
        if daily.index.has_duplicates:
            repeated = daily.loc[daily.index.duplicated(keep=False)]
            if (repeated.groupby(level=0).nunique(dropna=False) > 1).any().any():
                raise ValueError(f"Conflicting same-day ETF bars for {symbol}")
            daily = daily.loc[~daily.index.duplicated(keep="first")]
        daily = daily.reindex(index)
        prior_close = daily["close"].ffill().shift(1)
        daily["close"] = daily["close"].ffill()
        for field in ("open", "high", "low"):
            daily[field] = daily[field].fillna(prior_close)
        prices[symbol] = daily

    orders = orders.copy()
    order_time = pd.to_datetime(orders["time"])
    if isinstance(order_time.dtype, pd.DatetimeTZDtype):
        order_time = order_time.dt.tz_localize(None)
    orders["date"] = order_time.dt.normalize()
    terminal_mask = orders.get("terminal_liquidation", pd.Series(False, index=orders.index))
    terminal_mask = terminal_mask.fillna(False).astype(str).str.lower().eq("true")
    terminal = orders.loc[terminal_mask]
    ordinary = orders.loc[~terminal_mask]
    order_groups = {dt: group for dt, group in ordinary.groupby("date", sort=False)}
    terminal_groups = {dt: group for dt, group in terminal.groupby("date", sort=False)}
    cash = float(starting_capital)
    quantity = dict.fromkeys(files, 0)
    close_values, high_values, low_values = [], [], []
    max_close_error = 0.0

    def nav_at(when: pd.Timestamp, field: str) -> float:
        return cash + sum(
            qty * float(prices[symbol].at[when, field])
            for symbol, qty in quantity.items()
            if qty
        )

    for position, dt in enumerate(index):
        saved = equity.iloc[position]
        cash += float(saved.get("cash_distribution_inr", 0.0) or 0.0)
        held = [symbol for symbol, qty in quantity.items() if qty]
        for symbol in held:
            if prices[symbol].loc[dt, ["open", "high", "low", "close"]].isna().any():
                raise ValueError(f"Held ETF {symbol} lacks an OHLC mark on {dt.date()}")
        pretrade_open = nav_at(dt, "open")
        for order in order_groups.get(dt, pd.DataFrame()).itertuples(index=False):
            symbol, side, amount = order.symbol, order.side, int(order.quantity)
            if symbol not in quantity or amount <= 0:
                raise ValueError(f"Invalid ETF order on {dt.date()}: {order}")
            if side == "buy":
                quantity[symbol] += amount
                cash -= float(order.notional) + float(order.total)
            elif side == "sell":
                if amount > quantity[symbol]:
                    raise ValueError(f"ETF sell exceeds the reconstructed position: {order}")
                quantity[symbol] -= amount
                cash += float(order.notional) - float(order.total)
            else:
                raise ValueError(f"Unknown ETF order side: {side}")
        posttrade_open = nav_at(dt, "open")
        held = [symbol for symbol, qty in quantity.items() if qty]
        for symbol in held:
            if prices[symbol].loc[dt, ["high", "low", "close"]].isna().any():
                raise ValueError(f"Post-trade ETF {symbol} lacks an OHLC mark on {dt.date()}")
        high_nav = max(pretrade_open, posttrade_open, nav_at(dt, "high"))
        low_nav = min(pretrade_open, posttrade_open, nav_at(dt, "low"))
        close_nav = nav_at(dt, "close")
        for order in terminal_groups.get(dt, pd.DataFrame()).itertuples(index=False):
            amount = int(order.quantity)
            if amount != quantity.get(order.symbol, 0):
                raise ValueError(f"Terminal ETF order does not close the position: {order}")
            quantity[order.symbol] = 0
            cash += float(order.notional) - float(order.total)
            close_nav = cash
            high_nav = max(high_nav, close_nav)
            low_nav = min(low_nav, close_nav)
        error = abs(close_nav - float(saved["nav"]))
        max_close_error = max(max_close_error, error)
        if error > 0.03:
            raise AssertionError(f"ETF OHLC replay differs from saved NAV on {dt.date()}: {close_nav} vs {saved['nav']}")
        close_values.append(close_nav)
        high_values.append(high_nav)
        low_values.append(low_nav)

    if any(quantity.values()):
        raise AssertionError(f"ETF holdings remain after terminal liquidation: {quantity}")
    result = {
        "dates": index,
        "closes": np.asarray(close_values),
        "highs": np.asarray(high_values),
        "lows": np.asarray(low_values),
        "max_close_replay_error_inr": max_close_error,
    }
    assert np.all(result["highs"] + 0.03 >= result["closes"])
    assert np.all(result["lows"] - 0.03 <= result["closes"])
    return result


def risk_path(dates: pd.DatetimeIndex, starting_capital: float, closes: np.ndarray,
              highs: np.ndarray, lows: np.ndarray) -> dict:
    peak = starting_capital
    close_peak = starting_capital
    worst_ohlc = 0.0
    worst_close = 0.0
    peak_date = worst_peak_date = trough_date = "starting_capital"
    rows = []
    for dt, close, high, low in zip(dates, closes, highs, lows):
        if high > peak:
            peak, peak_date = high, dt.date().isoformat()
        dd = low / peak - 1
        if dd < worst_ohlc:
            worst_ohlc = dd
            worst_peak_date, trough_date = peak_date, dt.date().isoformat()
        close_peak = max(close_peak, close)
        worst_close = min(worst_close, close / close_peak - 1)
        rows.append((peak, low, dd))
    return {
        "close_max_drawdown_pct": worst_close * 100,
        "ohlc_drawdown_bound_pct": worst_ohlc * 100,
        "bound_peak_date": worst_peak_date,
        "bound_trough_date": trough_date,
        "daily_risk": rows,
    }


def register_master_outputs(summary: dict, order_count: int, trade_count: int) -> None:
    summary_path = ROOT / "outputs" / "backtest_summary.csv"
    ledger = stock.read_csv(summary_path)
    fields = list(ledger[0])
    ledger = [row for row in ledger if row["simulation_type"] != "stock_cross_asset_blend"]
    ledger_row = {field: "" for field in fields}
    ledger_row.update({
        "simulation_type": "stock_cross_asset_blend",
        "strategy": "50/50 stock momentum + NIFTY/Gold sleeves",
        "universe": "Restored-provisional NIFTY 50 stocks + NIFTYBEES + GOLDBEES",
        "period": "full_2021_2026",
        "period_start": summary["period_start"], "period_end": summary["period_end"],
        "starting_balance_inr": CAPITAL, "ending_balance_inr": summary["ending_balance_inr"],
        "total_return_pct": summary["total_return_pct"], "cagr_pct": summary["cagr_pct"],
        "max_drawdown_pct": summary["close_max_drawdown_pct"],
        "gross_exposure_cap_pct": "",
        "slippage_bps_per_side": SLIPPAGE_BPS,
        "fees_inr": summary["fees_inr"], "slippage_cost_inr": summary["slippage_cost_inr"],
        "trade_count": trade_count, "order_count": order_count,
        "within_20pct": summary["within_20pct_ohlc_bound"],
        "selection_or_sizing": "50% initial capital per sleeve; stock sleeve uses monthly top-10 12-1 momentum and stock/NIFTYBEES 200DMA gates at 95% cap; quarterly static 50/50 NIFTY/Gold ETF sleeve at 45% cap",
        "source_artifact": "outputs/stock_nifty_gold_blend.csv;outputs/stock_nifty_gold_blend_method.md;work/backtest_stock_nifty_gold_blend.py;work/backtests/stock_nifty_gold_blend/",
        "notes": "50 bps per side and current modeled fees; combined OHLC drawdown envelope -13.56%; 0% cash yield. Post-hoc stock rule, inspected historical folds, provisional membership/actions, and ETF total-return limits prevent winner/deployment claims.",
    })
    ledger.append(ledger_row)
    stock.atomic_csv(summary_path, ledger, fields)

    manifest_path = ROOT / "outputs" / "data_manifest.csv"
    manifest = stock.read_csv(manifest_path)
    manifest_fields = list(manifest[0])
    dataset = "Stock + NIFTY/Gold capital blend replay"
    manifest = [row for row in manifest if row["dataset"] != dataset]
    manifest.append({
        "dataset": dataset, "ticker": "Restored-universe NIFTY 50 stocks; NIFTYBEES; GOLDBEES",
        "instrument_key": "", "bar_interval": "daily marks; monthly and quarterly trades",
        "first_bar": summary["period_start"], "last_bar": summary["period_end"],
        "bar_count": "1420", "file_count": "1 runner; stock/ETF sleeve and combined ledgers",
        "empty_files": "0",
        "cache_paths": "work/backtest_stock_nifty_gold_blend.py;outputs/stock_nifty_gold_blend.csv;outputs/stock_nifty_gold_blend_method.md;work/backtests/stock_nifty_gold_blend/",
        "purpose": "Test a fixed 50/50 initial-capital stock momentum and NIFTY/Gold allocation under the ₹10 lakh and 20% historical drawdown constraints",
        "notes": "50 bps/side; current fee model; 0% cash yield; combined OHLC bound -13.56%; all folds inspected; post-hoc stock rule and incomplete corporate-action/ETF distribution evidence.",
    })
    for row in manifest:
        if row["dataset"] == "Consolidated backtest metric ledger":
            row["bar_count"] = str(len(ledger))
            phrase = "One 50/50 stock momentum + NIFTY/Gold blend row added."
            if phrase not in row["notes"]:
                row["notes"] = row["notes"].rstrip() + " " + phrase
    stock.atomic_csv(manifest_path, manifest, manifest_fields)


def main() -> None:
    stock.CAPITAL = SLEEVE_CAPITAL
    stock.ACTION_EXCLUSIONS = set()
    stock.START, stock.END = START, END
    stock_bars, tri, dividends = stock.load_prices()
    etf_bars = pd.read_csv(
        stock.DATA / "etf_daily" / "NSE_EQ_INF204KB14I2-days-1-2014-01-01-2026-10-23.csv",
        parse_dates=["time"],
    )
    etf_bars["date"] = pd.to_datetime(etf_bars["time"]).dt.tz_localize(None).dt.normalize()
    etf_bars = etf_bars.drop_duplicates("date").set_index("date").sort_index()
    scheduled, picks = stock.build_targets(stock_bars, tri, etf_bars["close"])
    if STOCK_RULE not in scheduled:
        raise ValueError(f"Frozen stock rule is missing: {STOCK_RULE}")
    stock_equity, stock_orders, stock_stats = stock.simulate(
        STOCK_RULE, stock_bars, dividends, scheduled[STOCK_RULE], STOCK_CAP, SLIPPAGE_BPS,
        start=START, end=END,
    )

    files, panels, portfolios, events = blend.make_portfolios()
    etf_equity, etf_orders, etf_stats = q._simulate(
        panels, portfolios["fixed_50_50_quarterly"], events["fixed_50_50_quarterly"],
        SLEEVE_CAPITAL, ETF_CAP, SLIPPAGE_BPS, "equity_delivery",
        START.date(), END.date(), 20.0,
    )

    stock_equity = stock_equity.copy()
    stock_equity.index = daily_index(stock_equity.index)
    stock_ohlc.CAPITAL = SLEEVE_CAPITAL
    stock_panels = stock_ohlc.price_panels(stock_equity.index, stock_bars, etf_bars)
    stock_result = stock_ohlc.replay(
        "restored-universe stock sleeve",
        (stock_equity, stock_orders, SLIPPAGE_BPS, "restored_universe"),
        stock_panels,
        dividends,
    )
    etf_result = replay_etf_ohlc(etf_equity, etf_orders, files, SLEEVE_CAPITAL)
    if not stock_equity.index.equals(etf_result["dates"]):
        raise AssertionError("Stock and ETF sleeves do not share the same daily session index")

    dates = stock_equity.index
    combined_close = stock_result["closes"] + etf_result["closes"]
    combined_high = stock_result["highs"] + etf_result["highs"]
    combined_low = stock_result["lows"] + etf_result["lows"]
    assert len(dates) > 1 and dates[0] == START and dates[-1] == END
    assert np.all(combined_high + 0.03 >= combined_close)
    assert np.all(combined_low - 0.03 <= combined_close)
    combined_risk = risk_path(dates, CAPITAL, combined_close, combined_high, combined_low)
    equity = pd.DataFrame({
        "nav_stock_inr": stock_result["closes"],
        "nav_nifty_gold_inr": etf_result["closes"],
        "nav_total_inr": combined_close,
        "ohlc_high_bound_nav_inr": combined_high,
        "ohlc_low_bound_nav_inr": combined_low,
        "running_ohlc_peak_nav_inr": [row[0] for row in combined_risk["daily_risk"]],
        "ohlc_drawdown_bound_pct": [row[2] * 100 for row in combined_risk["daily_risk"]],
    }, index=dates)
    equity.index.name = "date"
    OUT.mkdir(parents=True, exist_ok=True)
    equity.to_csv(OUT / "equity.csv")
    stock_equity.to_csv(OUT / "stock_sleeve_equity.csv")
    stock_orders.to_csv(OUT / "stock_sleeve_orders.csv", index=False)
    etf_equity.to_csv(OUT / "nifty_gold_sleeve_equity.csv", index_label="time")
    etf_orders.to_csv(OUT / "nifty_gold_sleeve_orders.csv", index=False)

    stock_slippage = float(stock_stats["slippage_cost_inr"])
    etf_slippage = float(blend.modeled_slippage(etf_orders, panels))
    combined_fees = float(stock_stats["fees_inr"] + etf_stats["total_fees_inr"])
    combined_slippage = stock_slippage + etf_slippage
    summary = {
        "strategy": "50/50 initial capital: restored-universe stock momentum + quarterly 45%-cap NIFTY/Gold static mix",
        "period_start": dates[0].date().isoformat(), "period_end": dates[-1].date().isoformat(),
        "starting_balance_inr": CAPITAL, "ending_balance_inr": float(combined_close[-1]),
        "total_return_pct": float((combined_close[-1] / CAPITAL - 1) * 100),
        "cagr_pct": float(((combined_close[-1] / CAPITAL) ** (365.25 / (dates[-1] - dates[0]).days) - 1) * 100),
        **{k: v for k, v in combined_risk.items() if k != "daily_risk"},
        "within_20pct_ohlc_bound": bool(combined_risk["ohlc_drawdown_bound_pct"] >= -20.0),
        "stock_sleeve_starting_balance_inr": SLEEVE_CAPITAL,
        "stock_sleeve_ending_balance_inr": float(stock_result["closes"][-1]),
        "stock_sleeve_return_pct": float((stock_result["closes"][-1] / SLEEVE_CAPITAL - 1) * 100),
        "stock_sleeve_ohlc_bound_pct": float(stock_result["details"]["ohlc_drawdown_bound_pct"]),
        "nifty_gold_sleeve_starting_balance_inr": SLEEVE_CAPITAL,
        "nifty_gold_sleeve_ending_balance_inr": float(etf_result["closes"][-1]),
        "nifty_gold_sleeve_return_pct": float((etf_result["closes"][-1] / SLEEVE_CAPITAL - 1) * 100),
        "nifty_gold_sleeve_ohlc_bound_pct": float(risk_path(dates, SLEEVE_CAPITAL, etf_result["closes"], etf_result["highs"], etf_result["lows"])["ohlc_drawdown_bound_pct"]),
        "fees_inr": combined_fees, "slippage_cost_inr": combined_slippage,
        "orders": int(len(stock_orders) + len(etf_orders)), "slippage_bps_per_side": SLIPPAGE_BPS,
        "cash_yield_pct": 0.0, "max_stock_close_replay_error_inr": stock_result["details"]["max_close_replay_error_inr"],
        "max_etf_close_replay_error_inr": etf_result["max_close_replay_error_inr"],
        "stock_strategy": STOCK_RULE, "stock_exposure_cap_pct": STOCK_CAP * 100,
        "etf_strategy": "quarterly static 50/50 NIFTYBEES/GOLDBEES, 45% aggregate exposure cap",
        "etf_exposure_cap_pct": ETF_CAP * 100,
        "periods_already_inspected": True,
        "market_data_source": "Saved Upstox daily candles; stock candidate returns use the existing candidate dividend/unit treatment.",
    }
    (OUT / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")

    result_rows = []
    for label, start, end in (
        ("full_2021_2026", START, END),
        ("train_2021_2023", START, pd.Timestamp("2023-12-29")),
        ("validation_2024", pd.Timestamp("2024-01-01"), pd.Timestamp("2024-12-31")),
        ("holdout_2025_plus", pd.Timestamp("2025-01-01"), END),
    ):
        segment = equity.loc[(equity.index >= start) & (equity.index <= end)]
        if segment.empty:
            continue
        prior = equity.loc[equity.index < start]
        start_nav = CAPITAL if prior.empty else float(prior["nav_total_inr"].iloc[-1])
        end_nav = float(segment["nav_total_inr"].iloc[-1])
        previous_peak = CAPITAL if prior.empty else float(prior["running_ohlc_peak_nav_inr"].max())
        previous_close_peak = CAPITAL if prior.empty else max(CAPITAL, float(prior["nav_total_inr"].max()))
        running_peak = previous_peak
        segment_dd = 0.0
        for row in segment.itertuples():
            running_peak = max(running_peak, float(row.ohlc_high_bound_nav_inr))
            segment_dd = min(segment_dd, float(row.ohlc_low_bound_nav_inr) / running_peak - 1)
        result_rows.append({
            "strategy": "stock_nifty_gold_50_50_sleeve_blend", "period": label,
            "period_start": segment.index[0].date().isoformat(), "period_end": segment.index[-1].date().isoformat(),
            "starting_balance_inr": start_nav, "ending_balance_inr": end_nav,
            "total_return_pct": (end_nav / start_nav - 1) * 100,
            "close_max_drawdown_pct": float((segment["nav_total_inr"] / pd.concat([
                pd.Series([previous_close_peak]), segment["nav_total_inr"].reset_index(drop=True)
            ], ignore_index=True).cummax().iloc[1:].to_numpy()).sub(1).min() * 100),
            "ohlc_drawdown_bound_pct": segment_dd * 100, "within_20pct_ohlc": segment_dd >= -0.20,
            "fees_inr": combined_fees if label == "full_2021_2026" else "",
            "slippage_cost_inr": combined_slippage if label == "full_2021_2026" else "",
            "order_count": len(stock_orders) + len(etf_orders) if label == "full_2021_2026" else "",
            "slippage_bps_per_side": SLIPPAGE_BPS,
        })
    pd.DataFrame(result_rows).to_csv(SUMMARY_CSV, index=False)
    trade_count = int(stock_orders["side"].eq("sell").sum() + etf_orders["side"].eq("sell").sum())
    register_master_outputs(summary, len(stock_orders) + len(etf_orders), trade_count)
    print(json.dumps({"summary": summary, "periods": result_rows}, indent=2))


if __name__ == "__main__":
    main()
