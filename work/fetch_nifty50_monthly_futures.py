"""Cache expired monthly NIFTY 50 futures contracts and daily candles from Upstox."""

from __future__ import annotations

import csv
import calendar
import hashlib
import json
import os
import sys
import tempfile
from collections import defaultdict
from datetime import date, timedelta
from io import BytesIO
from pathlib import Path
from zipfile import ZipFile

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import upstox_quant as q


ROOT = Path(__file__).resolve().parents[1]
UNDERLYING = "NSE_INDEX|Nifty 50"
START = date(2024, 10, 1)
END = date(2026, 9, 30)
OUT = ROOT / "work" / "data" / "expired" / "nifty50_monthly_futures"
NSE_ARCHIVE = ROOT / "work" / "data" / "universe_sources" / "nse_fo_udiff"


def monthly_expiries(values: list[str], start: date, end: date) -> list[date]:
    grouped: dict[tuple[int, int], list[date]] = defaultdict(list)
    for value in values:
        expiry = date.fromisoformat(value)
        if start <= expiry <= end:
            grouped[(expiry.year, expiry.month)].append(expiry)
    selected = []
    for (year, month), dates in grouped.items():
        last_day = date(year, month, calendar.monthrange(year, month)[1])
        # NSE monthly NIFTY expiries changed from last Thursday to last Tuesday in September 2025.
        weekday = 3 if date(year, month, 1) < date(2025, 9, 1) else 1
        target = last_day - timedelta(days=(last_day.weekday() - weekday) % 7)
        candidates = [expiry for expiry in dates if target - timedelta(days=7) <= expiry <= target]
        if candidates:
            selected.append(max(candidates))
    return sorted(selected)


