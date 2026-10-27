"""Replay one-lot, monthly NIFTY trend credit spreads from expired Upstox bars."""

from __future__ import annotations

import json
import math
import re
import sys
from collections import defaultdict
from datetime import date, datetime
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "work"))
import upstox_quant as q

UNDERLYING = "NSE_INDEX|Nifty 50"
SPOT_PATH = ROOT / "work" / "data" / "index_daily" / "NIFTY50-days-1-2014-01-01-2026-10-23.csv"
CONTRACT_DIR = ROOT / "work" / "data" / "expired"
OUT = ROOT / "outputs" / "monthly_nifty_credit_spread"
START, END = date(2024, 10, 1), date(2026, 9, 30)
TRAIN_END, VALIDATION_END = date(2025, 6, 30), date(2025, 12, 31)
CAPITAL, DD_LIMIT, WIDTH_POINTS, RISK_FRACTION = 1_000_000.0, 20.0, 200.0, 0.02
COSTS_BPS = (25.0, 50.0, 100.0)
FEE_COMPONENTS = q.FEE_COMPONENTS


def spread_mark(long_price: float, short_price: float, width: float) -> float:
    return min(0.0, max(-width, long_price - short_price))


def self_check() -> None:
    assert spread_mark(80, 120, 200) == -40
    assert spread_mark(250, 100, 200) == 0
    assert spread_mark(0, 250, 200) == -200
    assert q._fee_breakdown(100_000, "sell", "options")["stt"] > 0


def trading_sessions() -> tuple[pd.Series, list[date]]:
    bars = pd.read_csv(SPOT_PATH, usecols=["time", "close"])
    bars["time"] = pd.to_datetime(bars["time"], errors="raise")
    bars["session"] = bars["time"].dt.date
    closes = bars.groupby("session")["close"].last().sort_index()
    return closes, list(closes.index)


def cached_expiries() -> list[date]:
    paths = sorted(CONTRACT_DIR.glob("monthly-*-option-contracts.json"))
    expiries = [date.fromisoformat(p.name[len("monthly-") : -len("-option-contracts.json")]) for p in paths]
    selected = [d for d in expiries if START <= d <= END]
    assert len(selected) == 24 and selected == sorted(set(selected)), f"unexpected cached expiry coverage: {selected}"
    return selected


def selected_pair(contracts: list[dict], expiry: date, spot: float, direction: str) -> tuple[dict | None, dict | None, str]:
    listed = [
        c for c in contracts
        if c.get("instrument_type") == direction
        and not c.get("weekly", False)
        and date.fromisoformat(c["expiry"]) == expiry
        and int(c.get("lot_size", 0)) > 0
    ]
    if not listed:
        return None, None, "no non-weekly contracts for signal direction"
    strikes = sorted({float(c["strike_price"]) for c in listed})
    target = spot + WIDTH_POINTS if direction == "CE" else spot - WIDTH_POINTS
    candidates = [s for s in strikes if (s > spot if direction == "CE" else s < spot)]
    if not candidates:
        return None, None, "no listed OTM short strike"
    short_strike = min(candidates, key=lambda s: (abs(s - target), -s if direction == "CE" else s))
    long_strike = short_strike + WIDTH_POINTS if direction == "CE" else short_strike - WIDTH_POINTS
    short = next((c for c in listed if float(c["strike_price"]) == short_strike), None)
    long = next((c for c in listed if float(c["strike_price"]) == long_strike), None)
    if short is None or long is None:
        return None, None, "exact 200-point wing unavailable"
    if (short["instrument_key"] == long["instrument_key"]
            or short["expiry"] != long["expiry"]
            or short["instrument_type"] != long["instrument_type"]
            or int(short["lot_size"]) != int(long["lot_size"])):
        return None, None, "option pair metadata mismatch"
    return short, long, ""


def cached_or_fetch(contract: dict, entry: date, exit_: date) -> tuple[pd.DataFrame, str, Path]:
    safe_key = re.sub(r"[^A-Za-z0-9_-]+", "_", contract["instrument_key"]).strip("_")
    path = CONTRACT_DIR / f"{safe_key}-day-{entry}-{exit_}.csv"
    source = "cache"
    if path.exists():
        bars = pd.read_csv(path, parse_dates=["time"])
    else:
        bars = q.fetch_expired_candles(contract["instrument_key"], entry, exit_, "day")
        path.parent.mkdir(parents=True, exist_ok=True)
        bars.to_csv(path, index=False)
        source = "Upstox API"
    return q._daily_contract_bars(bars), source, path


