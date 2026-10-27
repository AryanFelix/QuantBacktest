"""Backtest a frozen one-lot NIFTY 50 futures 200-day trend rule."""

from __future__ import annotations

import csv
import json
import os
import tempfile
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "work" / "data"
FUTURES = DATA / "expired" / "nifty50_monthly_futures"
OUT = ROOT / "work" / "backtests" / "nifty50_futures_200dma"
START = date(2024, 10, 1)
END = date(2026, 9, 25)
HOLDOUT_START = date(2026, 1, 2)
CAPITAL = 1_000_000.0


def _atomic_csv(path: Path, rows: list[dict], fields: list[str] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if fields is None:
        fields = list(rows[0]) if rows else []
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", newline="", delete=False, dir=path.parent, suffix=".tmp") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
        temporary = Path(handle.name)
    os.replace(temporary, path)


def _fees(notional: float, side: str, on: date) -> dict[str, float]:
    if side not in {"buy", "sell"} or notional <= 0:
        raise ValueError("A positive notional and buy/sell side are required")
    brokerage = 10.0 if on < date(2026, 1, 1) else min(20.0, notional * 0.0005)
    exchange_rate = 0.0000173 if on < date(2026, 3, 1) else 0.0000183
    stt_rate = 0.0002 if on < date(2026, 4, 1) else 0.0005
    exchange = notional * exchange_rate
    stt = notional * stt_rate if side == "sell" else 0.0
    stamp = notional * 0.00002 if side == "buy" else 0.0
    sebi = notional * 0.000001
    ipft = notional * 0.000000001
    gst = 0.18 * (brokerage + exchange + ipft)
    parts = {"brokerage": brokerage, "stt": stt, "exchange": exchange, "stamp_duty": stamp, "sebi": sebi, "ipft": ipft, "gst": gst}
    parts["total"] = sum(parts.values())
    return parts


def _load_data() -> tuple[pd.DataFrame, dict[date, dict], dict[date, int], list[date], list[dict]]:
    schedule = json.loads((FUTURES / "expiry_schedule.json").read_text(encoding="utf-8"))
    spot_path = DATA / "index_daily" / "NIFTY50-days-1-2014-01-01-2026-10-23.csv"
    spot = pd.read_csv(spot_path)
    spot["date"] = pd.to_datetime(spot["time"].astype(str).str[:10], errors="raise").dt.date
    spot = spot.sort_values("date").drop_duplicates("date").set_index("date")
    spot["sma200"] = spot["close"].rolling(200, min_periods=200).mean()
    spot["signal"] = (spot["close"].shift(1) > spot["sma200"].shift(1)).astype("boolean")
    contracts: dict[date, dict] = {}
    lots: dict[date, int] = {}
    duplicate_audit = []
    for contract in schedule["monthly_contracts"]:
        expiry = date.fromisoformat(contract["expiry"])
        assert contract["candles"] in {"Upstox", "NSE fallback"}
        frame = pd.read_csv(FUTURES / f"{expiry.isoformat()}-daily.csv")
        frame["time_text"] = frame["time"].astype(str)
        frame["date"] = pd.to_datetime(frame["time_text"].str[:10], errors="raise").dt.date
        assert (frame[["open", "close"]] > 0).all().all()
        for day, group in frame.loc[frame["date"].duplicated(keep=False)].groupby("date"):
            assert group[["open", "high", "low"]].nunique().max() == 1, f"Conflicting daily OHLC for {expiry} / {day}"
            selected = group.sort_values("time_text").iloc[0]
            assert selected["time_text"][11:19] == "00:00:00", f"No midnight canonical row for {expiry} / {day}"
            duplicate_audit.append({
                "contract_expiry": expiry.isoformat(), "session_date": day.isoformat(),
                "candidate_count": len(group), "candidate_times": "|".join(group["time_text"].tolist()),
                "candidate_closes": "|".join(str(x) for x in group["close"].tolist()),
                "selected_time": selected["time_text"], "selected_close": float(selected["close"]),
                "nse_crosscheck": "exact OHLC/open interest match" if expiry == date(2025, 1, 30) and day == date(2024, 12, 2) else "not individually checked",
            })
        frame = frame.sort_values(["date", "time_text"]).drop_duplicates("date", keep="first")
        assert not frame["date"].duplicated().any()
        contracts[expiry] = {row.date: {"open": float(row.open), "close": float(row.close)} for row in frame.itertuples()}
        lots[expiry] = int(contract["lot_size"])
    expiries = sorted(contracts)
    assert len(expiries) == 24 and len({lots[e] for e in expiries}) == 3
    return spot, contracts, lots, expiries, duplicate_audit


def _active_contracts(dates: list[date], expiries: list[date]) -> dict[date, date]:
    dates = [day for day in dates if START <= day <= END]
    starts = [START]
    for i in range(1, len(expiries)):
        previous_expiry = expiries[i - 1]
        prior_sessions = [day for day in dates if day < previous_expiry]
        assert prior_sessions, f"No trading session before {previous_expiry}"
        starts.append(max(prior_sessions))
    active = {}
    for day in dates:
        eligible = [i for i, start in enumerate(starts) if start <= day]
        if eligible:
            active[day] = expiries[eligible[-1]]
    assert starts == sorted(starts) and len(active) == len(dates)
    return active


def _simulate(
    spot: pd.DataFrame,
    contracts: dict[date, dict],
    lots: dict[date, int],
    active: dict[date, date],
    start: date,
    end: date,
    slippage_bps: float,
) -> tuple[dict, list[dict], list[dict], list[dict]]:
    dates = [day for day in active if start <= day <= end]
    assert dates and dates[0] >= start and dates[-1] == end
    assert all(day in spot.index and pd.notna(spot.loc[day, "signal"]) for day in dates)
    nav = CAPITAL
    peak = CAPITAL
    held: dict | None = None
    order_rows: list[dict] = []
    trades: list[dict] = []
    daily: list[dict] = []

    def order(on: date, expiry: date, side: str, reason: str, price: float) -> tuple[float, float, dict]:
        notional = price * lots[expiry]
        fee = _fees(notional, side, on)
        slip = notional * slippage_bps / 10_000.0
        order_rows.append({
            "date": on.isoformat(), "contract_expiry": expiry.isoformat(), "side": side.upper(), "reason": reason,
            "reference_price": price, "lot_size": lots[expiry], "notional_inr": notional,
            **{key: fee[key] for key in ("brokerage", "stt", "exchange", "stamp_duty", "sebi", "ipft", "gst")},
            "fees_inr": fee["total"], "slippage_bps_per_side": slippage_bps, "slippage_inr": slip,
        })
        return fee["total"], slip, fee

    for day in dates:
        row = spot.loc[day]
        signal = bool(row["signal"])
        target = active[day] if signal else None
        day_fees = day_slippage = overnight = intraday = 0.0
        closing_reason = None

        if held is not None:
            old_bar = contracts[held["expiry"]].get(day)
            assert old_bar is not None, f"Missing held contract open for {day} / {held['expiry']}"
            overnight = (old_bar["open"] - held["last_close"]) * lots[held["expiry"]]
            held["gross_pnl_inr"] += overnight
            if target != held["expiry"]:
                fee, slip, _ = order(day, held["expiry"], "sell", "signal exit" if target is None else "monthly roll", old_bar["open"])
                held["fees_inr"] += fee
                held["slippage_inr"] += slip
                day_fees += fee
                day_slippage += slip
                held["exit_date"] = day.isoformat()
                held["exit_price"] = old_bar["open"]
                held["exit_reason"] = "signal exit" if target is None else "monthly roll"
                closing_reason = held["exit_reason"]
                trades.append({k: v for k, v in held.items() if k not in {"expiry", "last_close"}})
                held = None

        if target is not None and (held is None or held["expiry"] != target):
            bar = contracts[target].get(day)
            assert bar is not None, f"Missing target contract open for {day} / {target}"
            fee, slip, _ = order(day, target, "buy", "monthly roll" if closing_reason == "monthly roll" else "signal entry", bar["open"])
            held = {
                "expiry": target,
                "contract_expiry": target.isoformat(), "lot_size": lots[target], "entry_date": day.isoformat(),
                "entry_price": bar["open"], "exit_date": "", "exit_price": "", "exit_reason": "",
                "gross_pnl_inr": 0.0, "fees_inr": fee, "slippage_inr": slip,
            }
            day_fees += fee
            day_slippage += slip

        if held is not None:
            bar = contracts[held["expiry"]].get(day)
            assert bar is not None, f"Missing held contract close for {day} / {held['expiry']}"
            intraday = (bar["close"] - bar["open"]) * lots[held["expiry"]]
            held["gross_pnl_inr"] += intraday
            held["last_close"] = bar["close"]

        gross = overnight + intraday
        day_net = gross - day_fees - day_slippage
        nav += day_net
        peak = max(peak, nav)
        close_contract = active[day] if signal else None
        close_price = contracts[close_contract][day]["close"] if close_contract is not None else np.nan
        notional_close = close_price * lots[close_contract] if close_contract is not None else 0.0
        daily.append({
            "date": day.isoformat(), "spot_close": float(row["close"]), "spot_sma200": float(row["sma200"]),
            "signal_long": signal, "contract_expiry": close_contract.isoformat() if close_contract else "",
            "lot_size": lots[close_contract] if close_contract else 0, "futures_close": close_price,
            "overnight_pnl_inr": overnight, "intraday_pnl_inr": intraday, "gross_pnl_inr": gross,
            "fees_inr": day_fees, "slippage_inr": day_slippage, "net_pnl_inr": day_net,
            "equity_inr": nav, "drawdown_pct": (nav / peak - 1.0) * 100.0,
            "notional_close_inr": notional_close, "leverage_on_starting_capital": notional_close / CAPITAL,
            "margin_reserve_30pct_inr": 0.30 * notional_close,
        })

    if held is not None:
        last_day = dates[-1]
        last_bar = contracts[held["expiry"]][last_day]
        fee, slip, _ = order(last_day, held["expiry"], "sell", "terminal close", last_bar["close"])
        held["fees_inr"] += fee
        held["slippage_inr"] += slip
        held["exit_date"] = last_day.isoformat()
        held["exit_price"] = last_bar["close"]
        held["exit_reason"] = "terminal close"
        trades.append({k: v for k, v in held.items() if k not in {"expiry", "last_close"}})
        daily[-1]["fees_inr"] += fee
        daily[-1]["slippage_inr"] += slip
        daily[-1]["net_pnl_inr"] -= fee + slip
        nav -= fee + slip
        daily[-1]["equity_inr"] = nav
        peak = max(peak, nav)
        daily[-1]["drawdown_pct"] = (nav / peak - 1.0) * 100.0

    equity_values = [CAPITAL] + [r["equity_inr"] for r in daily]
    high_water = np.maximum.accumulate(equity_values)
    max_dd = float(np.min((np.asarray(equity_values) / high_water - 1.0) * 100.0))
    duration_years = (dates[-1] - dates[0]).days / 365.25
    total_return = nav / CAPITAL - 1.0
    total_fees = sum(r["fees_inr"] for r in order_rows)
    total_slippage = sum(r["slippage_inr"] for r in order_rows)
    max_margin = max((r["margin_reserve_30pct_inr"] for r in daily), default=0.0)
    min_equity = min(equity_values)
    summary = {
        "strategy": "NIFTY 50 futures long/flat, spot close > SMA200",
        "start": dates[0].isoformat(), "end": dates[-1].isoformat(), "session_count": len(dates),
        "starting_balance_inr": CAPITAL, "ending_balance_inr": nav, "total_return_pct": total_return * 100.0,
        "cagr_pct": ((nav / CAPITAL) ** (1.0 / duration_years) - 1.0) * 100.0 if duration_years > 0 and nav > 0 else np.nan,
        "max_drawdown_pct": max_dd, "within_20pct_drawdown": abs(max_dd) <= 20.0,
        "gross_pnl_inr": sum(r["gross_pnl_inr"] for r in daily), "fees_inr": total_fees,
        "slippage_inr": total_slippage, "slippage_bps_per_side": slippage_bps,
        "round_trip_count": len(trades), "order_count": len(order_rows),
        "win_rate_pct": 100.0 * sum(t["gross_pnl_inr"] - t["fees_inr"] - t["slippage_inr"] > 0 for t in trades) / len(trades) if trades else 0.0,
        "max_notional_inr": max((r["notional_close_inr"] for r in daily), default=0.0),
        "max_leverage_on_starting_capital": max((r["leverage_on_starting_capital"] for r in daily), default=0.0),
        "max_30pct_margin_reserve_inr": max_margin, "max_30pct_margin_reserve_pct_of_starting_capital": 100.0 * max_margin / CAPITAL,
        "stress_margin_covered_by_minimum_equity": max_margin <= min_equity,
        "trade_net_pnl_matches_account_pnl_inr": sum(t["gross_pnl_inr"] - t["fees_inr"] - t["slippage_inr"] for t in trades) - (nav - CAPITAL),
    }
    assert abs(summary["trade_net_pnl_matches_account_pnl_inr"]) < 0.02
    assert summary["fees_inr"] >= 0 and summary["slippage_inr"] >= 0 and all(r["equity_inr"] > 0 for r in daily)
    return summary, daily, order_rows, trades


def self_check() -> None:
    pre = _fees(1_000_000, "sell", date(2026, 2, 28))
    exchange_post = _fees(1_000_000, "sell", date(2026, 3, 1))
    stt_post = _fees(1_000_000, "sell", date(2026, 4, 1))
    assert _fees(1_000_000, "sell", date(2025, 12, 31))["brokerage"] == 10
    assert pre["brokerage"] == 20 and exchange_post["exchange"] > pre["exchange"]
    assert stt_post["stt"] == 500 and pre["stt"] == 200
    assert pre["sebi"] == 1.0
    assert _fees(1_000_000, "buy", date(2026, 4, 1))["stt"] == 0
    assert 0.0 < 0.30 * 25_000 * 75 < CAPITAL


def _write_manifest() -> None:
    manifest_path = ROOT / "outputs" / "data_manifest.csv"
    with manifest_path.open(encoding="utf-8-sig", newline="") as handle:
        existing = list(csv.DictReader(handle))
    fields = list(existing[0])
    artifacts = [
        ("NIFTY 50 futures trend backtest summary", "NIFTY", "1 day", "strategy comparison", "work/backtests/nifty50_futures_200dma/summary.json", "Fixed one-lot SMA200 futures test, dated Upstox fee schedule, capital and drawdown screen."),
        ("NIFTY 50 futures trend sensitivity", "NIFTY", "10/20/50 bps slippage", "strategy sensitivity", "work/backtests/nifty50_futures_200dma/sensitivity.csv", "Fixed slippage scenarios; no parameter selection from returns."),
        ("NIFTY 50 futures trend daily equity", "NIFTY", "1 day", "daily marked-to-market equity", "work/backtests/nifty50_futures_200dma/daily_equity.csv", "2024-10 through 2026-09 full sample and 2026 recent holdout at 10 bps per side."),
        ("NIFTY 50 futures trend orders", "NIFTY", "executed order sides", "fee and slippage ledger", "work/backtests/nifty50_futures_200dma/orders.csv", "Order-level fee components and slippage at reference open/terminal close."),
        ("NIFTY 50 futures trend round trips", "NIFTY", "position cycle", "trade ledger", "work/backtests/nifty50_futures_200dma/trades.csv", "Per-contract gross P&L, fee, slippage, and net P&L."),
        ("NIFTY 50 futures trend pre-registered method", "NIFTY", "method note", "strategy specification", "work/research/nifty50_futures_method.md", "Rule and accounting frozen before P&L calculation."),
        ("Upstox futures duplicate daily candle audit", "NIFTY", "same-session timestamp variants", "source quality audit", "outputs/upstox_futures_daily_duplicate_audit.csv", "Keeps the earliest local timestamp after duplicate OHLC agreement; one session matches official NSE UDiFF."),
    ]
    rows = []
    for dataset, ticker, interval, purpose, path, notes in artifacts:
        rows.append({"dataset": dataset, "ticker": ticker, "instrument_key": "NSE_INDEX|Nifty 50", "bar_interval": interval,
                     "first_bar": START.isoformat(), "last_bar": END.isoformat(), "bar_count": "", "file_count": "1",
                     "empty_files": "0", "cache_paths": path, "purpose": purpose, "notes": notes})
    paths = {r["cache_paths"] for r in rows}
    existing = [r for r in existing if r["cache_paths"] not in paths]
    _atomic_csv(manifest_path, existing + rows, fields)


def _write_backtest_ledger(results: list[dict]) -> None:
    path = ROOT / "outputs" / "backtest_summary.csv"
    with path.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    fields = list(rows[0])
    rows = [r for r in rows if r["strategy"] != "nifty50_futures_200dma"]
    for result in results:
        summary = result["metrics"]
        rows.append({
            "simulation_type": "fixed_rule_backtest", "strategy": "nifty50_futures_200dma", "universe": "NIFTY50_FUT",
            "period": result["period"], "period_start": summary["start"], "period_end": summary["end"],
            "starting_balance_inr": CAPITAL, "ending_balance_inr": summary["ending_balance_inr"],
            "total_return_pct": summary["total_return_pct"], "cagr_pct": summary["cagr_pct"],
            "max_drawdown_pct": summary["max_drawdown_pct"], "sharpe_zero_rf": "", "gross_exposure_cap_pct": "",
            "slippage_bps_per_side": 10, "fees_inr": summary["fees_inr"], "slippage_cost_inr": summary["slippage_inr"],
            "trade_count": summary["round_trip_count"], "order_count": summary["order_count"],
            "within_20pct": summary["within_20pct_drawdown"],
            "selection_or_sizing": "Pre-registered fixed SMA200 rule; one monthly futures lot; 30% notional margin is a stress assumption.",
            "source_artifact": "work/backtests/nifty50_futures_200dma/summary.json",
            "notes": "Daily close marks proxy settlement; 2026 Jan-Sep period starts flat; no historical SPAN/ELM or cash yield modeled.",
        })
    _atomic_csv(path, rows, fields)


def main() -> None:
    self_check()
    spot, contracts, lots, expiries, duplicate_audit = _load_data()
    all_dates = sorted(spot.index)
    active = _active_contracts(all_dates, expiries)
    cases = [("full_2024_10_to_2026_09", START, END), ("holdout_2026_01_to_2026_09", HOLDOUT_START, END)]
    results = []
    base_artifacts = {}
    for period, start, end in cases:
        for bps in (10.0, 20.0, 50.0):
            metrics, daily, orders, trades = _simulate(spot, contracts, lots, active, start, end, bps)
            results.append({"period": period, "slippage_bps_per_side": bps, "metrics": metrics})
            if bps == 10.0:
                base_artifacts[period] = {"daily": daily, "orders": orders, "trades": trades}
    OUT.mkdir(parents=True, exist_ok=True)
    _atomic_csv(OUT / "sensitivity.csv", [{"period": r["period"], "slippage_bps_per_side": r["slippage_bps_per_side"], **r["metrics"]} for r in results])
    _atomic_csv(ROOT / "outputs" / "upstox_futures_daily_duplicate_audit.csv", duplicate_audit)
    for suffix, key in (("daily_equity", "daily"), ("orders", "orders"), ("trades", "trades")):
        rows = [{"period": period, **row} for period, data in base_artifacts.items() for row in data[key]]
        _atomic_csv(OUT / f"{suffix}.csv", rows)
    summary = {
        "method_note": "work/research/nifty50_futures_method.md",
        "data_sources": {"spot": "Upstox NIFTY 50 daily candles", "futures": "Upstox expired futures; December 2024 gap filled by official NSE UDiFF"},
        "fee_source": "https://upstox.com/brokerage-charges/",
        "expiry_source": "https://www.nseindia.com/static/products-services/equity-derivatives-nifty50",
        "scenarios": results,
        "warnings": ["SMA200 parameters were fixed before the run; the short recent period is only a provisional holdout.", "Daily candle closes proxy exchange settlement marks.", "30% of notional is a margin stress assumption, not historical SPAN/ELM.", "One futures lot can exceed the ₹10 lakh cash capital; leverage is reported explicitly."],
    }
    (OUT / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    baseline = [r for r in results if r["slippage_bps_per_side"] == 10.0]
    _write_backtest_ledger(baseline)
    _write_manifest()
    for result in results:
        m = result["metrics"]
        print(f"{result['period']} slippage={result['slippage_bps_per_side']:.0f}bps return={m['total_return_pct']:.2f}% cagr={m['cagr_pct']:.2f}% mdd={m['max_drawdown_pct']:.2f}% fees={m['fees_inr']:.0f} orders={m['order_count']} lots={m['round_trip_count']} dd20={m['within_20pct_drawdown']} margin30_covered={m['stress_margin_covered_by_minimum_equity']}")
    print(f"saved={OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
