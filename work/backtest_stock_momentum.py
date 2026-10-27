"""Preliminary, dividend-aware point-in-time NIFTY 50 momentum screen."""

from __future__ import annotations

import csv
import json
import math
import os
import tempfile
from collections import defaultdict
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

import upstox_quant as q


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "work" / "data"
SOURCE = DATA / "universe_sources"
OUT = ROOT / "outputs"
CAPITAL = 1_000_000
EXPOSURE = 0.95
EXPOSURE_GRID = (0.50, 0.60, 0.70, 0.80, 0.95)
SLIPPAGE_BPS = 10
DD_LIMIT = 20
START = pd.Timestamp("2021-02-01")
END = pd.Timestamp("2026-10-23")
ALIASES = {"TATAMOTORS": "TMPV", "DUMMYTATAM": "TMCV", "DUMMYITC": "ITCHOTELS", "DUMMYHDLVR": "KWIL",
           "ZOMATO": "ETERNAL", "LTIM": "LTM", "INFRATEL": "INDUSTOWER"}
# These names cross unresolved rights, merger, or demerger accounting in the saved event sources.
ACTION_EXCLUSIONS = {
    "HDFC", "RELIANCE", "ITC", "SIEMENS", "TMPV", "HINDUNILVR", "VEDL",
    "ADANIENT", "BHARTIARTL", "GRASIM", "SHRIRAMFIN", "TATACONSUM", "UPL",
}
STRATEGIES = {
    "stock_top5_mom12_1": {"top_k": 5, "trend_filter": False},
    "stock_top5_mom12_1_trend200": {"top_k": 5, "trend_filter": True},
    "stock_top10_mom12_1_trend200": {"top_k": 10, "trend_filter": True},
    "stock_top10_mom12_1_trend200_market200": {"top_k": 10, "trend_filter": True, "market_filter": True},
}


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def atomic_csv(path: Path, rows: list[dict], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", newline="", delete=False, dir=path.parent, suffix=".tmp") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
        temporary = Path(handle.name)
    os.replace(temporary, path)


def load_prices() -> tuple[dict[str, pd.DataFrame], pd.DataFrame, dict[tuple[str, pd.Timestamp], float]]:
    coverage = read_csv(SOURCE / "stock_history_coverage.csv")
    dividend_rows = read_csv(OUT / "stock_dividend_share_unit_alignment.csv")
    dividends: dict[tuple[str, pd.Timestamp], float] = defaultdict(float)
    for row in dividend_rows:
        amount = row["candidate_dividend_per_candle_share_inr"]
        symbol = ALIASES.get(row["symbol"], row["symbol"])
        if amount:
            dividends[(symbol, pd.Timestamp(row["ex_date"]))] += float(amount)

    bars: dict[str, pd.DataFrame] = {}
    for row in coverage:
        symbol = ALIASES.get(row["trading_symbol"], row["trading_symbol"])
        frame = pd.read_csv(ROOT / row["cache_path"], parse_dates=["time"])
        frame["date"] = pd.to_datetime(frame["time"]).dt.tz_localize(None).dt.normalize()
        frame = frame.drop_duplicates("date").set_index("date").sort_index()
        frame = frame.loc[:, ["open", "high", "low", "close", "volume"]].apply(pd.to_numeric, errors="coerce")
        if symbol in bars:
            raise ValueError(f"Duplicate price history after ticker aliasing: {symbol}")
        bars[symbol] = frame
    assert len(bars) == 70 and all(not frame.empty for frame in bars.values())
    assert all(frame.index.is_monotonic_increasing and not frame.index.has_duplicates for frame in bars.values())

    # Work with total-return indices for ranking; actual fills and portfolio marks remain cash OHLC.
    tri = pd.DataFrame(index=sorted(set().union(*(set(frame.index) for frame in bars.values()))))
    for symbol, frame in bars.items():
        close = frame["close"].astype(float)
        cash = pd.Series([dividends.get((symbol, dt), 0.0) for dt in close.index], index=close.index, dtype="float64")
        gross = (close + cash) / close.shift(1)
        gross.iloc[0] = 1.0
        tri[symbol] = gross.cumprod()
    return bars, tri, dividends


def build_targets(bars: dict[str, pd.DataFrame], tri: pd.DataFrame, market_close: pd.Series) -> tuple[dict[str, dict[pd.Timestamp, dict]], list[dict]]:
    memberships = read_csv(SOURCE / "nifty50_monthly_universe_2020_2026.csv")
    market_dates = pd.DatetimeIndex(sorted(set().union(*(set(frame.index) for frame in bars.values()))))
    by_symbol: dict[str, pd.Series] = {}
    sma200: dict[str, pd.Series] = {}
    for symbol in tri.columns:
        by_symbol[symbol] = tri[symbol].dropna()
        sma200[symbol] = by_symbol[symbol].rolling(200, min_periods=200).mean()
    market_close = market_close.astype(float).sort_index()
    market_sma200 = market_close.rolling(200, min_periods=200).mean()

    targets = {f"{name}@{int(exposure * 100)}%": {} for name in STRATEGIES for exposure in EXPOSURE_GRID}
    picks = []
    for snapshot in memberships:
        signal_date = pd.Timestamp(snapshot["signal_date"])
        execution_pos = market_dates.searchsorted(signal_date, side="right")
        if execution_pos >= len(market_dates):
            continue
        execution_date = market_dates[execution_pos]
        members = [ALIASES.get(symbol, symbol) for symbol in snapshot["members"].split(";")]
        market_ok = bool(market_close.get(signal_date, np.nan) > market_sma200.get(signal_date, np.nan))
        candidates = []
        for symbol in members:
            if symbol in ACTION_EXCLUSIONS or symbol not in by_symbol:
                continue
            series = by_symbol[symbol]
            pos = series.index.get_indexer([signal_date])[0]
            if pos < 252:
                continue
            # 12-1 momentum: trailing 12-month total return excluding the latest 21 sessions.
            momentum = float(series.iloc[pos - 21] / series.iloc[pos - 252] - 1.0)
            trend_line = sma200[symbol]
            above_200 = bool(series.iloc[pos] > trend_line.loc[signal_date]) if pd.notna(trend_line.loc[signal_date]) else False
            candidates.append({"symbol": symbol, "momentum_12_1_pct": momentum * 100, "above_200dma": above_200})

        for strategy, rules in STRATEGIES.items():
            eligible = [x for x in candidates if x["momentum_12_1_pct"] > 0 and (x["above_200dma"] or not rules["trend_filter"])]
            if rules.get("market_filter") and not market_ok:
                eligible = []
            eligible.sort(key=lambda x: (-x["momentum_12_1_pct"], x["symbol"]))
            selected = eligible[: rules["top_k"]]
            for exposure in EXPOSURE_GRID:
                run_name = f"{strategy}@{int(exposure * 100)}%"
                weights = {x["symbol"]: exposure / len(selected) for x in selected} if selected else {}
                targets[run_name][execution_date] = {"signal_date": signal_date, "weights": weights}
                for rank, item in enumerate(selected, 1):
                    picks.append({
                        "strategy": run_name, "signal_date": signal_date.date().isoformat(),
                        "execution_date": execution_date.date().isoformat(), "rank": rank,
                        "symbol": item["symbol"], "momentum_12_1_pct": item["momentum_12_1_pct"],
                        "above_200dma": item["above_200dma"], "weight_pct": weights[item["symbol"]] * 100,
                        "eligible_count": len(eligible), "market_filter_passed": market_ok,
                        "provisional_universe_members": len(members),
                    })
    return targets, picks


def simulate(name: str, bars: dict[str, pd.DataFrame], dividends: dict[tuple[str, pd.Timestamp], float],
             scheduled: dict[pd.Timestamp, dict], exposure_cap: float = EXPOSURE, slippage_bps: float = SLIPPAGE_BPS,
             start: pd.Timestamp = START, end: pd.Timestamp = END) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    dates = pd.DatetimeIndex(sorted(set().union(*(set(frame.index) for frame in bars.values()))))
    dates = dates[(dates >= start) & (dates <= end)]
    close = pd.DataFrame({s: f["close"] for s, f in bars.items()}).reindex(dates)
    opening = pd.DataFrame({s: f["open"] for s, f in bars.items()}).reindex(dates)
    quantity = defaultdict(int)
    cash = float(CAPITAL)
    marks: dict[str, float] = {}
    costs = defaultdict(float)
    orders = []
    equity = []
    turnover = 0.0
    slip_rate = slippage_bps / 10_000
    fee_products = {symbol: q.FUND_FEE_PRODUCTS.get(symbol, "equity_delivery") for symbol in bars}

    for i, dt in enumerate(dates):
        # Cash dividends belong to shares carried through the prior close, including shares sold today.
        dividend_cash = sum(quantity[symbol] * amount for (symbol, exdate), amount in dividends.items()
                            if exdate == dt and quantity[symbol])
        cash += dividend_cash
        nav_before = cash + sum(qty * marks[s] for s, qty in quantity.items() if qty and s in marks)
        event = scheduled.get(dt)
        if event:
            weights = event["weights"]
            signal_date = event["signal_date"]
            desired = {
                s: int(math.floor(nav_before * weight / float(bars[s].at[signal_date, "close"])))
                if s in bars and signal_date in bars[s].index and pd.notna(bars[s].at[signal_date, "close"])
                and float(bars[s].at[signal_date, "close"]) > 0 else 0
                for s, weight in weights.items()
            }
            names = set(quantity) | set(desired)
            for symbol in sorted(names):
                delta = quantity[symbol] - desired.get(symbol, 0)
                raw = opening.at[dt, symbol] if symbol in opening.columns else np.nan
                if delta <= 0 or pd.isna(raw):
                    continue
                fill = float(raw) * (1 - slip_rate)
                notional = delta * fill
                fee = q._fee_breakdown(notional, "sell", fee_products.get(symbol, "equity_delivery"))
                cash += notional - fee["total"]
                quantity[symbol] -= delta
                turnover += notional
                costs["fees"] += fee["total"]
                costs["slippage"] += delta * abs(fill - float(raw))
                orders.append({"date": dt.date().isoformat(), "symbol": symbol, "side": "sell", "quantity": delta,
                               "raw_price": float(raw), "fill_price": fill, "notional": notional, **fee})
            for symbol in sorted(names):
                delta = desired.get(symbol, 0) - quantity[symbol]
                raw = opening.at[dt, symbol] if symbol in opening.columns else np.nan
                if delta <= 0 or pd.isna(raw):
                    continue
                fill = float(raw) * (1 + slip_rate)
                lo, hi = 0, delta
                while lo < hi:
                    mid = (lo + hi + 1) // 2
                    if mid * fill + q._fee_breakdown(mid * fill, "buy", fee_products.get(symbol, "equity_delivery"))["total"] <= cash:
                        lo = mid
                    else:
                        hi = mid - 1
                delta = lo
                if not delta:
                    continue
                notional = delta * fill
                fee = q._fee_breakdown(notional, "buy", fee_products.get(symbol, "equity_delivery"))
                cash -= notional + fee["total"]
                quantity[symbol] += delta
                turnover += notional
                costs["fees"] += fee["total"]
                costs["slippage"] += delta * abs(fill - float(raw))
                orders.append({"date": dt.date().isoformat(), "symbol": symbol, "side": "buy", "quantity": delta,
                               "raw_price": float(raw), "fill_price": fill, "notional": notional, **fee})

        for symbol in close.columns:
            value = close.at[dt, symbol]
            if pd.notna(value):
                marks[symbol] = float(value)
        nav = cash + sum(qty * marks[s] for s, qty in quantity.items() if qty and s in marks)
        invested = sum(qty * marks[s] for s, qty in quantity.items() if qty and s in marks)
        equity.append({"date": dt, "nav": nav, "cash": cash, "invested": invested,
                       "exposure_pct": invested / nav * 100 if nav > 0 else 0,
                       "holdings": sum(qty > 0 for qty in quantity.values())})

    if quantity:
        terminal_date = dates[-1]
        for symbol, qty in sorted(quantity.items()):
            raw = marks.get(symbol, np.nan)
            if qty <= 0 or pd.isna(raw):
                continue
            fill = float(raw) * (1 - slip_rate)
            notional = qty * fill
            fee = q._fee_breakdown(notional, "sell", fee_products.get(symbol, "equity_delivery"))
            cash += notional - fee["total"]
            turnover += notional
            costs["fees"] += fee["total"]
            costs["slippage"] += qty * abs(fill - float(raw))
            last_bar_date = bars[symbol].loc[:terminal_date].index[-1] if symbol in bars else terminal_date
            orders.append({"date": last_bar_date.date().isoformat(), "symbol": symbol, "side": "sell", "quantity": qty,
                           "raw_price": float(raw), "fill_price": fill, "notional": notional,
                           "terminal_liquidation": True, **fee})
        equity[-1].update({"nav": cash, "cash": cash, "invested": 0.0, "exposure_pct": 0.0, "holdings": 0})

    eq = pd.DataFrame(equity).set_index("date")
    rets = eq["nav"].pct_change().replace([np.inf, -np.inf], np.nan).fillna(0.0)
    rets.iloc[0] = eq["nav"].iloc[0] / CAPITAL - 1
    dd = pd.concat([pd.Series([CAPITAL]), eq["nav"].reset_index(drop=True)], ignore_index=True)
    max_dd = float((dd / dd.cummax() - 1).min() * 100)
    years = max((eq.index[-1] - start).days / 365.25, 1 / 252)
    total_ret = float(eq["nav"].iloc[-1] / CAPITAL - 1)
    sd = float(rets.std(ddof=1)) if len(rets) > 1 else 0.0
    stats = {
        "simulation_type": "stock_cross_sectional_momentum", "strategy": name,
        "universe": f"Provisional point-in-time NIFTY 50; {len(ACTION_EXCLUSIONS)} unresolved action-source names excluded",
        "period": f"{start.date()} to {end.date()}", "period_start": start.date().isoformat(), "period_end": eq.index[-1].date().isoformat(),
        "starting_balance_inr": CAPITAL, "ending_balance_inr": float(eq["nav"].iloc[-1]),
        "total_return_pct": total_ret * 100, "cagr_pct": ((1 + total_ret) ** (1 / years) - 1) * 100 if total_ret > -1 else -100,
        "max_drawdown_pct": max_dd, "sharpe_zero_rf": float(rets.mean() / sd * math.sqrt(252)) if sd else 0.0,
        "gross_exposure_cap_pct": exposure_cap * 100, "slippage_bps_per_side": slippage_bps,
        "fees_inr": costs["fees"], "slippage_cost_inr": costs["slippage"],
        "trade_count": sum(1 for x in orders if x["side"] == "sell"), "order_count": len(orders),
        "within_20pct": max_dd >= -DD_LIMIT,
        "selection_or_sizing": "Monthly point-in-time NIFTY 50 snapshot; rank positive 12-1 total return, optional stock and NIFTYBEES 200-session filters; equal-weight top K; next-session-open fills; integer shares",
        "source_artifact": "outputs/stock_momentum_screen.csv; see outputs/stock_momentum_method.md",
        "notes": "Current Upstox/NSE delivery fees + 10 bps per side; dividends credited from candidate share-unit-aligned NSE notices; known rights/merger/demerger source names excluded throughout. Research screen, not a verified total-return winner.",
    }
    return eq, pd.DataFrame(orders), stats


def period_row(stats: dict, eq: pd.DataFrame, orders: pd.DataFrame, label: str,
               start: pd.Timestamp, end: pd.Timestamp) -> dict | None:
    segment = eq.loc[(eq.index >= start) & (eq.index <= end)]
    if segment.empty:
        return None
    previous = eq.loc[eq.index < start, "nav"]
    baseline = float(previous.iloc[-1]) if not previous.empty else float(CAPITAL)
    nav = pd.concat([pd.Series([baseline]), segment["nav"].reset_index(drop=True)], ignore_index=True)
    returns = nav.pct_change().dropna()
    period_drawdown = nav / nav.cummax() - 1
    prior_peak = max(float(CAPITAL), float(previous.max())) if not previous.empty else float(CAPITAL)
    path_peaks = np.maximum(prior_peak, segment["nav"].cummax().to_numpy())
    continuous_drawdown = segment["nav"].to_numpy() / path_peaks - 1
    elapsed_years = max((segment.index[-1] - start).days / 365.25, 1 / 252)
    total_return = float(segment["nav"].iloc[-1] / baseline - 1)
    subset = orders.loc[(orders["date"] >= start.date().isoformat()) & (orders["date"] <= segment.index[-1].date().isoformat())] if not orders.empty else orders
    fees = float(subset["total"].sum()) if not subset.empty else 0.0
    slippage = float((subset["quantity"] * (subset["fill_price"] - subset["raw_price"]).abs()).sum()) if not subset.empty else 0.0
    sd = float(returns.std(ddof=1)) if len(returns) > 1 else 0.0
    return {
        **stats, "period": label, "period_start": start.date().isoformat(),
        "period_end": segment.index[-1].date().isoformat(), "starting_balance_inr": baseline,
        "ending_balance_inr": float(segment["nav"].iloc[-1]), "total_return_pct": total_return * 100,
        "cagr_pct": ((1 + total_return) ** (1 / elapsed_years) - 1) * 100 if total_return > -1 else -100.0,
        "max_drawdown_pct": float(continuous_drawdown.min() * 100),
        "period_max_drawdown_pct": float(period_drawdown.min() * 100),
        "sharpe_zero_rf": float(returns.mean() / sd * math.sqrt(252)) if sd else 0.0,
        "fees_inr": fees, "slippage_cost_inr": slippage,
        "trade_count": int((subset["side"] == "sell").sum()) if not subset.empty else 0,
        "order_count": len(subset), "within_20pct": float(continuous_drawdown.min() * 100) >= -DD_LIMIT,
    }


def main() -> None:
    bars, tri, dividends = load_prices()
    etf = pd.read_csv(DATA / "etf_daily" / "NSE_EQ_INF204KB14I2-days-1-2014-01-01-2026-10-23.csv", parse_dates=["time"])
    etf["date"] = pd.to_datetime(etf["time"]).dt.tz_localize(None).dt.normalize()
    etf = etf.drop_duplicates("date").set_index("date").sort_index()
    targets, picks = build_targets(bars, tri, etf["close"])
    assert len(targets) == len(STRATEGIES) * len(EXPOSURE_GRID) and len(picks) > 0
    full_results = []
    equity_rows = []
    order_rows = []
    for strategy, schedule in targets.items():
        exposure = int(strategy.rsplit("@", 1)[1].rstrip("%")) / 100
        eq, orders, stats = simulate(strategy, bars, dividends, schedule, exposure)
        full_results.append(stats)
        equity_rows.extend({"strategy": strategy, **row} for row in eq.reset_index().to_dict("records"))
        order_rows.extend({"strategy": strategy, **row} for row in orders.to_dict("records"))

    for base in ("stock_top10_mom12_1_trend200@95%", "stock_top10_mom12_1_trend200_market200@95%"):
        schedule = targets[base]
        for stress_bps in (20, 50):
            stress_name = f"{base}_slip{stress_bps}"
            eq, orders, stats = simulate(stress_name, bars, dividends, schedule, 0.95, stress_bps)
            full_results.append(stats)
            equity_rows.extend({"strategy": stress_name, **row} for row in eq.reset_index().to_dict("records"))
            order_rows.extend({"strategy": stress_name, **row} for row in orders.to_dict("records"))

    # NIFTYBEES buy-and-hold is the investable benchmark; ETF distributions are not reconciled here.
    benchmark = {"NIFTYBEES": etf.loc[:, ["open", "high", "low", "close", "volume"]]}
    bench_dates = pd.DatetimeIndex(sorted(set().union(*(set(frame.index) for frame in benchmark.values()))))
    first_entry = bench_dates[bench_dates >= START][0]
    bench_schedule = {first_entry: {"signal_date": bench_dates[bench_dates < first_entry][-1], "weights": {"NIFTYBEES": EXPOSURE}}}
    eq, orders, stats = simulate("NIFTYBEES buy-and-hold benchmark", benchmark, {}, bench_schedule, EXPOSURE)
    stats["universe"] = "NIFTYBEES Upstox daily cash candles; distributions not separately reconciled"
    full_results.append(stats)
    equity_rows.extend({"strategy": "NIFTYBEES buy-and-hold benchmark", **row} for row in eq.reset_index().to_dict("records"))
    order_rows.extend({"strategy": "NIFTYBEES buy-and-hold benchmark", **row} for row in orders.to_dict("records"))

    assert all(x["max_drawdown_pct"] <= 0 for x in full_results)
    assert all(x["fees_inr"] > 0 and x["slippage_cost_inr"] > 0 for x in full_results)
    assert all(x["ending_balance_inr"] > 0 for x in full_results)
    windows = [("train_2021_2023", START, pd.Timestamp("2023-12-31")),
               ("validation_2024", pd.Timestamp("2024-01-01"), pd.Timestamp("2024-12-31")),
               ("holdout_2025_plus", pd.Timestamp("2025-01-01"), END),
               ("full_2021_2026", START, END)]
    by_strategy = {name: (pd.DataFrame([r for r in equity_rows if r["strategy"] == name]).set_index("date"),
                          pd.DataFrame([r for r in order_rows if r["strategy"] == name]))
                   for name in {r["strategy"] for r in equity_rows}}
    results = []
    for stats in full_results:
        eq, orders = by_strategy[stats["strategy"]]
        for label, begin, finish in windows:
            row = period_row(stats, eq, orders, label, begin, finish)
            if row:
                results.append(row)
    train = [r for r in results if r["period"] == "train_2021_2023" and r["strategy"].startswith("stock_")
             and int(r["slippage_bps_per_side"]) == SLIPPAGE_BPS and r["within_20pct"]]
    selected = max(train, key=lambda x: (x["cagr_pct"], -x["gross_exposure_cap_pct"], x["strategy"]))["strategy"] if train else ""
    for row in results:
        row["selected_on_training_only"] = row["strategy"] == selected
    atomic_csv(OUT / "stock_momentum_screen.csv", results, list(results[0]))
    atomic_csv(OUT / "stock_momentum_monthly_picks.csv", picks, list(picks[0]))
    atomic_csv(OUT / "stock_momentum_daily_equity.csv", equity_rows, list(equity_rows[0]))
    atomic_csv(OUT / "stock_momentum_orders.csv", order_rows, sorted({key for row in order_rows for key in row}))

    method = OUT / "stock_momentum_method.md"
    method.write_text(
        "# Preliminary NIFTY 50 stock momentum screen\n\n"
        f"**Run date:** {date.today().isoformat()}  \n**Evaluation:** {START.date()} to {END.date()}  \n**Capital:** ₹10,00,000; 95% exposure ceiling; 20% historical drawdown screen; 10 bps per-side slippage.\n\n"
        "## Frozen comparisons and time split\n\n"
        "- Monthly equal-weight top 5 positive 12-1 total-return momentum.\n"
        "- Same top-5 rank with close above its 200-session total-return average.\n"
        "- Same 200-session filter with top 10 holdings.\n"
        "- Same top 10 with both stock and NIFTYBEES closes above their respective 200-session averages.\n"
        "Signals use the month-end point-in-time NIFTY 50 snapshot and execute at the next session open. Each rule is run at 50%, 60%, 70%, 80%, and 95% exposure. The exposure and rule with the highest train CAGR among train-period cases inside the 20% drawdown screen is selected; its 2024 and 2025+ rows are reported separately. Orders are integer-share NSE cash delivery with Upstox's current published fee schedule applied uniformly, 10 bps baseline slippage per side, and no cash interest. The unfiltered and market-filtered top-10 95% variants are stressed at 20 and 50 bps per side. All positions are liquidated at the end and charged.\n\n"
        "## Return and corporate-action treatment\n\n"
        "Dividend cash is credited on ex-date to positions held through the previous close. Parsed dividend amounts are converted to the observed Upstox candle share unit using later split/bonus factors where available; Upstox's adjustment convention and the NSE page feed's completeness are not guaranteed. The event feed records separate same-date notices and the script sums their parsed amounts.\n\n"
        f"The following {len(ACTION_EXCLUSIONS)} source symbols are excluded for the entire sample because their rights, merger, or demerger position path is not reconciled: {', '.join(sorted(ACTION_EXCLUSIONS))}. This materially narrows the historical NIFTY 50 universe and can bias results. Other unrecognized corporate actions, point-in-time membership archive incompleteness, taxes, and historical fee changes remain risks. NIFTYBEES is an investable price benchmark; ETF distributions are not separately reconstructed.\n\n"
        "The screen's `max_drawdown_pct` carries the account high-water mark from the start of the simulation through each window; `period_max_drawdown_pct` resets at the window boundary. The NIFTYBEES market 200DMA gate was added after the first stock-rule results were inspected, so all gated results are explicitly post-hoc comparisons and need fresh forward validation. These runs are not untouched out-of-sample evidence: the underlying data and several other strategy results have already been inspected. A 20% historical drawdown pass is not a future loss bound. See `stock_momentum_screen.csv`, `stock_momentum_monthly_picks.csv`, `stock_momentum_daily_equity.csv`, and `stock_momentum_orders.csv` for reproducible details.\n",
        encoding="utf-8",
    )

    # Idempotently replace this run's rows and register every user-facing artifact.
    ledger_path = OUT / "backtest_summary.csv"
    ledger = read_csv(ledger_path)
    ledger_fields = list(ledger[0])
    prefix = "stock_"
    ledger = [row for row in ledger if not row["strategy"].startswith(prefix) and row["simulation_type"] != "stock_cross_sectional_momentum"]
    for row in results:
        ledger.append({key: str(row.get(key, "")) for key in ledger_fields})
    atomic_csv(ledger_path, ledger, ledger_fields)

    manifest_path = OUT / "data_manifest.csv"
    manifest = read_csv(manifest_path)
    fields = list(manifest[0])
    artifacts = [
        ("Stock momentum results", "outputs/stock_momentum_screen.csv", "Net portfolio results for frozen stock momentum comparisons"),
        ("Stock momentum monthly selections", "outputs/stock_momentum_monthly_picks.csv", "Point-in-time ranking outputs and weights"),
        ("Stock momentum daily equity", "outputs/stock_momentum_daily_equity.csv", "Daily NAV, exposure, and cash paths"),
        ("Stock momentum orders", "outputs/stock_momentum_orders.csv", "Order-level fees, fills, and slippage"),
        ("Stock momentum method", "outputs/stock_momentum_method.md", "Strategy rules and corporate-action limitations"),
    ]
    paths = {x[1] for x in artifacts}
    manifest = [row for row in manifest if row["cache_paths"] not in paths]
    for title, path, purpose in artifacts:
        manifest.append({"dataset": title, "ticker": "point-in-time NIFTY 50 screen", "instrument_key": "", "bar_interval": "daily/monthly",
                         "first_bar": START.date().isoformat(), "last_bar": END.date().isoformat(), "bar_count": "", "file_count": "1", "empty_files": "0",
                         "cache_paths": path, "purpose": purpose, "notes": "Preliminary; see method for fees, action exclusions, and limitations."})
    atomic_csv(manifest_path, manifest, fields)
    print(json.dumps({"selected_on_training_only": selected,
                      "selection_results": [r for r in results if r["period"] in {"train_2021_2023", "validation_2024", "holdout_2025_plus"} and (r["selected_on_training_only"] or r["strategy"] == "NIFTYBEES buy-and-hold benchmark")],
                      "strategy_variants": len(targets), "selection_rows": len(picks),
                      "action_exclusions": sorted(ACTION_EXCLUSIONS)}, indent=2, default=str))


if __name__ == "__main__":
    main()
