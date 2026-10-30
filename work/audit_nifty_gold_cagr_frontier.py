"""Check two NIFTY/Gold trend mixes against the full-period OHLC drawdown limit."""

from __future__ import annotations

import csv
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "work"))

import audit_etf_intraday_drawdown as audit
import replay_volatility_weighted_blend as blend
import sensitivity_nifty_gold_allocation_ratio as allocation
import upstox_quant as q

CAPITAL = 1_000_000
START = date(2015, 1, 2)
END = date(2026, 10, 23)
SLIPPAGE_BPS = 50
RATIOS = (0.30, 0.50)
CAPS = (0.60, 0.65, 0.70, 0.75, 0.80, 0.85, 0.90, 1.00)
OUTPUT = ROOT / "outputs" / "nifty_gold_ohlc_cagr_frontier.csv"


def main() -> None:
    q._self_check()
    _, panels, portfolios, events = blend.make_portfolios()
    active = portfolios["fixed_50_50"].gt(0).astype(float)
    quarter_events = events["fixed_50_50_quarterly"]
    rows = []

    # shortcut: two established sleeve ratios and seven caps, expand if either is competitive.
    for ratio in RATIOS:
        rule = allocation._rule_id("quarterly", ratio, 1.0)
        targets = allocation._targets(active, ratio)
        for cap in CAPS:
            equity, orders, stats = allocation._measure(
                panels, targets, quarter_events, cap, START, END, SLIPPAGE_BPS
            )
            run_id = f"cagr_frontier/{rule}__cap{int(cap * 100)}__50bps"
            run_path = allocation._save_run(run_id, equity, orders, stats)
            risk = audit.run_case(rule, run_path, CAPITAL, slippage_bps=SLIPPAGE_BPS)
            assert risk["max_close_replay_error_inr"] <= 0.03
            rows.append({
                "rule_id": rule,
                "nifty_share_pct": ratio * 100,
                "gold_share_pct": (1 - ratio) * 100,
                "exposure_cap_pct": cap * 100,
                "period_start": START.isoformat(),
                "period_end": END.isoformat(),
                "slippage_bps_per_side": SLIPPAGE_BPS,
                "ending_balance_inr": stats["ending_balance_inr"],
                "total_return_pct": stats["total_return_pct"],
                "cagr_pct": stats["cagr_pct"],
                "close_max_drawdown_pct": stats["max_drawdown_pct"],
                "ohlc_drawdown_bound_pct": risk["simultaneous_ohlc_drawdown_bound_pct"],
                "within_20pct_ohlc": risk["within_20pct_under_bound"],
                "fees_inr": stats["total_fees_inr"],
                "slippage_cost_inr": stats["total_slippage_inr"],
                "run_artifact": run_path,
            })

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    eligible = [row for row in rows if row["within_20pct_ohlc"]]
    leader = max(eligible, key=lambda row: row["cagr_pct"])
    print(
        f"tested={len(rows)} eligible={len(eligible)} "
        f"leader={leader['rule_id']} cap={leader['exposure_cap_pct']:.0f}% "
        f"CAGR={leader['cagr_pct']:.2f}% "
        f"OHLC={leader['ohlc_drawdown_bound_pct']:.2f}%"
    )


if __name__ == "__main__":
    main()
