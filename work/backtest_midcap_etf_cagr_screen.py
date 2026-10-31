"""Compare high-exposure MID150BEES cash strategies with matched official TRI."""

from __future__ import annotations

import csv
import sys
from datetime import date
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "work"))
import upstox_quant as quant
import audit_etf_intraday_drawdown as audit

ETF = ROOT / "work/data/etf_daily/MID150BEES-days-1-2019-02-04-2026-10-30.csv"
BENCHMARKS = ROOT / "work/data/index_daily/midcap_etf_benchmark_2019_2026.csv"
OUTPUT = ROOT / "outputs/midcap_etf_cagr_screen.csv"
END = date(2026, 10, 23)
CAPITAL = 1_000_000.0
SLIPPAGE_BPS = 50.0
CASES = (
    ("buyhold", date(2019, 2, 4), 0.95),
    ("buyhold", date(2019, 2, 4), 1.00),
    ("trend200", date(2019, 2, 4), 0.95),
    ("trend200", date(2019, 2, 4), 1.00),
    ("buyhold", date(2021, 1, 1), 0.95),
    ("buyhold", date(2021, 1, 1), 1.00),
    ("trend200", date(2021, 1, 1), 0.95),
    ("trend200", date(2021, 1, 1), 1.00),
    ("trend200", date(2023, 1, 1), 0.95),
    ("trend200", date(2023, 1, 1), 1.00),
)


def main() -> None:
    frames, panels = quant._read_prices([f"MID150BEES={ETF}"])
    tri = pd.read_csv(BENCHMARKS, parse_dates=["date"]).set_index("date")
    audit.BARS["MID150BEES"] = "work/data/etf_daily/MID150BEES-days-1-2019-02-04-2026-10-30.csv"
    results = []
    for strategy, start, exposure in CASES:
        targets, rebalance = quant.make_targets(panels, strategy)
        equity, orders, stats = quant._simulate(
            panels, targets, rebalance, CAPITAL, exposure, SLIPPAGE_BPS,
            start=start, end=END, drawdown_limit_pct=100,
            fee_product_by_symbol={"MID150BEES": "equity_fund_delivery"},
        )
        session_index = equity.index.tz_localize(None)
        first, last = session_index[0].date(), session_index[-1].date()
        benchmark = tri.reindex(session_index)
        assert len(equity) == len(benchmark) and session_index.equals(benchmark.index)
        assert benchmark.notna().all().all(), f"Missing official index marks for {first}..{last}"
        days = (last - first).days
        benchmark_rows = {}
        for index_name in ("Nifty Midcap 150", "Nifty 50"):
            series = benchmark[index_name]
            benchmark_rows[f"{index_name.lower().replace(' ', '_')}_cagr_pct"] = (
                ((series.iloc[-1] / series.iloc[0]) ** (365.25 / days) - 1) * 100
            )
        case_name = f"{strategy}_{first}_{exposure:.2f}".replace(".", "p")
        relative = Path("work/backtests/midcap_etf_cagr_screen") / case_name
        absolute = ROOT / relative
        absolute.mkdir(parents=True, exist_ok=True)
        equity.to_csv(absolute / "equity.csv", index_label="time")
        orders.to_csv(absolute / "orders.csv", index=False)
        bound = audit.run_case(case_name, relative.as_posix(), slippage_bps=SLIPPAGE_BPS)
        strategy_cagr = (stats["ending_balance_inr"] / CAPITAL) ** (365.25 / days) - 1
        assert bound["max_close_replay_error_inr"] <= 0.03
        results.append({
            "strategy": strategy, "target_exposure_pct": exposure * 100,
            "period_start": first.isoformat(), "period_end": last.isoformat(),
            "sessions": len(equity), "cagr_pct": strategy_cagr * 100,
            "total_return_pct": stats["total_return_pct"],
            "ending_balance_inr": stats["ending_balance_inr"],
            "close_mdd_pct": stats["max_drawdown_pct"],
            "ohlc_drawdown_bound_pct": bound["simultaneous_ohlc_drawdown_bound_pct"],
            "fees_inr": stats["total_fees_inr"],
            "order_count": stats["order_count"], **benchmark_rows,
        })
    assert len(results) == len(CASES) and all(row["sessions"] > 500 for row in results)
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(results[0]))
        writer.writeheader()
        writer.writerows(results)
    print(f"cases={len(results)} bars={len(frames['MID150BEES'])} output={OUTPUT.relative_to(ROOT).as_posix()}")


if __name__ == "__main__":
    main()

