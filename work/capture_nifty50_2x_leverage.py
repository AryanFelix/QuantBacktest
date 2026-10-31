"""Measure the live NSE Nifty50 daily 2x leverage index and its funding drag."""

from __future__ import annotations

import csv
import json
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from urllib.request import Request, urlopen

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
START = date(2014, 6, 30)
END = date(2026, 10, 23)
NAME = "Nifty50 TR 2x Leverage"
URL = "https://www.niftyindices.com/BackPage/getHistoricaldatatabletoString"
REFERER = "https://www.niftyindices.com/reports/historical-data"
BASE = ROOT / "work/data/index_daily/nifty50_2x_leverage_2014_2026"
NIFTY_TRI = ROOT / "work/data/index_daily/NIFTY50TR-days-1-2014-01-01-2026-10-23.csv"


def _fetch(start: date, end: date) -> list[dict]:
    cinfo = json.dumps({"name": NAME.upper(), "startDate": start.strftime("%d-%b-%Y"),
                        "endDate": end.strftime("%d-%b-%Y"), "indexName": NAME}, separators=(",", ":"))
    body = json.dumps({"cinfo": cinfo}).encode("utf-8")
    headers = {"User-Agent": "Mozilla/5.0", "Referer": REFERER, "Origin": "https://www.niftyindices.com",
               "Content-Type": "application/json; charset=utf-8", "Accept": "application/json, text/javascript, */*; q=0.01"}
    with urlopen(Request(URL, data=body, headers=headers, method="POST"), timeout=30) as response:
        rows = json.loads(response.read())
    if isinstance(rows, dict) and isinstance(rows.get("d"), str):
        rows = json.loads(rows["d"])
    assert isinstance(rows, list)
    return rows


def _metrics(series: pd.Series) -> dict[str, float | int | str]:
    values = series.to_numpy(dtype=float)
    total = values[-1] / values[0] - 1
    days = (series.index[-1].date() - series.index[0].date()).days
    drawdown = series / series.cummax() - 1
    returns = series.pct_change().dropna()
    assert len(series) > 100 and days > 0 and np.isfinite(values).all() and (values > 0).all()
    return {"period_start": series.index[0].date().isoformat(), "period_end": series.index[-1].date().isoformat(),
            "sessions": len(series), "total_return_pct": total * 100,
            "cagr_pct": ((1 + total) ** (365.25 / days) - 1) * 100,
            "close_mdd_pct": drawdown.min() * 100,
            "annualized_volatility_pct": returns.std(ddof=1) * np.sqrt(252) * 100}


def main() -> None:
    raw_rows, captured = [], {}
    cursor = START
    while cursor <= END:
        last = min(END, cursor + timedelta(days=364))
        rows = _fetch(cursor, last)
        assert rows, f"No official 2x index data for {cursor}..{last}"
        for row in rows:
            assert row["INDEX_NAME"].strip().casefold() == NAME.casefold()
            day = datetime.strptime(row["HistoricalDate"], "%d %b %Y").date()
            value = float(row["CLOSE"])
            assert cursor <= day <= last and value > 0 and day not in captured
            captured[day] = value
        raw_rows.append({"from": cursor.isoformat(), "to": last.isoformat(), "rows": rows})
        cursor = last + timedelta(days=1)
        time.sleep(0.15)

    leverage = pd.Series(captured, dtype=float).sort_index()
    leverage.index = pd.DatetimeIndex(leverage.index)
    tri = pd.read_csv(NIFTY_TRI, parse_dates=["date"]).set_index("date")["tri"]
    aligned = pd.concat([leverage.rename(NAME), tri.rename("Nifty 50 TRI")], axis=1, join="inner").dropna()
    aligned = aligned.loc[pd.Timestamp(START):pd.Timestamp(END)]
    assert aligned.index[0].date() == START and aligned.index[-1].date() == END
    assert len(aligned) > 3_000 and np.isfinite(aligned.to_numpy()).all()
    BASE.with_suffix(".json").write_text(json.dumps({
        "retrieved_at_utc": datetime.now(timezone.utc).isoformat(), "index": NAME,
        "source_page": REFERER, "source_route": "/BackPage/getHistoricaldatatabletoString",
        "source_limit": "First-party page-backed route; the official leverage methodology deducts previous-day TREPS funding from daily 2x Nifty50 TRI returns.",
        "period": [START.isoformat(), END.isoformat()], "requests": raw_rows,
    }, indent=2), encoding="utf-8")
    aligned.to_csv(BASE.with_suffix(".csv"), index_label="date")

    summaries = []
    for segment, start in (("live_since_launch", START), ("2020_plus", date(2020, 1, 1)),
                           ("2023_plus", date(2023, 1, 1)), ("2025_plus", date(2025, 1, 1))):
        for name in aligned.columns:
            summaries.append({"segment": segment, "index": name, **_metrics(aligned.loc[pd.Timestamp(start):, name])})
    output = ROOT / "outputs/nifty50_2x_leverage_comparison.csv"
    with output.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(summaries[0]))
        writer.writeheader()
        writer.writerows(summaries)
    print(f"sessions={len(aligned)} range={aligned.index[0].date()}..{aligned.index[-1].date()} segments=4")


if __name__ == "__main__":
    main()

