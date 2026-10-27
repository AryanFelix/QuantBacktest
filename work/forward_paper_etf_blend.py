"""Fetch new Upstox ETF candles and replay frozen NIFTY/Gold portfolio controls."""

from __future__ import annotations

import json
import re
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pandas as pd

import backtest_passive_mix_drawdown_control as drawdown_control
import replay_volatility_weighted_blend as blend
import upstox_quant as q


ROOT = Path(__file__).resolve().parents[1]
BASE_DATA = ROOT / "work" / "data" / "etf_daily"
STATE = ROOT / "work" / "backtests" / "forward_paper"
INCREMENTAL = ROOT / "work" / "data" / "forward_paper" / "incremental"
SNAPSHOTS = ROOT / "work" / "data" / "forward_paper" / "snapshots"
PROBES = ROOT / "work" / "data" / "api_probes"
OUT = ROOT / "outputs"
PAPER_START = date(2026, 10, 28)
HISTORY_CUTOFF = date(2026, 10, 23)
REQUEST_START = date(2026, 10, 24)
CAPITAL = 1_000_000
EXPOSURE_CAP = 1.0
DRAW_DOWN_LIMIT = 20.0
SLIPPAGE = (10, 50)
INSTRUMENTS = {
    "NIFTYBEES": ("NSE_EQ|INF204KB14I2", "NSE_EQ_INF204KB14I2-days-1-2014-01-01-2026-10-23.csv"),
    "GOLDBEES": ("NSE_EQ|INF204KB17I5", "GOLDBEES-days-1-2014-01-01-2026-10-23.csv"),
}
PORTFOLIOS = {
    "passive_nifty_gold_22_5_each": ("passive_nifty_gold_22_5_each", 1.0),
    "passive_nifty_gold_13_5_31_5": ("passive_nifty_gold_13_5_31_5", 1.0),
    "passive_nifty_gold_18_27": ("passive_nifty_gold_18_27", 1.0),
    "monthly_fixed_50_50_100pct": ("fixed_50_50", 1.0),
    "monthly_fixed_50_50_95pct": ("fixed_50_50", 0.95),
    "quarterly_fixed_50_50_100pct": ("fixed_50_50_quarterly", 1.0),
    "quarterly_fixed_50_50_train_selected_70pct": ("fixed_50_50_quarterly", 0.70),
    "quarterly_fixed_50_50_train_selected_40pct_buffer": ("fixed_50_50_quarterly", 0.40),
    "quarterly_inverse_vol_63d_100pct": ("inverse_vol_63d_quarterly", 1.0),
    "quarterly_inverse_vol_63d_single65_100pct": ("inverse_vol_63d_quarterly_single65", 1.0),
    "quarterly_inverse_vol_63d_single65_vol16_100pct": ("inverse_vol_63d_quarterly_single65_vol16", 1.0),
    "quarterly_inverse_vol_63d_single80_vol16_100pct": ("inverse_vol_63d_quarterly_single80_vol16", 1.0),
    "passive_drawdown_8pct_cut_60_to_30": ("drawdown_control_8", 1.0),
    "passive_drawdown_10pct_cut_60_to_30": ("drawdown_control_10", 1.0),
    "passive_drawdown_12pct_cut_60_to_30": ("drawdown_control_12", 1.0),
}
DRAWDOWN_THRESHOLDS = {
    "passive_drawdown_8pct_cut_60_to_30": 8.0,
    "passive_drawdown_10pct_cut_60_to_30": 10.0,
    "passive_drawdown_12pct_cut_60_to_30": 12.0,
}
LEDGER = OUT / "forward_paper_ledger.csv"
EQUITY = OUT / "forward_paper_equity.csv"
ORDERS = OUT / "forward_paper_orders.csv"
CONFIG = STATE / "frozen_config_v9.json"
PRIOR_CONFIG = STATE / "frozen_config_v8.json"
STATUS = STATE / "latest_status.json"
CONFIG_VALUE = {
    "freeze_revision": 9,
    "freeze_date": "2026-10-27",
    "amendment": "Preserves all 13 revision-8 paths and adds two no-rebalance passive NIFTY/Gold initial-composition challengers at the same 45% initial exposure: 13.5%/31.5% NAV and 18%/27% NAV. These ratios were chosen after inspecting the full historical composition frontier; 30/70's OHLC result is only 0.07 percentage points inside the 20% screen. They are explicitly post-hoc shadow challengers, not validated selections. Frozen before the first post-freeze paper session; paper execution begins 2026-10-28.",
    "history_cutoff": HISTORY_CUTOFF.isoformat(),
    "paper_start": PAPER_START.isoformat(),
    "capital_inr": CAPITAL,
    "gross_exposure_cap_pct": EXPOSURE_CAP * 100,
    "max_drawdown_alert_pct": DRAW_DOWN_LIMIT,
    "slippage_bps_per_side": list(SLIPPAGE),
    "portfolios": {
        "passive_nifty_gold_22_5_each": "Buy 22.5% NAV of NIFTYBEES and 22.5% NAV of GOLDBEES at the first paper-session next-open fill; hold the units without rebalancing; initial gross exposure 45%, allowed cap 100% as exposure drifts",
        "passive_nifty_gold_13_5_31_5": "Post-hoc composition challenger: buy 13.5% NAV of NIFTYBEES and 31.5% NAV of GOLDBEES at the first paper-session next-open fill; hold units without rebalancing; initial gross exposure 45%, allowed cap 100% as exposure drifts",
        "passive_nifty_gold_18_27": "Post-hoc composition challenger: buy 18% NAV of NIFTYBEES and 27% NAV of GOLDBEES at the first paper-session next-open fill; hold units without rebalancing; initial gross exposure 45%, allowed cap 100% as exposure drifts",
        "passive_drawdown_8pct_cut_60_to_30": "Start at 60% gross exposure in equal NIFTYBEES and GOLDBEES; after close NAV drawdown reaches 8%, cut to 30% at the next open; recover at -4% close drawdown, at the next open",
        "passive_drawdown_10pct_cut_60_to_30": "Start at 60% gross exposure in equal NIFTYBEES and GOLDBEES; after close NAV drawdown reaches 10%, cut to 30% at the next open; recover at -5% close drawdown, at the next open",
        "passive_drawdown_12pct_cut_60_to_30": "Start at 60% gross exposure in equal NIFTYBEES and GOLDBEES; after close NAV drawdown reaches 12%, cut to 30% at the next open; recover at -6% close drawdown, at the next open",
        "monthly_fixed_50_50_100pct": "50% NIFTYBEES Donchian 55/20 + 50% GOLDBEES SMA200; signal changes and month-end; next-session open; 100% gross cap",
        "monthly_fixed_50_50_95pct": "same monthly fixed sleeves and weights; 95% gross cap provides a cash-buffer control",
        "quarterly_fixed_50_50_100pct": "same sleeves and weights; signal changes and quarter-end; next-session open; 100% gross cap",
        "quarterly_fixed_50_50_train_selected_70pct": "same quarterly fixed 50/50 sleeves; 70% gross exposure cap selected using 2014-2022 training under a 20% daily OHLC screen; next-session open",
        "quarterly_fixed_50_50_train_selected_40pct_buffer": "same quarterly fixed 50/50 sleeves; 40% gross exposure cap selected using 2014-2022 training under a 15% daily OHLC safety buffer; next-session open",
        "quarterly_inverse_vol_63d_100pct": "same active sleeves; inverse 63-session realized-vol split when both active, 50% when one active; signal changes and quarter-end; 100% gross cap",
        "quarterly_inverse_vol_63d_single65_100pct": "same quarterly inverse-vol rule when both sleeves are active; 65% NAV when only one is active; signal changes and quarter-end; 100% gross cap",
        "quarterly_inverse_vol_63d_single65_vol16_100pct": "same quarterly 65% solo-sleeve rule; at signal-change or quarter-end rebalance, scale base weights by min(1, 16% / trailing 63-session annualized volatility of lagged base-portfolio returns); next-session open; 100% gross cap",
        "quarterly_inverse_vol_63d_single80_vol16_100pct": "same quarterly inverse-vol split when both sleeves are active; 80% NAV when one is active; at signal-change or quarter-end rebalance, scale base weights by min(1, 16% / trailing 63-session annualized volatility of the lagged unthrottled 80%-sleeve portfolio); next-session open; 100% gross cap",
    },
    "fees": "current Upstox/NSE delivery schedule; zero cash interest",
    "execution": "paper only; no broker order placement; next-open and fixed-slippage fills are modeled",
}


