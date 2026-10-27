"""Local Upstox data and daily strategy research runner."""

from __future__ import annotations

import argparse
import calendar
import gzip
import json
import math
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "work" / "data"
RUN_DIR = ROOT / "work" / "backtests"
UPSTOX = "https://api.upstox.com"
INSTRUMENTS_URL = "https://assets.upstox.com/market-quote/instruments/exchange/complete.json.gz"
BAR_COLUMNS = ["time", "open", "high", "low", "close", "volume", "open_interest"]
FEE_COMPONENTS = ["brokerage", "stt", "exchange", "stamp_duty", "sebi", "ipft", "dp", "gst"]
FUND_FEE_PRODUCTS = {
    "NIFTYBEES": "equity_fund_delivery",
    "BANKBEES": "equity_fund_delivery",
    "ITBEES": "equity_fund_delivery",
    "AUTOBEES": "equity_fund_delivery",
    "PHARMABEES": "equity_fund_delivery",
    "PSUBNKBEES": "equity_fund_delivery",
    "JUNIORBEES": "equity_fund_delivery",
    "GOLDBEES": "other_fund_delivery",
    "LIQUIDBEES": "other_fund_delivery",
}
_LAST_API_CALL = 0.0


def _add_months(d: date, months: int) -> date:
    month_index = d.month - 1 + months
    year = d.year + month_index // 12
    month = month_index % 12 + 1
    day = min(d.day, calendar.monthrange(year, month)[1])
    return date(year, month, day)


def request_windows(start: date, end: date, unit: str, interval: int) -> list[tuple[date, date]]:
    if start > end:
        raise ValueError("start must be on or before end")
    if unit == "minutes" and not 1 <= interval <= 300:
        raise ValueError("minute interval must be from 1 to 300")
    if unit == "hours" and not 1 <= interval <= 5:
        raise ValueError("hour interval must be from 1 to 5")
    if unit in {"days", "weeks", "months"} and interval != 1:
        raise ValueError(f"{unit} interval must be 1")
    if unit not in {"minutes", "hours", "days", "weeks", "months"}:
        raise ValueError("unit must be minutes, hours, days, weeks, or months")

    if unit == "minutes":
        months = 1 if interval <= 15 else 3
    elif unit == "hours":
        months = 3
    elif unit == "days":
        months = 120
    else:
        months = 0
    if not months:
        return [(start, end)]

    result = []
    cursor = start
    while cursor <= end:
        next_cursor = _add_months(cursor, months)
        chunk_end = min(end, next_cursor - timedelta(days=1))
        result.append((cursor, chunk_end))
        cursor = chunk_end + timedelta(days=1)
    return result


def _http_get(url: str, token: str | None = None) -> bytes:
    global _LAST_API_CALL
    headers = {"Accept": "application/json", "User-Agent": "upstox-quant-research/0.1"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = urllib.request.Request(url, headers=headers)
    last_error = None
    for attempt in range(4):
        if token:
            wait = 1.1 - (time.monotonic() - _LAST_API_CALL)
            if wait > 0:
                time.sleep(wait)
            _LAST_API_CALL = time.monotonic()
        try:
            with urllib.request.urlopen(request, timeout=45) as response:
                return response.read()
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", "replace")[:400]
            if exc.code in {429, 500, 502, 503, 504} and attempt < 3:
                time.sleep(2**attempt)
                last_error = RuntimeError(f"Upstox HTTP {exc.code}; retrying")
                continue
            raise RuntimeError(f"Upstox HTTP {exc.code}: {detail}") from None
        except (urllib.error.URLError, TimeoutError) as exc:
            last_error = RuntimeError(f"Upstox request failed: {exc}")
            if attempt < 3:
                time.sleep(2**attempt)
                continue
    raise last_error or RuntimeError("Upstox request failed")


def _access_token() -> str:
    token = (os.environ.get("UPSTOX_ANALYTICS_TOKEN") or os.environ.get("UPSTOX_ACCESS_TOKEN") or "").strip()
    if not token and os.name == "nt":
        try:
            import winreg

            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment") as key:
                token = winreg.QueryValueEx(key, "UPSTOX_ANALYTICS_TOKEN")[0].strip()
        except OSError:
            pass
    if not token:
        raise RuntimeError("Set UPSTOX_ANALYTICS_TOKEN to a current Upstox Bearer access token.")
    return token


def instrument_catalog() -> list[dict]:
    compressed = _http_get(INSTRUMENTS_URL)
    try:
        parsed = json.loads(gzip.decompress(compressed))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"Could not parse Upstox instrument master: {exc}") from None
    if isinstance(parsed, dict):
        parsed = parsed.get("data", parsed.get("instruments", []))
    if not isinstance(parsed, list):
        raise RuntimeError("Upstox instrument master was not a JSON list")
    return parsed


def search_catalog(query: str, segment: str | None, instrument_type: str | None) -> pd.DataFrame:
    pattern = re.compile(query, re.IGNORECASE) if query else None
    rows = []
    for item in instrument_catalog():
        if segment and str(item.get("segment", "")).upper() != segment.upper():
            continue
        if instrument_type and str(item.get("instrument_type", "")).upper() != instrument_type.upper():
            continue
        haystack = " ".join(str(item.get(k, "")) for k in ("name", "trading_symbol", "short_name", "underlying_symbol"))
        if pattern and not pattern.search(haystack):
            continue
        rows.append({k: item.get(k) for k in (
            "segment", "exchange", "name", "trading_symbol", "short_name", "instrument_type",
            "instrument_key", "isin", "lot_size", "expiry", "strike_price", "option_type"
        )})
    return pd.DataFrame(rows)


def fetch_candles(instrument_key: str, start: date, end: date, unit: str, interval: int) -> pd.DataFrame:
    token = _access_token()
    encoded_key = urllib.parse.quote(instrument_key, safe="")
    candles = []
    for chunk_start, chunk_end in request_windows(start, end, unit, interval):
        url = (
            f"{UPSTOX}/v3/historical-candle/{encoded_key}/{unit}/{interval}/"
            f"{chunk_end.isoformat()}/{chunk_start.isoformat()}"
        )
        response = json.loads(_http_get(url, token))
        if response.get("status") != "success":
            raise RuntimeError(f"Upstox candle request was not successful: {response}")
        candles.extend(response.get("data", {}).get("candles", []))
    frame = pd.DataFrame(candles, columns=BAR_COLUMNS)
    if frame.empty:
        return frame
    frame["time"] = pd.to_datetime(frame["time"], errors="raise")
    frame = frame.drop_duplicates("time").sort_values("time").reset_index(drop=True)
    for column in BAR_COLUMNS[1:]:
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    if frame[["open", "high", "low", "close"]].isna().any().any():
        raise RuntimeError("Upstox returned candles with missing OHLC values")
    return frame


def fetch_expiries(instrument_key: str) -> dict:
    query = urllib.parse.urlencode({"instrument_key": instrument_key})
    response = json.loads(_http_get(f"{UPSTOX}/v2/expired-instruments/expiries?{query}", _access_token()))
    if response.get("status") != "success":
        raise RuntimeError(f"Upstox expiries request was not successful: {response}")
    return response.get("data", {})


def fetch_corporate_actions(isin: str) -> list[dict]:
    code = urllib.parse.quote(isin, safe="")
    response = json.loads(_http_get(f"{UPSTOX}/v2/fundamentals/{code}/corporate-actions", _access_token()))
    if response.get("status") != "success":
        raise RuntimeError(f"Upstox corporate actions request was not successful: {response}")
    return response.get("data", [])


def fetch_expired_contracts(instrument_key: str, expiry: date, kind: str) -> list[dict]:
    if kind not in {"option", "future"}:
        raise ValueError("kind must be option or future")
    query = urllib.parse.urlencode({"instrument_key": instrument_key, "expiry_date": expiry.isoformat()})
    response = json.loads(_http_get(f"{UPSTOX}/v2/expired-instruments/{kind}/contract?{query}", _access_token()))
    if response.get("status") != "success":
        raise RuntimeError(f"Upstox expired contract request was not successful: {response}")
    return response.get("data", [])


def fetch_expired_candles(instrument_key: str, start: date, end: date, interval: str) -> pd.DataFrame:
    if start > end or interval not in {"1minute", "3minute", "5minute", "15minute", "30minute", "day"}:
        raise ValueError("invalid expired candle interval or date range")
    key = urllib.parse.quote(instrument_key, safe="")
    url = f"{UPSTOX}/v2/expired-instruments/historical-candle/{key}/{interval}/{end.isoformat()}/{start.isoformat()}"
    response = json.loads(_http_get(url, _access_token()))
    if response.get("status") != "success":
        raise RuntimeError(f"Upstox expired candle request was not successful: {response}")
    frame = pd.DataFrame(response.get("data", {}).get("candles", []), columns=BAR_COLUMNS)
    if frame.empty:
        return frame
    frame["time"] = pd.to_datetime(frame["time"], errors="raise")
    frame = frame.drop_duplicates("time").sort_values("time").reset_index(drop=True)
    for column in BAR_COLUMNS[1:]:
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    return frame