def prepare_events(closes: pd.Series, sessions: list[date]) -> tuple[list[dict], list[dict], list[dict]]:
    sma200 = closes.rolling(200, min_periods=200).mean()
    events, audit, manifest_rows = [], [], []
    for expiry in cached_expiries():
        expiry_pos = max((i for i, d in enumerate(sessions) if d <= expiry), default=-1)
        signal_pos, exit_pos = expiry_pos - 20, expiry_pos - 5
        row = {"expiry": expiry.isoformat(), "status": "skipped", "reason": "", "signal_date": "", "entry_date": "", "exit_date": ""}
        if signal_pos < 199 or exit_pos <= signal_pos + 1:
            row["reason"] = "insufficient underlying history"
            audit.append(row)
            continue
        signal_date, entry_date, exit_date = sessions[signal_pos], sessions[signal_pos + 1], sessions[exit_pos]
        spot, average = float(closes.iloc[signal_pos]), float(sma200.iloc[signal_pos])
        direction = "PE" if spot >= average else "CE"
        row.update({"signal_date": signal_date.isoformat(), "entry_date": entry_date.isoformat(),
                    "exit_date": exit_date.isoformat(), "direction": direction, "signal_spot": spot,
                    "signal_sma200": average})
        chain_path = CONTRACT_DIR / f"monthly-{expiry}-option-contracts.json"
        contracts = json.loads(chain_path.read_text(encoding="utf-8"))
        short, long, reason = selected_pair(contracts, expiry, spot, direction)
        if reason:
            row["reason"] = reason
            audit.append(row)
            continue
        row.update({"short_strike": float(short["strike_price"]), "long_strike": float(long["strike_price"]),
                    "lot_size": int(short["lot_size"]), "short_key": short["instrument_key"],
                    "long_key": long["instrument_key"], "short_symbol": short.get("trading_symbol", ""),
                    "long_symbol": long.get("trading_symbol", "")})
        loaded = {}
        try:
            for leg, contract in (("short", short), ("long", long)):
                bars, source, path = cached_or_fetch(contract, entry_date, exit_date)
                loaded[leg] = (bars, source, path)
                manifest_rows.append({"dataset": "Upstox expired NIFTY monthly option candles", "ticker": contract.get("trading_symbol", ""),
                                      "instrument_key": contract["instrument_key"], "bar_interval": "1 day",
                                      "first_bar": str(bars.index.min()) if not bars.empty else "",
                                      "last_bar": str(bars.index.max()) if not bars.empty else "",
                                      "bar_count": str(len(bars)), "file_count": "1", "empty_files": "1" if bars.empty else "0",
                                      "cache_paths": path.relative_to(ROOT).as_posix(),
                                      "purpose": "Monthly NIFTY directional credit-spread replay",
                                      "notes": f"Expired Upstox {source} OHLCV/OI; entry {entry_date}, exit {exit_date}."})
        except Exception as exc:
            row["reason"] = f"expired-candle request failed ({type(exc).__name__})"
            audit.append(row)
            continue
        short_bars, short_source, short_path = loaded["short"]
        long_bars, long_source, long_path = loaded["long"]
        if short_bars.empty or long_bars.empty:
            row["reason"] = "one or both expired contracts returned no candles"
            audit.append(row)
            continue
        required = {entry_date, exit_date}
        if not required.issubset(short_bars.index) or not required.issubset(long_bars.index):
            row["reason"] = "missing entry or exit candle"
            audit.append(row)
            continue
        if min(float(short_bars.loc[entry_date, "volume"]), float(long_bars.loc[entry_date, "volume"]),
               float(short_bars.loc[exit_date, "volume"]), float(long_bars.loc[exit_date, "volume"])) <= 0:
            row["reason"] = "zero-volume entry or exit candle"
            audit.append(row)
            continue
        dates = [d for d in sessions if entry_date <= d <= exit_date]
        marks = {}
        stale_sessions = 0
        for contract_bars, leg in ((long_bars, "long"), (short_bars, "short")):
            closes_leg = contract_bars["close"].reindex(dates).ffill()
            if closes_leg.isna().any():
                row["reason"] = "missing mark-to-market candle before first close"
                break
            stale_sessions += int(contract_bars["close"].reindex(dates).isna().sum())
            for field in ("close", "high", "low"):
                series = contract_bars[field].reindex(dates)
                if field != "close":
                    series = series.where(series.notna(), closes_leg)
                else:
                    series = closes_leg
                marks[(leg, field)] = series
        if row["reason"]:
            audit.append(row)
            continue
        entry_mark = float(long_bars.loc[entry_date, "open"] - short_bars.loc[entry_date, "open"])
        if not (-WIDTH_POINTS - 0.01 <= entry_mark <= 0.01):
            row["reason"] = "entry vertical open mark outside width bounds"
            audit.append(row)
            continue
        invalid = [d for d in dates if not (-WIDTH_POINTS - 0.01 <=
                   float(marks[("long", "close")].loc[d] - marks[("short", "close")].loc[d]) <= 0.01)]
        if invalid:
            first = invalid[0]
            mark = float(marks[("long", "close")].loc[first] - marks[("short", "close")].loc[first])
            row["reason"] = f"vertical close mark {mark:.2f} points outside bounds on {first}"
            audit.append(row)
            continue
        entry_open_short = float(short_bars.loc[entry_date, "open"])
        entry_open_long = float(long_bars.loc[entry_date, "open"])
        exit_close_short = float(short_bars.loc[exit_date, "close"])
        exit_close_long = float(long_bars.loc[exit_date, "close"])
        if min(entry_open_short, entry_open_long, exit_close_short, exit_close_long) <= 0:
            row["reason"] = "non-positive entry or exit premium"
            audit.append(row)
            continue
        path = {d: {f"{leg}_{field}": float(marks[(leg, field)].loc[d])
                    for leg in ("long", "short") for field in ("close", "high", "low")} for d in dates}
        event = {"expiry": expiry.isoformat(), "signal_date": signal_date, "entry_date": entry_date,
                 "exit_date": exit_date, "direction": direction, "short_strike": float(short["strike_price"]),
                 "long_strike": float(long["strike_price"]), "lot_size": int(short["lot_size"]),
                 "short_key": short["instrument_key"], "long_key": long["instrument_key"],
                 "short_symbol": short.get("trading_symbol", ""), "long_symbol": long.get("trading_symbol", ""),
                 "width_points": WIDTH_POINTS, "entry_short_open": entry_open_short, "entry_long_open": entry_open_long,
                 "exit_short_close": exit_close_short, "exit_long_close": exit_close_long,
                 "stale_leg_sessions": stale_sessions, "path": path}
        events.append(event)
        row.update({"status": "eligible", "reason": "", "stale_leg_sessions": stale_sessions,
                    "short_bar_count": len(short_bars), "long_bar_count": len(long_bars)})
        audit.append(row)
        print(f"prepared {expiry}: {direction} short {event['short_strike']}/long {event['long_strike']}, "
              f"{entry_date}–{exit_date}; stale leg marks={stale_sessions}", flush=True)
    assert len(audit) == len(cached_expiries())
    return events, audit, manifest_rows


