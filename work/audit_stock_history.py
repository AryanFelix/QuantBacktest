from __future__ import annotations

import re
import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "work" / "data" / "universe_sources"
BAR_DIR = ROOT / "work" / "data" / "stocks"
START = "2020-01-01"
END = "2026-10-23"
THRESHOLD = 0.08

mapping = pd.read_csv(SOURCE / "upstox_stock_keys.csv", dtype=str).drop_duplicates("instrument_key")
coverage = []
large_moves = []
symbol_bars = {}
for row in mapping.itertuples(index=False):
    safe_key = re.sub(r"[^A-Za-z0-9_-]+", "_", row.instrument_key).strip("_")
    path = BAR_DIR / f"{safe_key}-days-1-{START}-{END}.csv"
    assert path.is_file(), f"Missing Upstox stock history for {row.trading_symbol}: {path}"
    bars = pd.read_csv(path, parse_dates=["time"]).sort_values("time").reset_index(drop=True)
    assert not bars.empty and (bars[["open", "high", "low", "close"]] > 0).all().all()
    coverage.append({
        "data_source": "Upstox",
        "trading_symbol": row.trading_symbol,
        "name": row.name,
        "instrument_key": row.instrument_key,
        "isin": row.isin,
        "first_bar": bars.time.iloc[0].date().isoformat(),
        "last_bar": bars.time.iloc[-1].date().isoformat(),
        "bar_count": len(bars),
        "cache_path": path.relative_to(ROOT).as_posix(),
    })
    symbol_bars[row.trading_symbol] = bars
    returns = bars.close.pct_change()
    for i in returns.index[returns.abs() >= THRESHOLD]:
        large_moves.append({
            "trading_symbol": row.trading_symbol,
            "data_source": "Upstox",
            "instrument_key": row.instrument_key,
            "date": bars.loc[i, "time"].date().isoformat(),
            "previous_close": bars.loc[i - 1, "close"],
            "close": bars.loc[i, "close"],
            "return_pct": returns.loc[i] * 100,
        })

assert len(coverage) == mapping.instrument_key.nunique() and all(x["bar_count"] > 0 for x in coverage)
symbol_bars["LTIM"] = symbol_bars["LTM"]
symbol_bars["INFRATEL"] = symbol_bars["INDUSTOWER"]

hdfc_raw_files = sorted(SOURCE.glob("nse_hdfc_eq_20*.json"))
assert len(hdfc_raw_files) == 4, "Expected NSE HDFC archives for 2020–2023"
hdfc_records = []
for raw_path in hdfc_raw_files:
    payload = json.loads(raw_path.read_text(encoding="utf-8"))
    assert payload["symbol"] == "HDFC"
    for chunk in payload["chunks"]:
        assert chunk["count"] == len(chunk["data"])
        assert all(x["CH_SYMBOL"] == "HDFC" and x["CH_SERIES"] == "EQ" for x in chunk["data"])
        hdfc_records.extend(chunk["data"])
hdfc = pd.DataFrame(hdfc_records)
hdfc["time"] = pd.to_datetime(hdfc["mTIMESTAMP"], format="%d-%b-%Y").dt.tz_localize("Asia/Kolkata")
hdfc = hdfc.rename(columns={
    "CH_OPENING_PRICE": "open", "CH_TRADE_HIGH_PRICE": "high",
    "CH_TRADE_LOW_PRICE": "low", "CH_CLOSING_PRICE": "close",
    "CH_TOT_TRADED_QTY": "volume",
})[["time", "open", "high", "low", "close", "volume"]]
hdfc["open_interest"] = 0
hdfc = hdfc.sort_values("time").reset_index(drop=True)
assert not hdfc.time.duplicated().any() and (hdfc[["open", "high", "low", "close"]] > 0).all().all()
assert hdfc.time.iloc[0].date().isoformat() == "2020-01-01"
assert hdfc.time.iloc[-1].date().isoformat() == "2023-07-12"
hdfc_path = BAR_DIR / "NSE_HDFC_EQ-days-1-2020-01-01-2023-07-12.csv"
hdfc.to_csv(hdfc_path, index=False)
hdfc_bars = pd.read_csv(hdfc_path, parse_dates=["time"]).sort_values("time").reset_index(drop=True)
symbol_bars["HDFC"] = hdfc_bars
coverage.append({
    "data_source": "NSE",
    "trading_symbol": "HDFC",
    "name": "Housing Development Finance Corporation Limited",
    "instrument_key": "",
    "isin": "INE001A01036",
    "first_bar": hdfc_bars.time.iloc[0].date().isoformat(),
    "last_bar": hdfc_bars.time.iloc[-1].date().isoformat(),
    "bar_count": len(hdfc_bars),
    "cache_path": hdfc_path.relative_to(ROOT).as_posix(),
})

