"""Record source-backed split identity bridges with measured price-unit checks."""

from __future__ import annotations

import csv
import hashlib
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
PUBLIC = ROOT / "work" / "data" / "public_research"
EVENTS = (
    ("HDFCBANK", "INE040A01026", "INE040A01034", "2019-09-19", "2019-09-20", "2019-09-20", 2, 2, 1, "FAOP42168_HDFCBANK.pdf", "https://nsearchives.nseindia.com/content/circulars/FAOP42168.pdf", "p.1"),
    ("VBL", "INE200M01013", "INE200M01021", "2023-06-15", "2023-06-15", "2023-06-15", 2, 10, 5, "CML56991_VBL_2023.pdf", "https://nsearchives.nseindia.com/content/circulars/CML56991.pdf", "p.1"),
    ("HAL", "INE066F01012", "INE066F01020", "2023-09-28", "2023-09-28", "2023-09-29", 2, 10, 5, "FAOP58629_HAL.pdf", "https://nsearchives.nseindia.com/content/circulars/FAOP58629.pdf", "p.1"),
    ("MAZDOCK", "INE249Z01012", "INE249Z01020", "2024-12-27", "2024-12-27", "2024-12-27", 2, 10, 5, "CMPT65800_MAZDOCK.pdf", "https://nsearchives.nseindia.com/content/circulars/CMPT65800.pdf", "p.1"),
    ("PERSISTENT", "INE262H01013", "INE262H01021", "2024-03-28", "2024-03-28", "2024-04-01", 2, 10, 5, "FAOP61344_PERSISTENT.pdf", "https://nsearchives.nseindia.com/content/circulars/FAOP61344.pdf", "p.1"),
    ("COFORGE", "INE591G01017", "INE591G01025", "2025-06-04", "2025-06-04", "2025-06-04", 5, 10, 2, "CMPT68326_COFORGE.pdf", "https://nsearchives.nseindia.com/content/circulars/CMPT68326.pdf", "p.1"),
    ("NAUKRI", "INE663F01024", "INE663F01032", "2025-05-07", "2025-05-07", "2025-05-07", 5, 10, 2, "CML67576_NAUKRI.pdf", "https://nsearchives.nseindia.com/content/circulars/CML67576.pdf", "p.1"),
    ("NBCC", "INE095N01023", "INE095N01031", "2018-04-25", "2018-04-26", "2018-04-26", 2, 2, 1, "MSE_Circular_6260_NBCC_2018.pdf", "https://www.msei.in/SX-Content/Circulars/2018/April/Circular-6260.pdf;https://www.nseindia.com/companies-listing/corporate-filings-actions?symbol=NBCC", "PDF p.1; NSE corporate-action record"),
    ("BRITANNIA", "INE216A01022", "INE216A01030", "2018-11-29", "2018-11-30", "2018-11-30", 2, 2, 1, "BRITANNIA_split_2018_nse_filing.pdf", "https://nsearchives.nseindia.com/corporate/BRITANNIA_23042019235153_BSENSENOTICEINTIMATION_013.pdf", "split terms and effective date"),
    ("MCDOWELL-N", "INE854D01016", "INE854D01024", "2018-06-15", "2018-06-18", "2018-06-18", 5, 10, 2, "MSE_Circular_6435_UNITDSPR_2018.pdf", "https://www.msei.in/SX-Content/Circulars/2018/June/Circular-6435.pdf;https://nsearchives.nseindia.com/corporate/MCDOWELL-N_14072022220127_SEinitmationAnnualReport_AGMnotice.pdf", "PDF p.1; annual-report shareholder section"),
    ("BAJFINANCE", "INE296A01024", "INE296A01032", "2025-06-16", "2025-06-16", "2025-06-16", 10, 2, 1, "CML68472_BAJFINANCE_2025.pdf", "https://nsearchives.nseindia.com/content/circulars/CML68472.pdf;https://nsearchives.nseindia.com/content/circulars/FAOP68462.pdf", "CML p.1; FAOP p.1"),
    ("KOTAKBANK", "INE237A01028", "INE237A01036", "2026-01-14", "2026-01-14", "2026-01-14", 5, 5, 1, "CML72216_KOTAKBANK_2026.pdf", "https://nsearchives.nseindia.com/content/circulars/CML72216.pdf", "p.1"),
    ("BEL", "INE263A01016", "INE263A01024", "2017-03-16", "2017-03-17", "2017-03-17", 10, 10, 1, "MSE_Circular_4994_BEL_2017.pdf", "https://www.msei.in/SX-Content/Circulars/2017/March/Circular-4994.pdf", "p.1"),
    ("IGL", "INE203G01019", "INE203G01027", "2017-11-09", "2017-11-10", "2017-11-10", 5, 10, 2, "MSE_Circular_5733_IGL_2017.pdf", "https://www.msei.in/SX-Content/Circulars/2017/November/Circular-5733.pdf;https://www.msei.in/corporates/corporate-securities-information/corporate-update/default?symbol=IGL&type=4&vmode=vm", "p.1; MSE corporate-action table"),
    ("JSWSTEEL", "INE019A01020", "INE019A01038", "2017-01-04", "2017-01-05", "2017-01-05", 10, 10, 1, "MSE_Circular_4824_JSWSTEEL_2017.pdf", "https://www.msei.in/SX-Content/Circulars/2017/January/Circular-4824.pdf", "p.1"),
    ("YESBANK", "INE528G01019", "INE528G01027", "2017-09-21", "2017-09-22", "2017-09-22", 5, 10, 2, "MSE_Circular_5543_YESBANK_2017.pdf", "https://www.msei.in/SX-Content/Circulars/2017/September/Circular-5543.pdf", "p.1"),
)
OFFICIAL_TRADE_ISIN_DATES = {
    ("BEL", "INE263A01016", "INE263A01024"): "2017-03-16",
    ("IGL", "INE203G01019", "INE203G01027"): "2017-11-09",
    ("JSWSTEEL", "INE019A01020", "INE019A01038"): "2017-01-04",
    ("YESBANK", "INE528G01019", "INE528G01027"): "2017-09-21",
}
EXTRA_PRIMARY_FILES = {("BAJFINANCE", "INE296A01024", "INE296A01032"): ("FAOP68462_BAJFINANCE_2025.pdf",)}


