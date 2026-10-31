"""Audit daily cash-ledger holdings against raw daily closes in saved caches."""

from __future__ import annotations

import csv
import json
from bisect import bisect_left
from collections import Counter
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "work" / "data"
BACKTESTS = ROOT / "work" / "backtests"
OUTPUT = ROOT / "outputs" / "stored_position_gap_audit_2026-10-31.json"
UNSUPPORTED_PATH_PARTS = ("intraday", "orb", "option", "derivative", "future", "credit_spread")


def display_path(path: Path) -> str:
    resolved = path.resolve()
    return resolved.relative_to(ROOT).as_posix() if resolved.is_relative_to(ROOT) else path.name


def read_close(path: Path, exceptions: list[dict] | None = None) -> dict[str, float]:
    frame = pd.read_csv(path)
    if not {"time", "close"}.issubset(frame.columns):
        raise ValueError(f"not a daily OHLC file: {path}")
    dates = pd.to_datetime(frame["time"], utc=True, errors="coerce").dt.tz_convert("Asia/Kolkata").dt.strftime("%Y-%m-%d")
    closes = pd.to_numeric(frame["close"], errors="coerce")
    good: dict[str, float] = {}
    for index, (day, close) in enumerate(zip(dates, closes)):
        if pd.isna(day):
            if exceptions is not None:
                exceptions.append({"kind": "invalid_price_date", "file": display_path(path), "row": index + 2})
            continue
        if not np.isfinite(close) or close <= 0:
            if exceptions is not None:
                exceptions.append({"kind": "invalid_raw_close", "file": display_path(path), "date": day, "row": index + 2})
            continue
        value = float(close)
        if day in good and good[day] != value:
            raise ValueError(f"conflicting duplicate daily closes in {path} on {day}")
        good[day] = value
    return good


def session_days(frame: pd.DataFrame) -> pd.Series:
    column = "time" if "time" in frame else "date"
    return pd.to_datetime(frame[column], utc=True, errors="coerce").dt.tz_convert("Asia/Kolkata").dt.strftime("%Y-%m-%d")


