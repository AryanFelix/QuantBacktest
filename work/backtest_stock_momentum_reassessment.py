"""Frozen cross-sectional momentum comparison on cached point-in-time NIFTY 50 data."""

from __future__ import annotations

import csv
import json
import math
import re
import sys
from collections import defaultdict
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "work"))
import backtest_stock_momentum as stock

OUT = ROOT / "outputs"
DATA = ROOT / "work" / "data"
START = pd.Timestamp("2021-02-01")
END = pd.Timestamp("2026-10-23")
CAPITAL = 1_000_000
TOP_K = (5, 10, 15)
SIGNALS = ("momentum_6_1", "momentum_12_1", "vol_adjusted_blend_6_12")
CONTROLS = ("full_exposure", "half_exposure_in_stress")
UNIVERSES = ("all_saved", "action_restricted")
SLIPPAGES = (10, 50)
RANK_BUFFER = 2
PERIODS = (
    ("train_2021_2023", pd.Timestamp("2021-02-01"), pd.Timestamp("2023-12-29")),
    ("validation_2024", pd.Timestamp("2024-01-01"), pd.Timestamp("2024-12-31")),
    ("holdout_2025_plus", pd.Timestamp("2025-01-01"), END),
    ("full_2021_2026", START, END),
)
ALIASES = stock.ALIASES
ACTION_RE = re.compile(r"split|bonus|right|merger|demerger|amalgamat|scheme|face value", re.I)


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def risk_state(market_close: pd.Series) -> tuple[pd.Series, pd.Series]:
    returns = market_close.pct_change(fill_method=None)
    vol63 = returns.rolling(63, min_periods=63).std(ddof=1) * math.sqrt(252)
    threshold = vol63.shift(1).rolling(252, min_periods=126).quantile(0.90)
    drawdown126 = market_close / market_close.rolling(126, min_periods=126).max() - 1
    stress = (vol63 > threshold) | (drawdown126 <= -0.10)
    return stress.fillna(False), vol63


def action_intervals(scheduled: dict[pd.Timestamp, dict]) -> list[dict]:
    source = json.loads((DATA / "universe_sources" / "nse_corporate_actions_2000_2026.json").read_text(encoding="utf-8"))
    events: dict[str, list[tuple[pd.Timestamp, str]]] = defaultdict(list)
    for raw_symbol, rows in source["responses"].items():
        symbol = ALIASES.get(raw_symbol, raw_symbol)
        for event in rows:
            subject = str(event.get("subject") or "")
            ex_date = pd.to_datetime(event.get("exDate"), format="%d-%b-%Y", errors="coerce")
            if pd.notna(ex_date) and ACTION_RE.search(subject):
                events[symbol].append((ex_date.normalize(), subject))

    dates = sorted(scheduled)
    flagged = []
    for i, execution_date in enumerate(dates):
        next_execution = dates[i + 1] if i + 1 < len(dates) else END + pd.Timedelta(days=1)
        holding_end = min(next_execution - pd.Timedelta(days=1), END)
        for symbol in scheduled[execution_date]["weights"]:
            for ex_date, subject in events.get(symbol, []):
                if execution_date <= ex_date <= holding_end:
                    flagged.append({
                        "execution_date": execution_date.date().isoformat(),
                        "action_date": ex_date.date().isoformat(), "symbol": symbol, "subject": subject,
                    })
    return flagged