def order_fill(raw_price: float, side: str, slip: float, lot: int) -> tuple[float, float, dict]:
    fill = raw_price * (1 + slip if side == "buy" else 1 - slip)
    slippage = abs(fill - raw_price) * lot
    charges = q._fee_breakdown(fill * lot, side, "options")
    return fill, slippage, charges


def simulate(events: list[dict], sessions: list[date], bps: float, label: str) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, dict]:
    slip = bps / 10_000
    starts = defaultdict(list)
    exits = defaultdict(list)
    for event in events:
        starts[event["entry_date"]].append(event)
        exits[event["exit_date"]].append(event)
    if events:
        dates = [d for d in sessions if min(e["entry_date"] for e in events) <= d <= max(e["exit_date"] for e in events)]
    else:
        dates = []
    cash = CAPITAL
    active: dict[str, dict] = {}
    fees, turnover, slippage_total = defaultdict(float), 0.0, 0.0
    trade_rows, order_rows, equity_rows, skipped = [], [], [], []
    last_nav = CAPITAL
    peak = close_peak = CAPITAL
    close_dd, envelope_dd = 0.0, 0.0
    for day in dates:
        for event in starts[day]:
            risk = event["width_points"] * event["lot_size"]
            open_risk = sum(p["event"]["width_points"] * p["event"]["lot_size"] for p in active.values())
            if risk + open_risk > RISK_FRACTION * last_nav + 1e-8:
                skipped.append({"expiry": event["expiry"], "reason": "gross spread-width risk exceeds 2% of current NAV"})
                continue
            lot = event["lot_size"]
            short_fill, short_slip, short_fee = order_fill(event["entry_short_open"], "sell", slip, lot)
            long_fill, long_slip, long_fee = order_fill(event["entry_long_open"], "buy", slip, lot)
            entry_fee = short_fee["total"] + long_fee["total"]
            entry_credit_net = (short_fill - long_fill) * lot - entry_fee
            if entry_credit_net <= 0:
                skipped.append({"expiry": event["expiry"], "reason": "net entry credit after fees/slippage is non-positive"})
                continue
            cash += (short_fill - long_fill) * lot - entry_fee
            for component in FEE_COMPONENTS:
                fees[component] += short_fee[component] + long_fee[component]
            slippage_total += short_slip + long_slip
            turnover += short_fill * lot + long_fill * lot
            pos = {"event": event, "entry_credit_raw_inr": (event["entry_short_open"] - event["entry_long_open"]) * lot,
                   "entry_credit_net_inr": entry_credit_net, "entry_fees_inr": entry_fee,
                   "entry_slippage_inr": short_slip + long_slip,
                   "entry_short_fill": short_fill, "entry_long_fill": long_fill,
                   "fees_by_component": {c: short_fee[c] + long_fee[c] for c in FEE_COMPONENTS}}
            active[event["expiry"]] = pos
            for symbol, side, raw, fill, order_fee, slip_cost in (
                (event["short_symbol"], "sell", event["entry_short_open"], short_fill, short_fee, short_slip),
                (event["long_symbol"], "buy", event["entry_long_open"], long_fill, long_fee, long_slip)):
                order_rows.append({"period": label, "slippage_bps_per_leg_per_side": bps,
                                   "expiry": event["expiry"], "time": day.isoformat(), "phase": "entry",
                                   "symbol": symbol, "instrument_key": event["short_key"] if side == "sell" else event["long_key"],
                                   "side": side, "quantity": lot, "raw_price": raw, "fill_price": fill,
                                   "notional_inr": fill * lot, "slippage_inr": slip_cost,
                                   **{f"fee_{c}_inr": order_fee[c] for c in FEE_COMPONENTS},
                                   "fee_total_inr": order_fee["total"]})
        favorable_nav, adverse_nav = cash, cash
        close_mark_nav = cash
        for expiry, pos in active.items():
            mark = pos["event"]["path"][day]
            lot = pos["event"]["lot_size"]
            close_mark_nav += lot * spread_mark(mark["long_close"], mark["short_close"], WIDTH_POINTS)
            favorable_nav += lot * spread_mark(mark["long_high"], mark["short_low"], WIDTH_POINTS)
            adverse_nav += lot * spread_mark(mark["long_low"], mark["short_high"], WIDTH_POINTS)
        peak = max(peak, favorable_nav)
        envelope_dd = min(envelope_dd, adverse_nav / peak - 1)
        for event in exits[day]:
            pos = active.pop(event["expiry"], None)
            if pos is None:
                continue
            lot = event["lot_size"]
            long_fill, long_slip, long_fee = order_fill(event["exit_long_close"], "sell", slip, lot)
            short_fill, short_slip, short_fee = order_fill(event["exit_short_close"], "buy", slip, lot)
            exit_fee = long_fee["total"] + short_fee["total"]
            exit_proceeds = (long_fill - short_fill) * lot
            cash += exit_proceeds - exit_fee
            for component in FEE_COMPONENTS:
                fees[component] += long_fee[component] + short_fee[component]
            slippage_total += long_slip + short_slip
            turnover += long_fill * lot + short_fill * lot
            gross_pnl = ((event["entry_short_open"] - event["entry_long_open"])
                         + (event["exit_long_close"] - event["exit_short_close"])) * lot
            net_pnl = gross_pnl - pos["entry_slippage_inr"] - long_slip - short_slip - pos["entry_fees_inr"] - exit_fee
            assert math.isclose(net_pnl, pos["entry_credit_net_inr"] + exit_proceeds - exit_fee, abs_tol=1e-7)
            trade_rows.append({"period": label, "slippage_bps_per_leg_per_side": bps,
                               "expiry": event["expiry"], "signal_date": event["signal_date"].isoformat(),
                               "entry_date": event["entry_date"].isoformat(), "exit_date": day.isoformat(),
                               "direction": event["direction"], "short_strike": event["short_strike"],
                               "long_strike": event["long_strike"], "lot_size": lot,
                               "short_symbol": event["short_symbol"], "long_symbol": event["long_symbol"],
                               "short_key": event["short_key"], "long_key": event["long_key"],
                               "entry_credit_raw_inr": pos["entry_credit_raw_inr"],
                               "entry_credit_net_after_costs_inr": pos["entry_credit_net_inr"],
                               "exit_value_raw_inr": (event["exit_long_close"] - event["exit_short_close"]) * lot,
                               "gross_pnl_before_costs_inr": gross_pnl, "fees_inr": pos["entry_fees_inr"] + exit_fee,
                               "slippage_inr": pos["entry_slippage_inr"] + long_slip + short_slip,
                               "net_pnl_inr": net_pnl, "stale_leg_sessions": event["stale_leg_sessions"]})
            for symbol, side, raw, fill, order_fee, slip_cost in (
                (event["long_symbol"], "sell", event["exit_long_close"], long_fill, long_fee, long_slip),
                (event["short_symbol"], "buy", event["exit_short_close"], short_fill, short_fee, short_slip)):
                order_rows.append({"period": label, "slippage_bps_per_leg_per_side": bps,
                                   "expiry": event["expiry"], "time": day.isoformat(), "phase": "exit",
                                   "symbol": symbol, "instrument_key": event["long_key"] if side == "sell" else event["short_key"],
                                   "side": side, "quantity": lot, "raw_price": raw, "fill_price": fill,
                                   "notional_inr": fill * lot, "slippage_inr": slip_cost,
                                   **{f"fee_{c}_inr": order_fee[c] for c in FEE_COMPONENTS},
                                   "fee_total_inr": order_fee["total"]})
        close_nav = cash
        for pos in active.values():
            mark = pos["event"]["path"][day]
            close_nav += pos["event"]["lot_size"] * spread_mark(mark["long_close"], mark["short_close"], WIDTH_POINTS)
        close_peak = max(close_peak, close_nav)
        close_dd = min(close_dd, close_nav / close_peak - 1)
        last_nav = close_nav
        equity_rows.append({"session": day.isoformat(), "nav": close_nav, "cash": cash,
                            "active_spreads": len(active), "favorable_nav": favorable_nav,
                            "adverse_nav": adverse_nav, "high_water_mark": peak,
                            "close_drawdown_pct": close_dd * 100, "ohlc_envelope_drawdown_pct": envelope_dd * 100})
    assert not active, "a credit spread remained open after its scheduled exit"
    equity = pd.DataFrame(equity_rows)
    trades = pd.DataFrame(trade_rows)
    orders = pd.DataFrame(order_rows)
    if not equity.empty:
        assert math.isclose(float(equity.iloc[-1]["nav"]) - CAPITAL,
                            float(trades["net_pnl_inr"].sum()) if not trades.empty else 0.0, abs_tol=0.02)
        returns = equity["nav"].pct_change().replace([np.inf, -np.inf], np.nan)
        returns = returns.fillna(equity.iloc[0]["nav"] / CAPITAL - 1)
        win = trades.loc[trades["net_pnl_inr"] > 0, "net_pnl_inr"] if not trades.empty else pd.Series(dtype=float)
        loss = -trades.loc[trades["net_pnl_inr"] < 0, "net_pnl_inr"] if not trades.empty else pd.Series(dtype=float)
        stats = {"period": label, "starting_balance_inr": CAPITAL, "ending_balance_inr": float(equity.iloc[-1]["nav"]),
                 "total_return_pct": float((equity.iloc[-1]["nav"] / CAPITAL - 1) * 100),
                 "cagr_pct": float(((equity.iloc[-1]["nav"] / CAPITAL) ** (252 / len(equity)) - 1) * 100)
                 if equity.iloc[-1]["nav"] > 0 else -100.0,
                 "max_close_drawdown_pct": float(close_dd * 100),
                 "max_ohlc_envelope_drawdown_pct": float(envelope_dd * 100),
                 "within_20pct_close_limit": bool(close_dd >= -DD_LIMIT / 100),
                 "within_20pct_ohlc_envelope_limit": bool(envelope_dd >= -DD_LIMIT / 100),
                 "sharpe_zero_rf": float(returns.mean() / returns.std(ddof=1) * math.sqrt(252)) if len(returns) > 1 and returns.std(ddof=1) else 0.0,
                 "trade_count": len(trades), "order_count": len(orders),
                 "win_rate_pct": float(len(win) / len(trades) * 100) if len(trades) else 0.0,
                 "profit_factor": float(win.sum() / loss.sum()) if len(loss) and loss.sum() else (None if len(win) else 0.0),
                 "turnover_inr": float(turnover), "total_fees_inr": float(sum(fees.values())),
                 "total_slippage_inr": float(slippage_total),
                 "fees_by_component_inr": {c: round(v, 2) for c, v in fees.items()},
                 "risk_filter_skips": skipped,
                 "assumptions": {"fee_schedule": "shared current Upstox/NSE options schedule applied uniformly to all history",
                                 "slippage_bps_per_leg_per_side": bps, "cash_yield_pct": 0,
                                 "risk": "one lot per expiry; open gross spread width limited to 2% of prior close NAV",
                                 "margin": "SPAN/ELM and collateral not modelled",
                                 "close_mark": "daily option closes, forward-filled when a leg has no trade",
                                 "ohlc_envelope": "long low/short high adverse; long high/short low favorable; spread bounded to [−width, 0]; favorable extreme precedes adverse"}}
    else:
        stats = {"period": label, "starting_balance_inr": CAPITAL, "ending_balance_inr": CAPITAL,
                 "total_return_pct": 0.0, "max_close_drawdown_pct": 0.0,
                 "max_ohlc_envelope_drawdown_pct": 0.0, "trade_count": 0, "order_count": 0,
                 "total_fees_inr": 0.0, "total_slippage_inr": 0.0, "risk_filter_skips": skipped}
    return equity, trades, orders, stats