def prices_by_symbol(exceptions: list[dict] | None = None) -> dict[str, dict[str, float]]:
    prices: dict[str, dict[str, float]] = {}

    def load(symbol: str, path: Path) -> None:
        try:
            prices[symbol] = read_close(path, exceptions)
        except (OSError, ValueError, pd.errors.ParserError) as error:
            prices[symbol] = {}
            if exceptions is not None:
                exceptions.append({"kind": "invalid_price_file", "file": display_path(path),
                                   "detail": str(error).replace(str(path), display_path(path))[:240]})

    with (DATA / "universe_sources" / "stock_history_coverage.csv").open(encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            load(row["trading_symbol"], ROOT / row["cache_path"])

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
                    load(ticker, candidates[0])

    load("HDFCSML250", DATA / "etf_daily" / "smallcap_candidates" / "NSE_EQ_INF179KC1FB2-days-1-2019-01-01-2026-10-23.csv")
    load("MID150BEES", DATA / "etf_daily" / "MID150BEES-days-1-2019-02-04-2026-10-30.csv")
    return prices


def audit_backtests(backtests: Path, prices: dict[str, dict[str, float]],
                    price_exceptions: list[dict] | None = None) -> dict:
    price_days = {symbol: set(rows) for symbol, rows in prices.items()}
    market_days = sorted(set().union(*price_days.values())) if price_days else []
    gaps_by_symbol = {symbol: sorted(set(market_days) - days) for symbol, days in price_days.items()}
    order_files = sorted(backtests.rglob("orders.csv"))
    files = {"discovered": len(order_files), "paired": 0, "checked": 0, "excluded": 0,
             "invalid": 0, "orphan_order_files": 0, "excluded_paired": 0, "invalid_paired": 0}
    held_days = terminal_cases = terminal_rows = early_terminal_rows = missing_observations = 0
    affected: list[tuple[str, str, str, str]] = []
    gap_detail: Counter = Counter()
    unmapped: set[str] = set()
    exceptions: Counter = Counter()
    exception_examples: list[dict] = []

    def issue(kind: str, path: Path, **details) -> None:
        exceptions[kind] += 1
        if len(exception_examples) < 30:
            exception_examples.append({"kind": kind, "file": display_path(path), **details})

    for order_path in order_files:
        relative = str(order_path.relative_to(ROOT)) if order_path.is_relative_to(ROOT) else str(order_path)
        equity_path = order_path.with_name("equity.csv")
        if not equity_path.is_file():
            files["excluded"] += 1
            files["orphan_order_files"] += 1
            issue("missing_equity_pair", order_path)
            continue
        files["paired"] += 1
        if any(part in relative.lower() for part in UNSUPPORTED_PATH_PARTS):
            files["excluded"] += 1
            files["excluded_paired"] += 1
            issue("unsupported_intraday_or_derivative_path", order_path)
            continue
        try:
            orders, equity = pd.read_csv(order_path), pd.read_csv(equity_path)
            order_date_col = "time" if "time" in orders else "date" if "date" in orders else None
            equity_date_col = "time" if "time" in equity else "date" if "date" in equity else None
            if order_date_col is None or equity_date_col is None or not {"symbol", "side", "quantity"}.issubset(orders.columns):
                files["excluded"] += 1
                files["excluded_paired"] += 1
                issue("unsupported_daily_cash_schema", order_path)
                continue
            orders["day"], equity["day"] = session_days(orders), session_days(equity)
            if orders["day"].isna().any() or equity["day"].isna().any():
                raise ValueError("unparseable order or equity session date")
            if equity["day"].duplicated().any():
                files["excluded"] += 1
                files["excluded_paired"] += 1
                issue("non_daily_equity_rows", order_path)
                continue
            quantities = pd.to_numeric(orders["quantity"], errors="coerce")
            sides = orders["side"].astype(str).str.lower()
            if quantities.isna().any() or not np.isfinite(quantities.to_numpy(dtype=float)).all() or (quantities <= 0).any() or not np.equal(quantities, np.floor(quantities)).all() or not sides.isin(["buy", "sell"]).all():
                raise ValueError("quantity must be a positive integer and side must be buy/sell")
        except (OSError, ValueError, pd.errors.ParserError, KeyError) as error:
            files["invalid"] += 1
            files["invalid_paired"] += 1
            issue("invalid_paired_ledger", order_path,
                  detail=str(error).replace(str(order_path), relative)[:240])
            continue

        files["checked"] += 1
        terminal_mask = orders.get("terminal_liquidation", pd.Series(False, index=orders.index)).astype(str).str.lower().eq("true")
        terminal = orders.loc[terminal_mask]
        equity_days = equity["day"].tolist()
        equity_day_set = set(equity_days)
        if not terminal.empty:
            terminal_cases += 1
            terminal_rows += len(terminal)
            early_terminal_rows += int((terminal["day"] < max(equity_days)).sum())
            for row in terminal.itertuples():
                if row.symbol not in prices:
                    unmapped.add(row.symbol)
                elif row.day not in price_days[row.symbol]:
                    missing_observations += 1
                    gap_detail[(row.symbol, row.day, "terminal")] += 1
                    affected.append((relative, row.day, row.symbol, "terminal"))

        orders["signed_quantity"] = quantities.astype(int) * sides.map({"buy": 1, "sell": -1})
        for symbol, symbol_orders in orders.groupby("symbol", sort=False):
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
                first, last = bisect_left(equity_days, day), bisect_left(equity_days, next_event)
                if first >= last:
                    continue
                held_days += last - first
                gaps = gaps_by_symbol[symbol]
                for missing_day in gaps[bisect_left(gaps, day):bisect_left(gaps, next_event)]:
                    if missing_day in equity_day_set:
                        missing_observations += 1
                        gap_detail[(symbol, missing_day, "held")] += 1
                        affected.append((relative, missing_day, symbol, "held"))

    files["excluded_unpaired"] = files["orphan_order_files"]
    files["reconciliation"] = {
        "discovered_equals_checked_plus_excluded_plus_invalid": files["discovered"] == files["checked"] + files["excluded"] + files["invalid"],
        "paired_equals_checked_plus_excluded_paired_plus_invalid_paired": files["paired"] == files["checked"] + files["excluded_paired"] + files["invalid_paired"],
        "discovered_equals_paired_plus_orphans": files["discovered"] == files["paired"] + files["orphan_order_files"],
    }
    return {
        "audit_scope": "daily net positions in supported cash ledgers; does not establish intraday order-price validity; intraday and derivative paths/schemas are excluded",
        "files": files,
        "coverage": {
            "mapped_symbols": len(prices), "valid_symbol_dates": sum(map(len, price_days.values())),
            "invalid_price_observations": sum(1 for item in (price_exceptions or []) if item["kind"] in {"invalid_raw_close", "invalid_price_date"}),
            "invalid_price_files": sum(1 for item in (price_exceptions or []) if item["kind"] == "invalid_price_file"),
            "terminal_cases": terminal_cases, "terminal_rows": terminal_rows,
            "terminal_rows_before_equity_end": early_terminal_rows, "held_symbol_days": held_days,
            "missing_raw_close_observations": missing_observations,
            "affected_cases": len({row[0] for row in affected}), "unmapped_symbols": sorted(unmapped),
        },
        "missing_detail": [{"symbol": key[0], "date": key[1], "kind": key[2], "occurrences": count}
                           for key, count in sorted(gap_detail.items())],
        "exception_counts": dict(exceptions), "exception_examples": exception_examples,
        "price_exception_examples": (price_exceptions or [])[:30],
        "affected_examples": [{"file": row[0], "date": row[1], "symbol": row[2], "kind": row[3]} for row in affected[:30]],
    }


def main() -> None:
    price_exceptions: list[dict] = []
    result = audit_backtests(BACKTESTS, prices_by_symbol(price_exceptions), price_exceptions)
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, separators=(",", ":")))


if __name__ == "__main__":
    main()