def _write_if_missing(path: Path, columns: list[str]) -> None:
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        pd.DataFrame(columns=columns).to_csv(path, index=False)
        return
    existing = pd.read_csv(path)
    extras = [column for column in existing.columns if column not in columns]
    for column in columns:
        if column not in existing.columns:
            existing[column] = ""
    existing = existing[columns + extras]
    existing.to_csv(path, index=False)


def _freeze() -> None:
    CONFIG.parent.mkdir(parents=True, exist_ok=True)
    if CONFIG.exists():
        saved = json.loads(CONFIG.read_text(encoding="utf-8"))
        assert saved == CONFIG_VALUE, "Frozen paper rules changed; create an explicit new paper version."
    else:
        if PRIOR_CONFIG.exists():
            prior_status = json.loads(STATUS.read_text(encoding="utf-8"))
            assert prior_status["new_common_sessions"] == 0, "Cannot amend the portfolio set after paper data arrived."
        CONFIG.write_text(json.dumps(CONFIG_VALUE, indent=2), encoding="utf-8")


def _safe_error(exc: Exception) -> str:
    return re.sub(r"(?i)Bearer\s+\S+|UPSTOX_ANALYTICS_TOKEN=\S+", "[REDACTED]", str(exc))[:500]


def _fetch_incremental(today: date) -> list[dict]:
    outcomes = []
    for symbol, (instrument_key, _) in INSTRUMENTS.items():
        path = INCREMENTAL / f"{symbol}.csv"
        outcome = {
            "symbol": symbol,
            "instrument_key": instrument_key,
            "request_start": REQUEST_START.isoformat(),
            "request_end": today.isoformat(),
            "retrieved_at_utc": datetime.now(timezone.utc).isoformat(),
            "token_value_saved": False,
        }
        try:
            fetched = q.fetch_candles(instrument_key, REQUEST_START, today, "days", 1)
            outcome["status"] = "success_with_bars" if not fetched.empty else "success_no_bars"
            outcome["bars_received"] = int(len(fetched))
            if not fetched.empty:
                path.parent.mkdir(parents=True, exist_ok=True)
                prior = pd.read_csv(path) if path.exists() else pd.DataFrame(columns=q.BAR_COLUMNS)
                combined = pd.concat([prior, fetched], ignore_index=True)
                combined["time"] = pd.to_datetime(combined["time"], errors="raise")
                combined = combined.drop_duplicates("time", keep="last").sort_values("time")
                combined.to_csv(path, index=False)
                outcome["cached_incremental_bars"] = int(len(combined))
                outcome["last_bar"] = str(combined["time"].iloc[-1])
        except Exception as exc:
            outcome["status"] = "request_error"
            outcome["error"] = _safe_error(exc)
        outcomes.append(outcome)
    PROBES.mkdir(parents=True, exist_ok=True)
    probe = {
        "retrieved_at_utc": datetime.now(timezone.utc).isoformat(),
        "request_window": [REQUEST_START.isoformat(), today.isoformat()],
        "endpoint_family": "Upstox v3 historical candles",
        "results": outcomes,
        "credential_policy": "token is read through the existing secure runner and is never serialized",
    }
    with (PROBES / "forward_paper_history.jsonl").open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(probe) + "\n")
    (PROBES / "forward_paper_latest.json").write_text(json.dumps(probe, indent=2), encoding="utf-8")
    return outcomes


