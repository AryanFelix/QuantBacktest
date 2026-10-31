"""Research a synthetic daily 2x Smallcap 250 TRI path using an overnight-rate proxy."""

from __future__ import annotations

import csv
import json
import math
from datetime import date, datetime
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "work" / "data" / "index_daily"
OUT = ROOT / "outputs"
START = pd.Timestamp("2016-04-01")
END = pd.Timestamp("2026-10-23")
MTF_SIMPLE_ANNUAL_RATE = 0.1825


def read_1d_rate() -> pd.Series:
    rows = []
    for filename in ("nifty_1d_rate_2014_2019_raw.json", "nifty_1d_rate_2020_2026_raw.json"):
        payload = json.loads((DATA / filename).read_text(encoding="utf-8"))
        rows.extend(payload["rows"])
    frame = pd.DataFrame(rows)
    frame["date"] = pd.to_datetime(frame["date"], format="%d %b %Y", errors="raise")
    frame["close"] = pd.to_numeric(frame["close"], errors="raise")
    assert not frame["date"].duplicated().any() and (frame["close"] > 0).all()
    return frame.set_index("date")["close"].sort_index()


def read_tbill_rate() -> pd.Series:
    frame = pd.read_csv(ROOT / "outputs" / "rbi_91d_tbill_yields_2015_2026.csv", parse_dates=["issue_date"])
    frame["cutoff_yield_pct"] = pd.to_numeric(frame["cutoff_yield_pct"], errors="coerce")
    result = frame.dropna(subset=["issue_date", "cutoff_yield_pct"]).drop_duplicates("issue_date", keep="last")
    return result.set_index("issue_date")["cutoff_yield_pct"].sort_index()


def build_proxy() -> tuple[pd.DataFrame, dict]:
    benchmark = pd.read_csv(DATA / "smallcap250_benchmark_2014_2026.csv", parse_dates=["date"]).set_index("date").sort_index()
    live_2x = pd.read_csv(DATA / "nifty50_2x_leverage_2014_2026.csv", parse_dates=["date"]).set_index("date").sort_index()
    rate = read_1d_rate()
    tbill = read_tbill_rate()
    sample = benchmark.loc[START:END, ["Nifty Smallcap 250 TRI", "Nifty 50 TRI"]].dropna()
    assert sample.index[0] == START and sample.index[-1] == END and len(sample) > 2_600
    rates_on_market = rate.reindex(sample.index)
    tbill_on_market = tbill.reindex(sample.index, method="ffill")
    level_smallcap = [1_000.0]
    level_smallcap_mtf = [1_000.0]
    level_nifty = [1_000.0]
    rows = [{"date": sample.index[0].date().isoformat(), "smallcap_return": 0.0, "nifty_return": 0.0,
             "funding_return": 0.0, "funding_source": "anchor", "smallcap_2x": 1_000.0,
             "smallcap_mtf_2x": 1_000.0, "nifty_2x_proxy": 1_000.0}]
    source_counts = {"NIFTY_1D_RATE_INDEX": 0, "RBI_91D_TBILL_PROXY": 0}

    for i in range(1, len(sample)):
        day, previous = sample.index[i], sample.index[i - 1]
        calendar_days = (day - previous).days
        if pd.notna(rates_on_market.iloc[i]) and pd.notna(rates_on_market.iloc[i - 1]):
            funding = float(rates_on_market.iloc[i] / rates_on_market.iloc[i - 1] - 1)
            source = "NIFTY_1D_RATE_INDEX"
        else:
            annualized = tbill_on_market.iloc[i - 1]
            if pd.isna(annualized):
                annualized = tbill_on_market.iloc[i]
            assert pd.notna(annualized), f"No prior funding proxy for {day.date()}"
            funding = float(annualized) / 100 * calendar_days / 360
            source = "RBI_91D_TBILL_PROXY"
        smallcap_return = float(sample["Nifty Smallcap 250 TRI"].iloc[i] / sample["Nifty Smallcap 250 TRI"].iloc[i - 1] - 1)
        nifty_return = float(sample["Nifty 50 TRI"].iloc[i] / sample["Nifty 50 TRI"].iloc[i - 1] - 1)
        smallcap_2x_return = 2 * smallcap_return - funding
        smallcap_mtf_2x_return = 2 * smallcap_return - MTF_SIMPLE_ANNUAL_RATE * calendar_days / 365
        nifty_2x_return = 2 * nifty_return - funding
        assert smallcap_2x_return > -1 and smallcap_mtf_2x_return > -1 and nifty_2x_return > -1 and 0 <= funding < 0.02
        level_smallcap.append(level_smallcap[-1] * (1 + smallcap_2x_return))
        level_smallcap_mtf.append(level_smallcap_mtf[-1] * (1 + smallcap_mtf_2x_return))
        level_nifty.append(level_nifty[-1] * (1 + nifty_2x_return))
        source_counts[source] += 1
        rows.append({
            "date": day.date().isoformat(), "smallcap_return": smallcap_return,
            "nifty_return": nifty_return, "funding_return": funding, "funding_source": source,
            "smallcap_2x": level_smallcap[-1], "smallcap_mtf_2x": level_smallcap_mtf[-1],
            "nifty_2x_proxy": level_nifty[-1],
        })

    path = pd.DataFrame(rows).set_index("date")
    path.index = pd.to_datetime(path.index)
    actual = live_2x.loc[START:END, "Nifty50 TR 2x Leverage"]
    aligned = pd.concat([path["nifty_2x_proxy"], actual.rename("official_nifty_2x")], axis=1).dropna()
    proxy = aligned["nifty_2x_proxy"] / aligned["nifty_2x_proxy"].iloc[0]
    official = aligned["official_nifty_2x"] / aligned["official_nifty_2x"].iloc[0]
    validation = {
        "matched_sessions": len(aligned),
        "proxy_end_value_indexed_1000": float(proxy.iloc[-1] * 1_000),
        "official_end_value_indexed_1000": float(official.iloc[-1] * 1_000),
        "endpoint_difference_pct": float((proxy.iloc[-1] / official.iloc[-1] - 1) * 100),
        "max_path_difference_pct": float(((proxy / official - 1).abs().max()) * 100),
        "annualized_daily_tracking_error_pct": float((proxy.pct_change() - official.pct_change()).dropna().std(ddof=1) * math.sqrt(252) * 100),
    }
    assert validation["matched_sessions"] > 2_600 and abs(validation["endpoint_difference_pct"]) < 3.0, validation
    assert path.index.is_monotonic_increasing and not path.index.has_duplicates
    path["smallcap_tri"] = sample["Nifty Smallcap 250 TRI"]
    path["nifty50_tri"] = sample["Nifty 50 TRI"]
    path.to_csv(DATA / "smallcap250_2x_proxy_2016_2026.csv", index_label="date")
    return path, {"funding_source_counts": source_counts, "nifty_2x_validation": validation}


