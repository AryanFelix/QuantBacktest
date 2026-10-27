"""Backtest a first-candle reversal after a large NIFTY opening gap."""

from __future__ import annotations

import math
import json
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

import upstox_quant as q


ROOT = Path(__file__).resolve().parents[1]
SIGNAL_FILE = ROOT / "work" / "data" / "intraday" / "NSE_INDEX_Nifty_50-minutes-30-2022-01-01-2026-10-23.csv"
TRADE_FILE = ROOT / "work" / "data" / "intraday" / "NSE_EQ_INF204KB14I2-minutes-30-2022-01-01-2026-10-23.csv"
RUN_ROOT = ROOT / "work" / "backtests" / "intraday_gap_fade"
OUTPUT = ROOT / "outputs" / "intraday_gap_fade_sensitivity.csv"
CAPITAL = 1_000_000.0
RISK_FRACTION = 0.005
MAX_EXPOSURE = 1.0
DD_LIMIT = 20.0
GAP_THRESHOLDS = (0.30, 0.50, 0.75)
SLIPPAGE_LEVELS = (10.0, 25.0, 50.0, 100.0)
MODES = ("gap_down_long", "gap_up_short", "both")
PERIODS = (
    ("train_2022_2023", date(2022, 1, 3), date(2023, 12, 29)),
    ("validation_2024", date(2024, 1, 1), date(2024, 12, 31)),
    ("holdout_2025_plus", date(2025, 1, 1), date(2026, 10, 23)),
    ("full_2022_plus", date(2022, 1, 3), date(2026, 10, 23)),
)


def reversal_direction(gap_pct: float, first_open: float, first_close: float, prior_close: float, threshold_pct: float) -> str | None:
    if gap_pct <= -threshold_pct and first_close > first_open and first_close < prior_close:
        return "long"
    if gap_pct >= threshold_pct and first_close < first_open and first_close > prior_close:
        return "short"
    return None


def _sessions(frame: pd.DataFrame) -> dict[date, pd.DataFrame]:
    frame = frame.copy()
    frame["time"] = pd.to_datetime(frame["time"], errors="raise")
    return {day: group.sort_values("time").reset_index(drop=True) for day, group in frame.groupby(frame["time"].dt.date)}


def _fee(quantity: int, price: float, side: str) -> float:
    return q._fee_breakdown(quantity * price, side, "equity_fund_intraday")["total"]


def _quantity(nav: float, direction: str, entry_raw: float, stop: float, slip: float) -> tuple[int, float, float, float]:
    entry_fill = entry_raw * (1 + slip if direction == "long" else 1 - slip)
    stop_fill = stop * (1 - slip if direction == "long" else 1 + slip)
    risk_per_share = entry_fill - stop_fill if direction == "long" else stop_fill - entry_fill
    if risk_per_share <= 0 or entry_fill <= 0:
        return 0, entry_fill, stop_fill, 0.0
    side_in = "buy" if direction == "long" else "sell"
    side_out = "sell" if direction == "long" else "buy"
    quantity = min(math.floor(nav / entry_fill), math.floor(nav * RISK_FRACTION / risk_per_share))
    while quantity > 0:
        entry_fee = _fee(quantity, entry_fill, side_in)
        stop_fee = _fee(quantity, stop_fill, side_out)
        stop_risk = quantity * risk_per_share + entry_fee + stop_fee
        if quantity * entry_fill + entry_fee <= nav and stop_risk <= nav * RISK_FRACTION:
            return quantity, entry_fill, stop_fill, entry_fee
        quantity -= 1
    return 0, entry_fill, stop_fill, 0.0


def _candidate_map(signal: dict[date, pd.DataFrame], trade: dict[date, pd.DataFrame], threshold: float) -> dict[date, dict]:
    common = sorted(set(signal) & set(trade))
    candidates = {}
    for i in range(1, len(common)):
        day, prior = common[i], common[i - 1]
        index_day, stock_day = signal[day], trade[day]
        if len(index_day) != 13 or len(stock_day) != 13 or not index_day["time"].equals(stock_day["time"]):
            continue
        prior_index_close = float(signal[prior].iloc[-1]["close"])
        prior_trade_close = float(trade[prior].iloc[-1]["close"])
        first = index_day.iloc[0]
        gap_pct = 100 * (float(first["open"]) / prior_index_close - 1)
        direction = reversal_direction(gap_pct, float(first["open"]), float(first["close"]), prior_index_close, threshold)
        if direction is None:
            continue
        candidates[day] = {
            "direction": direction,
            "gap_pct": gap_pct,
            "entry_time": stock_day.iloc[1]["time"],
            "entry_raw": float(stock_day.iloc[1]["open"]),
            "stop": float(stock_day.iloc[0]["low"] if direction == "long" else stock_day.iloc[0]["high"]),
            "target": prior_trade_close,
            "bars": stock_day.iloc[1:].reset_index(drop=True),
        }
    return candidates


