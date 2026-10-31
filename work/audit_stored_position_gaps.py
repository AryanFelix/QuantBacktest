"""Audit held-position daily marks and terminal sales in saved cash backtests."""

from __future__ import annotations

import csv
from bisect import bisect_left
from collections import Counter, defaultdict
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "work" / "data"
BACKTESTS = ROOT / "work" / "backtests"


def read_close(path: Path) -> dict[str, float]:
    frame = pd.read_csv(path)
    if not {"time", "close"}.issubset(frame.columns):
        raise ValueError(f"not a daily OHLC file: {path}")
    frame = frame[["time", "close"]]
    dates = pd.to_datetime(frame["time"], utc=True).dt.tz_convert("Asia/Kolkata").dt.strftime("%Y-%m-%d")
    return dict(zip(dates, pd.to_numeric(frame["close"], errors="coerce")))


def session_days(frame: pd.DataFrame) -> pd.Series:
    column = "time" if "time" in frame else "date"
    return pd.to_datetime(frame[column], utc=True, errors="coerce").dt.tz_convert("Asia/Kolkata").dt.strftime("%Y-%m-%d")


def prices_by_symbol() -> dict[str, dict[str, float]]:
    prices = {}
    with (DATA / "universe_sources" / "stock_history_coverage.csv").open(encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            prices[row["trading_symbol"]] = read_close(ROOT / row["cache_path"])

    with (ROOT / "outputs" / "data_manifest.csv").open(encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            if "ETF" not in row.get("dataset", "").upper():
                continue
            tickers = [value.strip() for value in row.get("ticker", "").split(";") if value.strip()]
            keys = [value.strip().replace("|", "_") for value in row.get("instrument_key", "").split(";") if value.strip()]
            paths = [value.strip().replace("\\", "/") for value in row.get("cache_paths", "").split(";") if value.strip()]
            for i, ticker in enumerate(tickers):
                key = keys[i] if i < len(keys) else ""
                candidates = [ROOT / value for value in paths if "days-1-" in value.lower() and value.lower().endswith(".csv") and (ROOT / value).is_file()]
                if key:
                    candidates = [path for path in candidates if key in path.name] or candidates
                if not candidates:
                    for value in paths:
                        folder = ROOT / value
                        if folder.is_dir():
                            candidates = sorted(folder.rglob(f"*{key}*days-1*.csv")) if key else sorted(folder.rglob(f"*{ticker}*days-1*.csv"))
                            break
                if candidates:
                    prices[ticker] = read_close(candidates[0])

    hdfc = DATA / "etf_daily" / "smallcap_candidates" / "NSE_EQ_INF179KC1FB2-days-1-2019-01-01-2026-10-23.csv"
    prices["HDFCSML250"] = read_close(hdfc)
    prices["MID150BEES"] = read_close(DATA / "etf_daily" / "MID150BEES-days-1-2019-02-04-2026-10-30.csv")
    return prices


def main() -> None:
    prices = prices_by_symbol()
    price_days = {symbol: set(rows) for symbol, rows in prices.items()}
    market_days = sorted(set().union(*price_days.values()))
    gaps_by_symbol = {symbol: sorted(set(market_days) - days) for symbol, days in price_days.items()}
    order_files = sorted(BACKTESTS.rglob("orders.csv"))
    held_days = gap_days = terminal_cases = terminal_rows = early_terminal_rows = 0
    affected = []
    gap_detail = Counter()
    unmapped = set()
    skipped_cases = 0

    for order_path in order_files:
        equity_path = order_path.with_name("equity.csv")
        if not equity_path.is_file():
            continue
        orders = pd.read_csv(order_path)
        equity = pd.read_csv(equity_path)
        if "symbol" not in orders or not ({"time", "date"} & set(equity.columns)) or not ({"time", "date"} & set(orders.columns)):
            skipped_cases += 1
            continue
        orders["day"] = session_days(orders)
        equity["day"] = session_days(equity)
        terminal_mask = orders.get("terminal_liquidation", pd.Series(False, index=orders.index)).astype(str).str.lower().eq("true")
        terminal = orders.loc[terminal_mask]
        if not terminal.empty:
            terminal_cases += 1
            terminal_rows += len(terminal)
            early_terminal_rows += int((terminal["day"] < equity["day"].max()).sum())
            for row in terminal.itertuples():
                if row.symbol not in prices:
                    unmapped.add(row.symbol)
                elif row.day not in price_days[row.symbol]:
                    gap_days += 1
                    gap_detail[(row.symbol, row.day, "terminal")] += 1
                    affected.append((str(order_path.relative_to(ROOT)), row.day, row.symbol, "terminal"))
        equity_days = equity["day"].dropna().tolist()
        equity_day_set = set(equity_days)
        if orders.empty:
            continue
        order_rows = orders.copy()
        order_rows["signed_quantity"] = order_rows["quantity"].astype(int) * order_rows["side"].map({"buy": 1, "sell": -1})
        for symbol, symbol_orders in order_rows.groupby("symbol", sort=False):
            if symbol not in prices:
                unmapped.add(symbol)
                continue
            events = symbol_orders.groupby("day")["signed_quantity"].sum().sort_index()
            quantity = 0
            event_days = list(events.index)
            for i, day in enumerate(event_days):
                quantity += int(events.iloc[i])
                if quantity <= 0:
                    continue
                next_event = event_days[i + 1] if i + 1 < len(event_days) else "9999-12-31"
                first = bisect_left(equity_days, day)
                last = bisect_left(equity_days, next_event)
                if first >= last:
                    continue
                held_days += last - first
                gaps = gaps_by_symbol[symbol]
                for missing_day in gaps[bisect_left(gaps, day):bisect_left(gaps, next_event)]:
                    if missing_day in equity_day_set:
                        gap_days += 1
                        gap_detail[(symbol, missing_day, "held")] += 1
                        affected.append((str(order_path.relative_to(ROOT)), missing_day, symbol, "held"))

    print({"order_files": len(order_files), "skipped_cases": skipped_cases, "terminal_cases": terminal_cases, "terminal_rows": terminal_rows,
           "terminal_rows_before_equity_end": early_terminal_rows, "held_symbol_days": held_days,
           "missing_raw_close_observations": gap_days, "affected_cases": len({row[0] for row in affected}),
           "missing_detail": [{"symbol": key[0], "date": key[1], "kind": key[2], "cases": count} for key, count in sorted(gap_detail.items())],
           "unmapped_symbols": sorted(unmapped), "examples": affected[:5]})
    if unmapped:
        raise SystemExit("unmapped symbols prevent a complete audit")


if __name__ == "__main__":
    main()