def build_schedules(bars: dict, tri: pd.DataFrame, market_close: pd.Series) -> tuple[dict, dict[str, list[dict]]]:
    memberships = read_rows(DATA / "universe_sources" / "nifty50_monthly_universe_2020_2026.csv")
    market_dates = pd.DatetimeIndex(sorted(set().union(*(set(frame.index) for frame in bars.values()))))
    series = {symbol: tri[symbol].dropna() for symbol in tri.columns}
    returns = {symbol: value.pct_change(fill_method=None) for symbol, value in series.items()}
    trend = {symbol: value.rolling(200, min_periods=200).mean() for symbol, value in series.items()}
    stress, _ = risk_state(market_close)
    keys = [(universe, signal, k, control) for universe in UNIVERSES for signal in SIGNALS for k in TOP_K for control in CONTROLS]
    schedules = {f"{universe}__{signal}_top{k}_{control}_buffer{RANK_BUFFER}": {} for universe, signal, k, control in keys}
    picks: dict[str, list[dict]] = {name: [] for name in schedules}
    previous: dict[tuple[str, str, int], list[str]] = defaultdict(list)

    for snapshot in memberships:
        signal_date = pd.Timestamp(snapshot["signal_date"])
        execution_pos = market_dates.searchsorted(signal_date, side="right")
        if execution_pos >= len(market_dates):
            continue
        execution_date = market_dates[execution_pos]
        if execution_date > END:
            continue
        all_members = [ALIASES.get(value, value) for value in snapshot["members"].split(";")]
        features: dict[str, tuple[float, float, float, bool]] = {}
        for symbol in all_members:
            values = series.get(symbol)
            if values is None:
                continue
            pos = values.index.get_indexer([signal_date])[0]
            if pos < 252:
                continue
            r6 = float(values.iloc[pos - 21] / values.iloc[pos - 126] - 1)
            r12 = float(values.iloc[pos - 21] / values.iloc[pos - 252] - 1)
            daily_vol = returns[symbol].iloc[max(1, pos - 251):pos + 1].std(ddof=1) * math.sqrt(252)
            vol_adjusted = (0.5 * r6 + 0.5 * r12) / float(daily_vol) if pd.notna(daily_vol) and daily_vol > 0 else np.nan
            above_200 = bool(values.iloc[pos] > trend[symbol].iloc[pos]) if pd.notna(trend[symbol].iloc[pos]) else False
            features[symbol] = (r6, r12, vol_adjusted, above_200)

        for universe, signal, k, control in keys:
            name = f"{universe}__{signal}_top{k}_{control}_buffer{RANK_BUFFER}"
            feature_idx = {"momentum_6_1": 0, "momentum_12_1": 1, "vol_adjusted_blend_6_12": 2}[signal]
            members = set(all_members)
            if universe == "action_restricted":
                members.difference_update(stock.ACTION_EXCLUSIONS)
            scores = {symbol: row[feature_idx] for symbol, row in features.items()
                      if symbol in members and pd.notna(row[feature_idx])}
            ranked = sorted((symbol for symbol, score in scores.items() if score > 0), key=lambda symbol: (-scores[symbol], symbol))
            rank = {symbol: i + 1 for i, symbol in enumerate(ranked)}
            prior = previous[(universe, signal, k)]
            keep = [symbol for symbol in prior if rank.get(symbol, math.inf) <= k + RANK_BUFFER]
            selected = keep[:k] + [symbol for symbol in ranked if symbol not in keep][:max(k - len(keep), 0)]
            previous[(universe, signal, k)] = selected
            exposure = 0.5 if control == "half_exposure_in_stress" and bool(stress.get(signal_date, False)) else 1.0
            weights = {symbol: exposure / len(selected) for symbol in selected} if selected else {}
            assert signal_date < execution_date and sum(weights.values()) <= 1.0 + 1e-12
            schedules[name][execution_date] = {"signal_date": signal_date, "weights": weights}
            for position, symbol in enumerate(selected, 1):
                picks[name].append({
                    "strategy": name, "signal_date": signal_date.date().isoformat(),
                    "execution_date": execution_date.date().isoformat(), "rank": rank[symbol],
                    "symbol": symbol, "score": scores[symbol], "momentum_6_1_pct": features[symbol][0] * 100,
                    "momentum_12_1_pct": features[symbol][1] * 100,
                    "above_200dma": features[symbol][3], "exposure_pct": exposure * 100,
                    "weight_pct": weights[symbol] * 100, "eligible_count": len(ranked),
                    "universe_member_count": len(members), "universe_policy": universe,
                })

    for schedule in schedules.values():
        assert all(date_ in schedule for date_ in sorted(schedule))
        assert all(sum(event["weights"].values()) <= 1.0 + 1e-12 for event in schedule.values())
    return schedules, picks


