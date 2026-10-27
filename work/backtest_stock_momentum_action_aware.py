"""Rerun the fixed post-hoc stock rule with excluded names restored after event audit."""

from __future__ import annotations

import csv
import json
import sys
from datetime import date
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "work"))
import backtest_stock_momentum as stock


STRATEGY = "stock_top10_mom12_1_trend200_market200"
TARGET = f"{STRATEGY}@95%"
PERIODS = (
    ("train_2021_2023", pd.Timestamp("2021-02-01"), pd.Timestamp("2023-12-29")),
    ("validation_2024", pd.Timestamp("2024-01-01"), pd.Timestamp("2024-12-31")),
    ("holdout_2025_plus", pd.Timestamp("2025-01-01"), pd.Timestamp("2026-10-23")),
    ("full_2021_2026", pd.Timestamp("2021-02-01"), pd.Timestamp("2026-10-23")),
)
SLIPPAGES = (10, 20, 50)
RUN_DIR = ROOT / "work" / "backtests" / "stock_momentum_action_aware"
OUT = ROOT / "outputs"


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def main() -> None:
    rank_audit = [row for row in read_csv(OUT / "stock_action_exclusion_rank_audit.csv") if row["strategy"] == STRATEGY]
    assert rank_audit and all(not row["saved_nondividend_action_events_during_next_holding_interval"] for row in rank_audit)
    for row in rank_audit:
        for column in ("saved_nondividend_action_events_in_12_1_window", "saved_nondividend_action_events_in_200dma_window"):
            events = row[column]
            if events:
                assert all("split" in event.lower() or "bonus" in event.lower() for event in events.split(";")), (row, column)

    split_check = [
        row for row in read_csv(OUT / "upstox_split_bonus_adjustment_audit.csv")
        if row["symbol"] == "SHRIRAMFIN" and row["ex_date"] == "2025-01-10"
    ]
    assert len(split_check) == 1 and split_check[0]["normalized_share_factor"] == "5"
    assert 0.8 <= float(split_check[0]["observed_close_factor"]) <= 1.2

    bars, tri, dividends = stock.load_prices()
    etf = pd.read_csv(
        stock.DATA / "etf_daily" / "NSE_EQ_INF204KB14I2-days-1-2014-01-01-2026-10-23.csv",
        parse_dates=["time"],
    )
    etf["date"] = pd.to_datetime(etf["time"]).dt.tz_localize(None).dt.normalize()
    etf = etf.drop_duplicates("date").set_index("date").sort_index()

    # This runner changes only the candidate universe for this process; the source screen stays unchanged.
    stock.ACTION_EXCLUSIONS = set()
    targets, picks = stock.build_targets(bars, tri, etf["close"])
    assert TARGET in targets
    chosen_picks = [pick for pick in picks if pick["strategy"] == TARGET]
    assert chosen_picks and any(pick["symbol"] in {
        "ADANIENT", "BHARTIARTL", "GRASIM", "HDFC", "HINDUNILVR", "ITC", "RELIANCE",
        "SHRIRAMFIN", "SIEMENS", "TATACONSUM", "TMPV", "UPL", "VEDL",
    } for pick in chosen_picks)

    RUN_DIR.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(chosen_picks).to_csv(RUN_DIR / "monthly_picks.csv", index=False)
    base_rows = read_csv(OUT / "stock_momentum_screen.csv")
    summary_rows = []
    for slippage in SLIPPAGES:
        equity, orders, stats = stock.simulate(
            TARGET, bars, dividends, targets[TARGET], 0.95, slippage,
            start=stock.START, end=stock.END,
        )
        stats["universe"] = "Point-in-time NIFTY 50; all 13 prior action-source exclusions restored after rank/event audit"
        stats["selection_or_sizing"] = "Post-hoc monthly top-10 positive 12-1 total-return momentum; stock and NIFTYBEES 200DMA gates; 95% exposure; integer shares; next-open execution"
        stats["notes"] = "Saved event feed shows no selected holding interval crossing a known non-dividend action date; signal-window overlaps are limited to the SHRIRAMFIN split, whose Upstox price continuity is empirically consistent with share-unit adjustment. Event-feed completeness is not guaranteed; retrospective screen, not validated stock P&L."
        run_dir = RUN_DIR / f"slippage_{slippage}bps"
        run_dir.mkdir(parents=True, exist_ok=True)
        equity.to_csv(run_dir / "daily_equity.csv")
        orders.to_csv(run_dir / "orders.csv", index=False)
        (run_dir / "summary.json").write_text(json.dumps(stats, indent=2), encoding="utf-8")
        for label, start, end in PERIODS:
            row = stock.period_row(stats, equity, orders, label, start, end)
            if row is None:
                continue
            row.update({
                "simulation_type": "stock_cross_sectional_momentum_action_audit",
                "strategy": f"{TARGET}_full_universe" if slippage == 10 else f"{TARGET}_full_universe_slip{slippage}",
                "universe": stats["universe"],
                "gross_exposure_cap_pct": 95,
                "slippage_bps_per_side": slippage,
                "selection_or_sizing": stats["selection_or_sizing"],
                "source_artifact": "outputs/stock_momentum_action_aware_screen.csv; outputs/stock_action_exclusion_rank_audit.csv; outputs/stock_momentum_action_aware_method.md",
                "notes": stats["notes"],
            })
            base_name = TARGET if slippage == 10 else f"{TARGET}_slip{slippage}"
            baseline = next((item for item in base_rows if item["strategy"] == base_name and item["period"] == label), None)
            row["restricted_universe_return_pct"] = float(baseline["total_return_pct"]) if baseline else ""
            row["return_delta_vs_restricted_pp"] = float(row["total_return_pct"]) - float(baseline["total_return_pct"]) if baseline else ""
            summary_rows.append(row)

    assert len(summary_rows) == len(PERIODS) * len(SLIPPAGES)
    fields = list(summary_rows[0])
    stock.atomic_csv(OUT / "stock_momentum_action_aware_screen.csv", summary_rows, fields)

    money = lambda value: f"₹{float(value):,.0f}"
    table = [
        "| Window | Slip bps/side | Start value | End value | Return | CAGR | Continuous max drawdown | Fees | Slippage | Orders | 20% screen |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|",
    ]
    for row in summary_rows:
        table.append(
            f"| {row['period']} | {row['slippage_bps_per_side']} | {money(row['starting_balance_inr'])} | "
            f"{money(row['ending_balance_inr'])} | {float(row['total_return_pct']):+.2f}% | "
            f"{float(row['cagr_pct']):.2f}% | {float(row['max_drawdown_pct']):.2f}% | "
            f"{money(row['fees_inr'])} | {money(row['slippage_cost_inr'])} | {row['order_count']} | "
            f"{'Pass' if row['within_20pct'] else 'Fail'} |"
        )
    momentum_hits = [row for row in rank_audit if row["saved_nondividend_action_events_in_12_1_window"]]
    trend_hits = [row for row in rank_audit if row["saved_nondividend_action_events_in_200dma_window"]]
    by_case = {(int(row["slippage_bps_per_side"]), row["period"]): row for row in summary_rows}
    full_10 = by_case[(10, "full_2021_2026")]
    recent_10 = by_case[(10, "holdout_2025_plus")]
    full_50 = by_case[(50, "full_2021_2026")]
    recent_50 = by_case[(50, "holdout_2025_plus")]
    method = f'''# Restored-universe NIFTY 50 momentum sensitivity

**Run date:** {date.today().isoformat()}
**Data:** Upstox stock daily bars and dividend notices through 2026-10-23; official NSE HDFC history through 2023-07-12  
**Capital:** ₹10,00,000 at the start of the continuous run  
**Risk screen:** maximum historical drawdown 20%  
**Status:** retrospective sensitivity of the post-hoc stock rule; not a validated winner.

## Frozen strategy and universe change

This reruns the existing post-hoc monthly top-10 strategy: positive 12–1 total-return momentum, stock close above its 200-session average, NIFTYBEES close above its 200-session average, equal weight, integer shares, next-session-open execution, and a 95% gross exposure cap. The prior version permanently excluded 13 names with rights, merger, or demerger source records. This sensitivity restores those names to ranking; it does not change signal, sizing, execution, or rebalance rules.

Before replay, `work/audit_stock_action_exclusion_rank.py` ranked all 13 names without treating their hypothetical ranks as trades. Across the four existing rules it recorded 346 potential top-K slots. For this top-10 market-gated rule, 9 excluded names would occupy 84 of 510 selected stock slots across 51 signal dates; the excluded picks appeared on 48 of those dates. The saved NSE action feed shows no such position crossing a non-dividend action date in the next monthly holding interval. {len(momentum_hits)} candidate slots overlap a saved action date in the 12–1 formation window and {len(trend_hits)} in the stock 200DMA window; all flagged slots concern SHRIRAMFIN's Jan 2025 10-to-2 face-value subdivision. Upstox's observed close around that event is price-continuous and consistent with share-unit adjustment, an empirical inference rather than an API guarantee. The action feed is not known to be complete.

The replay computes returns from cached OHLC and dividend-adjusted price histories. It does not model merger or demerger successor shares, rights subscriptions, or unlisted entitlement marks. The absence of known action events in this rule's selected holding intervals makes the replay a useful universe sensitivity; it does not establish complete action accounting.

## Results

Results include the current NSE/Upstox cash-delivery fee model plus 10/20/50 bps per-side slippage. Windows are slices of one continuous account: validation and recent-period start balances are the prior period's ending NAV. `max_drawdown_pct` preserves the account high-water mark; cash earns 0%.

{chr(10).join(table)}

At 10 bps, restoring the excluded names changed the full-period return from {float(full_10['restricted_universe_return_pct']):+.2f}% to {float(full_10['total_return_pct']):+.2f}% ({float(full_10['return_delta_vs_restricted_pp']):+.2f} pp); the 2025–October 2026 return changed from {float(recent_10['restricted_universe_return_pct']):+.2f}% to {float(recent_10['total_return_pct']):+.2f}%. At 50 bps the full-period return changed from {float(full_50['restricted_universe_return_pct']):+.2f}% to {float(full_50['total_return_pct']):+.2f}%, and the recent return from {float(recent_50['restricted_universe_return_pct']):+.2f}% to {float(recent_50['total_return_pct']):+.2f}%. This sensitivity shows the stock result depends on universe treatment; it does not establish that either variant is reliable.

The market gate itself was added after earlier results were inspected. The train, 2024 validation, and 2025+ slices are retrospective comparisons, not untouched out-of-sample evidence. The existing 20% screen is not a bound on future losses.

## Reproduction and outputs

- Rank diagnostic: `work/audit_stock_action_exclusion_rank.py`; candidate rows: `outputs/stock_action_exclusion_rank_audit.csv`.
- Portfolio replay: `work/backtest_stock_momentum_action_aware.py`; daily equity, orders, and summaries: `work/backtests/stock_momentum_action_aware/`.
- Consolidated 12-row comparison: `outputs/stock_momentum_action_aware_screen.csv`.
'''
    (OUT / "stock_momentum_action_aware_method.md").write_text(method, encoding="utf-8")

    ledger_path = OUT / "backtest_summary.csv"
    ledger = read_csv(ledger_path)
    ledger_fields = list(ledger[0])
    ledger = [row for row in ledger if row["simulation_type"] != "stock_cross_sectional_momentum_action_audit"]
    for row in summary_rows:
        ledger.append({field: row.get(field, "") for field in ledger_fields})
    stock.atomic_csv(ledger_path, ledger, ledger_fields)

    manifest_path = OUT / "data_manifest.csv"
    manifest = read_csv(manifest_path)
    manifest_fields = list(manifest[0])
    manifest = [row for row in manifest if row["dataset"] != "Stock momentum action-exclusion ranking audit" and row["dataset"] != "Stock momentum restored-universe action audit replay"]
    manifest.extend([
        {
            "dataset": "Stock momentum action-exclusion ranking audit", "ticker": "13 previously excluded NIFTY 50 names",
            "instrument_key": "", "bar_interval": "monthly signal ranks", "first_bar": "2021-01-29", "last_bar": "2026-09-30",
            "bar_count": str(len(read_csv(OUT / "stock_action_exclusion_rank_audit.csv"))), "file_count": "1", "empty_files": "0",
            "cache_paths": "work/audit_stock_action_exclusion_rank.py;outputs/stock_action_exclusion_rank_audit.csv;outputs/stock_momentum_action_aware_method.md",
            "purpose": "Measure when unresolved-action source names would enter the four frozen stock momentum candidate lists without calculating their P&L",
            "notes": "Ranks use dividend-adjusted momentum and saved prices; corporate-action treatment is incomplete, so candidate slots are diagnostic only.",
        },
        {
            "dataset": "Stock momentum restored-universe action audit replay", "ticker": "NIFTY 50; stock top-10 momentum with stock/NIFTY 200DMA gates",
            "instrument_key": "", "bar_interval": "daily marks; monthly trades", "first_bar": "2021-02-01", "last_bar": "2026-10-23",
            "bar_count": str(len(summary_rows)), "file_count": "3 slippage levels x 4 periods; daily equity/order ledgers",
            "empty_files": "0", "cache_paths": "work/backtest_stock_momentum_action_aware.py;work/backtests/stock_momentum_action_aware/;outputs/stock_momentum_action_aware_screen.csv;outputs/stock_momentum_action_aware_method.md",
            "purpose": "Compare the post-hoc stock momentum rule with all 13 action-source names restored after a signal/holding-interval event audit",
            "notes": "95% exposure; 10/20/50 bps; no selected holding interval overlaps a saved non-dividend action date; split adjustment remains an empirical inference; event feed is incomplete and results are retrospective.",
        },
    ])
    for row in manifest:
        if row["dataset"] == "Consolidated backtest metric ledger":
            row["bar_count"] = str(len(ledger))
            row["notes"] = "Includes 40 fixed/inverse-vol NIFTY/Gold blend scenarios, 12 restored-universe stock momentum cases, 105 local ETF parameter-stability cases, 140 single-sleeve deployment cases, and six price-only plus six distribution-adjusted NIFTYBEES/GOLDBEES momentum cases; source artifacts and assumptions are linked in the research report."
    stock.atomic_csv(manifest_path, manifest, manifest_fields)
    print(json.dumps({"monthly_pick_rows": len(chosen_picks), "period_rows": len(summary_rows)}, indent=2))


if __name__ == "__main__":
    main()