def vendor_share_ratio(terms: pd.DataFrame) -> float:
    ratio = 1.0
    for kind, group in terms.groupby("type"):
        variants = group[["ratio_num", "ratio_den", "face_value_from", "face_value_to"]].drop_duplicates()
        if len(variants) != 1:
            raise ValueError(f"conflicting {kind} terms")
        term = variants.iloc[0]
        if kind == "split":
            ratio *= float(term.face_value_from) / float(term.face_value_to)
        elif kind == "bonus":
            ratio *= 1 + float(term.ratio_num) / float(term.ratio_den)
        else:
            raise ValueError(f"unsupported share conversion: {kind}")
    return ratio


def self_check() -> None:
    terms = pd.DataFrame([
        {"type": "split", "face_value_from": 2, "face_value_to": 1, "ratio_num": np.nan, "ratio_den": np.nan},
        {"type": "bonus", "face_value_from": np.nan, "face_value_to": np.nan, "ratio_num": 4, "ratio_den": 1},
    ])
    assert np.isclose(vendor_share_ratio(terms), 10)
    assert all(pd.Timestamp(OFFICIAL_TRADE_ISIN_DATES[key]) == pd.Timestamp(event[3]) for event in EVENTS
               if (key := (event[0], event[1], event[2])) in OFFICIAL_TRADE_ISIN_DATES)


