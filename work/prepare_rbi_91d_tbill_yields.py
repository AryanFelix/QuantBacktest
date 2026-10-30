"""Normalize RBI 91-day T-bill auction yields and attach issue dates."""

from __future__ import annotations

from datetime import date
from pathlib import Path
from urllib.request import Request, urlopen

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "work" / "data" / "rbi_sources"
MEASURE = RAW / "rates-tbill-91_measure_2026-10-08.csv"
REPORT_307 = RAW / "rbi_report_307_91d_tbill_raw_2026-09-29.csv"
OUT = ROOT / "outputs" / "rbi_91d_tbill_yields_2015_2026.csv"
MEASURE_URL = "https://measure.thisindianlife.today/data/rates-tbill-91.csv"
REPORT_307_URL = (
    "https://data-api.dbie.rbihub.in/api/tables/public_finance/"
    "r307_auctions_of_91_day_government_of_india_treasury_bills/csv"
)
YIELD_COLUMN = "91-day T-bill: cut-off yield"
PRICE_COLUMN = "91-day T-bill: cut-off price, ₹ per ₹100"
SOURCE_START, START, END = date(2014, 12, 1), date(2015, 1, 2), date(2026, 10, 23)


def _capture(path: Path, url: str) -> None:
    if path.exists():
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    request = Request(url, headers={"User-Agent": "QuantBacktest research data capture"})
    with urlopen(request, timeout=30) as response:
        if response.status != 200:
            raise RuntimeError(f"Source returned HTTP {response.status}: {url}")
        content = response.read()
    if len(content) < 1_000:
        raise RuntimeError(f"Source response is unexpectedly small: {url}")
    path.write_bytes(content)


def main() -> None:
    _capture(MEASURE, MEASURE_URL)
    _capture(REPORT_307, REPORT_307_URL)
    rates = pd.read_csv(MEASURE, dtype=str, keep_default_na=False)
    report = pd.read_csv(REPORT_307, dtype=str, keep_default_na=False)
    auction_dates = pd.to_datetime(rates["date"], format="%Y-%m-%d", errors="coerce")
    rates = rates.assign(auction_date=auction_dates).dropna(subset=["auction_date"])
    rates["cutoff_yield_pct"] = pd.to_numeric(rates[YIELD_COLUMN], errors="coerce")
    rates["cutoff_price_rupees_per_100"] = pd.to_numeric(rates[PRICE_COLUMN], errors="coerce")

    report["auction_date"] = pd.to_datetime(report["c1"], format="%d-%b-%Y", errors="coerce")
    report["issue_date"] = pd.to_datetime(report["c2"], format="%d-%b-%Y", errors="coerce")
    issue_dates = report.dropna(subset=["auction_date", "issue_date"])[["auction_date", "issue_date"]]
    issue_dates = issue_dates.drop_duplicates("auction_date")
    rates = rates[(rates["auction_date"].dt.date >= SOURCE_START) & (rates["auction_date"].dt.date <= END)]
    joined = rates.merge(issue_dates, on="auction_date", how="left", validate="one_to_one")

    research_window = joined[joined["auction_date"].dt.date >= START]
    assert len(research_window) == 606, f"Unexpected auction-row count: {len(research_window)}"
    assert joined["auction_date"].is_unique and joined["issue_date"].notna().all()
    assert (joined["issue_date"] >= joined["auction_date"]).all()
    assert (joined["issue_date"] <= joined["auction_date"] + pd.Timedelta(days=7)).all()
    assert int(research_window["cutoff_yield_pct"].isna().sum()) == 5
    assert (joined.loc[joined["cutoff_yield_pct"].notna(), "cutoff_yield_pct"] > 0).all()
    for auction_date, expected_yield, expected_price in (
        ("2022-08-03", 5.5586, 98.63),
        ("2022-08-10", 5.5949, 98.62),
        ("2023-08-17", 6.8781, 98.31),
        ("2023-08-30", 6.8225, 98.33),
    ):
        row = joined.loc[joined["auction_date"] == auction_date].iloc[0]
        assert abs(float(row["cutoff_yield_pct"]) - expected_yield) <= 0.0001
        assert abs(float(row["cutoff_price_rupees_per_100"]) - expected_price) < 0.01

    result = joined[["auction_date", "issue_date", "cutoff_price_rupees_per_100", "cutoff_yield_pct"]].copy()
    result["auction_date"] = result["auction_date"].dt.strftime("%Y-%m-%d")
    result["issue_date"] = result["issue_date"].dt.strftime("%Y-%m-%d")
    result["source_vintage"] = "2026-10-08"
    OUT.parent.mkdir(parents=True, exist_ok=True)
    result.to_csv(OUT, index=False)
    print(f"Wrote {len(result)} RBI 91-day auction rows through {result.auction_date.iloc[-1]} ({result.cutoff_yield_pct.isna().sum()} missing yields).")


if __name__ == "__main__":
    main()
