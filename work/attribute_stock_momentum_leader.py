"""Attribute the frozen stock-momentum leader without changing its rule."""

from __future__ import annotations

import csv
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "work"))
import backtest_stock_momentum as stock
import backtest_stock_momentum_reassessment as reassessment

START, END = reassessment.START, reassessment.END
NAME = "all_saved__momentum_12_1_top15_full_exposure_buffer2"
PERIODS = reassessment.PERIODS
CAPITAL = reassessment.CAPITAL


def gross_replay(equity: pd.DataFrame, orders: pd.DataFrame, bars: dict, dividends: dict,
                 sectors: dict[str, str]) -> tuple[pd.Series, pd.DataFrame, dict[str, float]]:
    cash = float(CAPITAL)
    quantity: dict[str, int] = defaultdict(int)
    marks: dict[str, float] = {}
    by_day = {pd.Timestamp(day): group for day, group in orders.groupby("date")} if not orders.empty else {}
    rows, sector_rows = [], []
    symbol_pnl: dict[str, float] = defaultdict(float)
    for day in equity.index:
        for (symbol, ex_date), amount in dividends.items():
            if ex_date == day and quantity[symbol]:
                payout = quantity[symbol] * amount
                cash += payout
                symbol_pnl[symbol] += payout
        for order in by_day.get(day, pd.DataFrame()).itertuples():
            raw = float(order.raw_price)
            notional = int(order.quantity) * raw
            if order.side == "buy":
                cash -= notional
                quantity[order.symbol] += int(order.quantity)
                symbol_pnl[order.symbol] -= notional
            else:
                cash += notional
                quantity[order.symbol] -= int(order.quantity)
                symbol_pnl[order.symbol] += notional
        for symbol, frame in bars.items():
            if day in frame.index and pd.notna(frame.at[day, "close"]):
                marks[symbol] = float(frame.at[day, "close"])
        holdings = {symbol: qty * marks.get(symbol, 0.0) for symbol, qty in quantity.items() if qty > 0}
        nav = cash + sum(holdings.values())
        rows.append((day, nav))
        sector_value: dict[str, float] = defaultdict(float)
        for symbol, value in holdings.items():
            sector_value[sectors.get(symbol, "Unclassified") or "Unclassified"] += value
        sector_rows.append({"date": day, "nav": nav, **{sector: value / nav * 100 for sector, value in sector_value.items()}})
    result = pd.Series(dict(rows), name="gross_nav").sort_index()
    replay_net = replay_orders(equity.index, orders, bars, dividends, include_costs=True)
    if not np.allclose(replay_net.to_numpy(), equity["nav"].to_numpy(), atol=0.05, rtol=0):
        raise AssertionError("independent order replay does not reconcile to simulated NAV")
    terminal = orders.loc[orders.get("terminal_liquidation", pd.Series(False, index=orders.index)).astype(str).str.lower().eq("true")]
    if not terminal.empty and any(quantity.values()):
        raise AssertionError("terminal order replay leaves a position open")
    return result, pd.DataFrame(sector_rows).set_index("date"), symbol_pnl


def replay_orders(dates: pd.DatetimeIndex, orders: pd.DataFrame, bars: dict, dividends: dict,
                  include_costs: bool) -> pd.Series:
    cash, quantity, marks = float(CAPITAL), defaultdict(int), {}
    by_day = {pd.Timestamp(day): group for day, group in orders.groupby("date")} if not orders.empty else {}
    values = []
    for day in dates:
        for (symbol, ex_date), amount in dividends.items():
            if ex_date == day:
                cash += quantity[symbol] * amount
        for order in by_day.get(day, pd.DataFrame()).itertuples():
            price = float(order.fill_price if include_costs else order.raw_price)
            fee = float(order.total) if include_costs else 0.0
            notional = int(order.quantity) * price
            if order.side == "buy":
                cash -= notional + fee
                quantity[order.symbol] += int(order.quantity)
            else:
                cash += notional - fee
                quantity[order.symbol] -= int(order.quantity)
        for symbol, frame in bars.items():
            if day in frame.index and pd.notna(frame.at[day, "close"]):
                marks[symbol] = float(frame.at[day, "close"])
        values.append(cash + sum(qty * marks.get(symbol, 0.0) for symbol, qty in quantity.items() if qty))
    return pd.Series(values, index=dates)


def cagr_for_window(nav: pd.Series, start: pd.Timestamp, end: pd.Timestamp) -> float | None:
    segment = nav.loc[(nav.index >= start) & (nav.index <= end)]
    if segment.empty:
        return None
    previous = nav.loc[nav.index < start]
    baseline = float(previous.iloc[-1]) if not previous.empty else float(CAPITAL)
    baseline_date = previous.index[-1] if not previous.empty else segment.index[0]
    return stock.q._calendar_cagr_pct(baseline, float(segment.iloc[-1]), baseline_date, segment.index[-1])


