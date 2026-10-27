"""Screen a close-to-next-open India VIX exposure overlay on the NIFTY/Gold blend."""

from __future__ import annotations

import csv
import json
from datetime import date
from pathlib import Path

import pandas as pd

import replay_volatility_weighted_blend as blend
import upstox_quant as q


ROOT = Path(__file__).resolve().parents[1]
RAW_DATA = ROOT / "work" / "data" / "index_daily" / "IndiaVIX-days-1-2014-01-01-2026-10-23.csv"
SOURCE = ROOT / "outputs" / "india_vix_nse_conflict_reconciliation.json"
DATA = ROOT / "work" / "data" / "index_daily" / "IndiaVIX-NSE-reconciled-days-1-2014-01-01-2026-10-23.csv"
OUT = ROOT / "work" / "backtests" / "india_vix_overlay"
CAPITAL = 1_000_000
THRESHOLDS = (15, 20, 25, 30)
NIFTY_RETENTION = (0.0, 0.5)
SLIPPAGE = (10, 50)


def reconcile_vix_data() -> pd.DataFrame:
    raw = pd.read_csv(RAW_DATA)
    raw["session"] = pd.to_datetime(raw["time"]).dt.date
    counts = raw.groupby("session").size()
    conflicted = set(counts[counts > 1].index)
    source = json.loads(SOURCE.read_text(encoding="utf-8"))
    assert source["source_page"] == "https://www.nseindia.com/reports-indices-historical-vix"
    assert len(source["records"]) == 3
    replacements = []
    for item in source["records"]:
        record = item["record"]
        session = pd.to_datetime(record["EOD_TIMESTAMP"], format="%d-%b-%Y").date()
        assert item["status"] == 200 and record["EOD_INDEX_NAME"] == "INDIA VIX" and session in conflicted
        duplicates = raw.loc[raw["session"] == session]
        close = float(record["EOD_CLOSE_INDEX_VAL"])
        assert len(duplicates) == 2 and (duplicates["close"].sub(close).abs() <= 0.00501).any()
        replacements.append({
            "time": f"{session.isoformat()} 00:00:00+05:30",
            "open": record["EOD_OPEN_INDEX_VAL"],
            "high": record["EOD_HIGH_INDEX_VAL"],
            "low": record["EOD_LOW_INDEX_VAL"],
            "close": close,
            "volume": 0,
            "open_interest": 0,
        })
    replacement_dates = {pd.to_datetime(row["time"]).date() for row in replacements}
    assert conflicted == replacement_dates
    clean = raw.loc[~raw["session"].isin(replacement_dates)].drop(columns="session")
    clean = pd.concat([clean, pd.DataFrame(replacements)], ignore_index=True)
    clean = clean.sort_values("time").reset_index(drop=True)
    assert not pd.to_datetime(clean["time"]).dt.date.duplicated().any()
    DATA.parent.mkdir(parents=True, exist_ok=True)
    clean.to_csv(DATA, index=False)
    return clean


def align_confirmed_vix(raw: pd.DataFrame, sessions: pd.DatetimeIndex) -> tuple[pd.Series, list[dict]]:
    raw = raw.copy()
    raw["session"] = raw["time"].dt.date
    counts = raw.groupby("session").size()
    ambiguous = set(counts[counts > 1].index)
    clean = raw[~raw["session"].isin(ambiguous)].set_index("session")["close"].to_dict()
    observed = set(raw["session"])
    aligned, audit = [], []
    last_value = None
    last_date = None
    for timestamp in sessions:
        session = timestamp.date()
        if session in clean:
            last_value, last_date = float(clean[session]), session
        else:
            issue = "ambiguous duplicate Upstox dates" if session in ambiguous else "no Upstox VIX row on NIFTY/ETF session"
            audit.append({
                "session_date": session.isoformat(),
                "issue": issue,
                "raw_rows": int(counts.get(session, 0)),
                "raw_close_values": ";".join(f"{x:g}" for x in raw.loc[raw["session"] == session, "close"]),
                "carried_value": "" if last_value is None else last_value,
                "carried_from_session": "" if last_date is None else last_date.isoformat(),
                "treatment": "Use prior confirmed VIX close; no same-day ambiguous or future value is used.",
            })
        aligned.append(last_value)
    if any(value is None for value in aligned):
        raise RuntimeError("India VIX history does not cover the start of the ETF sessions")
    assert observed.issuperset(set(clean)) and len(aligned) == len(sessions)
    return pd.Series(aligned, index=sessions, dtype=float), audit


def apply_vix_overlay(base: pd.DataFrame, events: pd.Series, vix: pd.Series, threshold: float, retention: float) -> pd.DataFrame:
    adjusted = base.copy()
    factor = 1.0
    for i, timestamp in enumerate(base.index):
        if bool(events.iloc[i]):
            factor = retention if float(vix.iloc[i]) >= threshold else 1.0
        adjusted.iloc[i, adjusted.columns.get_loc("NIFTYBEES")] *= factor
    assert adjusted["NIFTYBEES"].le(base["NIFTYBEES"] + 1e-12).all()
    assert adjusted["GOLDBEES"].sub(base["GOLDBEES"]).abs().lt(1e-12).all()
    assert (adjusted.sum(axis=1) <= base.sum(axis=1) + 1e-12).all()
    return adjusted


