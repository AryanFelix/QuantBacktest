"""Rank excluded corporate-action names without claiming their returns are valid."""

from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "work"))
import backtest_stock_momentum as stock


def main() -> None:
    bars, tri, _ = stock.load_prices()
    etf = pd.read_csv(
        stock.DATA / "etf_daily" / "NSE_EQ_INF204KB14I2-days-1-2014-01-01-2026-10-23.csv",
        parse_dates=["time"],
    )
    etf["date"] = pd.to_datetime(etf["time"]).dt.tz_localize(None).dt.normalize()
    etf = etf.drop_duplicates("date").set_index("date").sort_index()
    market = etf["close"].astype(float)
    market_sma = market.rolling(200, min_periods=200).mean()
    market_dates = pd.DatetimeIndex(sorted(set().union(*(set(frame.index) for frame in bars.values()))))
    returns = {symbol: tri[symbol].dropna() for symbol in tri.columns}
    trend = {symbol: series.rolling(200, min_periods=200).mean() for symbol, series in returns.items()}

    action_events: dict[str, list[tuple[str, pd.Timestamp]]] = {}
    action_feed = json.loads((stock.SOURCE / "nse_corporate_actions_2000_2026.json").read_text(encoding="utf-8"))
    action_terms = ("rights", "demerger", "merger", "bonus", "split", "sub-division", "amalgamation", "scheme")
    for source_symbol, records in action_feed["responses"].items():
        symbol = stock.ALIASES.get(source_symbol, source_symbol)
        for record in records:
            subject = record.get("subject") or ""
            ex_date = record.get("exDate") or ""
            if not ex_date or ex_date == "-" or not any(term in subject.lower() for term in action_terms):
                continue
            event_date = pd.Timestamp(datetime.strptime(ex_date, "%d-%b-%Y").date())
            action_events.setdefault(symbol, []).append((f"NSE:{ex_date}:{subject}", event_date))
    for event in stock.read_csv(stock.OUT / "corporate_action_entitlements.csv"):
        source = stock.ALIASES.get(event["source_symbol"], event["source_symbol"])
        event_date = event["ex_date"] or event["scheme_effective_date"]
        if event_date:
            action_events.setdefault(source, []).append((f"entitlement:{event['event_id']}", pd.Timestamp(event_date)))

    snapshots = stock.read_csv(stock.SOURCE / "nifty50_monthly_universe_2020_2026.csv")
    execution_dates = []
    for snapshot in snapshots:
        signal_date = pd.Timestamp(snapshot["signal_date"])
        position = market_dates.searchsorted(signal_date, side="right")
        execution_dates.append(market_dates[position] if position < len(market_dates) else None)

    rows = []
    for snapshot_index, snapshot in enumerate(snapshots):
        signal_date = pd.Timestamp(snapshot["signal_date"])
        execution_date = execution_dates[snapshot_index]
        if execution_date is None:
            continue
        next_execution = next((date for date in execution_dates[snapshot_index + 1:] if date is not None), market_dates[-1])
        members = [stock.ALIASES.get(symbol, symbol) for symbol in snapshot["members"].split(";")]
        market_ok = bool(market.get(signal_date, float("nan")) > market_sma.get(signal_date, float("nan")))
        candidates = []
        for symbol in members:
            if symbol not in returns:
                continue
            series = returns[symbol]
            pos = series.index.get_indexer([signal_date])[0]
            if pos < 252:
                continue
            momentum = float(series.iloc[pos - 21] / series.iloc[pos - 252] - 1.0) * 100
            average = trend[symbol].loc[signal_date]
            above_200 = bool(series.iloc[pos] > average) if pd.notna(average) else False
            candidates.append({"symbol": symbol, "momentum": momentum, "above_200": above_200})

        for strategy, rules in stock.STRATEGIES.items():
            eligible = [
                item for item in candidates
                if item["momentum"] > 0 and (item["above_200"] or not rules["trend_filter"])
            ]
            if rules.get("market_filter") and not market_ok:
                eligible = []
            eligible.sort(key=lambda item: (-item["momentum"], item["symbol"]))
            for rank, item in enumerate(eligible[: rules["top_k"]], 1):
                symbol = item["symbol"]
                if symbol not in stock.ACTION_EXCLUSIONS:
                    continue
                symbol_returns = returns[symbol]
                symbol_pos = symbol_returns.index.get_loc(signal_date)
                momentum_start = symbol_returns.index[symbol_pos - 252]
                momentum_end = symbol_returns.index[symbol_pos - 21]
                trend_start = symbol_returns.index[max(0, symbol_pos - 199)]
                events = action_events.get(symbol, [])
                momentum_events = [event_id for event_id, dt in events if momentum_start <= dt <= momentum_end]
                trend_events = [event_id for event_id, dt in events if trend_start <= dt <= signal_date]
                holding_events = [event_id for event_id, dt in events if execution_date <= dt <= next_execution]
                rows.append({
                    "strategy": strategy,
                    "signal_date": signal_date.date().isoformat(),
                    "execution_date": execution_date.date().isoformat(),
                    "symbol": symbol,
                    "raw_candidate_rank": rank,
                    "top_k": rules["top_k"],
                    "dividend_adjusted_12_1_momentum_pct": round(item["momentum"], 6),
                    "above_200dma_using_cached_price_history": item["above_200"],
                    "market_filter_passed": market_ok,
                    "eligible_count_including_excluded_names": len(eligible),
                    "saved_nondividend_action_events_during_next_holding_interval": ";".join(sorted(set(holding_events))),
                    "saved_nondividend_action_events_in_12_1_window": ";".join(sorted(set(momentum_events))),
                    "saved_nondividend_action_events_in_200dma_window": ";".join(sorted(set(trend_events))),
                })

    assert rows and all(row["symbol"] in stock.ACTION_EXCLUSIONS for row in rows)
    fields = list(rows[0])
    stock.atomic_csv(stock.OUT / "stock_action_exclusion_rank_audit.csv", rows, fields)
    summary = {}
    for strategy in stock.STRATEGIES:
        subset = [row for row in rows if row["strategy"] == strategy]
        summary[strategy] = {
            "top_k_slots": len(subset),
            "signal_dates_affected": len({row["signal_date"] for row in subset}),
            "excluded_symbols": sorted({row["symbol"] for row in subset}),
            "slots_overlapping_saved_holding_interval_action_events": sum(bool(row["saved_nondividend_action_events_during_next_holding_interval"]) for row in subset),
            "slots_overlapping_saved_12_1_action_events": sum(bool(row["saved_nondividend_action_events_in_12_1_window"]) for row in subset),
            "slots_overlapping_saved_200dma_action_events": sum(bool(row["saved_nondividend_action_events_in_200dma_window"]) for row in subset),
        }
    print(json.dumps({"candidate_slots": len(rows), "summary": summary}, indent=2))


if __name__ == "__main__":
    main()
