"""Compare live HDFC Smallcap 250 ETF rules with official total-return indices."""

from __future__ import annotations

import csv
import json
import sys
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "work"))
import upstox_quant as quant
import audit_etf_intraday_drawdown as audit
import capture_sector_tri_signal_history as capture

ETF = ROOT / "work/data/etf_daily/smallcap_candidates/NSE_EQ_INF179KC1FB2-days-1-2019-01-01-2026-10-23.csv"
NIFTY_TRI = ROOT / "work/data/index_daily/NIFTY50TR-days-1-2014-01-01-2026-10-23.csv"
RAW = ROOT / "work/data/index_daily/smallcap250_tri_2014_2026.json"
PANEL = ROOT / "work/data/index_daily/smallcap250_benchmark_2014_2026.csv"
OUTPUT = ROOT / "outputs/smallcap_etf_cagr_screen.csv"
INDEX_OUTPUT = ROOT / "outputs/smallcap250_index_benchmark_comparison.csv"
INDEX_NAME = "Nifty Smallcap 250"
START = date(2014, 1, 1)
END = date(2026, 10, 23)
CAPITAL = 1_000_000.0
CASES = (("buyhold", 50.0), ("buyhold", 100.0), ("trend200", 50.0), ("trend200", 100.0))


def capture_benchmarks() -> pd.DataFrame:
    values: dict[date, float] = {}
    requests = []
    cursor = START
    while cursor <= END:
        last = min(END, cursor + timedelta(days=364))
        rows = capture._get_rows(INDEX_NAME, cursor, last)
        assert rows, f"No official {INDEX_NAME} TRI for {cursor}..{last}"
        for row in rows:
            assert row["Index Name"].strip().casefold() == INDEX_NAME.casefold()
            day = datetime.strptime(row["Date"], "%d %b %Y").date()
            value = float(row["TotalReturnsIndex"])
            assert cursor <= day <= last and value > 0 and day not in values
            values[day] = value
        requests.append({"from": cursor.isoformat(), "to": last.isoformat(), "rows": rows})
        cursor = last + timedelta(days=1)
        time.sleep(0.15)

    smallcap = pd.Series(values, dtype=float).sort_index()
    smallcap.index = pd.DatetimeIndex(smallcap.index)
    nifty = pd.read_csv(NIFTY_TRI, parse_dates=["date"]).set_index("date")["tri"]
    nifty.index = pd.DatetimeIndex(nifty.index).normalize()
    assert smallcap.index.equals(nifty.index), "Official benchmark calendars must match exactly"
    assert smallcap.index[0].date() == START and smallcap.index[-1].date() == END and len(values) > 3_000
    raw = {"retrieved_at_utc": datetime.now(timezone.utc).isoformat(), "index": INDEX_NAME,
           "source_page": capture.SOURCE_PAGE, "source_route": capture.SOURCE_ROUTE,
           "source_limit": "First-party page-backed historical-data route; full series includes pre-launch backfill.",
           "requests": requests}
    RAW.write_text(json.dumps(raw, indent=2), encoding="utf-8")
    panel = pd.concat([smallcap.rename("Nifty Smallcap 250 TRI"), nifty.rename("Nifty 50 TRI")], axis=1)
    panel.index.name = "date"
    panel.to_csv(PANEL)
    return panel


def main() -> None:
    benchmarks = capture_benchmarks()
    index_rows = []
    for label, start in (("live_since_launch", date(2016, 4, 1)), ("2020_plus", date(2020, 1, 1)),
                         ("2023_plus", date(2023, 1, 1)), ("2025_plus", date(2025, 1, 1))):
        window = benchmarks.loc[pd.Timestamp(start):]
        first, last = window.index[0].date(), window.index[-1].date()
        days = (last - first).days
        for name in benchmarks.columns:
            series = window[name]
            index_rows.append({
                "segment": label, "index": name, "period_start": first.isoformat(),
                "period_end": last.isoformat(), "sessions": len(window),
                "cagr_pct": ((series.iloc[-1] / series.iloc[0]) ** (365.25 / days) - 1) * 100,
                "close_mdd_pct": (series / series.cummax() - 1).min() * 100,
            })
    with INDEX_OUTPUT.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(index_rows[0]))
        writer.writeheader()
        writer.writerows(index_rows)

    frames, panels = quant._read_prices([f"HDFCSML250={ETF}"])
    audit.BARS["HDFCSML250"] = "work/data/etf_daily/smallcap_candidates/NSE_EQ_INF179KC1FB2-days-1-2019-01-01-2026-10-23.csv"
    results = []
    for strategy, slippage in CASES:
        targets, rebalance = quant.make_targets(panels, strategy)
        equity, orders, stats = quant._simulate(
            panels, targets, rebalance, CAPITAL, 1.0, slippage,
            start=date(2023, 1, 1), end=END, drawdown_limit_pct=100,
            fee_product_by_symbol={"HDFCSML250": "equity_fund_delivery"},
        )
        dates = equity.index.tz_localize(None).normalize()
        benchmark = benchmarks.reindex(dates)
        assert dates.equals(benchmark.index) and benchmark.notna().all().all()
        slip = slippage / 10_000
        assert orders["side"].isin({"buy", "sell"}).all() and orders["notional"].gt(0).all()
        slippage_cost = sum(
            row.notional * slip / (1 + slip if row.side == "buy" else 1 - slip)
            for row in orders.itertuples()
        )
        first, last = dates[0].date(), dates[-1].date()
        days = (last - first).days
        case = f"{strategy}_{slippage:g}bps".replace(".", "p")
        relative = Path("work/backtests/smallcap_etf_cagr_screen") / case
        absolute = ROOT / relative
        absolute.mkdir(parents=True, exist_ok=True)
        equity.to_csv(absolute / "equity.csv", index_label="time")
        orders.to_csv(absolute / "orders.csv", index=False)
        bound = audit.run_case(case, relative.as_posix(), slippage_bps=slippage)
        row = {
            "strategy": strategy, "slippage_bps_per_side": slippage,
            "period_start": first.isoformat(), "period_end": last.isoformat(),
            "sessions": len(equity), "ending_balance_inr": stats["ending_balance_inr"],
            "total_return_pct": stats["total_return_pct"],
            "cagr_pct": (stats["ending_balance_inr"] / CAPITAL) ** (365.25 / days) * 100 - 100,
            "close_mdd_pct": stats["max_drawdown_pct"],
            "ohlc_drawdown_bound_pct": bound["simultaneous_ohlc_drawdown_bound_pct"],
            "fees_inr": stats["total_fees_inr"], "slippage_cost_inr": slippage_cost,
            "order_count": stats["order_count"],
        }
        for name in benchmarks.columns:
            series = benchmark[name]
            row[f"{name.lower().replace(' ', '_')}_cagr_pct"] = (
                ((series.iloc[-1] / series.iloc[0]) ** (365.25 / days) - 1) * 100
            )
        assert bound["max_close_replay_error_inr"] <= 0.03
        results.append(row)
    assert len(results) == len(CASES) and all(row["sessions"] > 800 for row in results)
    with OUTPUT.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(results[0]))
        writer.writeheader()
        writer.writerows(results)
    print(f"official_sessions={len(benchmarks)} ETF_sessions={len(frames['HDFCSML250'])} cases={len(results)}")


if __name__ == "__main__":
    main()