def matched_benchmark_cagr(benchmark: pd.Series, nav: pd.Series, start: pd.Timestamp, end: pd.Timestamp) -> float | None:
    segment = nav.loc[(nav.index >= start) & (nav.index <= end)]
    if segment.empty:
        return None
    previous = nav.loc[nav.index < start]
    baseline_date = previous.index[-1] if not previous.empty else segment.index[0]
    benchmark_start = float(benchmark.loc[baseline_date])
    benchmark_end = float(benchmark.loc[benchmark.index <= segment.index[-1]].iloc[-1])
    return stock.q._calendar_cagr_pct(benchmark_start, benchmark_end, baseline_date, segment.index[-1])


def main() -> None:
    bars, tri, dividends = stock.load_prices()
    etf = pd.read_csv(stock.DATA / "etf_daily" / "NSE_EQ_INF204KB14I2-days-1-2014-01-01-2026-10-23.csv", parse_dates=["time"])
    etf["date"] = etf["time"].dt.tz_localize(None).dt.normalize()
    etf = etf.drop_duplicates("date").set_index("date").sort_index()
    market_close = etf["close"].astype(float)
    schedules, _ = reassessment.build_schedules(bars, tri, market_close)
    sector_rows = stock.read_csv(stock.SOURCE / "current_nifty50_constituents_2026-09-30.csv")
    sectors = {row["Symbol"]: row["Industry"] for row in sector_rows}
    benchmark_rows = pd.read_csv(stock.DATA / "index_daily" / "NIFTY50TR-days-1-2014-01-01-2026-10-23.csv", parse_dates=["date"])
    benchmark = benchmark_rows.drop_duplicates("date").set_index("date")["tri"].astype(float).sort_index()

    passive_panels = {
        field: pd.DataFrame({"NIFTYBEES": pd.to_numeric(etf[field], errors="coerce")}, index=etf.index)
        for field in ("open", "high", "low", "close")
    }
    passive_targets = pd.DataFrame(1.0, index=etf.index, columns=["NIFTYBEES"])
    passive_events = pd.Series(False, index=etf.index)
    passive_equity, passive_orders, passive_stats = stock.q._simulate(
        passive_panels, passive_targets, passive_events, CAPITAL, 1.0, 50,
        "equity_delivery", START.date(), END.date(),
    )
    passive_cash, passive_quantity = float(CAPITAL), 0
    passive_by_day = {pd.Timestamp(day): group for day, group in passive_orders.groupby("time")}
    passive_errors = []
    for day, row in passive_equity.iterrows():
        for order in passive_by_day.get(day, pd.DataFrame()).itertuples():
            notional = int(order.quantity) * float(order.fill_price)
            if order.side == "buy":
                passive_cash -= notional + float(order.total)
                passive_quantity += int(order.quantity)
            else:
                passive_cash += notional - float(order.total)
                passive_quantity -= int(order.quantity)
        replay_nav = passive_cash + passive_quantity * float(passive_panels["close"].at[day, "NIFTYBEES"])
        passive_errors.append(abs(replay_nav - float(row["nav"])))
    if max(passive_errors, default=0.0) > 0.05 or passive_quantity != 0:
        raise AssertionError("NIFTYBEES passive order replay does not reconcile or leaves a terminal position")
    passive_slippage = 0.0
    for order in passive_orders.itertuples():
        terminal = order.side == "sell" and str(order.terminal_liquidation).lower() == "true"
        raw_field = "close" if terminal else "open"
        raw_price = float(passive_panels[raw_field].at[order.time, "NIFTYBEES"])
        passive_slippage += int(order.quantity) * abs(float(order.fill_price) - raw_price)
    passive_row = {
        "benchmark": "NIFTYBEES buy-and-hold, 100% unlevered; price-only ETF series",
        "period_start": passive_stats["first_bar"][:10], "period_end": passive_stats["last_bar"][:10],
        "starting_balance_inr": CAPITAL, "ending_balance_inr": passive_stats["ending_balance_inr"],
        "calendar_cagr_pct": passive_stats["cagr_pct"], "close_mdd_pct": passive_stats["max_drawdown_pct"],
        "fees_inr": passive_stats["total_fees_inr"], "slippage_cost_inr": passive_slippage,
        "orders": passive_stats["order_count"], "independent_replay_max_error_inr": max(passive_errors, default=0.0),
        "slippage_bps_per_side": 50,
    }
    pd.DataFrame([passive_row]).to_csv(stock.OUT / "stock_momentum_passive_comparison_2026-10-31.csv", index=False)

    outputs, selected = [], None
    for bps in (10, 50):
        equity, orders, stats = stock.simulate(NAME, bars, dividends, schedules[NAME], 1.0, bps, START, END)
        gross, sector_weights, _ = gross_replay(equity, orders, bars, dividends, sectors)
        if bps == 50:
            selected = (equity, orders, stats, gross, sector_weights)
        for label, start, end in PERIODS:
            row = stock.period_row(stats, equity, orders, label, start, end)
            if row is None:
                continue
            benchmark_cagr = float(matched_benchmark_cagr(benchmark, equity["nav"], start, end))
            gross_cagr = cagr_for_window(gross, start, end)
            section = equity.loc[(equity.index >= start) & (equity.index <= end), "nav"]
            previous = equity.loc[equity.index < start, "nav"]
            baseline = float(previous.iloc[-1]) if not previous.empty else float(CAPITAL)
            net_returns = section.pct_change()
            if not net_returns.empty:
                net_returns.iloc[0] = float(section.iloc[0]) / baseline - 1
            aligned = pd.concat([net_returns.rename("strategy"), benchmark.pct_change().reindex(section.index).rename("benchmark")], axis=1).dropna()
            beta = float(aligned.cov().loc["strategy", "benchmark"] / aligned["benchmark"].var()) if len(aligned) > 2 and aligned["benchmark"].var() else np.nan
            order_days = pd.to_datetime(orders["date"]) if not orders.empty else pd.Series(dtype="datetime64[ns]")
            period_orders = orders.loc[(order_days >= start) & (order_days <= end)] if not orders.empty else orders
            outputs.append({"strategy": NAME, "window": label, "slippage_bps_per_side": bps,
                            "gross_same_shares_cagr_pct": gross_cagr, "net_cagr_pct": float(row["cagr_pct"]),
                            "nifty50_tri_cagr_pct": benchmark_cagr,
                            "net_excess_vs_nifty50_pp": float(row["cagr_pct"]) - benchmark_cagr,
                            "market_beta_to_nifty50_tri": beta, "fees_inr": float(period_orders["total"].sum()) if not period_orders.empty else 0.0,
                            "slippage_cost_inr": float(period_orders.apply(lambda x: int(x["quantity"]) * abs(float(x["fill_price"]) - float(x["raw_price"])), axis=1).sum()) if not period_orders.empty else 0.0,
                            "traded_notional_inr": float(period_orders["notional"].sum()) if not period_orders.empty else 0.0,
                            "orders": len(period_orders), "capital_turnovers": float(period_orders["notional"].sum()) / CAPITAL if not period_orders.empty else 0.0})

    assert selected is not None
    equity, orders, stats, gross, sector_weights = selected
    annual_turnover = float(orders["notional"].sum()) / CAPITAL / ((END - START).days / 365.25)
    benchmark_cagr = float(pd.read_csv(stock.OUT / "stock_momentum_benchmark_comparison.csv").query("row_type == 'official_index' and scenario == 'NIFTY 50 Total Return' and period == 'full_2021_2026'").iloc[0]["cagr_pct"])
    lo, hi = 0.0, 500.0
    _, _, zero_stats = stock.simulate(NAME, bars, dividends, schedules[NAME], 1.0, 0, START, END)
    _, _, upper_stats = stock.simulate(NAME, bars, dividends, schedules[NAME], 1.0, 500, START, END)
    if float(zero_stats["cagr_pct"]) <= benchmark_cagr or float(upper_stats["cagr_pct"]) >= benchmark_cagr:
        raise AssertionError("break-even slippage is not bracketed by 0 and 500 bps")
    for _ in range(14):
        mid = (lo + hi) / 2
        _, _, test_stats = stock.simulate(NAME, bars, dividends, schedules[NAME], 1.0, mid, START, END)
        if float(test_stats["cagr_pct"]) > benchmark_cagr:
            lo = mid
        else:
            hi = mid
    break_even_bps = (lo + hi) / 2

    full_sector = sector_weights.loc[(sector_weights.index >= START) & (sector_weights.index <= END)].drop(columns="nav", errors="ignore").fillna(0.0)
    sector_summary = []
    for sector in full_sector.columns:
        sector_summary.append({"sector_basis": "2026-09-30 industry labels applied retrospectively",
                               "industry": sector, "average_exposure_pct_of_nav": float(full_sector[sector].mean()),
                               "peak_exposure_pct_of_nav": float(full_sector[sector].max())})
    pd.DataFrame(outputs).to_csv(stock.OUT / "stock_momentum_attribution_2026-10-31.csv", index=False)
    pd.DataFrame(sector_summary).sort_values("average_exposure_pct_of_nav", ascending=False).to_csv(stock.OUT / "stock_momentum_sector_exposure_2026-10-31.csv", index=False)
    print({"strategy": NAME, "full_period_net_ending_inr": stats["ending_balance_inr"],
           "gross_same_shares_ending_inr": float(gross.iloc[-1]), "full_fees_inr": stats["fees_inr"],
           "full_slippage_cost_inr": stats["slippage_cost_inr"], "full_order_notional_inr": float(orders["notional"].sum()),
           "annual_turnover_x_initial_capital": annual_turnover, "break_even_slippage_bps_per_side_vs_nifty50_tri": break_even_bps,
           "niftybees_passive_net_cagr_pct": passive_stats["cagr_pct"],
           "niftybees_passive_end_nav_inr": passive_stats["ending_balance_inr"],
           "niftybees_replay_max_error_inr": max(passive_errors, default=0.0),
           "output_rows": len(outputs), "sector_rows": len(sector_summary)})


if __name__ == "__main__":
    main()