def run() -> None:
    self_check()
    closes, sessions = trading_sessions()
    events, audit, manifest_rows = prepare_events(closes, sessions)
    if not events:
        OUT.mkdir(parents=True, exist_ok=True)
        pd.DataFrame(audit).to_csv(OUT / "expiry_audit.csv", index=False)
        raise RuntimeError(f"no eligible option histories; details saved to {OUT / 'expiry_audit.csv'}")
    periods = {"full": (START, END), "train": (START, TRAIN_END),
               "validation": (TRAIN_END + pd.Timedelta(days=1), VALIDATION_END),
               "later_segment": (VALIDATION_END + pd.Timedelta(days=1), END)}
    all_stats, all_equity, all_trades, all_orders = [], {}, {}, {}
    for bps in COSTS_BPS:
        for label, (period_start, period_end) in periods.items():
            sample = [e for e in events if period_start <= e["entry_date"] <= period_end]
            equity, trades, orders, stats = simulate(sample, sessions, bps, label)
            stats["slippage_bps_per_leg_per_side"] = bps
            all_stats.append(stats)
            if bps == 50:
                all_equity[label], all_trades[label], all_orders[label] = equity, trades, orders
            print(f"{label} {bps:g} bps: {stats['trade_count']} trades, "
                  f"net {stats['total_return_pct']:+.2f}%, close DD {stats.get('max_close_drawdown_pct', 0):.2f}%, "
                  f"OHLC envelope {stats.get('max_ohlc_envelope_drawdown_pct', 0):.2f}%", flush=True)
    OUT.mkdir(parents=True, exist_ok=True)
    base_full = next(r for r in all_stats if r["period"] == "full" and r["slippage_bps_per_leg_per_side"] == 50)
    execution_skips = {r["expiry"]: r["reason"] for r in base_full.get("risk_filter_skips", [])}
    for row in audit:
        row["status_at_50bps"] = "executed" if row["status"] == "eligible" and row["expiry"] not in execution_skips else "skipped"
        row["reason_at_50bps"] = execution_skips.get(row["expiry"], row["reason"] if row["status"] != "eligible" else "")
    pd.DataFrame(audit).to_csv(OUT / "expiry_audit.csv", index=False)
    pd.DataFrame(all_stats).to_csv(OUT / "cost_screen.csv", index=False)
    for label, frame in all_equity.items():
        frame.to_csv(OUT / f"equity_{label}_50bps.csv", index=False)
    pd.concat(all_trades.values(), ignore_index=True).to_csv(OUT / "trades_50bps.csv", index=False)
    pd.concat(all_orders.values(), ignore_index=True).to_csv(OUT / "orders_50bps.csv", index=False)
    summary = {"strategy": "monthly NIFTY 200DMA directional credit vertical",
               "method": "work/research/monthly_nifty_credit_spread_method.md",
               "sources": "work/research/monthly_nifty_credit_spread_sources.md",
               "capital_inr": CAPITAL, "drawdown_limit_pct": DD_LIMIT,
               "data_start": START.isoformat(), "data_end": END.isoformat(),
               "underlying_key": UNDERLYING, "cached_expiries": len(audit),
               "eligible_expiries": sum(r["status"] == "eligible" for r in audit),
               "skipped_expiries": [r for r in audit if r["status"] != "eligible"],
               "executed_expiries_at_50bps": sum(r["status_at_50bps"] == "executed" for r in audit),
               "execution_skips_at_50bps": [r for r in audit if r["status"] == "eligible" and r["status_at_50bps"] == "skipped"],
               "fee_schedule_note": "Current shared fee schedule applied uniformly; sell-side options STT is conservative versus pre-2026-04 historical rate.",
               "margin_note": "SPAN/ELM margin, financing, tax and cash yield are not modelled.",
               "mark_note": "OHLC envelope is a mark stress; it does not deduct hypothetical liquidation fees/slippage at each daily extreme.",
               "results": all_stats, "data_cache_not_committed": True,
               "last_underlying_bar": max(sessions).isoformat()}
    (OUT / "summary.json").write_text(json.dumps(summary, indent=2, default=str), encoding="utf-8")
    manifest_rows.append({"dataset": "Monthly NIFTY directional credit-spread replay", "ticker": "NIFTY 50 monthly PE/CE verticals",
                          "instrument_key": UNDERLYING, "bar_interval": "daily option OHLC; monthly entry/exit rules",
                          "first_bar": min(e["entry_date"] for e in events).isoformat(),
                          "last_bar": max(e["exit_date"] for e in events).isoformat(),
                          "bar_count": f"{len(events)} data-eligible expiry pairs; 12 cost/period scenarios",
                          "file_count": "summary + cost screen + expiry audit + 4 equity curves + trade/order ledgers",
                          "empty_files": "0",
                          "cache_paths": "outputs/monthly_nifty_credit_spread;work/backtest_monthly_nifty_credit_spread.py;work/research/monthly_nifty_credit_spread_method.md;work/research/monthly_nifty_credit_spread_sources.md",
                          "purpose": "Compare a fixed 200DMA directional monthly credit vertical after option fees and per-leg slippage",
                          "notes": f"50-bps full-sample net return {base_full['total_return_pct']:.3f}%; current fee rates applied uniformly. Not a live recommendation."})
    manifest_path = ROOT / "outputs" / "data_manifest.csv"
    manifest = pd.read_csv(manifest_path, dtype=str).fillna("")
    if manifest_rows:
        new = pd.DataFrame(manifest_rows).drop_duplicates("cache_paths", keep="last")
        manifest = manifest.loc[~manifest["cache_paths"].isin(new["cache_paths"])]
        manifest = pd.concat([manifest, new[manifest.columns]], ignore_index=True)
        assert manifest["cache_paths"].is_unique
        manifest.to_csv(manifest_path, index=False, encoding="utf-8-sig")
    print(f"outputs={OUT}; eligible={summary['eligible_expiries']}/{summary['cached_expiries']}; "
          f"latest_underlying={summary['last_underlying_bar']}", flush=True)


if __name__ == "__main__":
    run()