def _exit_bar(direction: str, bar: pd.Series, stop: float, target: float, last: bool, slip: float) -> tuple[float | None, str | None]:
    open_price, high, low = float(bar["open"]), float(bar["high"]), float(bar["low"])
    if direction == "long":
        if open_price <= stop:
            return open_price * (1 - slip), "stop_gap"
        if open_price >= target:
            return open_price * (1 - slip), "target_gap"
        stop_hit, target_hit = low <= stop, high >= target
        if stop_hit:
            return stop * (1 - slip), "stop" if not target_hit else "stop_and_target_stop_first"
        if target_hit:
            return target * (1 - slip), "target"
        if last:
            return float(bar["close"]) * (1 - slip), "session_close"
    else:
        if open_price >= stop:
            return open_price * (1 + slip), "stop_gap"
        if open_price <= target:
            return open_price * (1 + slip), "target_gap"
        stop_hit, target_hit = high >= stop, low <= target
        if stop_hit:
            return stop * (1 + slip), "stop" if not target_hit else "stop_and_target_stop_first"
        if target_hit:
            return target * (1 + slip), "target"
        if last:
            return float(bar["close"]) * (1 + slip), "session_close"
    return None, None


def simulate(
    signal: dict[date, pd.DataFrame], trade: dict[date, pd.DataFrame], candidates: dict[date, dict],
    mode: str, start: date, end: date, slippage_bps: float,
) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    slip = slippage_bps / 10_000
    cash, peak, max_drawdown = CAPITAL, CAPITAL, 0.0
    equity_rows, trades = [], []
    signals_seen = rejected = 0
    total_fees = total_slippage = turnover = 0.0
    exposures = []
    daily_nav = []
    for day in sorted(set(signal) & set(trade)):
        if not start <= day <= end:
            continue
        day_start_cash = cash
        day_min_nav = cash
        candidate = candidates.get(day)
        if candidate and (mode == "both" or candidate["direction"] == ("long" if mode == "gap_down_long" else "short")):
            signals_seen += 1
            direction, stop, target = candidate["direction"], candidate["stop"], candidate["target"]
            entry_raw = candidate["entry_raw"]
            quantity, entry_fill, stop_fill, entry_fee = _quantity(cash, direction, entry_raw, stop, slip)
            target_valid = target > entry_fill if direction == "long" else target < entry_fill
            if quantity <= 0 or not target_valid:
                rejected += 1
            else:
                side_in, side_out = ("buy", "sell") if direction == "long" else ("sell", "buy")
                if direction == "long":
                    cash -= quantity * entry_fill + entry_fee
                else:
                    cash -= entry_fee
                total_fees += entry_fee
                exposures.append(quantity * entry_fill / day_start_cash)
                entry_slippage = quantity * abs(entry_fill - entry_raw)
                turnover += quantity * entry_fill
                peak = max(peak, day_start_cash)
                exit_fill = None
                exit_reason = ""
                exit_time = None
                exit_raw = None
                for bar_i, bar in candidate["bars"].iterrows():
                    exit_fill, exit_reason = _exit_bar(direction, bar, stop, target, bar_i == len(candidate["bars"]) - 1, slip)
                    if exit_fill is not None and exit_reason.endswith("_gap"):
                        exit_fee = _fee(quantity, exit_fill, side_out)
                        gap_nav = (
                            cash + quantity * exit_fill - exit_fee if direction == "long"
                            else cash + quantity * (entry_fill - exit_fill) - exit_fee
                        )
                        peak = max(peak, gap_nav)
                        day_min_nav = min(day_min_nav, gap_nav)
                        max_drawdown = min(max_drawdown, gap_nav / peak - 1)
                        exit_time, exit_raw = bar["time"], float(bar["open"])
                        break
                    high, low = float(bar["high"]), float(bar["low"])
                    if direction == "long":
                        high_nav, low_nav = cash + quantity * high, cash + quantity * low
                    else:
                        high_nav = cash + quantity * (entry_fill - low)
                        low_nav = cash + quantity * (entry_fill - high)
                    peak = max(peak, high_nav)
                    day_min_nav = min(day_min_nav, low_nav)
                    max_drawdown = min(max_drawdown, low_nav / peak - 1)
                    if exit_fill is not None:
                        exit_time = bar["time"]
                        exit_raw = stop if exit_reason.startswith("stop") else target if exit_reason == "target" else float(bar["close"])
                        break
                if exit_fill is None or exit_time is None:
                    raise ValueError(f"intraday position did not exit on {day}")
                exit_fee = _fee(quantity, exit_fill, side_out)
                if direction == "long":
                    cash += quantity * exit_fill - exit_fee
                    gross_pnl = quantity * (exit_fill - entry_fill)
                else:
                    cash += quantity * (entry_fill - exit_fill) - exit_fee
                    gross_pnl = quantity * (entry_fill - exit_fill)
                total_fees += exit_fee
                exit_slippage = quantity * abs(exit_fill - exit_raw)
                total_slippage += entry_slippage + exit_slippage
                turnover += quantity * exit_fill
                net_pnl = cash - day_start_cash
                trades.append({
                    "date": day.isoformat(), "direction": direction, "gap_pct": candidate["gap_pct"],
                    "entry_time": candidate["entry_time"], "entry_raw": entry_raw, "entry_fill": entry_fill,
                    "exit_time": exit_time, "exit_reason": exit_reason, "exit_raw": exit_raw,
                    "exit_fill": exit_fill, "stop": stop, "target": target, "quantity": quantity,
                    "gross_pnl_inr": gross_pnl, "net_pnl_inr": net_pnl, "fees_inr": entry_fee + exit_fee,
                    "slippage_inr": entry_slippage + exit_slippage, "entry_fee_inr": entry_fee,
                    "exit_fee_inr": exit_fee, "capital_at_risk_inr": day_start_cash * RISK_FRACTION,
                })
        peak = max(peak, cash)
        max_drawdown = min(max_drawdown, day_min_nav / peak - 1, cash / peak - 1)
        daily_nav.append(cash)
        equity_rows.append({"date": day.isoformat(), "nav_close": cash, "intraday_min_nav": day_min_nav, "peak_nav": peak})

    if len(daily_nav) == 0:
        raise ValueError(f"no common intraday sessions in {start}–{end}")
    returns = pd.Series(daily_nav).pct_change().fillna(0.0)
    stdev = float(returns.std(ddof=1)) if len(returns) > 1 else 0.0
    winners = [trade["net_pnl_inr"] for trade in trades if trade["net_pnl_inr"] > 0]
    losers = [-trade["net_pnl_inr"] for trade in trades if trade["net_pnl_inr"] < 0]
    total_return = cash / CAPITAL - 1
    years = max(len(daily_nav) / 252, 1 / 252)
    stats = {
        "starting_balance_inr": CAPITAL, "ending_balance_inr": cash,
        "total_return_pct": total_return * 100,
        "cagr_pct": ((cash / CAPITAL) ** (1 / years) - 1) * 100 if cash > 0 else -100.0,
        "max_drawdown_pct": max_drawdown * 100, "drawdown_limit_pct": DD_LIMIT,
        "within_drawdown_limit": max_drawdown * 100 >= -DD_LIMIT,
        "sharpe_zero_rf": float(returns.mean() / stdev * math.sqrt(252)) if stdev else 0.0,
        "trade_count": len(trades), "order_count": 2 * len(trades),
        "signal_count": signals_seen, "rejected_signals": rejected,
        "win_rate_pct": 100 * len(winners) / len(trades) if trades else 0.0,
        "profit_factor": sum(winners) / sum(losers) if losers else (None if winners else 0.0),
        "turnover_inr": turnover, "total_fees_inr": total_fees, "total_slippage_inr": total_slippage,
        "average_trade_entry_exposure_pct": float(np.mean(exposures) * 100) if exposures else 0.0,
        "period_start": start.isoformat(), "period_end": end.isoformat(),
        "first_session": equity_rows[0]["date"], "last_session": equity_rows[-1]["date"],
        "execution": "signal from first 30-minute index candle; enter NIFTYBEES at second bar open; intraday only",
        "risk": "0.5% of current NAV at modeled stop including entry/stop fees; max gross exposure 100%; no leverage",
        "costs": f"equity intraday fee schedule; {slippage_bps:g} bps adverse slippage per side",
        "limitations": "30-minute OHLC stop/target order is ambiguous; when both touched stop is assumed first; within-bar high is assumed before low for drawdown stress.",
    }
    return pd.DataFrame(equity_rows), pd.DataFrame(trades), stats