def atomic_text(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", newline="", delete=False, dir=path.parent, suffix=".tmp") as handle:
        handle.write(value)
        temporary = Path(handle.name)
    os.replace(temporary, path)


def nse_gap_candles(expiry: date, previous_expiry: date, lot_size: int, trading_dates: list[date]):
    roll_date = max(START, max(day for day in trading_dates if day < previous_expiry))
    bars = []
    sources = []
    for day in trading_dates:
        if not roll_date <= day <= expiry:
            continue
        stamp = day.strftime("%Y%m%d")
        url = f"https://archives.nseindia.com/content/fo/BhavCopy_NSE_FO_0_0_0_{stamp}_F_0000.csv.zip"
        archive_path = NSE_ARCHIVE / str(day.year) / f"{day.month:02d}" / f"{day.isoformat()}.zip"
        if archive_path.exists():
            payload = archive_path.read_bytes()
        else:
            payload = q._http_get(url)
            archive_path.parent.mkdir(parents=True, exist_ok=True)
            with tempfile.NamedTemporaryFile("wb", delete=False, dir=archive_path.parent, suffix=".tmp") as handle:
                handle.write(payload)
                temporary = Path(handle.name)
            os.replace(temporary, archive_path)
        with ZipFile(BytesIO(payload)) as archive:
            data_file = next(name for name in archive.namelist() if name.lower().endswith(".csv"))
            frame = pd.read_csv(archive.open(data_file), usecols=["TradDt", "FinInstrmTp", "TckrSymb", "FininstrmActlXpryDt", "OpnPric", "HghPric", "LwPric", "ClsPric", "TtlTradgVol", "OpnIntrst", "NewBrdLotQty"])
        expiry_dates = pd.to_datetime(frame["FininstrmActlXpryDt"], errors="coerce").dt.date
        match = frame.loc[(frame["TradDt"] == day.isoformat()) & (frame["FinInstrmTp"] == "IDF") & (frame["TckrSymb"] == "NIFTY") & (expiry_dates == expiry)]
        assert len(match) == 1, f"Expected one NSE NIFTY future row for {day} / {expiry}, got {len(match)}"
        row = match.iloc[0]
        assert int(row["NewBrdLotQty"]) == lot_size
        bars.append({"time": f"{day.isoformat()}T09:15:00+05:30", "open": float(row["OpnPric"]), "high": float(row["HghPric"]), "low": float(row["LwPric"]), "close": float(row["ClsPric"]), "volume": int(row["TtlTradgVol"]) * lot_size, "open_interest": int(row["OpnIntrst"])})
        sources.append({"date": day.isoformat(), "url": url, "cache_path": archive_path.relative_to(ROOT).as_posix(), "sha256": hashlib.sha256(payload).hexdigest()})
    return pd.DataFrame(bars), roll_date, sources


def main() -> None:
    assert monthly_expiries(["2024-10-03", "2024-10-31", "2024-11-07", "2024-11-28"], START, END) == [date(2024, 10, 31), date(2024, 11, 28)]
    assert monthly_expiries(["2025-04-24", "2025-04-30", "2026-03-24", "2026-03-30"], START, END) == [date(2025, 4, 24), date(2026, 3, 30)]
    raw_expiries = q.fetch_expiries(UNDERLYING)
    values = raw_expiries if isinstance(raw_expiries, list) else raw_expiries.get("expiries", [])
    expiries = monthly_expiries(values, START, END)
    expected_months = pd.period_range(START, END, freq="M").astype(str).tolist()
    assert [expiry.strftime("%Y-%m") for expiry in expiries] == expected_months, f"Monthly expiry coverage is incomplete: {expiries}"
    index_times = pd.to_datetime(pd.read_csv(ROOT / "work" / "data" / "index_daily" / "NIFTY50-days-1-2014-01-01-2026-10-23.csv", usecols=["time"])["time"], errors="raise")
    trading_dates = sorted(set(index_times.dt.date))

    rows = []
    files = []
    monthly_status = []
    for position, expiry in enumerate(expiries):
        contract_path = OUT / f"{expiry}-contract.json"
        candles_path = OUT / f"{expiry}-daily.csv"
        fetch_start = max(START, expiry - timedelta(days=60))
        previous_expiry = START - timedelta(days=1) if position == 0 else expiries[position - 1]
        if contract_path.exists():
            contracts = json.loads(contract_path.read_text(encoding="utf-8"))
        else:
            contracts = q.fetch_expired_contracts(UNDERLYING, expiry, "future")
        if not contracts:
            monthly_status.append({"expiry": expiry.isoformat(), "instrument_key": "", "lot_size": 0, "candles": "contract unavailable", "bar_count": 0})
            continue
        assert len(contracts) == 1, f"Expected one NIFTY future for {expiry}, got {len(contracts)}"
        contract = contracts[0]
        assert contract["instrument_type"] == "FUT" and contract["underlying_key"] == UNDERLYING
        assert date.fromisoformat(contract["expiry"]) == expiry and int(contract["lot_size"]) > 0
        atomic_text(contract_path, json.dumps(contracts, indent=2))

        if candles_path.exists():
            candles = pd.read_csv(candles_path)
        else:
            candles = q.fetch_expired_candles(contract["instrument_key"], fetch_start, expiry, "day")
            if not candles.empty:
                candles.to_csv(candles_path, index=False)
        if candles.empty:
            candles, roll_date, source_archives = nse_gap_candles(expiry, previous_expiry, int(contract["lot_size"]), trading_dates)
            assert not candles.empty, f"No Upstox or NSE daily candles for {expiry}"
            candles.to_csv(candles_path, index=False)
            monthly_status.append({"expiry": expiry.isoformat(), "instrument_key": contract["instrument_key"], "lot_size": contract["lot_size"], "candles": "NSE fallback", "roll_date": roll_date.isoformat(), "first_bar": candles["time"].min()[:10], "last_bar": candles["time"].max()[:10], "bar_count": len(candles), "source_archives": source_archives})
        else:
            candles["time"] = pd.to_datetime(candles["time"], errors="raise")
            assert not candles["time"].duplicated().any()
            assert candles["time"].max().date() == expiry, f"No expiry-day candle for {expiry}"
            assert (candles[["open", "high", "low", "close"]] > 0).all().all()
            monthly_status.append({"expiry": expiry.isoformat(), "instrument_key": contract["instrument_key"], "lot_size": contract["lot_size"], "candles": "Upstox", "first_bar": candles["time"].min().date().isoformat(), "last_bar": candles["time"].max().date().isoformat(), "bar_count": len(candles)})
            files.append(candles_path)
        source_name = "NSE normalized NIFTY 50 futures candles" if monthly_status[-1]["candles"] == "NSE fallback" else "Upstox expired NIFTY 50 futures candles"
        source_note = "Official NSE UDiFF F&O bhavcopy fills empty Upstox candles; OHLC matches a separate Upstox contract spot-check and volume is converted from lots to units." if monthly_status[-1]["candles"] == "NSE fallback" else f"Daily expired-contract OHLCV from Upstox; fetched from {fetch_start} through expiry for pre-expiry roll pricing."
        rows.append({"dataset": source_name, "ticker": contract["trading_symbol"], "instrument_key": contract["instrument_key"], "bar_interval": "1 day", "first_bar": pd.to_datetime(candles["time"]).min().isoformat(), "last_bar": pd.to_datetime(candles["time"]).max().isoformat(), "bar_count": str(len(candles)), "file_count": "1", "empty_files": "0", "cache_paths": candles_path.relative_to(ROOT).as_posix(), "purpose": "NIFTY 50 futures trend and roll-aware backtests", "notes": source_note})
        rows.append({"dataset": "Upstox expired NIFTY 50 futures contract", "ticker": contract["trading_symbol"], "instrument_key": contract["instrument_key"], "bar_interval": "contract metadata", "first_bar": expiry.isoformat(), "last_bar": expiry.isoformat(), "bar_count": "1", "file_count": "1", "empty_files": "0", "cache_paths": contract_path.relative_to(ROOT).as_posix(), "purpose": "Monthly futures contract and lot-size history", "notes": f"Expiry {expiry}; lot size {contract['lot_size']}; read from Upstox expired futures API."})
        files.append(contract_path)

    schedule = {"underlying_key": UNDERLYING, "study_start": START.isoformat(), "last_complete_month": END.isoformat(), "all_available_expiries": values, "monthly_expiries": [expiry.isoformat() for expiry in expiries], "monthly_contracts": monthly_status, "contract_count": len(expiries), "candles_available": sum(row["candles"] in {"Upstox", "NSE fallback"} for row in monthly_status)}
    schedule_path = OUT / "expiry_schedule.json"
    atomic_text(schedule_path, json.dumps(schedule, indent=2))
    missing_expiries = [row["expiry"] for row in monthly_status if row["candles"] not in {"Upstox", "NSE fallback"}]
    rows.extend({"dataset": "NSE UDiFF F&O bhavcopy archive", "ticker": "NIFTY", "instrument_key": "", "bar_interval": "1 day source file", "first_bar": source["date"], "last_bar": source["date"], "bar_count": "1", "file_count": "1", "empty_files": "0", "cache_paths": source["cache_path"], "purpose": "Fill the December 2024 Upstox expired-futures candle gap", "notes": f"Official NSE daily UDiFF archive; {source['url']}; SHA-256 {source['sha256']}."} for status in monthly_status for source in status.get("source_archives", []))
    rows.append({"dataset": "Upstox expired NIFTY 50 futures expiry schedule", "ticker": "NIFTY", "instrument_key": UNDERLYING, "bar_interval": "expiry dates", "first_bar": expiries[0].isoformat(), "last_bar": expiries[-1].isoformat(), "bar_count": str(len(expiries)), "file_count": "1", "empty_files": "0", "cache_paths": schedule_path.relative_to(ROOT).as_posix(), "purpose": "Select one expired monthly futures contract per calendar month", "notes": f"Weekly expiry dates retained; monthly futures day follows NSE's Thursday-to-Tuesday rule. Empty candle periods: {', '.join(missing_expiries) if missing_expiries else 'none'}."})

    manifest_path = ROOT / "outputs" / "data_manifest.csv"
    with manifest_path.open(encoding="utf-8-sig", newline="") as handle:
        manifest = list(csv.DictReader(handle))
    fields = list(manifest[0])
    assert all(set(row) == set(fields) for row in rows)
    paths = {row["cache_paths"] for row in rows}
    manifest = [row for row in manifest if row["cache_paths"] not in paths]
    manifest.extend(rows)
    assert len({row["cache_paths"] for row in manifest}) == len(manifest)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", newline="", delete=False, dir=manifest_path.parent, suffix=".tmp") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(manifest)
        temporary = Path(handle.name)
    os.replace(temporary, manifest_path)
    print(f"monthly_contracts={len(expiries)} candle_histories={schedule['candles_available']} empty_months={missing_expiries} lot_sizes={sorted({int(json.loads(path.read_text(encoding='utf-8'))[0]['lot_size']) for path in files if path.name.endswith('-contract.json')})} first={expiries[0]} last={expiries[-1]} manifest_rows={len(manifest)}")


if __name__ == "__main__":
    main()