pd.DataFrame(coverage).to_csv(SOURCE / "stock_history_coverage.csv", index=False)
pd.DataFrame(large_moves, columns=["trading_symbol", "instrument_key", "date", "previous_close", "close", "return_pct"]).to_csv(SOURCE / "large_stock_daily_moves.csv", index=False)

snapshots = pd.read_csv(SOURCE / "nifty50_monthly_universe_2020_2026.csv", dtype=str)
monthly_coverage = []
for row in snapshots.itertuples(index=False):
    signal = pd.Timestamp(row.signal_date).date()
    members = row.members.split(";")
    missing = []
    short_history = []
    for symbol in members:
        bars = symbol_bars.get(symbol)
        if bars is None:
            missing.append(symbol)
            continue
        history = bars[bars.time.dt.date <= signal]
        if history.empty:
            missing.append(symbol)
        elif len(history) < 252:
            short_history.append(symbol)
    monthly_coverage.append({
        "month": row.month,
        "signal_date": row.signal_date,
        "member_count": len(members),
        "missing_price_members": ";".join(missing),
        "missing_price_member_count": len(missing),
        "under_252_bars_members": ";".join(short_history),
        "under_252_bars_member_count": len(short_history),
    })
assert len(monthly_coverage) == len(snapshots)
assert not any("HDFC" in row["missing_price_members"].split(";") for row in monthly_coverage)
pd.DataFrame(monthly_coverage).to_csv(SOURCE / "stock_monthly_universe_coverage.csv", index=False)

manifest_path = ROOT / "outputs" / "data_manifest.csv"
manifest = pd.read_csv(manifest_path, dtype=str)
notes = {
    "HDFC": "NSE security-wise archive, series EQ; supplements unavailable retired Upstox instrument key. Merger and total-return accounting not built.",
    "LTM": "Current symbol for the historical LTIM member; same ISIN. Upstox OHLC as returned.",
    "INDUSTOWER": "Historical NIFTY member alias INFRATEL. Upstox OHLC as returned.",
    "ETERNAL": "Historical NIFTY member alias ZOMATO. Upstox OHLC as returned.",
    "TMPV": "Historical TATAMOTORS alias; Upstox-returned bars include the 2025-10-14 demerger discontinuity.",
    "VEDL": "Upstox-returned bars include the 2026-04-30 demerger discontinuity.",
    "RELIANCE": "Upstox-returned bars cross the 2023-07-20 Jio Financial demerger.",
    "ITC": "Upstox-returned bars cross the 2025-01-06 ITC Hotels demerger.",
    "HINDUNILVR": "Upstox-returned bars cross the 2025-12-05 Kwality Wall's demerger.",
    "TMCV": "New listing history; its 2025-10 index placeholder period is not tradeable.",
    "ITCHOTELS": "New listing history; its 2025-01 index placeholder period is not tradeable.",
    "KWIL": "New listing history; 2025-12/2026-01 index placeholder periods are not tradeable.",
}
stock_rows = pd.DataFrame([{
    "dataset": "NSE equity security-wise archive" if row["data_source"] == "NSE" else "Upstox NSE equity historical candles",
    "ticker": row["trading_symbol"],
    "instrument_key": row["instrument_key"],
    "bar_interval": "1 day",
    "first_bar": row["first_bar"] + "T00:00:00+05:30",
    "last_bar": row["last_bar"] + "T00:00:00+05:30",
    "bar_count": row["bar_count"],
    "file_count": 1,
    "empty_files": 0,
    "cache_paths": row["cache_path"],
    "purpose": "Point-in-time NIFTY 50 stock strategy research and price-quality audit",
    "notes": notes.get(row["trading_symbol"], "Upstox OHLC as returned; 21-event sample is consistent with split/bonus share-unit back-adjustment but is not a documented guarantee. Dividends, rights, mergers and demergers are not normalized."),
} for row in coverage])
old_stock_rows = manifest.cache_paths.str.contains("work/data/stocks/", regex=False, na=False)
manifest = manifest.loc[~(old_stock_rows & manifest.ticker.isin(stock_rows.ticker))]
manifest = pd.concat([manifest, stock_rows], ignore_index=True)
assert not manifest.cache_paths.duplicated().any()
manifest.to_csv(manifest_path, index=False)
print(f"instruments={len(coverage)} bars={sum(x['bar_count'] for x in coverage)} large_moves_abs_ge_8pct={len(large_moves)} months={len(monthly_coverage)} manifest_rows={len(manifest)}")