def self_check() -> None:
    assert reversal_direction(-0.50, 99.0, 99.5, 100.0, 0.30) == "long"
    assert reversal_direction(0.50, 101.0, 100.5, 100.0, 0.30) == "short"
    assert reversal_direction(-0.50, 99.0, 98.5, 100.0, 0.30) is None
    assert reversal_direction(0.20, 100.2, 100.3, 100.0, 0.30) is None
    assert _quantity(1_000_000, "long", 100.0, 99.0, 0.001)[0] > 0
    assert _quantity(1_000_000, "short", 100.0, 101.0, 0.001)[0] > 0
    bar = pd.Series({"open": 100.0, "high": 102.0, "low": 98.0, "close": 101.0})
    assert _exit_bar("long", bar, 99.0, 101.0, False, 0.001)[1] == "stop_and_target_stop_first"
    assert _exit_bar("short", bar, 101.0, 99.0, False, 0.001)[1] == "stop_and_target_stop_first"
    assert _exit_bar("long", pd.Series({"open": 98.0, "high": 100.0, "low": 97.0, "close": 99.0}), 99.0, 101.0, False, 0.001)[1] == "stop_gap"


def main() -> None:
    self_check()
    signal_frames, _ = q._read_prices([f"NIFTY50={SIGNAL_FILE}"])
    trade_frames, _ = q._read_prices([f"NIFTYBEES={TRADE_FILE}"])
    signal = _sessions(next(iter(signal_frames.values())).reset_index())
    trade = _sessions(next(iter(trade_frames.values())).reset_index())
    common_days = sorted(set(signal) & set(trade))
    aligned_days = [
        day for day in common_days
        if len(signal[day]) == len(trade[day]) == 13 and signal[day]["time"].equals(trade[day]["time"])
    ]
    assert len(aligned_days) > 1_000
    print(f"common_sessions={len(common_days)} complete_aligned_sessions={len(aligned_days)} excluded={len(common_days) - len(aligned_days)}")
    rows = []
    for threshold in GAP_THRESHOLDS:
        candidates = _candidate_map(signal, trade, threshold)
        for mode in MODES:
            for slippage in SLIPPAGE_LEVELS:
                for period, start, end in PERIODS:
                    equity, trades, stats = simulate(signal, trade, candidates, mode, start, end, slippage)
                    run_name = f"{mode}__gap{threshold:.2f}__{period}__{slippage:g}bps"
                    run_dir = RUN_ROOT / run_name
                    run_dir.mkdir(parents=True, exist_ok=True)
                    equity.to_csv(run_dir / "equity.csv", index=False)
                    trades.to_csv(run_dir / "trades.csv", index=False)
                    stats.update({
                        "strategy": "NIFTY opening-gap reversal",
                        "mode": mode,
                        "gap_threshold_pct": threshold,
                        "slippage_bps_per_side": slippage,
                        "source_artifact": f"{run_dir.relative_to(ROOT).as_posix()}/summary.json",
                    })
                    (run_dir / "summary.json").write_text(json.dumps(stats, indent=2), encoding="utf-8")
                    rows.append({
                        "strategy": "NIFTY opening-gap reversal",
                        "mode": mode,
                        "gap_threshold_pct": threshold,
                        "period": period,
                        "period_start": start.isoformat(),
                        "period_end": end.isoformat(),
                        "starting_balance_inr": CAPITAL,
                        "ending_balance_inr": stats["ending_balance_inr"],
                        "total_return_pct": stats["total_return_pct"],
                        "cagr_pct": stats["cagr_pct"],
                        "max_drawdown_pct": stats["max_drawdown_pct"],
                        "sharpe_zero_rf": stats["sharpe_zero_rf"],
                        "within_20pct": stats["within_drawdown_limit"],
                        "slippage_bps_per_side": slippage,
                        "fees_inr": stats["total_fees_inr"],
                        "slippage_cost_inr": stats["total_slippage_inr"],
                        "trade_count": stats["trade_count"],
                        "order_count": stats["order_count"],
                        "signal_count": stats["signal_count"],
                        "rejected_signals": stats["rejected_signals"],
                        "win_rate_pct": stats["win_rate_pct"],
                        "profit_factor": stats["profit_factor"],
                        "source_artifact": f"{run_dir.relative_to(ROOT).as_posix()}/summary.json",
                    })
    expected = len(GAP_THRESHOLDS) * len(MODES) * len(SLIPPAGE_LEVELS) * len(PERIODS)
    assert len(rows) == expected == 144
    keys = [(r["mode"], r["gap_threshold_pct"], r["period"], r["slippage_bps_per_side"]) for r in rows]
    assert len(keys) == len(set(keys))
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(OUTPUT, index=False)
    print(f"cases={len(rows)} thresholds={GAP_THRESHOLDS} modes={MODES} slippage={SLIPPAGE_LEVELS}")


if __name__ == "__main__":
    main()