def ohlc_envelope(eq: pd.DataFrame, orders: pd.DataFrame, bars: dict,
                  dividends: dict[tuple[str, pd.Timestamp], float]) -> pd.DataFrame:
    """Conservative envelope; simultaneous asset highs/lows need not be jointly attainable."""
    if orders.empty:
        orders_by_day = {}
    else:
        orders_by_day = {pd.Timestamp(day): frame.to_dict("records") for day, frame in orders.groupby("date")}
    quantities: dict[str, int] = defaultdict(int)
    marks: dict[str, float] = {}
    cash = float(CAPITAL)
    rows = []

    def value(field: str) -> float:
        total = cash
        for symbol, quantity in quantities.items():
            if quantity:
                raw = bars[symbol].at[day, field] if day in bars[symbol].index else np.nan
                price = float(raw) if pd.notna(raw) else marks.get(symbol, 0.0)
                total += quantity * price
        return total

    for day in eq.index:
        for (symbol, ex_date), amount in dividends.items():
            if ex_date == day and quantities[symbol]:
                cash += quantities[symbol] * amount
        pre_values = []
        for field in ("open", "high", "low"):
            pre_values.append(value(field))

        day_orders = orders_by_day.get(day, [])
        is_terminal = lambda row: pd.notna(row.get("terminal_liquidation")) and bool(row["terminal_liquidation"])
        ordinary = [row for row in day_orders if not is_terminal(row)]
        terminal = [row for row in day_orders if is_terminal(row)]
        for row in ordinary:
            symbol, quantity = row["symbol"], int(row["quantity"])
            fee = float(row["total"])
            notional = quantity * float(row["fill_price"])
            if row["side"] == "buy":
                cash -= notional + fee
                quantities[symbol] += quantity
            else:
                cash += notional - fee
                quantities[symbol] -= quantity
        post_values = [value(field) for field in ("open", "high", "low")]
        day_high = max(pre_values[0], pre_values[1], *post_values[:2])
        day_low = min(pre_values[0], pre_values[2], *post_values[::2])

        for symbol, frame in bars.items():
            close = frame.at[day, "close"] if day in frame.index else np.nan
            if pd.notna(close):
                marks[symbol] = float(close)
        if terminal:
            for row in terminal:
                symbol, quantity = row["symbol"], int(row["quantity"])
                cash += quantity * float(row["fill_price"]) - float(row["total"])
                quantities[symbol] -= quantity
        close_nav = cash + sum(quantity * marks.get(symbol, 0.0) for symbol, quantity in quantities.items())
        assert abs(close_nav - float(eq.at[day, "nav"])) < 0.05, (day, close_nav, float(eq.at[day, "nav"]))
        rows.append({"date": day, "ohlc_high_nav": day_high, "ohlc_low_nav": day_low, "close_nav_rebuilt": close_nav})
    result = pd.DataFrame(rows).set_index("date")
    result["running_intraday_peak"] = result["ohlc_high_nav"].cummax().clip(lower=CAPITAL)
    result["ohlc_drawdown_pct"] = result["ohlc_low_nav"] / result["running_intraday_peak"] - 1
    assert result.index.equals(eq.index) and result["ohlc_drawdown_pct"].min() <= 0
    return result