def _build_snapshots() -> list[str]:
    SNAPSHOTS.mkdir(parents=True, exist_ok=True)
    specs = []
    for symbol, (_, base_name) in INSTRUMENTS.items():
        base = pd.read_csv(BASE_DATA / base_name)
        incremental_path = INCREMENTAL / f"{symbol}.csv"
        if incremental_path.exists():
            incremental = pd.read_csv(incremental_path)
            base = pd.concat([base, incremental], ignore_index=True)
        snapshot = base.drop_duplicates("time", keep="last").sort_values("time")
        path = SNAPSHOTS / f"{symbol}.csv"
        snapshot.to_csv(path, index=False)
        specs.append(f"{symbol}={path}")
    return specs


def _store_latest(path: Path, new: pd.DataFrame, keys: list[str]) -> None:
    if path.exists():
        old = pd.read_csv(path)
        new = pd.concat([old, new], ignore_index=True)
    if not new.empty:
        new = new.drop_duplicates(keys, keep="last").sort_values(keys)
    new.to_csv(path, index=False)


def main() -> None:
    today = date.today()
    fetch_through = today - timedelta(days=1)
    assert fetch_through < today, "Paper data fetch must exclude the current calendar date"
    _freeze()
    for path, columns in (
        (LEDGER, ["freeze_date", "freeze_revision", "paper_start", "as_of", "observed_sessions", "strategy", "gross_exposure_cap_pct", "slippage_bps_per_side", "starting_balance_inr", "ending_balance_inr", "total_return_pct", "cagr_pct", "max_drawdown_pct", "within_20pct", "order_count", "total_fees_inr", "total_slippage_inr", "average_exposure_pct", "source_status"]),
        (EQUITY, ["strategy", "slippage_bps_per_side", "time", "nav", "risky_exposure", "gross_exposure"]),
        (ORDERS, ["strategy", "slippage_bps_per_side"]),
    ):
        _write_if_missing(path, columns)

    outcomes = _fetch_incremental(fetch_through)
    specs = _build_snapshots()
    _, panels, portfolios, portfolio_events = blend.make_portfolios(specs)
    portfolios["inverse_vol_63d_quarterly_single65"] = blend.single_sleeve_weight_targets(
        portfolios["inverse_vol_63d_quarterly"], 0.65,
    )
    close = panels["close"]
    for passive_name, nifty_weight, gold_weight in (
        ("passive_nifty_gold_22_5_each", 0.225, 0.225),
        ("passive_nifty_gold_13_5_31_5", 0.135, 0.315),
        ("passive_nifty_gold_18_27", 0.18, 0.27),
    ):
        passive_targets = pd.DataFrame(0.0, index=close.index, columns=close.columns)
        passive_targets["NIFTYBEES"] = nifty_weight
        passive_targets["GOLDBEES"] = gold_weight
        passive_events = pd.Series(False, index=close.index, dtype=bool)
        assert (passive_targets.sum(axis=1) - 0.45).abs().lt(1e-12).all() and not passive_events.any()
        portfolios[passive_name] = passive_targets
        portfolio_events[passive_name] = passive_events
    base_returns = (
        close.pct_change(fill_method=None).fillna(0.0)
        * portfolios["inverse_vol_63d_quarterly_single65"].shift(1).fillna(0.0)
    ).sum(axis=1)
    portfolios["inverse_vol_63d_quarterly_single65_vol16"] = blend.trailing_volatility_throttle_targets(
        portfolios["inverse_vol_63d_quarterly_single65"],
        portfolio_events["inverse_vol_63d_quarterly"],
        base_returns,
        0.16,
    )
    portfolios["inverse_vol_63d_quarterly_single80"] = blend.single_sleeve_weight_targets(
        portfolios["inverse_vol_63d_quarterly"], 0.80,
    )
    base_returns80 = (
        close.pct_change(fill_method=None).fillna(0.0)
        * portfolios["inverse_vol_63d_quarterly_single80"].shift(1).fillna(0.0)
    ).sum(axis=1)
    portfolios["inverse_vol_63d_quarterly_single80_vol16"] = blend.trailing_volatility_throttle_targets(
        portfolios["inverse_vol_63d_quarterly_single80"],
        portfolio_events["inverse_vol_63d_quarterly"],
        base_returns80,
        0.16,
    )
    common = close.dropna(subset=["NIFTYBEES", "GOLDBEES"]).index
    paper_sessions = common[common.date >= PAPER_START]
    latest_history = common[-1].date().isoformat()
    new_sessions = len(paper_sessions)
    status = {
        "freeze_date": CONFIG_VALUE["freeze_date"],
        "freeze_revision": CONFIG_VALUE["freeze_revision"],
        "paper_start": PAPER_START.isoformat(),
        "latest_common_history_bar": latest_history,
        "new_common_sessions": int(new_sessions),
        "api_results": outcomes,
    }
    if not new_sessions:
        status["state"] = "waiting_for_first_post_freeze_common_bar"
        STATUS.write_text(json.dumps(status, indent=2), encoding="utf-8")
        print(f"waiting: latest common bar {latest_history}; no post-freeze bars; no performance row created")
        return

    as_of = paper_sessions[-1].date()
    equity_rows, order_frames, ledger_rows = [], [], []
    for strategy, (portfolio_name, exposure_cap) in PORTFOLIOS.items():
        for slip in SLIPPAGE:
            if strategy in DRAWDOWN_THRESHOLDS:
                equity, orders, stats = drawdown_control.simulate(
                    panels, strategy, 0.60, DRAWDOWN_THRESHOLDS[strategy], slip,
                    start=PAPER_START, end=as_of,
                )
            else:
                equity, orders, stats = q._simulate(
                    panels, portfolios[portfolio_name], portfolio_events[portfolio_name],
                    CAPITAL, exposure_cap, slip, "equity_delivery", PAPER_START, as_of,
                    DRAW_DOWN_LIMIT,
                )
            path = equity.reset_index(names="time")
            path.insert(0, "slippage_bps_per_side", slip)
            path.insert(0, "strategy", strategy)
            equity_rows.append(path)
            if not orders.empty:
                orders = orders.copy()
                orders.insert(0, "slippage_bps_per_side", slip)
                orders.insert(0, "strategy", strategy)
                order_frames.append(orders)
            ledger_rows.append({
                "freeze_date": CONFIG_VALUE["freeze_date"],
                "freeze_revision": CONFIG_VALUE["freeze_revision"],
                "paper_start": PAPER_START.isoformat(),
                "as_of": as_of.isoformat(),
                "observed_sessions": int(len(equity)),
                "strategy": strategy,
                "gross_exposure_cap_pct": exposure_cap * 100,
                "slippage_bps_per_side": slip,
                "starting_balance_inr": CAPITAL,
                "ending_balance_inr": stats["ending_balance_inr"],
                "total_return_pct": stats["total_return_pct"],
                "cagr_pct": stats["cagr_pct"] if len(equity) >= 126 else "",
                "max_drawdown_pct": stats["max_drawdown_pct"],
                "within_20pct": stats["within_drawdown_limit"],
                "order_count": stats["order_count"],
                "total_fees_inr": stats["total_fees_inr"],
                "total_slippage_inr": blend.modeled_slippage(orders, panels),
                "average_exposure_pct": stats["average_gross_exposure_pct"],
                "source_status": ";".join(f"{row['symbol']}:{row['status']}" for row in outcomes),
            })
    fresh_ledger = pd.DataFrame(ledger_rows)
    _store_latest(LEDGER, fresh_ledger, ["as_of", "strategy", "slippage_bps_per_side"])
    pd.concat(equity_rows, ignore_index=True).to_csv(EQUITY, index=False)
    pd.concat(order_frames, ignore_index=True).to_csv(ORDERS, index=False) if order_frames else pd.DataFrame(columns=["strategy", "slippage_bps_per_side"]).to_csv(ORDERS, index=False)
    status["state"] = "paper_paths_updated"
    status["as_of"] = as_of.isoformat()
    status["scenarios_updated"] = len(ledger_rows)
    STATUS.write_text(json.dumps(status, indent=2), encoding="utf-8")
    print(f"updated {len(ledger_rows)} paper scenarios through {as_of}; no broker orders placed")


if __name__ == "__main__":
    main()