def main() -> None:
    path, diagnostics = build_proxy()
    rows = []
    for period, start in (("live_since_launch", START), ("2020_plus", pd.Timestamp("2020-01-01")),
                          ("2023_plus", pd.Timestamp("2023-01-01")), ("2025_plus", pd.Timestamp("2025-01-01"))):
        for name in ("smallcap_tri", "smallcap_2x", "smallcap_mtf_2x", "nifty50_tri", "nifty_2x_proxy"):
            series = path[name]
            sample = series.loc[start:END]
            if len(sample) < 2:
                continue
            total = float(sample.iloc[-1] / sample.iloc[0] - 1)
            years = (sample.index[-1] - sample.index[0]).days / 365.25
            rows.append({
                "period": period, "index_or_proxy": name, "start": sample.index[0].date().isoformat(),
                "end": sample.index[-1].date().isoformat(), "sessions": len(sample),
                "total_return_pct": total * 100,
                "cagr_pct": ((1 + total) ** (1 / years) - 1) * 100,
                "close_mdd_pct": float((sample / sample.cummax() - 1).min() * 100),
                "annualized_volatility_pct": float(sample.pct_change().dropna().std(ddof=1) * math.sqrt(252) * 100),
            })
    with (OUT / "smallcap250_2x_leverage_proxy.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

    note = f'''# Synthetic Smallcap 250 daily-2x funding sensitivity — {date.today().isoformat()}

## Question and result

Does daily-resetting a 2x long position in NIFTY Smallcap 250 total return produce a reliable 20% result if we accept a much larger drawdown? `smallcap250_2x_leverage_proxy.csv` compares the official Smallcap 250 TRI, a synthetic 2x daily path, NIFTY 50 TRI, and an independently generated 2x NIFTY proxy over matched segments. The daily proxy formula is twice the underlying TRI simple return less financing return. It is an index-level sensitivity, not an executable Indian product or a completed broker backtest.

Funding uses the first-party NIFTY 1D Rate Index daily change wherever both neighboring market sessions exist. During its missing source interval, funding uses the latest previously issued RBI 91-day T-bill cut-off yield on actual calendar days / 360. The transition-day fallback and source coverage are recorded in `work/data/index_daily/smallcap250_2x_proxy_2016_2026.csv`.

Sources: NSE [Nifty Smallcap 250 factsheet](https://www.niftyindices.com/Factsheet/ind_Nifty_Smallcap_250.pdf), [Nifty 1D Rate methodology](https://www.niftyindices.com/Methodology/Method_Nifty_1D_Rate.pdf), and [Nifty50 TR 2x factsheet](https://www.niftyindices.com/Factsheet/Nifty50_TR_2X_Leverage.pdf); RBI [91-day T-bill auction data](https://data-api.dbie.rbihub.in/api/tables/public_finance/r307_auctions_of_91_day_government_of_india_treasury_bills/csv).

## Calibration against the live NIFTY 2x index

The identical formula was calibrated against NSE's live Nifty50 TR 2x Leverage Index from 2016-04-01 through 2026-10-23. Diagnostics: {json.dumps(diagnostics, ensure_ascii=False)}. The proxy is accepted only if its ending normalized value stays within 3% of the official live index; the path difference and annualized daily tracking error show the remaining model error. This calibration does not validate Smallcap 250 funding when its rate source is missing.

## Execution limits

No Indian Smallcap 250 2x instrument is modeled. A hypothetical MTF purchase would use a different financing rate and stock-level eligibility/margin, plus brokerage, pledge/unpledge, and liquidation rules. Upstox's [Standard MTF price](https://upstox.com/help-center/t-251427/) is ₹20/day per ₹40,000 borrowed, equivalent to 18.25% simple annualized; substituting overnight NIFTY funding materially overstates financed returns. Upstox's [MTF terms](https://upstox.com/help-center/t-251427/) permit positions to be fully or partially squared off for a margin or MTM shortfall. The synthetic index omits management fees, tracking error, ETF premium/discount, market impact, taxes, and actual collateral calls; its drawdown is a loss of index level, not proof that borrowed exposure could be held through it.

An additional `smallcap_mtf_2x` sensitivity charges 18.25% simple annual financing on debt reset to equal account equity at each close, with daily 2x exposure and actual calendar days / 365. This is today's Upstox Standard MTF rate applied uniformly across the full history, not a reconstruction of historical broker bills. The rate converts the published charge of ₹20 per ₹40,000 borrowed per day. It excludes brokerage, pledge/unpledge fees, taxes, margin changes, and forced liquidation; the index-level path assumes those do not interrupt trading. The product is equity-delivery MTF for eligible stocks, not a Smallcap 250 2x instrument.

The full NIFTY Smallcap 250 index launched on 2016-04-01. Its history before the live ETF sample is index evidence, not an investable ETF backtest. The low-cost overnight-funding proxy and MTF sensitivity are research comparisons only; neither establishes a tradeable 20% strategy.
'''
    (OUT / "smallcap250_2x_leverage_proxy_method.md").write_text(note, encoding="utf-8")
    manifest_path = OUT / "data_manifest.csv"
    manifest = pd.read_csv(manifest_path, dtype=str, keep_default_na=False)
    manifest = manifest.loc[manifest["dataset"] != "Smallcap250 daily-2x funding sensitivities"]
    manifest.loc[len(manifest)] = {
        "dataset": "Smallcap250 daily-2x funding sensitivities", "ticker": "Nifty Smallcap250 TRI; Nifty50 TRI; Nifty50 TR 2x",
        "instrument_key": "NSE Indices official TRI histories", "bar_interval": "daily TRI close; synthetic daily leverage",
        "first_bar": path.index[0].date().isoformat(), "last_bar": path.index[-1].date().isoformat(),
        "bar_count": str(len(path)), "file_count": "20 segment rows; 5 series x 4 periods", "empty_files": "0",
        "cache_paths": "work/backtest_smallcap250_2x_sensitivity.py;work/data/index_daily/smallcap250_2x_proxy_2016_2026.csv;outputs/smallcap250_2x_leverage_proxy.csv;outputs/smallcap250_2x_leverage_proxy_method.md",
        "purpose": "Compare daily 2x Smallcap250 TRI with NSE-calibrated overnight funding and an Upstox MTF-rate sensitivity",
        "notes": "Synthetic, not investable; NSE Nifty50 TR 2x calibration endpoint gap 0.58%; MTF sensitivity excludes execution costs and forced liquidation.",
    }
    temp = manifest_path.with_suffix(".csv.tmp")
    manifest.to_csv(temp, index=False, encoding="utf-8")
    temp.replace(manifest_path)
    print(json.dumps(diagnostics, indent=2))
    print(f"wrote {len(rows)} segment rows for {path.index[0].date()}..{path.index[-1].date()}")


if __name__ == "__main__":
    main()