def _fee_breakdown(
    notional: float, side: str, product: str, exchange: str = "NSE", trade_date: date | None = None,
) -> dict[str, float]:
    if notional < 0 or side not in {"buy", "sell"}:
        raise ValueError("notional must be non-negative and side must be buy or sell")
    if trade_date is not None and not isinstance(trade_date, date):
        raise ValueError("trade_date must be a datetime.date")
    if exchange.upper() != "NSE":
        raise ValueError("The first fee model supports NSE; BSE rates vary by scrip group")
    brokerage_rates = {
        "equity_delivery": (20.0, 0.0),
        "equity_fund_delivery": (20.0, 0.0),
        "other_fund_delivery": (20.0, 0.0),
        "equity_intraday": (20.0, 0.001),
        "equity_fund_intraday": (20.0, 0.001),
        "other_fund_intraday": (20.0, 0.001),
        "futures": (20.0, 0.0005),
        "options": (20.0, 0.0),
    }
    if product not in brokerage_rates:
        raise ValueError("unsupported NSE fee product")
    cap, rate = brokerage_rates[product]
    brokerage = min(cap, notional * rate) if rate else cap
    exchange_rates = {
        "equity_delivery": 0.0000307, "equity_fund_delivery": 0.0000307,
        "other_fund_delivery": 0.0000307, "equity_intraday": 0.0000307,
        "equity_fund_intraday": 0.0000307, "other_fund_intraday": 0.0000307,
        "futures": 0.0000183, "options": 0.0003552,
    }
    exchange_fee = notional * exchange_rates[product]
    stt_rates = {
        "equity_delivery": (0.001, 0.001),
        "equity_fund_delivery": (0.0, 0.00001),
        "other_fund_delivery": (0.0, 0.0),
        "equity_intraday": (0.0, 0.00025),
        "equity_fund_intraday": (0.0, 0.00025),
        "other_fund_intraday": (0.0, 0.0),
        "futures": (0.0, 0.0005),
        "options": (0.0, 0.0015),
    }
    stt_rate = stt_rates[product][side == "sell"]
    stamp_rates = {
        "equity_delivery": 0.00015, "equity_fund_delivery": 0.00015,
        "other_fund_delivery": 0.00015, "equity_intraday": 0.00003,
        "equity_fund_intraday": 0.00003, "other_fund_intraday": 0.00003,
        "futures": 0.00002, "options": 0.00003,
    }
    stamp = notional * stamp_rates[product] if side == "buy" else 0.0
    sebi = notional * 0.000001
    ipft_rate = 0.000000001
    if product == "options":
        effective_date = trade_date or date(2026, 4, 1)
        if effective_date < date(2024, 10, 1):
            raise ValueError("dated NSE options charges are audited here from 2024-10-01 onward")
        stt_rate = 0.0 if side == "buy" else (0.0015 if effective_date >= date(2026, 4, 1) else 0.001)
        if effective_date < date(2026, 3, 1):
            exchange_fee = notional * 0.0003503
            ipft_rate = 0.000005
        else:
            exchange_fee = notional * 0.0003552
    stt = notional * stt_rate
    ipft = notional * ipft_rate
    dp = 20.0 if product in {"equity_delivery", "equity_fund_delivery", "other_fund_delivery"} and side == "sell" else 0.0
    gst = 0.18 * (brokerage + exchange_fee + ipft + dp)
    return {
        "brokerage": brokerage,
        "stt": stt,
        "exchange": exchange_fee,
        "stamp_duty": stamp,
        "sebi": sebi,
        "ipft": ipft,
        "dp": dp,
        "gst": gst,
        "total": brokerage + stt + exchange_fee + stamp + sebi + ipft + dp + gst,
    }


def _read_prices(specs: list[str]) -> tuple[dict[str, pd.DataFrame], dict[str, pd.DataFrame]]:
    frames = {}
    for spec in specs:
        if "=" not in spec:
            raise ValueError("each --data must be SYMBOL=CSV_PATH")
        symbol, raw_path = spec.split("=", 1)
        if not symbol or symbol in frames:
            raise ValueError(f"invalid or duplicate symbol in --data: {symbol}")
        path = Path(raw_path)
        if not path.is_absolute():
            path = ROOT / path
        frame = pd.read_csv(path)
        missing = set(BAR_COLUMNS) - set(frame.columns)
        if missing:
            raise ValueError(f"{path} is missing columns: {', '.join(sorted(missing))}")
        frame["time"] = pd.to_datetime(frame["time"], errors="raise")
        for col in BAR_COLUMNS[1:]:
            frame[col] = pd.to_numeric(frame[col], errors="coerce")
        if "-days-1-" in path.name:
            frame["time"] = frame["time"].dt.normalize()
            duplicate_bars = frame.loc[frame.duplicated("time", keep=False)]
            if not duplicate_bars.empty and (duplicate_bars.groupby("time")[BAR_COLUMNS[1:]].nunique(dropna=False) > 1).any().any():
                raise ValueError(f"{path} has conflicting daily bars for one session")
        frame = frame.drop_duplicates("time").sort_values("time").set_index("time")
        frame = frame.dropna(subset=["open", "high", "low", "close"])
        if (frame[["open", "high", "low", "close"]] <= 0).any().any():
            raise ValueError(f"{path} contains non-positive OHLC values")
        frames[symbol] = frame
    if not frames:
        raise ValueError("provide at least one --data SYMBOL=CSV_PATH")
    names = sorted(frames)
    panels = {}
    for field in ("open", "high", "low", "close", "volume"):
        panels[field] = pd.concat({name: frames[name][field] for name in names}, axis=1, join="outer", sort=True).sort_index()
    if panels["close"].dropna(how="all").empty:
        raise ValueError("the input files contain no usable close prices")
    return frames, panels


def make_targets(panels: dict[str, pd.DataFrame], strategy: str, top_n: int = 3, cash_proxy: str | None = None) -> tuple[pd.DataFrame, pd.Series]:
    close = panels["close"]
    names = list(close.columns)
    if cash_proxy and cash_proxy not in names:
        raise ValueError(f"cash proxy {cash_proxy} is missing from --data")
    risk_names = [name for name in names if name != cash_proxy]
    targets = pd.DataFrame(0.0, index=close.index, columns=names)
    rebalance = pd.Series(False, index=close.index)
    if strategy in {"buyhold", "trend200", "donchian55_20"}:
        if len(risk_names) != 1:
            raise ValueError(f"{strategy} takes one instrument; supply one --data")
        name = risk_names[0]
        state = False
        if strategy == "buyhold":
            state = True
            rebalance.iloc[0] = True
        elif strategy == "trend200":
            trend = close[name] > close[name].rolling(200, min_periods=200).mean()
            for i, value in enumerate(trend):
                new_state = bool(value) if pd.notna(value) else False
                if new_state != state:
                    state = new_state
                    rebalance.iloc[i] = True
                targets.iloc[i, 0] = float(state)
            return targets, rebalance
        else:
            high, low = panels["high"][name], panels["low"][name]
            entry = close[name] > high.shift(1).rolling(55, min_periods=55).max()
            exit_ = close[name] < low.shift(1).rolling(20, min_periods=20).min()
            for i in range(len(close)):
                new_state = state
                if pd.notna(entry.iloc[i]) and bool(entry.iloc[i]):
                    new_state = True
                elif pd.notna(exit_.iloc[i]) and bool(exit_.iloc[i]):
                    new_state = False
                if new_state != state:
                    state = new_state
                    rebalance.iloc[i] = True
                targets.iloc[i, 0] = float(state)
            return targets, rebalance
        targets.iloc[:, 0] = 1.0
        return targets, rebalance

    if strategy != "momentum12_1":
        raise ValueError("strategy must be buyhold, trend200, donchian55_20, or momentum12_1")
    if len(risk_names) < 2:
        raise ValueError("momentum12_1 needs at least two instruments")
    if top_n < 1:
        raise ValueError("top_n must be positive")
    scores = close.shift(21) / close.shift(252) - 1.0
    above_trend = close > close.rolling(200, min_periods=200).mean()
    state_weights = pd.Series(0.0, index=names)
    for i, timestamp in enumerate(close.index):
        end_of_month = i == len(close.index) - 1 or (timestamp.year, timestamp.month) != (close.index[i + 1].year, close.index[i + 1].month)
        if end_of_month:
            eligible = scores.iloc[i][risk_names][above_trend.iloc[i][risk_names]].dropna()
            eligible = eligible[eligible > 0].nlargest(top_n)
            state_weights[:] = 0.0
            if not eligible.empty:
                state_weights.loc[eligible.index] = 1.0 / len(eligible)
            rebalance.iloc[i] = True
        targets.iloc[i] = state_weights
    return targets, rebalance