def main() -> None:
    bars, tri, dividends = stock.load_prices()
    etf = pd.read_csv(DATA / "etf_daily" / "NSE_EQ_INF204KB14I2-days-1-2014-01-01-2026-10-23.csv", parse_dates=["time"])
    etf["date"] = etf["time"].dt.tz_localize(None).dt.normalize()
    etf = etf.drop_duplicates("date").set_index("date").sort_index()
    market_close = etf["close"].astype(float)
    schedules, all_picks = build_schedules(bars, tri, market_close)
    benchmark = {
        (row["period"], row["scenario"]): row
        for row in read_rows(OUT / "stock_momentum_benchmark_comparison.csv")
        if row["row_type"] == "official_index"
    }

    rows = []
    for name, schedule in schedules.items():
        action_flags = action_intervals(schedule)
        for slippage in SLIPPAGES:
            equity, orders, stats = stock.simulate(
                name, bars, dividends, schedule, 1.0, slippage, start=START, end=END,
            )
            envelope = ohlc_envelope(equity, orders, bars, dividends)
            for label, period_start, period_end in PERIODS:
                row = stock.period_row(stats, equity, orders, label, period_start, period_end)
                if row is None:
                    continue
                segment = envelope.loc[(envelope.index >= period_start) & (envelope.index <= period_end)]
                bench = benchmark[(label, "NIFTY 50 Total Return")]
                row.update({
                    "strategy": name, "slippage_bps_per_side": slippage,
                    "gross_exposure_cap_pct": 100, "rank_buffer": RANK_BUFFER,
                    "ohlc_drawdown_bound_pct": float(segment["ohlc_drawdown_pct"].min() * 100),
                    "nifty50_tri_cagr_pct": float(bench["cagr_pct"]),
                    "excess_vs_nifty50_tri_cagr_pp": float(row["cagr_pct"]) - float(bench["cagr_pct"]),
                    "action_overlap_count": len(action_flags),
                    "action_overlap_examples": "; ".join(f"{x['symbol']} {x['action_date']} {x['subject']}" for x in action_flags),
                    "universe": "Reconstructed point-in-time NIFTY 50; 70-symbol cached Upstox history; all saved names included" if name.startswith("all_saved") else "Reconstructed point-in-time NIFTY 50; 70-symbol cached history less 13 unresolved rights/merger/demerger names",
                    "source_artifact": "work/backtest_stock_momentum_reassessment.py; outputs/stock_momentum_reassessment_method.md",
                    "selection_or_sizing": f"Monthly {name}; equal-weight top {name.split('_top')[1].split('_')[0]}, two-rank exit buffer; 100% gross exposure with predeclared stress cut where named; next-session-open integer-share execution",
                    "notes": "Dividend-adjusted ranking, candidate dividend cash credit, current modeled cash-delivery charges, and per-side slippage. Historical fees, full corporate-action successor accounting, and executable fills are not complete.",
                })
                rows.append(row)

    rows.sort(key=lambda row: (int(row["slippage_bps_per_side"]), row["strategy"], row["period"]))
    stock.atomic_csv(OUT / "stock_momentum_reassessment_frontier.csv", rows, list(rows[0]))
    pick_rows = [row for values in all_picks.values() for row in values]
    stock.atomic_csv(OUT / "stock_momentum_reassessment_picks.csv", pick_rows, list(pick_rows[0]))

    by_model = {}
    for row in rows:
        if row["slippage_bps_per_side"] == 50 and row["period"] == "train_2021_2023" and row["strategy"].startswith("all_saved__"):
            by_model[row["strategy"]] = row
    training_ranked = sorted((row for row in by_model.values() if row["strategy"].startswith("all_saved__")),
                             key=lambda row: (-float(row["cagr_pct"]), row["strategy"]))
    selected_name = training_ranked[0]["strategy"]
    frozen = [row for row in rows if row["strategy"] == selected_name and row["slippage_bps_per_side"] == 50]
    table = [
        "| Period | CAGR | NIFTY 50 TRI CAGR | Excess | Close MDD | OHLC bound | Fees | Slippage |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in sorted(frozen, key=lambda value: [label for label, _, _ in PERIODS].index(value["period"])):
        table.append(
            f"| {row['period']} | {float(row['cagr_pct']):.2f}% | {float(row['nifty50_tri_cagr_pct']):.2f}% | "
            f"{float(row['excess_vs_nifty50_tri_cagr_pp']):+.2f} pp | {float(row['max_drawdown_pct']):.2f}% | "
            f"{float(row['ohlc_drawdown_bound_pct']):.2f}% | ₹{float(row['fees_inr']):,.0f} | ₹{float(row['slippage_cost_inr']):,.0f} |"
        )
    top = [
        "| Rank | Strategy | Train CAGR | 2024 CAGR | 2025+ CAGR | Full CAGR | Full close / OHLC DD |",
        "|---:|---|---:|---:|---:|---:|---:|",
    ]
    for rank, train in enumerate(training_ranked[:5], 1):
        case = [r for r in rows if r["strategy"] == train["strategy"] and r["slippage_bps_per_side"] == 50]
        lookup = {r["period"]: r for r in case}
        full = lookup["full_2021_2026"]
        top.append(
            f"| {rank} | {train['strategy']} | {float(train['cagr_pct']):.2f}% | "
            f"{float(lookup['validation_2024']['cagr_pct']):.2f}% | {float(lookup['holdout_2025_plus']['cagr_pct']):.2f}% | "
            f"{float(full['cagr_pct']):.2f}% | {float(full['max_drawdown_pct']):.2f}% / {float(full['ohlc_drawdown_bound_pct']):.2f}% |"
        )
    method = f'''# NIFTY 50 cross-sectional momentum reassessment — {date.today().isoformat()}

## Scope and frozen comparison

The earlier restored-universe top-10 12–1 screen returned 12.39% CAGR for 2021–October 2026 at 50 bps per side, and 1.02% in 2025–October 2026. This bounded rerun tests three fixed signals (6–1 return; 12–1 return; equal blend of 6–1 and 12–1 returns divided by trailing annualized volatility), top 5/10/15 names, and two exposure policies. The second policy cuts the risky sleeve to 50% when 63-session NIFTYBEES realized volatility exceeds its prior 252-session 90th percentile or its close is at least 10% below the 126-session high. All cases rebalance monthly, require positive signal momentum, use equal weights, and keep a two-rank exit buffer. Both all-saved and 13-name action-restricted universes are reported; training selection uses only the all-saved universe. No parameters were added after seeing the results.

Point-in-time NIFTY 50 memberships are reconstructed from NSE notices. The cached Upstox daily files cover 70 symbols, not the full NIFTY 500. Stock rankings use dividend-adjusted histories; execution uses cash OHLC, integer shares, next-session opens, the existing modeled cash-delivery fee helper, and 10/50 bps adverse slippage per side. Zero cash yield is assumed. Strategy returns are matched to NIFTY 50 TRI over the same date windows. The currently available 2025–October 2026 period has already been inspected in earlier work and is not a fresh holdout.

The complete candidate matrix and monthly picks are in `stock_momentum_reassessment_frontier.csv` and `stock_momentum_reassessment_picks.csv`. For transparency, the table below ranks all-saved-universe candidates using 2021–2023 training CAGR at 50 bps; later periods remain separate. Action-restricted sensitivity rows are in the frontier CSV.

{chr(10).join(top)}

## Training-only selected candidate

The highest training-CAGR row at 50 bps is `{selected_name}`. Its frozen later-window results are:

{chr(10).join(table)}

This is an exploratory, finite grid rather than evidence of a durable winner. Any discrepancy between its training result and the later windows is evidence against extrapolating the training CAGR. Each full-period rule and the prior 20.72% NIFTY/Gold result are retrospective comparisons across repeatedly inspected data.

## Conservative intraday envelope and action checks

For every strategy/day, the audit marks pre-trade and post-trade holdings at available opens, highs, and lows, then reconciles reconstructed close NAV to the shared simulator. The OHLC drawdown assumes each held asset reaches its high before the combined portfolio reaches its low, which is conservative and not a realizable intraday path. Known NSE split, bonus, rights, merger, demerger, or scheme-action events overlapping planned holding intervals are counted in the CSV. The existing Upstox audit finds split/bonus close continuity consistent with backward unit adjustment, but this is not an API guarantee; merger, demerger, rights, dividend, successor-share, and historical unit coverage are not fully resolved. The action-restricted policy excludes the 13 names already flagged for unresolved rights/merger/demerger paths. Neither policy makes corporate-action accounting complete.

## Reproduction and limits

Run `python work/backtest_stock_momentum_reassessment.py` from the repository root. The script asserts that signal dates precede execution, gross target weights do not exceed 100%, OHLC replay close NAV reconciles to the cash simulator, and the envelope remains non-positive relative to running highs. This is not independent verification: data through 2026-10-23 and earlier result slices have already been inspected. Costs use a current modeled schedule, slippage is assumed rather than measured, cash earns zero, and there is no derivatives financing or margin model.
'''
    (OUT / "stock_momentum_reassessment_method.md").write_text(method, encoding="utf-8")

    ledger_path = OUT / "backtest_summary.csv"
    ledger = read_rows(ledger_path)
    ledger_fields = list(ledger[0])
    ledger = [row for row in ledger if row["simulation_type"] != "stock_cross_sectional_momentum_reassessment"]
    for row in rows:
        row["simulation_type"] = "stock_cross_sectional_momentum_reassessment"
        ledger.append({field: row.get(field, "") for field in ledger_fields})
    stock.atomic_csv(ledger_path, ledger, ledger_fields)

    manifest_path = OUT / "data_manifest.csv"
    manifest = read_rows(manifest_path)
    manifest_fields = list(manifest[0])
    manifest = [row for row in manifest if row["dataset"] != "NIFTY 50 cross-sectional momentum reassessment"]
    manifest.append({
        "dataset": "NIFTY 50 cross-sectional momentum reassessment", "ticker": "70-symbol point-in-time NIFTY 50 sample",
        "instrument_key": "", "bar_interval": "daily marks; monthly signal and rebalance",
        "first_bar": START.date().isoformat(), "last_bar": END.date().isoformat(), "bar_count": str(len(rows)),
        "file_count": "36 fixed models x 2 slippage levels x 4 periods", "empty_files": "0",
        "cache_paths": "work/backtest_stock_momentum_reassessment.py;outputs/stock_momentum_reassessment_frontier.csv;outputs/stock_momentum_reassessment_picks.csv;outputs/stock_momentum_reassessment_method.md",
        "purpose": "Compare finite cross-sectional momentum rules and one predeclared risk control against matched NIFTY 50 TRI",
        "notes": "50 bps/side training ranking; all-saved and action-restricted universe policies; modeled fees and conservative OHLC drawdown; later slices were previously inspected; full corporate-action and execution validation remain incomplete.",
    })
    stock.atomic_csv(manifest_path, manifest, manifest_fields)

    print(json.dumps({
        "strategies": len(schedules), "cases": len(rows), "picks": len(pick_rows),
        "training_selected": selected_name, "training_top5": [row["strategy"] for row in training_ranked[:5]],
        "frozen_rows": [{"period": row["period"], "cagr_pct": row["cagr_pct"], "ohlc_dd_pct": row["ohlc_drawdown_bound_pct"]} for row in frozen],
    }, indent=2))


if __name__ == "__main__":
    main()