def main() -> None:
    files, panels, portfolios, event_sets = blend.make_portfolios()
    base = blend.single_sleeve_weight_targets(portfolios["inverse_vol_63d_quarterly"], 0.65)
    events = event_sets["inverse_vol_63d_quarterly"]
    raw_vix = reconcile_vix_data()
    raw_vix["time"] = pd.to_datetime(raw_vix["time"])
    vix, quality = align_confirmed_vix(raw_vix, base.index)
    configurations = [("no_overlay", None, None)] + [
        (f"vix{threshold}_nifty{int(retention * 100)}", threshold, retention)
        for threshold in THRESHOLDS for retention in NIFTY_RETENTION
    ]
    end = panels["close"].index[-1].date()
    periods = (
        ("train_2014_2019", date(2014, 1, 1), date(2019, 12, 31)),
        ("validation_2020_2022", date(2020, 1, 1), date(2022, 12, 31)),
        ("holdout_2023_plus", date(2023, 1, 1), end),
        ("full_2020_plus", date(2020, 1, 1), end),
        ("full_2014_plus", date(2014, 1, 1), end),
    )
    rows = []
    for name, threshold, retention in configurations:
        targets = base if threshold is None else apply_vix_overlay(base, events, vix, threshold, retention)
        rule = "No VIX overlay." if threshold is None else (
            f"At signal-change/quarter-end close, if India VIX >= {threshold}, retain {retention:.0%} "
            "of the base NIFTYBEES weight and leave Gold unchanged until the next rebalance."
        )
        for period, start, finish in periods:
            for slip in SLIPPAGE:
                equity, orders, stats = q._simulate(
                    panels, targets, events, CAPITAL, 1.0, slip,
                    "equity_delivery", start, finish, 20,
                )
                row = {
                    "strategy": name,
                    "vix_threshold": "" if threshold is None else threshold,
                    "nifty_retention_pct_when_vix_high": "" if retention is None else retention * 100,
                    "period": period,
                    "period_start": start.isoformat(),
                    "period_end": finish.isoformat(),
                    "starting_balance_inr": CAPITAL,
                    "exposure_cap_pct": 100,
                    "slippage_bps_per_side": slip,
                    "total_slippage_inr": blend.modeled_slippage(orders, panels),
                    "selection_or_sizing": rule,
                    "first_bar": str(equity.index[0]),
                    "last_bar": str(equity.index[-1]),
                    **stats,
                }
                rows.append(row)
                run = OUT / f"{name}__{period}__{slip}bps"
                run.mkdir(parents=True, exist_ok=True)
                equity.to_csv(run / "equity.csv", index_label="time")
                orders.to_csv(run / "orders.csv", index=False)
    assert len(rows) == len(configurations) * len(periods) * len(SLIPPAGE) == 90
    OUT.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(OUT / "summary.csv", index=False)
    pd.DataFrame(rows).to_csv(ROOT / "outputs" / "india_vix_overlay_sensitivity.csv", index=False)
    pd.DataFrame(quality).to_csv(ROOT / "outputs" / "india_vix_daily_quality.csv", index=False)
    (OUT / "strategy.json").write_text(json.dumps({
        "capital_inr": CAPITAL,
        "base_rule": "Quarterly 63-session inverse-vol split for NIFTYBEES Donchian 55/20 and GOLDBEES SMA200; 65% gross when only one sleeve is active.",
        "vix_overlay": "At signal-change and quarter-end close, if confirmed India VIX close is at or above the threshold, multiply only NIFTYBEES base weight by the retention factor; leave Gold unchanged until the next scheduled event.",
        "thresholds": list(THRESHOLDS),
        "nifty_retention_pct": [100 * value for value in NIFTY_RETENTION],
        "vix_sources": {
            "upstox_raw": RAW_DATA.relative_to(ROOT).as_posix(),
            "nse_conflict_records": SOURCE.relative_to(ROOT).as_posix(),
            "reconciled_input": DATA.relative_to(ROOT).as_posix(),
        },
        "ambiguous_or_missing_vix_sessions": quality,
        "execution": "Use VIX close known at signal close; all resulting orders fill at next session open. No leverage.",
        "slippage_bps_per_side": list(SLIPPAGE),
        "data_end": end.isoformat(),
        "source_data": {name: f"{frame.index[0].date()} to {frame.index[-1].date()}" for name, frame in files.items()},
        "limits": ["All tested history was previously inspected; this is retrospective sensitivity, not independent validation.", "India VIX is a signal only; no VIX contract is traded.", "Cash yield is zero; current delivery charges are applied uniformly; slippage is modeled."],
    }, indent=2), encoding="utf-8")

    baseline = next(r for r in rows if r["strategy"] == "no_overlay" and r["period"] == "full_2014_plus" and r["slippage_bps_per_side"] == 50)
    with (ROOT / "outputs" / "single_sleeve_deployment_sensitivity.csv").open(encoding="utf-8-sig", newline="") as handle:
        established = next(r for r in csv.DictReader(handle) if r["portfolio"] == "inverse_vol_quarterly_single_65" and r["period"] == "full_2014_plus" and int(r["slippage_bps_per_side"]) == 50)
    for field in ("ending_balance_inr", "total_return_pct", "cagr_pct", "max_drawdown_pct", "total_fees_inr", "total_slippage_inr", "order_count"):
        assert abs(float(baseline[field]) - float(established[field])) < 1e-8, f"Baseline mismatch for {field}"
    print(f"scenarios={len(rows)} baseline_checks=7 vix_quality_rows={len(quality)} output=outputs/india_vix_overlay_sensitivity.csv")


if __name__ == "__main__":
    main()