def _simulate(
    panels: dict[str, pd.DataFrame],
    targets: pd.DataFrame,
    rebalance: pd.Series,
    starting_balance: float,
    max_exposure: float,
    slippage_bps: float,
    product: str = "equity_delivery",
    start: date | None = None,
    end: date | None = None,
    drawdown_limit_pct: float = 20.0,
    cash_proxy: str | None = None,
    cash_distributions: list[tuple[str, date, float]] | None = None,
    fee_product_by_symbol: dict[str, str] | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    if starting_balance <= 0 or not 0 < max_exposure <= 1 or slippage_bps < 0 or drawdown_limit_pct <= 0:
        raise ValueError("capital must be positive, exposure in (0, 1], slippage non-negative, and drawdown limit positive")
    opens, closes = panels["open"], panels["close"]
    open_marks = opens.where(opens.notna(), closes.ffill().shift(1))
    close_marks = closes.ffill()
    names = list(closes.columns)
    distribution_by_date = defaultdict(list)
    available_dates = {timestamp.date() for timestamp in closes.index}
    for symbol, ex_date, amount_per_share in cash_distributions or []:
        if symbol not in names or ex_date not in available_dates or not math.isfinite(amount_per_share) or amount_per_share < 0:
            raise ValueError("cash distributions need a known symbol, a cached session date, and a finite non-negative amount")
        distribution_by_date[ex_date].append((symbol, amount_per_share))
    if cash_proxy and cash_proxy not in names:
        raise ValueError(f"cash proxy {cash_proxy} is missing from price data")
    product_overrides = {**FUND_FEE_PRODUCTS, **(fee_product_by_symbol or {})}
    allowed_fee_products = {
        "equity_delivery", "equity_fund_delivery", "other_fund_delivery",
        "equity_intraday", "equity_fund_intraday", "other_fund_intraday", "futures", "options",
    }
    if set(product_overrides.values()) - allowed_fee_products:
        raise ValueError("fee_product_by_symbol contains an unsupported product")
    instrument_fee_products = {name: product_overrides.get(name, product) for name in names}
    risk_names = [name for name in names if name != cash_proxy]
    targets = targets.reindex(index=closes.index, columns=names).fillna(0.0)
    rebalance = rebalance.reindex(closes.index).fillna(False)
    run_dates = [timestamp for timestamp in closes.index if (start is None or timestamp.date() >= start) and (end is None or timestamp.date() <= end)]
    if not run_dates:
        raise ValueError("the selected run period contains no common bars")
    cash = float(starting_balance)
    quantity = {name: 0 for name in names}
    slip = slippage_bps / 10_000
    orders = []
    totals = defaultdict(float)
    turnover = 0.0
    equity = []
    daily_distributions = []
    applied_distributions = []
    risky_exposures = []
    gross_exposures = []
    prior_close_nav = float(starting_balance)
    full_index = closes.index
    for step, timestamp in enumerate(run_dates):
        source_i = full_index.get_loc(timestamp)
        open_prices = open_marks.loc[timestamp]
        close_prices = close_marks.loc[timestamp]
        executable_prices = opens.loc[timestamp]
        distribution_cash = 0.0
        for name, amount_per_share in distribution_by_date.get(timestamp.date(), []):
            eligible_quantity = quantity[name]
            amount = eligible_quantity * amount_per_share
            cash += amount
            distribution_cash += amount
            applied_distributions.append({
                "symbol": name,
                "ex_date": timestamp.date().isoformat(),
                "cash_per_share_inr": amount_per_share,
                "eligible_quantity": eligible_quantity,
                "cash_inr": amount,
            })
        signal_i = source_i - 1
        first_bar_entry = step == 0 and signal_i >= 0
        should_rebalance = signal_i >= 0 and (first_bar_entry or bool(rebalance.iloc[signal_i]))
        if should_rebalance:
            weights = targets.iloc[signal_i].clip(lower=0)
            total_weight = float(weights.sum())
            if cash_proxy:
                risky_weights = weights[risk_names]
                risky_total = float(risky_weights.sum())
                if risky_total > max_exposure:
                    risky_weights = risky_weights * (max_exposure / risky_total)
                weights[risk_names] = risky_weights
                weights[cash_proxy] = 1.0 - float(risky_weights.sum())
            elif total_weight > max_exposure:
                weights = weights * (max_exposure / total_weight)
            reference_prices = close_marks.iloc[signal_i]
            desired = {
                name: int(math.floor(prior_close_nav * float(weights[name]) / float(reference_prices[name])))
                if pd.notna(reference_prices[name]) and float(reference_prices[name]) > 0 else 0
                for name in names
            }
            for name in names:
                if pd.isna(executable_prices[name]):
                    continue
                amount = quantity[name] - desired[name]
                if amount <= 0:
                    continue
                fill = float(open_prices[name]) * (1 - slip)
                notional = amount * fill
                charges = _fee_breakdown(notional, "sell", instrument_fee_products[name])
                cash += notional - charges["total"]
                quantity[name] -= amount
                turnover += notional
                for component in FEE_COMPONENTS:
                    totals[component] += charges[component]
                orders.append({"time": timestamp, "symbol": name, "side": "sell", "quantity": amount, "fill_price": fill, "notional": notional, **charges})
            for name in names:
                if pd.isna(executable_prices[name]):
                    continue
                amount = desired[name] - quantity[name]
                if amount <= 0:
                    continue
                fill = float(open_prices[name]) * (1 + slip)
                lo, hi = 0, amount
                while lo < hi:
                    mid = (lo + hi + 1) // 2
                    charges = _fee_breakdown(mid * fill, "buy", instrument_fee_products[name])
                    if mid * fill + charges["total"] <= cash:
                        lo = mid
                    else:
                        hi = mid - 1
                amount = lo
                if not amount:
                    continue
                notional = amount * fill
                charges = _fee_breakdown(notional, "buy", instrument_fee_products[name])
                cash -= notional + charges["total"]
                quantity[name] += amount
                turnover += notional
                for component in FEE_COMPONENTS:
                    totals[component] += charges[component]
                orders.append({"time": timestamp, "symbol": name, "side": "buy", "quantity": amount, "fill_price": fill, "notional": notional, **charges})
        nav_close = cash + sum(quantity[name] * float(close_prices[name]) for name in names if quantity[name] and pd.notna(close_prices[name]))
        invested = sum(quantity[name] * float(close_prices[name]) for name in names if quantity[name] and pd.notna(close_prices[name]))
        invested_risk = sum(quantity[name] * float(close_prices[name]) for name in risk_names if quantity[name] and pd.notna(close_prices[name]))
        equity.append(nav_close)
        daily_distributions.append(distribution_cash)
        risky_exposures.append(invested_risk / nav_close if nav_close > 0 else 0.0)
        gross_exposures.append(invested / nav_close if nav_close > 0 else 0.0)
        prior_close_nav = nav_close

    for name in names:
        amount = quantity[name]
        if amount <= 0:
            continue
        available = closes.loc[run_dates, name].dropna()
        if available.empty:
            continue
        last_trade_time = available.index[-1]
        fill = float(available.iloc[-1]) * (1 - slip)
        notional = amount * fill
        charges = _fee_breakdown(notional, "sell", instrument_fee_products[name])
        cash += notional - charges["total"]
        turnover += notional
        for component in FEE_COMPONENTS:
            totals[component] += charges[component]
        orders.append({"time": last_trade_time, "symbol": name, "side": "sell", "quantity": amount, "fill_price": fill, "notional": notional, "terminal_liquidation": True, **charges})
    equity[-1] = cash
    equity_frame = pd.DataFrame({"nav": equity, "risky_exposure": risky_exposures, "gross_exposure": gross_exposures,
                                 "cash_distribution_inr": daily_distributions}, index=run_dates)
    trades = pd.DataFrame(orders)
    daily_returns = equity_frame["nav"].pct_change().replace([np.inf, -np.inf], np.nan).fillna(0)
    daily_returns.iloc[0] = equity_frame["nav"].iloc[0] / starting_balance - 1
    years = max(len(equity_frame) / 252, 1 / 252)
    total_return = equity_frame["nav"].iloc[-1] / starting_balance - 1
    cagr = (equity_frame["nav"].iloc[-1] / starting_balance) ** (1 / years) - 1 if equity_frame["nav"].iloc[-1] > 0 else -1.0
    stdev = float(daily_returns.std(ddof=1)) if len(daily_returns) > 1 else 0.0
    downside = daily_returns[daily_returns < 0]
    downside_std = float(downside.std(ddof=1)) if len(downside) > 1 else 0.0
    full_nav = pd.concat([pd.Series([starting_balance]), equity_frame["nav"].reset_index(drop=True)], ignore_index=True)
    drawdown = full_nav / full_nav.cummax() - 1
    max_drawdown_pct = float(drawdown.min() * 100)
    stats = {
        "starting_balance_inr": starting_balance,
        "ending_balance_inr": float(equity_frame["nav"].iloc[-1]),
        "total_return_pct": float(total_return * 100),
        "cagr_pct": float(cagr * 100),
        "annualized_volatility_pct": float(stdev * math.sqrt(252) * 100),
        "sharpe_zero_rf": float(daily_returns.mean() / stdev * math.sqrt(252)) if stdev else 0.0,
        "sortino_zero_rf": float(daily_returns.mean() / downside_std * math.sqrt(252)) if downside_std else 0.0,
        "max_drawdown_pct": max_drawdown_pct,
        "drawdown_limit_pct": drawdown_limit_pct,
        "within_drawdown_limit": max_drawdown_pct >= -drawdown_limit_pct,
        "drawdown_budget_used_pct": abs(max_drawdown_pct) / drawdown_limit_pct * 100,
        "calmar": float(cagr / abs(drawdown.min())) if drawdown.min() < 0 else 0.0,
        "average_exposure_pct": float(equity_frame["risky_exposure"].mean() * 100),
        "average_gross_exposure_pct": float(equity_frame["gross_exposure"].mean() * 100),
        "order_count": len(trades),
        "turnover_inr": float(turnover),
        "turnover_to_starting_capital": float(turnover / starting_balance),
        "total_fees_inr": float(sum(totals.values())),
        "cash_distributions_inr": float(sum(event["cash_inr"] for event in applied_distributions)),
        "cash_distribution_events": applied_distributions,
        "fees_by_component_inr": {key: round(value, 2) for key, value in totals.items()},
        "first_bar": str(run_dates[0]),
        "last_bar": str(run_dates[-1]),
        "assumptions": {
            "product": product,
            "exchange": "NSE",
            "slippage_bps_per_side": slippage_bps,
            "max_gross_exposure": max_exposure,
            "max_drawdown_limit_pct": drawdown_limit_pct,
            "cash_proxy": cash_proxy,
            "cash_distributions_credited_on_ex_date": bool(cash_distributions),
            "fee_schedule": "current Upstox/NSE charges applied uniformly to all history; fund-unit STT is classified by instrument",
            "instrument_fee_products": instrument_fee_products,
            "cash_interest_pct": 0,
            "terminal_liquidation": True,
        },
    }
    return equity_frame, trades, stats


def _intraday_orb(
    signal_bars: pd.DataFrame,
    trade_bars: pd.DataFrame,
    starting_balance: float,
    risk_fraction: float = 0.005,
    max_exposure: float = 0.95,
    slippage_bps: float = 10.0,
    drawdown_limit_pct: float = 20.0,
    mode: str = "long",
    start: date | None = None,
    end: date | None = None,
    min_opening_range_pct: float = 0.0,
    max_opening_range_pct: float | None = None,
    fee_product: str = "equity_intraday",
    allowed_sessions: set[date] | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    if (starting_balance <= 0 or not 0 < risk_fraction <= 1 or not 0 < max_exposure <= 1
            or slippage_bps < 0 or drawdown_limit_pct <= 0 or mode not in {"long", "long_short"}
            or min_opening_range_pct < 0
            or (max_opening_range_pct is not None and max_opening_range_pct <= min_opening_range_pct)):
        raise ValueError("invalid capital, sizing, cost, drawdown, or intraday mode")
    if "time" not in signal_bars.columns:
        signal_bars = signal_bars.reset_index()
    if "time" not in trade_bars.columns:
        trade_bars = trade_bars.reset_index()
    index = signal_bars[["time", "high", "low", "close"]].rename(
        columns={"high": "signal_high", "low": "signal_low", "close": "signal_close"})
    traded = trade_bars[["time", "open", "high", "low", "close"]]
    bars = traded.merge(index, on="time", how="inner", validate="one_to_one").sort_values("time")
    if bars.empty:
        raise ValueError("signal and trade data have no matching bars")
    cash = float(starting_balance)
    slip = slippage_bps / 10_000
    fee_totals = defaultdict(float)
    turnover = slippage_cost = 0.0
    rows, trades = [], []
    range_filtered_sessions = 0
    regime_filtered_sessions = 0
    eligible_sessions = 0
    sessions = bars.groupby(bars["time"].dt.date, sort=True)
    for session, day in sessions:
        if (start is not None and session < start) or (end is not None and session > end):
            continue
        day = day.reset_index(drop=True)
        eligible_sessions += 1
        if allowed_sessions is not None and session not in allowed_sessions:
            regime_filtered_sessions += 1
            rows.append({"time": day.loc[len(day) - 1, "time"], "nav": cash, "trade_exposure_pct": 0.0})
            continue
        if len(day) < 4:
            rows.append({"time": day.loc[len(day) - 1, "time"], "nav": cash, "trade_exposure_pct": 0.0})
            continue
        opening_range_pct = 100 * (float(day.loc[0, "signal_high"]) - float(day.loc[0, "signal_low"])) / float(day.loc[0, "signal_close"])
        if (opening_range_pct < min_opening_range_pct
                or (max_opening_range_pct is not None and opening_range_pct > max_opening_range_pct)):
            range_filtered_sessions += 1
            rows.append({"time": day.loc[len(day) - 1, "time"], "nav": cash, "trade_exposure_pct": 0.0})
            continue
        side = 1 if day.loc[1, "signal_close"] > day.loc[0, "signal_high"] else -1 if day.loc[1, "signal_close"] < day.loc[0, "signal_low"] else 0
        if side == 0:
            rows.append({"time": day.loc[len(day) - 1, "time"], "nav": cash, "trade_exposure_pct": 0.0})
            continue
        if side < 0 and mode == "long":
            rows.append({"time": day.loc[len(day) - 1, "time"], "nav": cash, "trade_exposure_pct": 0.0})
            continue
        entry_bar = day.loc[2]
        raw_entry = float(entry_bar["open"])
        stop = float(day.loc[0, "low"] if side > 0 else day.loc[0, "high"])
        distance = side * (raw_entry - stop)
        if distance <= 0:
            rows.append({"time": day.loc[len(day) - 1, "time"], "nav": cash, "trade_exposure_pct": 0.0})
            continue
        quantity = min(int(cash * risk_fraction / distance), int(cash * max_exposure / raw_entry))
        if quantity <= 0:
            rows.append({"time": day.loc[len(day) - 1, "time"], "nav": cash, "trade_exposure_pct": 0.0})
            continue
        entry_fill = raw_entry * (1 + side * slip)
        entry_notional = quantity * entry_fill
        entry_charges = _fee_breakdown(entry_notional, "buy" if side > 0 else "sell", fee_product)
        exit_bar, raw_exit = day.iloc[-1], float(day.iloc[-1]["close"])
        stop_hit = False
        for _, bar in day.iloc[2:].iterrows():
            crossed = float(bar["low"]) <= stop if side > 0 else float(bar["high"]) >= stop
            if crossed:
                raw_exit = min(stop, float(bar["open"])) if side > 0 else max(stop, float(bar["open"]))
                exit_bar, stop_hit = bar, True
                break
        exit_fill = raw_exit * (1 - side * slip)
        exit_notional = quantity * exit_fill
        exit_charges = _fee_breakdown(exit_notional, "sell" if side > 0 else "buy", fee_product)
        fees = entry_charges["total"] + exit_charges["total"]
        pnl = side * (exit_fill - entry_fill) * quantity - fees
        cash += pnl
        turnover += entry_notional + exit_notional
        slippage_cost += quantity * (abs(entry_fill - raw_entry) + abs(exit_fill - raw_exit))
        for component in FEE_COMPONENTS:
            fee_totals[component] += entry_charges[component] + exit_charges[component]
        trades.append({
            "session": str(session), "side": "long" if side > 0 else "short", "quantity": quantity,
            "entry_time": entry_bar["time"], "exit_time": exit_bar["time"],
            "entry_price": entry_fill, "exit_price": exit_fill, "stop_price": stop,
            "stop_hit": stop_hit, "net_pnl_inr": pnl, "fees_inr": fees,
            "slippage_inr": quantity * (abs(entry_fill - raw_entry) + abs(exit_fill - raw_exit)),
        })
        rows.append({"time": day.loc[len(day) - 1, "time"], "nav": cash, "trade_exposure_pct": entry_notional / max(cash - pnl, 1) * 100})
    equity = pd.DataFrame(rows).set_index("time")
    if equity.empty:
        raise ValueError("the selected intraday period contains no sessions")
    returns = equity["nav"].pct_change().fillna(0)
    returns.iloc[0] = equity["nav"].iloc[0] / starting_balance - 1
    years = max(len(equity) / 252, 1 / 252)
    total_return = equity["nav"].iloc[-1] / starting_balance - 1
    full_nav = pd.concat([pd.Series([starting_balance]), equity["nav"].reset_index(drop=True)], ignore_index=True)
    drawdown = full_nav / full_nav.cummax() - 1
    stdev = float(returns.std(ddof=1)) if len(returns) > 1 else 0.0
    stats = {
        "starting_balance_inr": starting_balance, "ending_balance_inr": float(equity["nav"].iloc[-1]),
        "total_return_pct": float(total_return * 100),
        "cagr_pct": float(((1 + total_return) ** (1 / years) - 1) * 100) if total_return > -1 else -100.0,
        "max_drawdown_pct": float(drawdown.min() * 100), "drawdown_limit_pct": drawdown_limit_pct,
        "within_drawdown_limit": bool(drawdown.min() * 100 >= -drawdown_limit_pct),
        "sharpe_zero_rf": float(returns.mean() / stdev * math.sqrt(252)) if stdev else 0.0,
        "trade_count": len(trades), "order_count": 2 * len(trades), "turnover_inr": turnover,
        "total_fees_inr": float(sum(fee_totals.values())), "total_slippage_inr": slippage_cost,
        "fees_by_component_inr": {key: round(value, 2) for key, value in fee_totals.items()},
        "average_trade_exposure_pct": float(equity.loc[equity["trade_exposure_pct"] > 0, "trade_exposure_pct"].mean()) if equity["trade_exposure_pct"].gt(0).any() else 0.0,
        "first_bar": str(equity.index[0]), "last_bar": str(equity.index[-1]),
        "range_filter_sessions": range_filtered_sessions, "eligible_sessions": eligible_sessions,
        "regime_filtered_sessions": regime_filtered_sessions,
        "assumptions": {"signal": "30-minute opening-range close breakout", "entry": "next 30-minute bar open",
                        "stop": "opposite side of first 30-minute traded-ETF range; gap-through fills at bar open",
                        "exit": "stop or final bar close, flat by session end", "mode": mode,
                        "minimum_opening_range_pct": min_opening_range_pct,
                        "maximum_opening_range_pct": max_opening_range_pct,
                        "product": "equity_intraday", "exchange": "NSE", "risk_per_trade_pct": risk_fraction * 100,
                        "fee_product": fee_product,
                        "max_gross_exposure_pct": max_exposure * 100, "slippage_bps_per_side": slippage_bps},
    }
    return equity, pd.DataFrame(trades), stats


def _simulate_expiry_spreads(
    events: list[dict], session_dates: list[date], capital: float, slippage_bps: float, drawdown_limit_pct: float,
) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    if not events:
        raise ValueError("no monthly option spreads are available for this period")
    slip = slippage_bps / 10_000
    cash = capital
    active, completed, rows = [], [], []
    fees = defaultdict(float)
    turnover = slippage_cost = 0.0
    entries = defaultdict(list)
    for event in events:
        entries[event["entry_date"]].append(event)
    for session in session_dates:
        for source in entries.get(session, []):
            event = dict(source)
            qty = event["lot_size"]
            event["long_entry_fill"] = event["long_open"] * (1 + slip)
            event["short_entry_fill"] = event["short_open"] * (1 - slip)
            event["long_buy_fee"] = _fee_breakdown(qty * event["long_entry_fill"], "buy", "options", trade_date=event["entry_date"])
            event["short_sell_fee"] = _fee_breakdown(qty * event["short_entry_fill"], "sell", "options", trade_date=event["entry_date"])
            entry_cashflow = -qty * event["long_entry_fill"] - event["long_buy_fee"]["total"] + qty * event["short_entry_fill"] - event["short_sell_fee"]["total"]
            if -entry_cashflow > cash:
                continue
            cash += entry_cashflow
            event["entry_cashflow"] = entry_cashflow
            event["premium_debit_inr"] = -entry_cashflow
            event["last_mark"] = event["path"].get(session)
            active.append(event)
            turnover += qty * (event["long_entry_fill"] + event["short_entry_fill"])
            slippage_cost += qty * (abs(event["long_entry_fill"] - event["long_open"]) + abs(event["short_entry_fill"] - event["short_open"]))
            for component in FEE_COMPONENTS:
                fees[component] += event["long_buy_fee"][component] + event["short_sell_fee"][component]
        for event in active:
            event["last_mark"] = event["path"].get(session, event["last_mark"])
        for event in list(active):
            if event["exit_date"] != session:
                continue
            qty = event["lot_size"]
            event["long_exit_fill"] = event["long_close"] * (1 - slip)
            event["short_exit_fill"] = event["short_close"] * (1 + slip)
            event["long_sell_fee"] = _fee_breakdown(qty * event["long_exit_fill"], "sell", "options", trade_date=event["exit_date"])
            event["short_buy_fee"] = _fee_breakdown(qty * event["short_exit_fill"], "buy", "options", trade_date=event["exit_date"])
            exit_cashflow = qty * event["long_exit_fill"] - event["long_sell_fee"]["total"] - qty * event["short_exit_fill"] - event["short_buy_fee"]["total"]
            cash += exit_cashflow
            event["net_pnl_inr"] = event["entry_cashflow"] + exit_cashflow
            event["fees_inr"] = sum(event[k]["total"] for k in ("long_buy_fee", "short_sell_fee", "long_sell_fee", "short_buy_fee"))
            event["slippage_inr"] = qty * (
                abs(event["long_entry_fill"] - event["long_open"]) + abs(event["short_entry_fill"] - event["short_open"])
                + abs(event["long_exit_fill"] - event["long_close"]) + abs(event["short_exit_fill"] - event["short_close"])
            )
            turnover += qty * (event["long_exit_fill"] + event["short_exit_fill"])
            slippage_cost += qty * (abs(event["long_exit_fill"] - event["long_close"]) + abs(event["short_exit_fill"] - event["short_close"]))
            for component in FEE_COMPONENTS:
                fees[component] += event["long_sell_fee"][component] + event["short_buy_fee"][component]
            completed.append({k: v for k, v in event.items() if k not in {"path", "last_mark", "entry_cashflow", "long_buy_fee", "short_sell_fee", "long_sell_fee", "short_buy_fee"}})
            active.remove(event)
        nav = cash + sum(e["lot_size"] * (e["last_mark"][0] - e["last_mark"][1]) for e in active if e["last_mark"] is not None)
        rows.append({"session": session, "nav": nav})
    if active:
        raise ValueError("an option spread remained open after its scheduled exit")
    equity = pd.DataFrame(rows).set_index("session")
    returns = equity["nav"].pct_change().fillna(0)
    returns.iloc[0] = equity["nav"].iloc[0] / capital - 1
    full_nav = pd.concat([pd.Series([capital]), equity["nav"].reset_index(drop=True)], ignore_index=True)
    drawdown = full_nav / full_nav.cummax() - 1
    total_return = equity["nav"].iloc[-1] / capital - 1
    stdev = float(returns.std(ddof=1)) if len(returns) > 1 else 0.0
    wins = [t["net_pnl_inr"] for t in completed if t["net_pnl_inr"] > 0]
    losses = [-t["net_pnl_inr"] for t in completed if t["net_pnl_inr"] < 0]
    stats = {
        "starting_balance_inr": capital, "ending_balance_inr": float(equity["nav"].iloc[-1]),
        "total_return_pct": float(total_return * 100),
        "cagr_pct": float(((1 + total_return) ** (252 / len(equity)) - 1) * 100) if total_return > -1 else -100.0,
        "max_drawdown_pct": float(drawdown.min() * 100), "drawdown_limit_pct": drawdown_limit_pct,
        "within_drawdown_limit": bool(drawdown.min() * 100 >= -drawdown_limit_pct),
        "sharpe_zero_rf": float(returns.mean() / stdev * math.sqrt(252)) if stdev else 0.0,
        "trade_count": len(completed), "order_count": 4 * len(completed),
        "win_rate_pct": 100 * len(wins) / len(completed) if completed else 0.0,
        "profit_factor": sum(wins) / sum(losses) if losses else (None if wins else 0.0),
        "turnover_inr": turnover, "total_fees_inr": float(sum(fees.values())), "total_slippage_inr": slippage_cost,
        "fees_by_component_inr": {key: round(value, 2) for key, value in fees.items()},
        "average_debit_inr": float(np.mean([t["premium_debit_inr"] for t in completed])) if completed else 0.0,
        "first_session": str(equity.index[0]), "last_session": str(equity.index[-1]),
        "assumptions": {"fee_schedule": "date-aware NSE options STT and transaction/IPFT rates; 2024-10 onward",
                        "slippage_bps_per_leg_per_side": slippage_bps, "defined_risk": "one NIFTY debit spread per monthly expiry",
                        "cash_interest_pct": 0, "option_mark": "daily close; realized at close 5 sessions before expiry"},
    }
    return equity, pd.DataFrame(completed), stats


def _daily_contract_bars(bars: pd.DataFrame) -> pd.DataFrame:
    if bars.empty:
        return bars
    bars = bars.copy()
    bars["time"] = pd.to_datetime(bars["time"], errors="raise")
    bars["session"] = bars["time"].dt.date
    return bars.sort_values("time").drop_duplicates("session", keep="first").set_index("session")


def _monthly_atm_spreads(
    signal_bars: pd.DataFrame, underlying_key: str, start: date, end: date, train_end: date,
    validation_end: date, capital: float, drawdown_limit_pct: float, slippage_bps: float,
) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    if start > train_end or train_end >= validation_end or validation_end >= end:
        raise ValueError("periods must satisfy start <= train_end < validation_end < end")
    if "time" not in signal_bars.columns:
        signal_bars = signal_bars.reset_index()
    signal_bars = signal_bars.sort_values("time").copy()
    signal_bars["session"] = signal_bars["time"].dt.date
    closes = signal_bars.groupby("session")["close"].last().sort_index()
    index_dates = list(closes.index)
    sma200 = closes.rolling(200, min_periods=200).mean()
    expiry_data = fetch_expiries(underlying_key)
    raw_expiries = expiry_data if isinstance(expiry_data, list) else expiry_data.get("expiries", [])
    last_complete_month = date.today().replace(day=1)
    month_ends = {}
    for raw in raw_expiries:
        expiry = date.fromisoformat(raw)
        if start <= expiry <= end and expiry < last_complete_month:
            key = (expiry.year, expiry.month)
            month_ends[key] = max(expiry, month_ends.get(key, expiry))
    expiries = sorted(month_ends.values())
    events, skipped = [], []
    cache_dir = DATA_DIR / "expired"
    cache_dir.mkdir(parents=True, exist_ok=True)
    for number, expiry in enumerate(expiries, 1):
        expiry_pos = max((i for i, d in enumerate(index_dates) if d <= expiry), default=-1)
        signal_pos, exit_pos = expiry_pos - 20, expiry_pos - 5
        if signal_pos < 199 or exit_pos <= signal_pos + 1:
            skipped.append({"expiry": str(expiry), "reason": "insufficient underlying history"})
            continue
        signal_date, entry_date, exit_date = index_dates[signal_pos], index_dates[signal_pos + 1], index_dates[exit_pos]
        spot, trend = float(closes.iloc[signal_pos]), float(sma200.iloc[signal_pos])
        option_type = "CE" if spot >= trend else "PE"
        contract_file = cache_dir / f"monthly-{expiry}-option-contracts.json"
        if contract_file.exists():
            contracts = json.loads(contract_file.read_text(encoding="utf-8"))
        else:
            contracts = fetch_expired_contracts(underlying_key, expiry, "option")
            contract_file.write_text(json.dumps(contracts), encoding="utf-8")
        listed = [c for c in contracts if c.get("instrument_type") == option_type and not c.get("weekly", False)]
        strikes = sorted({float(c["strike_price"]) for c in listed})
        if not strikes:
            skipped.append({"expiry": str(expiry), "reason": "monthly option chain unavailable"})
            continue
        atm = min(strikes, key=lambda value: abs(value - spot))
        short_strike = atm + 200 if option_type == "CE" else atm - 200
        long_contract = next((c for c in listed if float(c["strike_price"]) == atm), None)
        short_contract = next((c for c in listed if float(c["strike_price"]) == short_strike), None)
        if not long_contract or not short_contract or long_contract["lot_size"] != short_contract["lot_size"]:
            skipped.append({"expiry": str(expiry), "reason": "required 200-point vertical spread unavailable"})
            continue
        bars_by_contract = []
        empty_contract = False
        for contract in (long_contract, short_contract):
            safe_key = re.sub(r"[^A-Za-z0-9_-]+", "_", contract["instrument_key"]).strip("_")
            bar_file = cache_dir / f"{safe_key}-day-{entry_date}-{exit_date}.csv"
            if bar_file.exists():
                option_bars = pd.read_csv(bar_file, parse_dates=["time"])
            else:
                option_bars = fetch_expired_candles(contract["instrument_key"], entry_date, exit_date, "day")
                option_bars.to_csv(bar_file, index=False)
            if option_bars.empty:
                empty_contract = True
                break
            bars_by_contract.append(_daily_contract_bars(option_bars))
        if empty_contract:
            skipped.append({"expiry": str(expiry), "reason": "expired contract returned no daily candles"})
            continue
        long_bars, short_bars = bars_by_contract
        if entry_date not in long_bars.index or exit_date not in long_bars.index or entry_date not in short_bars.index or exit_date not in short_bars.index:
            skipped.append({"expiry": str(expiry), "reason": "missing entry or exit candle"})
            continue
        if min(float(long_bars.loc[entry_date, "volume"]), float(short_bars.loc[entry_date, "volume"]),
               float(long_bars.loc[exit_date, "volume"]), float(short_bars.loc[exit_date, "volume"])) <= 0:
            skipped.append({"expiry": str(expiry), "reason": "zero-volume entry or exit candle"})
            continue
        dates = [d for d in index_dates if entry_date <= d <= exit_date]
        long_marks = long_bars["close"].reindex(dates).ffill()
        short_marks = short_bars["close"].reindex(dates).ffill()
        if long_marks.isna().any() or short_marks.isna().any():
            skipped.append({"expiry": str(expiry), "reason": "missing mark-to-market candle"})
            continue
        events.append({
            "expiry": str(expiry), "entry_date": entry_date, "exit_date": exit_date,
            "signal_date": signal_date, "underlying_close": spot, "sma200": trend, "direction": option_type,
            "long_strike": atm, "short_strike": short_strike, "long_symbol": long_contract["trading_symbol"],
            "short_symbol": short_contract["trading_symbol"], "long_key": long_contract["instrument_key"],
            "short_key": short_contract["instrument_key"], "lot_size": int(long_contract["lot_size"]),
            "long_open": float(long_bars.loc[entry_date, "open"]), "short_open": float(short_bars.loc[entry_date, "open"]),
            "long_close": float(long_bars.loc[exit_date, "close"]), "short_close": float(short_bars.loc[exit_date, "close"]),
            "path": {d: (float(long_marks.loc[d]), float(short_marks.loc[d])) for d in dates},
        })
        print(f"expiry {expiry}: {option_type} {atm}/{short_strike}, entry {entry_date}, exit {exit_date}", flush=True)
    if not events:
        raise ValueError(f"no eligible monthly option spreads; skipped {len(skipped)} expiries")
    all_dates = [d for d in index_dates if min(e["entry_date"] for e in events) <= d <= max(e["exit_date"] for e in events)]
    equity, trades, overall = _simulate_expiry_spreads(events, all_dates, capital, slippage_bps, drawdown_limit_pct)
    splits = {}
    periods = {
        "train": (start, train_end),
        "validation": (train_end + timedelta(days=1), validation_end),
        "holdout": (validation_end + timedelta(days=1), end),
    }
    for label, (period_start, period_end) in periods.items():
        sample = [e for e in events if period_start <= e["entry_date"] <= period_end]
        if sample:
            dates = [d for d in index_dates if min(e["entry_date"] for e in sample) <= d <= max(e["exit_date"] for e in sample)]
            _, _, splits[label] = _simulate_expiry_spreads(sample, dates, capital, slippage_bps, drawdown_limit_pct)
        else:
            splits[label] = {"trade_count": 0, "total_return_pct": 0.0, "max_drawdown_pct": 0.0}
    holdout_events = [e for e in events if periods["holdout"][0] <= e["entry_date"] <= periods["holdout"][1]]
    holdout_dates = (
        [d for d in index_dates if min(e["entry_date"] for e in holdout_events) <= d <= max(e["exit_date"] for e in holdout_events)]
        if holdout_events else []
    )
    sensitivity = {}
    for bps in sorted({slippage_bps / 2, slippage_bps, slippage_bps * 2}):
        full_stats = _simulate_expiry_spreads(events, all_dates, capital, bps, drawdown_limit_pct)[2]
        holdout_stats = _simulate_expiry_spreads(holdout_events, holdout_dates, capital, bps, drawdown_limit_pct)[2] if holdout_events else None
        sensitivity[str(bps)] = {"full_sample": full_stats, "holdout": holdout_stats}
    summary = {
        "strategy": "monthly 200-day trend-following NIFTY debit spread",
        "underlying_key": underlying_key, "capital_inr": capital, "drawdown_limit_pct": drawdown_limit_pct,
        "data_start": start.isoformat(), "data_end": end.isoformat(), "expiries_tested": len(events),
        "skipped_expiries": skipped, "full_sample": overall, "periods": splits,
        "slippage_sensitivity_bps_per_leg_per_side": sensitivity,
    }
    return equity, trades, summary


def _walkforward(
    panels: dict[str, pd.DataFrame],
    targets: pd.DataFrame,
    rebalance: pd.Series,
    capital: float,
    train_start: date,
    train_end: date,
    validation_end: date,
    drawdown_limit_pct: float,
    slippage_bps: float,
    product: str,
    cash_proxy: str | None = None,
) -> tuple[pd.DataFrame, dict, tuple[pd.DataFrame, pd.DataFrame] | None]:
    if train_start > train_end or train_end >= validation_end:
        raise ValueError("periods must satisfy train_start <= train_end < validation_end")
    validation_start = train_end + timedelta(days=1)
    test_start = validation_end + timedelta(days=1)
    last_date = panels["close"].index[-1].date()
    if validation_end >= last_date:
        raise ValueError("validation_end must precede the final data date so a holdout remains")
    exposures = [0.10, 0.25, 0.50, 0.75, 0.95]
    rows = []
    for exposure in exposures:
        _, _, train = _simulate(panels, targets, rebalance, capital, exposure, slippage_bps, product, train_start, train_end, drawdown_limit_pct, cash_proxy)
        _, _, validation = _simulate(panels, targets, rebalance, capital, exposure, slippage_bps, product, validation_start, validation_end, drawdown_limit_pct, cash_proxy)
        _, _, combined = _simulate(panels, targets, rebalance, capital, exposure, slippage_bps, product, train_start, validation_end, drawdown_limit_pct, cash_proxy)
        feasible = train["within_drawdown_limit"] and validation["within_drawdown_limit"] and combined["within_drawdown_limit"]
        rows.append({
            "max_exposure_pct": exposure * 100,
            "train_cagr_pct": train["cagr_pct"],
            "train_max_drawdown_pct": train["max_drawdown_pct"],
            "validation_cagr_pct": validation["cagr_pct"],
            "validation_max_drawdown_pct": validation["max_drawdown_pct"],
            "train_plus_validation_max_drawdown_pct": combined["max_drawdown_pct"],
            "eligible_under_drawdown_budget": feasible,
        })
    screen = pd.DataFrame(rows)
    eligible = screen[screen["eligible_under_drawdown_budget"]]
    selected_exposure = float(eligible.sort_values(["validation_cagr_pct", "max_exposure_pct"], ascending=False).iloc[0]["max_exposure_pct"] / 100) if not eligible.empty else None
    result = {
        "capital_inr": capital,
        "drawdown_limit_pct": drawdown_limit_pct,
        "cash_proxy": cash_proxy,
        "periods": {
            "train_start": train_start.isoformat(),
            "train_end": train_end.isoformat(),
            "validation_start": validation_start.isoformat(),
            "validation_end": validation_end.isoformat(),
            "test_start": test_start.isoformat(),
            "test_end": last_date.isoformat(),
        },
        "exposure_grid_pct": [row["max_exposure_pct"] for row in rows],
        "selection_rule": "highest validation CAGR among exposures within the drawdown limit in train, validation, and the continuous train-plus-validation account",
        "selected_exposure_pct": selected_exposure * 100 if selected_exposure is not None else None,
        "selection_positive_validation_cagr": bool(eligible["validation_cagr_pct"].max() > 0) if not eligible.empty else False,
        "test_result": None,
    }
    test_artifacts = None
    if selected_exposure is not None:
        test_equity, test_orders, test = _simulate(
            panels, targets, rebalance, capital, selected_exposure, slippage_bps, product,
            test_start, last_date, drawdown_limit_pct, cash_proxy,
        )
        result["test_result"] = test
        test_artifacts = (test_equity, test_orders)
    return screen, result, test_artifacts


def _self_check() -> None:
    windows = request_windows(date(2024, 1, 20), date(2024, 3, 10), "minutes", 5)
    assert windows[0][0] == date(2024, 1, 20) and windows[-1][1] == date(2024, 3, 10)
    assert all((b - a).days < 32 for a, b in windows)
    cash_buy = _fee_breakdown(100_000, "buy", "equity_delivery")
    cash_sell = _fee_breakdown(100_000, "sell", "equity_delivery")
    assert cash_buy["total"] > 0 and cash_sell["total"] > cash_buy["total"]
    assert math.isclose(cash_buy["sebi"], 0.10)
    assert math.isclose(cash_buy["stt"], 100.0) and math.isclose(cash_sell["stt"], 100.0)
    assert _fee_breakdown(100_000, "buy", "equity_fund_delivery")["stt"] == 0
    assert math.isclose(_fee_breakdown(100_000, "sell", "equity_fund_delivery")["stt"], 1.0)
    assert _fee_breakdown(100_000, "buy", "other_fund_delivery")["stt"] == 0
    assert _fee_breakdown(100_000, "sell", "other_fund_delivery")["stt"] == 0
    assert math.isclose(_fee_breakdown(100_000, "sell", "equity_fund_intraday")["stt"], 25.0)
    assert _fee_breakdown(100_000, "sell", "other_fund_intraday")["stt"] == 0
    assert _fee_breakdown(100_000, "sell", "options")["stt"] == 150
    assert math.isclose(_fee_breakdown(100_000, "sell", "options")["exchange"], 35.52)
    old_option_sell = _fee_breakdown(100_000, "sell", "options", trade_date=date(2025, 10, 1))
    old_option_buy = _fee_breakdown(100_000, "buy", "options", trade_date=date(2025, 10, 1))
    march_option_sell = _fee_breakdown(100_000, "sell", "options", trade_date=date(2026, 3, 1))
    april_option_sell = _fee_breakdown(100_000, "sell", "options", trade_date=date(2026, 4, 1))
    assert old_option_sell["stt"] == 100 and math.isclose(old_option_sell["exchange"], 35.03)
    assert old_option_buy["stt"] == 0
    assert math.isclose(old_option_sell["ipft"], 0.50)
    assert march_option_sell["stt"] == 100 and math.isclose(march_option_sell["exchange"], 35.52)
    assert math.isclose(march_option_sell["ipft"], 0.0001)
    assert april_option_sell["stt"] == 150
    intraday_time = pd.date_range("2024-01-02 09:15", periods=5, freq="30min")
    signal = pd.DataFrame({"time": intraday_time, "open": [100, 101, 103, 104, 105], "high": [102, 103, 104, 105, 111],
                           "low": [98, 100, 102, 103, 104], "close": [101, 103, 104, 105, 110]})
    traded = signal.copy()
    _, intraday_trades, intraday = _intraday_orb(signal.set_index("time"), traded.set_index("time"), 10_000, risk_fraction=0.05, slippage_bps=0)
    assert intraday["trade_count"] == 1 and intraday_trades.iloc[0]["side"] == "long"
    assert intraday["ending_balance_inr"] > 10_000 and intraday["within_drawdown_limit"]
    _, filtered_trades, filtered_intraday = _intraday_orb(
        signal.set_index("time"), traded.set_index("time"), 10_000, risk_fraction=0.05,
        slippage_bps=0, min_opening_range_pct=4.0,
    )
    assert filtered_intraday["trade_count"] == 0 and filtered_intraday["range_filter_sessions"] == 1
    assert filtered_trades.empty and filtered_intraday["ending_balance_inr"] == 10_000
    _, upper_filtered_trades, upper_filtered_intraday = _intraday_orb(
        signal.set_index("time"), traded.set_index("time"), 10_000, risk_fraction=0.05,
        slippage_bps=0, max_opening_range_pct=3.9,
    )
    assert upper_filtered_trades.empty and upper_filtered_intraday["range_filter_sessions"] == 1
    _, regime_filtered_trades, regime_filtered = _intraday_orb(
        signal.set_index("time"), traded.set_index("time"), 10_000, risk_fraction=0.05,
        slippage_bps=0, allowed_sessions=set(),
    )
    assert regime_filtered_trades.empty and regime_filtered["regime_filtered_sessions"] == 1
    assert regime_filtered["ending_balance_inr"] == 10_000
    spread_dates = [date(2024, 10, day) for day in (2, 3, 4)]
    spread = {"entry_date": spread_dates[0], "exit_date": spread_dates[-1], "lot_size": 10,
              "long_open": 100, "short_open": 40, "long_close": 120, "short_close": 30,
              "path": {spread_dates[0]: (95, 38), spread_dates[1]: (105, 35), spread_dates[-1]: (120, 30)}}
    _, spread_trades, spread_stats = _simulate_expiry_spreads([spread], spread_dates, 10_000, 0, 20)
    assert spread_stats["trade_count"] == 1 and spread_stats["order_count"] == 4
    assert spread_trades.iloc[0]["net_pnl_inr"] > 0 and spread_stats["within_drawdown_limit"]
    duplicate_daily = pd.DataFrame({"time": [pd.Timestamp("2024-01-02 00:00", tz="Asia/Kolkata"), pd.Timestamp("2024-01-02 09:15", tz="Asia/Kolkata")],
                                    "close": [101, 99]})
    assert len(_daily_contract_bars(duplicate_daily)) == 1 and _daily_contract_bars(duplicate_daily)["close"].iloc[0] == 101
    index = pd.date_range("2020-01-01", periods=300, freq="B")
    values = np.arange(100.0, 400.0)
    frame = pd.DataFrame({"open": values, "high": values + 1, "low": values - 1, "close": values, "volume": 1}, index=index)
    panels = {key: pd.DataFrame({"TEST": frame[key]}) for key in ("open", "high", "low", "close", "volume")}
    targets = pd.DataFrame({"TEST": 1.0}, index=index)
    rebalance = pd.Series(False, index=index)
    rebalance.iloc[0] = True
    equity, orders, stats = _simulate(panels, targets, rebalance, 10_000, 0.95, 0)
    assert stats["ending_balance_inr"] > 10_000
    assert stats["total_fees_inr"] > 0 and len(orders) == 2
    assert equity["nav"].iloc[-1] < 10_000 * values[-1] / values[1]
    assert stats["within_drawdown_limit"]
    ex_date = index[100].date()
    distributed_equity, distributed_orders, distributed_stats = _simulate(
        panels, targets, rebalance, 10_000, 0.95, 0, cash_distributions=[("TEST", ex_date, 2.0)])
    held = sum(int(row["quantity"]) if row["side"] == "buy" else -int(row["quantity"])
               for _, row in distributed_orders.iterrows() if row["time"].date() < ex_date)
    assert distributed_stats["cash_distributions_inr"] == held * 2.0
    assert distributed_equity.loc[pd.Timestamp(ex_date), "cash_distribution_inr"] == held * 2.0
    holdout_start = index[260].date()
    _, holdout_orders, holdout = _simulate(panels, targets, rebalance, 10_000, 0.95, 0, start=holdout_start)
    assert holdout_orders.iloc[0]["time"] == index[260]
    assert holdout["first_bar"] == str(index[260])


def main() -> None:
    parser = argparse.ArgumentParser(description="Upstox data and daily strategy research runner")
    commands = parser.add_subparsers(dest="command", required=True)
    catalog = commands.add_parser("catalog", help="search the current Upstox instrument master")
    catalog.add_argument("--query", default="", help="regular expression over name and symbols")
    catalog.add_argument("--segment")
    catalog.add_argument("--type", dest="instrument_type")
    catalog.add_argument("--out")
    fetch = commands.add_parser("fetch", help="fetch and cache historical OHLCV bars")
    fetch.add_argument("--instrument-key", action="append", required=True, help="repeat for each instrument")
    fetch.add_argument("--start", required=True, type=date.fromisoformat)
    fetch.add_argument("--end", required=True, type=date.fromisoformat)
    fetch.add_argument("--unit", choices=["minutes", "hours", "days", "weeks", "months"], default="days")
    fetch.add_argument("--interval", type=int, default=1)
    fetch.add_argument("--out")
    fetch.add_argument("--out-dir")
    expiries = commands.add_parser("expiries", help="check access to historical expired derivative expiries")
    expiries.add_argument("--instrument-key", required=True)
    actions = commands.add_parser("corporate-actions", help="download dividends and other corporate actions for an ISIN")
    actions.add_argument("--isin", required=True)
    actions.add_argument("--out")
    contracts = commands.add_parser("expired-contracts", help="download one expired futures/options contract list")
    contracts.add_argument("--instrument-key", required=True)
    contracts.add_argument("--expiry", required=True, type=date.fromisoformat)
    contracts.add_argument("--kind", choices=["option", "future"], required=True)
    contracts.add_argument("--out")
    expired_fetch = commands.add_parser("expired-fetch", help="download historical candles for one expired derivative contract")
    expired_fetch.add_argument("--instrument-key", required=True)
    expired_fetch.add_argument("--start", required=True, type=date.fromisoformat)
    expired_fetch.add_argument("--end", required=True, type=date.fromisoformat)
    expired_fetch.add_argument("--interval", choices=["1minute", "3minute", "5minute", "15minute", "30minute", "day"], default="day")
    expired_fetch.add_argument("--out")
    backtest = commands.add_parser("backtest", help="run a cash-account daily strategy backtest")
    backtest.add_argument("--data", action="append", required=True, help="SYMBOL=CSV_PATH; repeat for each asset")
    backtest.add_argument("--strategy", choices=["buyhold", "trend200", "donchian55_20", "momentum12_1"], required=True)
    backtest.add_argument("--top-n", type=int, default=3)
    backtest.add_argument("--capital", type=float, default=1_000_000)
    backtest.add_argument("--max-exposure", type=float, default=0.95, help="maximum risky allocation as a fraction of equity")
    backtest.add_argument("--slippage-bps", type=float, default=10)
    backtest.add_argument("--drawdown-limit", type=float, default=20)
    backtest.add_argument("--cash-proxy", help="symbol to hold idle allocation in, such as LIQUIDBEES")
    backtest.add_argument("--cash-distribution", action="append", nargs=3,
                          metavar=("SYMBOL", "EX_DATE", "INR_PER_SHARE"),
                          help="credit a known distribution to prior-close units on its ex-date; repeatable")
    backtest.add_argument("--out-dir")
    walkforward = commands.add_parser("walkforward", help="select exposure on train/validation, then run one untouched holdout")
    walkforward.add_argument("--data", action="append", required=True, help="SYMBOL=CSV_PATH; repeat for each asset")
    walkforward.add_argument("--strategy", choices=["buyhold", "trend200", "donchian55_20", "momentum12_1"], required=True)
    walkforward.add_argument("--top-n", type=int, default=3)
    walkforward.add_argument("--train-start", type=date.fromisoformat)
    walkforward.add_argument("--train-end", required=True, type=date.fromisoformat)
    walkforward.add_argument("--validation-end", required=True, type=date.fromisoformat)
    walkforward.add_argument("--capital", type=float, default=1_000_000)
    walkforward.add_argument("--drawdown-limit", type=float, default=20)
    walkforward.add_argument("--slippage-bps", type=float, default=10)
    walkforward.add_argument("--cash-proxy", help="symbol to hold idle allocation in, such as LIQUIDBEES")
    walkforward.add_argument("--out-dir")
    intraday = commands.add_parser("intraday-orb", help="backtest a 30-minute NIFTY opening-range breakout on a tradable ETF")
    intraday.add_argument("--signal-data", required=True, help="INDEX_OR_SYMBOL=CSV_PATH")
    intraday.add_argument("--trade-data", required=True, help="ETF_OR_SYMBOL=CSV_PATH")
    intraday.add_argument("--mode", choices=["long", "long_short"], default="long")
    intraday.add_argument("--start", type=date.fromisoformat)
    intraday.add_argument("--end", type=date.fromisoformat)
    intraday.add_argument("--capital", type=float, default=1_000_000)
    intraday.add_argument("--risk-per-trade", type=float, default=0.005, help="fraction of account risked to the opening-range stop")
    intraday.add_argument("--max-exposure", type=float, default=0.95)
    intraday.add_argument("--drawdown-limit", type=float, default=20)
    intraday.add_argument("--slippage-bps", type=float, default=10)
    intraday.add_argument("--min-opening-range-pct", type=float, default=0.0)
    intraday.add_argument("--max-opening-range-pct", type=float)
    intraday.add_argument("--out-dir")
    monthly_options = commands.add_parser("monthly-options", help="backtest monthly NIFTY 200-day trend debit spreads using expired Upstox data")
    monthly_options.add_argument("--signal-data", required=True, help="INDEX_OR_SYMBOL=CSV_PATH")
    monthly_options.add_argument("--underlying-key", required=True)
    monthly_options.add_argument("--start", type=date.fromisoformat, default=date(2024, 10, 1))
    monthly_options.add_argument("--end", type=date.fromisoformat, default=date(2026, 9, 30))
    monthly_options.add_argument("--train-end", type=date.fromisoformat, default=date(2025, 6, 30))
    monthly_options.add_argument("--validation-end", type=date.fromisoformat, default=date(2025, 12, 31))
    monthly_options.add_argument("--capital", type=float, default=1_000_000)
    monthly_options.add_argument("--drawdown-limit", type=float, default=20)
    monthly_options.add_argument("--slippage-bps", type=float, default=50, help="slippage per leg per side; sensitivity is half and double")
    monthly_options.add_argument("--out-dir")
    commands.add_parser("self-check", help="run a small assert-based implementation check")
    args = parser.parse_args()

    if args.command == "self-check":
        _self_check()
        print("self-check passed")
    elif args.command == "catalog":
        result = search_catalog(args.query, args.segment, args.instrument_type)
        if args.out:
            path = Path(args.out)
            if not path.is_absolute():
                path = ROOT / path
            path.parent.mkdir(parents=True, exist_ok=True)
            result.to_csv(path, index=False)
            print(f"{len(result)} instruments saved to {path}")
        else:
            print(result.to_string(index=False, max_rows=200))
    elif args.command == "fetch":
        if args.out and len(args.instrument_key) != 1:
            raise ValueError("--out accepts one instrument; use --out-dir for a batch")
        if args.out and args.out_dir:
            raise ValueError("choose either --out or --out-dir")
        for instrument_key in args.instrument_key:
            result = fetch_candles(instrument_key, args.start, args.end, args.unit, args.interval)
            safe_key = re.sub(r"[^A-Za-z0-9_-]+", "_", instrument_key).strip("_")
            name = f"{safe_key}-{args.unit}-{args.interval}-{args.start}-{args.end}.csv"
            path = Path(args.out) if args.out else (Path(args.out_dir) / name if args.out_dir else DATA_DIR / name)
            if not path.is_absolute():
                path = ROOT / path
            path.parent.mkdir(parents=True, exist_ok=True)
            result.to_csv(path, index=False)
            print(f"{instrument_key}: {len(result)} bars saved to {path}")
    elif args.command == "expiries":
        print(json.dumps(fetch_expiries(args.instrument_key), indent=2))
    elif args.command == "corporate-actions":
        result = fetch_corporate_actions(args.isin)
        if args.out:
            path = Path(args.out)
            if not path.is_absolute():
                path = ROOT / path
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(result, indent=2), encoding="utf-8")
            print(f"{len(result)} actions saved to {path}")
        else:
            print(json.dumps(result, indent=2))
    elif args.command == "expired-contracts":
        result = fetch_expired_contracts(args.instrument_key, args.expiry, args.kind)
        safe_key = re.sub(r"[^A-Za-z0-9_-]+", "_", args.instrument_key).strip("_")
        path = Path(args.out) if args.out else DATA_DIR / "expired" / f"{safe_key}-{args.kind}-{args.expiry}.json"
        if not path.is_absolute():
            path = ROOT / path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(result, indent=2), encoding="utf-8")
        print(f"{len(result)} contracts saved to {path}")
    elif args.command == "expired-fetch":
        result = fetch_expired_candles(args.instrument_key, args.start, args.end, args.interval)
        safe_key = re.sub(r"[^A-Za-z0-9_-]+", "_", args.instrument_key).strip("_")
        path = Path(args.out) if args.out else DATA_DIR / "expired" / f"{safe_key}-{args.interval}-{args.start}-{args.end}.csv"
        if not path.is_absolute():
            path = ROOT / path
        path.parent.mkdir(parents=True, exist_ok=True)
        result.to_csv(path, index=False)
        print(f"{len(result)} candles saved to {path}")
    elif args.command == "backtest":
        frames, panels = _read_prices(args.data)
        targets, rebalance = make_targets(panels, args.strategy, args.top_n, args.cash_proxy)
        distributions = [(symbol, date.fromisoformat(ex_date), float(amount))
                         for symbol, ex_date, amount in (args.cash_distribution or [])]
        equity, trades, stats = _simulate(panels, targets, rebalance, args.capital, args.max_exposure,
                                          args.slippage_bps, drawdown_limit_pct=args.drawdown_limit,
                                          cash_proxy=args.cash_proxy, cash_distributions=distributions)
        run_path = Path(args.out_dir) if args.out_dir else RUN_DIR / f"{args.strategy}-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
        if not run_path.is_absolute():
            run_path = ROOT / run_path
        run_path.mkdir(parents=True, exist_ok=True)
        equity.to_csv(run_path / "equity.csv", index_label="time")
        trades.to_csv(run_path / "orders.csv", index=False)
        stats["strategy"] = args.strategy
        stats["symbols"] = sorted(frames)
        (run_path / "summary.json").write_text(json.dumps(stats, indent=2), encoding="utf-8")
        print(json.dumps({"run_dir": str(run_path), **stats}, indent=2))
    elif args.command == "intraday-orb":
        signal_frames, _ = _read_prices([args.signal_data])
        trade_frames, _ = _read_prices([args.trade_data])
        trade_symbol = next(iter(trade_frames))
        fund_intraday_products = {
            "equity_fund_delivery": "equity_fund_intraday",
            "other_fund_delivery": "other_fund_intraday",
        }
        fee_product = fund_intraday_products.get(FUND_FEE_PRODUCTS.get(trade_symbol), "equity_intraday")
        equity, trades, stats = _intraday_orb(
            next(iter(signal_frames.values())), next(iter(trade_frames.values())), args.capital,
            args.risk_per_trade, args.max_exposure, args.slippage_bps, args.drawdown_limit, args.mode, args.start, args.end,
            args.min_opening_range_pct, args.max_opening_range_pct, fee_product,
        )
        run_path = Path(args.out_dir) if args.out_dir else RUN_DIR / f"intraday-orb-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
        if not run_path.is_absolute():
            run_path = ROOT / run_path
        run_path.mkdir(parents=True, exist_ok=True)
        equity.to_csv(run_path / "equity.csv", index_label="time")
        trades.to_csv(run_path / "trades.csv", index=False)
        stats["signal_symbol"] = next(iter(signal_frames))
        stats["trade_symbol"] = next(iter(trade_frames))
        (run_path / "summary.json").write_text(json.dumps(stats, indent=2), encoding="utf-8")
        print(json.dumps({"run_dir": str(run_path), **stats}, indent=2))
    elif args.command == "monthly-options":
        signal_frames, _ = _read_prices([args.signal_data])
        equity, trades, summary = _monthly_atm_spreads(
            next(iter(signal_frames.values())), args.underlying_key, args.start, args.end, args.train_end,
            args.validation_end, args.capital, args.drawdown_limit, args.slippage_bps,
        )
        run_path = Path(args.out_dir) if args.out_dir else RUN_DIR / "monthly-atm-options"
        if not run_path.is_absolute():
            run_path = ROOT / run_path
        run_path.mkdir(parents=True, exist_ok=True)
        equity.to_csv(run_path / "equity.csv", index_label="session")
        trades.to_csv(run_path / "trades.csv", index=False)
        summary["signal_symbol"] = next(iter(signal_frames))
        (run_path / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
        print(json.dumps({"run_dir": str(run_path), **summary}, indent=2))
    else:
        frames, panels = _read_prices(args.data)
        targets, rebalance = make_targets(panels, args.strategy, args.top_n, args.cash_proxy)
        train_start = args.train_start or panels["close"].index[0].date()
        screen, result, test_artifacts = _walkforward(
            panels, targets, rebalance, args.capital, train_start, args.train_end, args.validation_end,
            args.drawdown_limit, args.slippage_bps, "equity_delivery", args.cash_proxy,
        )
        run_path = Path(args.out_dir) if args.out_dir else RUN_DIR / f"walkforward-{args.strategy}-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
        if not run_path.is_absolute():
            run_path = ROOT / run_path
        run_path.mkdir(parents=True, exist_ok=True)
        screen.to_csv(run_path / "exposure_screen.csv", index=False)
        if test_artifacts:
            test_equity, test_orders = test_artifacts
            test_equity.to_csv(run_path / "test_equity.csv", index_label="time")
            test_orders.to_csv(run_path / "test_orders.csv", index=False)
        result["strategy"] = args.strategy
        result["symbols"] = sorted(frames)
        result["assumptions"] = {
            "product": "equity_delivery",
            "cash_proxy": args.cash_proxy,
            "exchange": "NSE",
            "slippage_bps_per_side": args.slippage_bps,
            "fee_schedule": "date-aware NSE options STT and transaction/IPFT rates; 2024-10 onward",
            "cash_interest_pct": 0,
            "exposure_grid_pct": [10, 25, 50, 75, 95],
        }
        (run_path / "summary.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
        print(json.dumps({"run_dir": str(run_path), **result}, indent=2))


if __name__ == "__main__":
    try:
        main()
    except (RuntimeError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(2)