def main() -> None:
    self_check()
    history = pd.read_parquet(PUBLIC / "tejhq" / "symbol_history" / "nse.parquet")
    history["symbol"] = history["symbol"].str.upper()
    history["isin"] = history["isin"].str.upper()
    history["valid_from"] = pd.to_datetime(history["valid_from"]).dt.normalize()
    history["valid_to"] = pd.to_datetime(history["valid_to"]).dt.normalize()
    prices = pd.concat([
        pd.read_parquet(PUBLIC / "tejhq" / "prices_adjusted" / f"nse_{year}.parquet",
                        columns=["date", "isin", "close", "adj_factor_cumulative", "adj_close"])
        for year in {int(row[3][:4]) for row in EVENTS}
    ], ignore_index=True)
    prices["date"] = pd.to_datetime(prices["date"]).dt.normalize()
    prices["isin"] = prices["isin"].str.upper()
    actions = pd.concat([
        pd.read_parquet(PUBLIC / "tejhq" / "actions" / f"nse_{year}.parquet")
        for year in {int(row[3][:4]) for row in EVENTS}
    ], ignore_index=True)
    actions["symbol"] = actions["symbol"].str.upper()
    actions["isin"] = actions["isin"].str.upper()
    actions["ex_date"] = pd.to_datetime(actions["ex_date"]).dt.normalize()

    output = PUBLIC / "isin_bridges" / "reviewed_identity_bridges.csv"
    with output.open(encoding="utf-8-sig", newline="") as handle:
        old_rows = list(csv.DictReader(handle))
    fields = list(old_rows[0])
    if "official_trade_isin_effective_date" not in fields:
        fields.insert(fields.index("economic_ex_date"), "official_trade_isin_effective_date")
        for row in old_rows:
            row["official_trade_isin_effective_date"] = ""
    seen = {(row["symbol"], row["from_isin"], row["to_isin"]) for row in old_rows}
    additions = []
    for symbol, old, new, ex_text, identity_text, record_date, ratio, face_from, face_to, pdf, url, page in EVENTS:
        if (symbol, old, new) in seen:
            continue
        ex_date, identity_date = pd.Timestamp(ex_text), pd.Timestamp(identity_text)
        trade_isin_date = OFFICIAL_TRADE_ISIN_DATES.get((symbol, old, new), "")
        spans = history[(history["symbol"] == symbol) & history["isin"].isin([old, new])]
        old_span, new_span = spans[spans["isin"] == old].iloc[-1], spans[spans["isin"] == new].iloc[-1]
        if new_span.valid_from != identity_date or old_span.valid_to > identity_date:
            raise ValueError(f"{symbol}: point-in-time identity spans do not support the recorded bridge")
        prior_date = prices.loc[(prices["date"] < ex_date) & prices["isin"].eq(old), "date"].max()
        previous = prices[(prices["date"] == prior_date) & (prices["isin"] == old)]
        on_ex = prices[(prices["date"] == ex_date) & prices["isin"].isin([old, new])]
        event_terms = actions[(actions["symbol"] == symbol) & (actions["ex_date"] == ex_date)
                              & actions["type"].isin({"split", "bonus"})]
        if len(previous) != 1 or len(on_ex) != 1:
            raise ValueError(f"{symbol}: raw event row is ambiguous")
        before, after = previous.iloc[0], on_ex.iloc[0]
        vendor_ratio = vendor_share_ratio(event_terms)
        if not event_terms.empty and not np.isclose(vendor_ratio, ratio):
            raise ValueError(f"{symbol}: combined vendor share conversion {vendor_ratio} disagrees with official ratio {ratio}")
        factor_ratio = float(after.adj_factor_cumulative) / float(before.adj_factor_cumulative)
        if not np.isclose(factor_ratio, ratio, rtol=2e-4, atol=2e-5):
            raise ValueError(f"{symbol}: adjusted-factor ratio {factor_ratio} disagrees with official ratio {ratio}")
        scaled_reference = float(before.close) / ratio
        ex_gap = (float(after.close) / scaled_reference - 1) * 100
        source_files = [
            Path("isin_bridges/primary") / pdf,
            *(Path("isin_bridges/primary") / name for name in EXTRA_PRIMARY_FILES.get((symbol, old, new), ())),
            Path("tejhq/symbol_history/nse.parquet"),
            Path("tejhq/prices_adjusted") / f"nse_{ex_date.year}.parquet",
            Path("tejhq/actions") / f"nse_{ex_date.year}.parquet",
        ]
        source_hashes = [hashlib.sha256((PUBLIC / name).read_bytes()).hexdigest() for name in source_files]
        pdf_hash = source_hashes[0]
        first_new = prices.loc[prices["isin"].eq(new), "date"].min().date().isoformat()
        row = {key: "" for key in fields}
        row.update({
            "symbol": symbol, "from_isin": old, "to_isin": new, "effective_date": identity_date.date().isoformat(),
            "official_trade_isin_effective_date": trade_isin_date,
            "economic_ex_date": ex_date.date().isoformat(), "record_date": record_date, "share_ratio": str(ratio),
            "old_face_value": str(face_from), "new_face_value": str(face_to),
            "vendor_old_valid_to": old_span.valid_to.date().isoformat(), "vendor_new_valid_from": new_span.valid_from.date().isoformat(),
            "vendor_first_new_observation": first_new, "raw_pre_date": prior_date.date().isoformat(),
            "raw_pre_close": str(float(before.close)), "raw_ex_date": ex_date.date().isoformat(),
            "raw_ex_isin": after["isin"], "raw_ex_close": str(float(after.close)),
            "split_scaled_reference": str(scaled_reference), "ex_gap_pct": str(ex_gap),
            "adjusted_pre_factor": str(float(before.adj_factor_cumulative)), "adjusted_ex_factor": str(float(after.adj_factor_cumulative)),
            "adjusted_pre_close": str(float(before.adj_close)), "adjusted_ex_close": str(float(after.adj_close)),
            "action_feed_isin": ";".join(event_terms["isin"].dropna().astype(str).str.upper().unique()),
            "identity_date_conflict": f"economic ex-date={ex_date.date()}; circular says new-ISIN trades start {trade_isin_date or 'not separately recorded'}; old vendor ID valid through {old_span.valid_to.date()}; successor history begins {identity_date.date()}; first successor row={first_new}",
            "source_files": ";".join(name.as_posix() for name in source_files), "source_hashes": ";".join(source_hashes),
            "source_urls": url, "source_pages": page, "status": "verified", "membership_replay": "true",
            "filename": pdf, "page_ref": page, "official_url": url, "pdf_sha256": pdf_hash,
            "reference_close_date": prior_date.date().isoformat(), "identity_bridge": f"{old}->{new}; face-value split {face_from}->{face_to}",
            "review_note": f"Official exchange split/bonus evidence; economic ex-date {ex_date.date()}, official new-ISIN trade-effective date {trade_isin_date or 'not separately recorded'}, vendor-history successor date {identity_date.date()}. Raw close {before.close:.2f} before, {after.close:.2f} on ex-date; converted reference {scaled_reference:.2f}, realized ex-gap {ex_gap:.4f}%. Adjusted factor ratio {factor_ratio:.8f} matches combined share ratio {ratio}; quantity conversion does not re-scale the already ex-unit close."
                          + (" Local vendor action terms agree." if not event_terms.empty else " No local vendor action row; official terms and price/factor checks govern."),
        })
        additions.append(row)

    if additions:
        with output.open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fields)
            writer.writeheader()
            writer.writerows(old_rows + additions)
    print(f"added={len(additions)}")
    for row in additions:
        print(row["symbol"], row["economic_ex_date"], row["effective_date"], row["share_ratio"], row["ex_gap_pct"])


if __name__ == "__main__":
    main()
