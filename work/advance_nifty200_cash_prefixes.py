"""Correct the first source-backed signals and run their actual cash-account prefixes."""

from __future__ import annotations

import json
import hashlib
import sys
import tempfile
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow.dataset as ds

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "work"))
import audit_strategy_dependencies as audit
import upstox_quant as cash_engine

DETAIL = audit.PUBLIC / "strategy_dependencies" / "nifty200"
OUT = ROOT / "outputs" / "nifty200_sequential_account_cycle4_2026-11-03.json"
LOCAL = DETAIL / "sequential_cash_prefixes_cycle4_2026-11-03"
CAPITAL = 1_000_000.0
SLIPPAGE_BPS = 50.0
AGEL_ISIN = "INE364U01010"
AGEL_RATIO = Decimal("761") / Decimal("1000")
AGEL_LISTING_DATE = date(2018, 6, 18)
AGEL_DISPOSAL_DATE = date(2018, 6, 19)
DIVIDEND_DELAY_DAYS = 30

# Ratios and full subscription prices come from the registered source protocol.
RIGHTS = {
    ("CANBK", "2017-02-17"): [(1 / 10, 207.0)],
    ("INDHOTEL", "2017-10-04"): [(1 / 5, 75.0)],
    ("KARURVYSYA", "2017-10-12"): [(1 / 6, 76.0)],
    ("TATASTEEL", "2018-01-31"): [(4 / 25, 510.0), (2 / 25, 615.0)],
    ("PEL", "2018-01-31"): [(1 / 23, 2380.0)],
    ("IBVENTURES", "2018-02-09"): [(3 / 16, 240.0)],
    ("IDEA", "2019-03-29"): [(87 / 38, 12.50)],
    ("BHARTIARTL", "2019-04-23"): [(19 / 67, 220.0)],
}
DIVIDENDS = {
    ("COLPAL", "2017-12-18"): 4.0,
    ("ENGINERSIN", "2017-09-11"): 0.50,
    ("HCLTECH", "2018-08-02"): 2.0,
    ("HINDPETRO", "2018-02-28"): 14.50,
    ("MINDTREE", "2018-10-25"): 3.0,
    ("NHPC", "2019-02-18"): 0.71,
    ("TCS", "2018-10-23"): 4.0,
    ("VAKRANGEE", "2018-09-19"): 0.25,
}
SOURCE_CONVERSION_AVAILABILITY = {
    ("AVANTIFEED", "2018-06-26"): {
        "tradable_date": date(2018, 7, 5),
        "source_url": "https://avantifeeds.com/v2/wp-content/uploads/2021/03/26th-Annual-Report-2018-19.pdf",
    },
}
SOURCE_DEMERGERS = {
    ("GRASIM", "2017-07-19"): {
        "child_symbol": "ABCAPITAL", "child_isin": "INE674K01013", "ratio_num": 7,
        "ratio_den": 5, "listing_date": "2017-09-01",
        "source_urls": ["https://www.msei.in/SX-Content/Circulars/2017/June/Circular-5299.pdf"],
    },
    ("CESC", "2018-10-30"): {
        "record_date": "2018-10-31", "allotment_date": "2018-11-14", "listing_date": "2019-01-25",
        "children": [
            {"child_symbol": "SPENCERS", "child_isin": "INE020801028", "ratio_num": 6, "ratio_den": 10},
            {"child_symbol": "CESCVENT", "child_isin": "INE425Y01011", "ratio_num": 2, "ratio_den": 10},
        ],
        "source_urls": [
            "https://www.msei.in/corporates/corporate-securities-information/corporate-update/default?symbol=CESC&type=4&vmode=vm",
            "https://www.cesc.co.in/storage/uploads/stock_exchange_intimation/NSE_PRESS_121018.pdf",
            "https://www.cesc.co.in/storage/uploads/annreport/CESC_AR_2019.pdf",
            "https://nsearchives.nseindia.com/web/sites/default/files/inline-files/NSE_Market_Pulse_Jan2019_2.pdf",
        ],
    },
    ("FRETAIL", "2017-11-29"): {
        "child_symbol": "PRAXIS", "child_isin": "INE546Y01022", "ratio_num": 1,
        "ratio_den": 20, "listing_date": "2018-01-31",
        "source_urls": ["https://www.bseindia.com/bseplus/AnnualReport/540064/5400640317.pdf",
                        "https://praxisretail.in/assets/download/PRAXIS-Annual-Report-2017-18.pdf",
                        "https://www.bseindia.com/xml-data/corpfiling/AttachHis/48c3486f-2096-45e2-8dad-2ac5edafe59c.pdf"],
    },
}
IDFC_INFERENCE = {
    "vendor_symbol": "IDFCBANK", "vendor_isin": "INE092T01019",
    "debt_isin": "INE092T08352", "classification": "supported_debt_event_inference",
}
SOURCE_DEBT_EVENTS = {
    ("IDFCBANK", "2018-02-28"): {"series": "HB", "record_date": "2018-03-01"},
    ("IDFCBANK", "2018-03-08"): {"series": "HD", "record_date": "2018-03-09"},
    ("IDFCBANK", "2019-02-28"): {"series": "HB", "record_date": "2019-03-01"},
    ("IDFCBANK", "2019-03-14"): {"series": "HD", "record_date": "2019-03-15"},
}
SOURCE_DEBT_DISTRIBUTIONS = {
    ("BRITANNIA", "2019-08-22"): {
        "record_date": "2019-08-23", "allotment_date": "2019-08-28",
        "security_isin": "INE216A07052", "debentures_per_share": 1,
        "face_value_inr": 30.0, "coupon_rate": 0.08, "coupon_payments": 3,
        "redemption_date": "2022-08-26",
        "valuation_bound": "undiscounted contractual cash flows at non-negative required yield",
        "source_urls": [
            "https://www.nseindia.com/companies-listing/corporate-filings-actions?symbol=BRITANNIA",
            "https://nsearchives.nseindia.com/corporate/BRITANNIA_28082019165059_OUTCOMEBONUSDEBENTURECOMMITTEEALLOTMENT_260.pdf",
            "https://www.bseindia.com/bseplus/annualreport/500825/5008250320.pdf",
        ],
    },
}
CONFIGURATIONS = ("NIFTY200-A-M", "NIFTY200-A-Q", "NIFTY200-B-M", "NIFTY200-B-Q")


def source_child_series() -> pd.Series:
    history = pd.read_parquet(audit.PUBLIC / "tejhq" / "symbol_history" / "nse.parquet")
    isins = history.loc[history["symbol"].astype(str).str.upper().eq("RHFL"), "isin"].dropna().astype(str).unique()
    if len(isins) != 1:
        raise ValueError(f"RHFL needs one dated identity; found {isins.tolist()}")
    files = sorted(audit.RAW_DIR.glob("year=*/nse_*.parquet"))
    raw = ds.dataset([str(path) for path in files], format="parquet").to_table(
        columns=["date", "isin", "series", "close"], filter=ds.field("isin").isin(isins.tolist())
    ).to_pandas()
    raw["date"] = pd.to_datetime(raw["date"]).dt.normalize()
    raw = raw.loc[raw["series"].isin({"EQ", "BE"})].drop_duplicates("date")
    return pd.to_numeric(raw.set_index("date")["close"], errors="coerce").sort_index()


def setup():
    cache_manifest = audit.verify_signal_cache()
    sessions, intervals, data, actions, symbols, reviewed, unreviewed, canonical, history = audit.load_data()
    signals = pd.read_csv(DETAIL / "signal_dependencies.csv", dtype=str).fillna("")
    signals["score"] = pd.to_numeric(signals["score"], errors="coerce")
    signals["rank"] = pd.to_numeric(signals["rank"], errors="coerce")
    signals["unresolved_dependency_keys"] = signals["unresolved_dependency_keys"].map(json.loads)
    dependency_rows = pd.read_csv(DETAIL / "unresolved_dependencies.csv", dtype=str).fillna("")
    dependency_records = {row["dependency_key"]: row.to_dict() for _, row in dependency_rows.iterrows()}
    if not all(audit.dependency_key(row) == key for key, row in dependency_records.items()):
        raise ValueError("unresolved dependency key does not match its pinned source record")
    index = {day: i for i, day in enumerate(sessions)}
    by_canonical = {}
    for name, group in data.groupby("canonical", sort=False):
        frame = group[["date", "close", "adj_close", "adj_factor_cumulative"]]
        frame = frame.sort_values("date").drop_duplicates("date").set_index("date").reindex(sessions)
        by_canonical[name] = frame
    account_data = data[["date", "isin", "symbol", "canonical", "open", "close",
                         "adj_factor_cumulative"]].copy()
    return sessions, account_data, actions, signals, index, by_canonical, source_child_series(), dependency_records, cache_manifest


def interval_return(parent: pd.DataFrame, child: pd.Series, start: pd.Timestamp,
                    end: pd.Timestamp) -> float:
    demerger = pd.Timestamp("2017-09-05")
    dividend_date = pd.Timestamp("2017-09-21")
    if start not in parent.index or end not in parent.index:
        raise ValueError("RELCAPITAL endpoint missing from the source-session calendar")
    p0, p1 = float(parent.at[start, "close"]), float(parent.at[end, "close"])
    if not np.isfinite([p0, p1]).all() or min(p0, p1) <= 0:
        raise ValueError("RELCAPITAL endpoint close missing or invalid")
    initial = p0
    q_child = 0.0
    if start < demerger <= end:
        q_child = 1.0
    q_parent = 1.0
    if start < dividend_date <= end:
        ex_close = parent.at[dividend_date, "close"]
        if not np.isfinite(ex_close) or ex_close <= 0:
            raise ValueError("RELCAPITAL dividend ex-date close missing")
        q_parent += 10.50 / float(ex_close)
    final = q_parent * p1
    if q_child:
        child_close = child.get(end, np.nan)
        if not np.isfinite(child_close) or child_close <= 0:
            raise ValueError(f"RHFL endpoint mark missing on {end.date()}")
        final += float(child_close)
    return final / initial - 1.0


def demerger_interval_return(parent: pd.DataFrame, child: pd.DataFrame | dict, start: pd.Timestamp,
                             end: pd.Timestamp, event: dict) -> float:
    if start not in parent.index or end not in parent.index:
        raise ValueError("demerger parent endpoint missing from the source-session calendar")
    p0, p1 = float(parent.at[start, "adj_close"]), float(parent.at[end, "adj_close"])
    if not np.isfinite([p0, p1]).all() or min(p0, p1) <= 0:
        raise ValueError("demerger parent adjusted endpoint missing or invalid")
    ex_date = pd.Timestamp(event["ex_date"])
    child_terms = event.get("children") or [{"child_symbol": event.get("child_symbol", "child"),
                                               "child_isin": event.get("child_isin"),
                                               "ratio_num": event["ratio_num"],
                                               "ratio_den": event["ratio_den"],
                                               "listing_date": event.get("listing_date")}]
    child_value = 0.0
    if start < ex_date <= end:
        for terms in child_terms:
            series = child.get(terms["child_isin"]) if isinstance(child, dict) else child
            if series is None or end not in series.index:
                raise ValueError(f"{terms['child_symbol']} endpoint missing from the source-session calendar")
            child_close = float(series.at[end, "adj_close"])
            if not np.isfinite(child_close) or child_close <= 0:
                raise ValueError(f"{terms['child_symbol']} adjusted endpoint missing on {end.date()}")
            child_value += terms["ratio_num"] / terms["ratio_den"] * child_close
    return (p1 + child_value) / p0 - 1.0


def demerger_volatility_lower_bound(parent: pd.DataFrame, child: pd.DataFrame | dict,
                                    window: list[pd.Timestamp], event: dict,
                                    total_return: float) -> float | None:
    ex_date = pd.Timestamp(event["ex_date"])
    parent_close = parent["adj_close"].reindex(window).to_numpy(dtype=float)
    combined = parent_close.copy()
    child_terms = event.get("children") or [{"child_symbol": event.get("child_symbol", "child"),
                                               "child_isin": event.get("child_isin"),
                                               "ratio_num": event["ratio_num"],
                                               "ratio_den": event["ratio_den"],
                                               "listing_date": event.get("listing_date")}]
    listing_dates = []
    if not np.isfinite(parent_close).all():
        return None
    for terms in child_terms:
        child_frame = child.get(terms["child_isin"]) if isinstance(child, dict) else child
        if child_frame is None:
            return None
        listing_date = pd.Timestamp(terms.get("listing_date") or event["listing_date"])
        listing_dates.append(listing_date)
        child_close = child_frame["adj_close"].reindex(window).to_numpy(dtype=float)
        listed = np.asarray(window) >= listing_date
        if not np.isfinite(child_close[listed]).all():
            return None
        combined[listed] += terms["ratio_num"] / terms["ratio_den"] * child_close[listed]
    if (combined <= 0).any():
        return None
    returns = np.diff(np.log(combined))
    return_dates = window[1:]
    unknown = np.asarray([any(ex_date <= day <= listed_through for listed_through in listing_dates)
                          for day in return_dates])
    known_returns, unknown_count = returns[~unknown], int(unknown.sum())
    if unknown_count == 0 or total_return <= -1:
        return None
    unknown_sum = np.log1p(total_return) - float(known_returns.sum())
    minimum_path = np.concatenate((known_returns, np.repeat(unknown_sum / unknown_count, unknown_count)))
    volatility = float(np.std(minimum_path, ddof=1) * np.sqrt(252))
    return volatility if np.isfinite(volatility) and volatility > 0 else None


def score_with_corrections(candidate: str, day: pd.Timestamp, row: pd.Series,
                           sessions: list[pd.Timestamp], index: dict, series_by_canonical: dict,
                           raw_child: pd.Series, event_log: list[dict],
                           free_right: tuple[str, str] | None = None) -> tuple[float | None, dict]:
    symbol, canon = str(row["symbol"]).upper(), str(row["canonical"])
    rule = candidate.split("-")[1]
    if canon == IDFC_INFERENCE["vendor_isin"]:
        i = index[day]
        start_i = i - (273 if rule == "B" else 252)
        end_i = i - 21
        debt_events = [{"source_symbol": event_symbol, "event_isin": canon,
                        "ex_date": date_text, **terms}
                       for (event_symbol, date_text), terms in SOURCE_DEBT_EVENTS.items()
                       if start_i <= index.get(pd.Timestamp(date_text), -1) <= end_i]
        if debt_events:
            return float(row["score"]), {"method": "official_nse_listed_debt_interest_not_common_equity_return",
                                         "score_status": "VALID_SCORE", "source_debt_events": debt_events,
                                         "source_url": "https://www.nseindia.com/companies-listing/corporate-filings-actions?symbol=IDFCFIRSTB"}
    for (event_symbol, date_text), event in SOURCE_DEMERGERS.items():
        if event_symbol != symbol:
            continue
        i = index[day]
        end_i = i - 21
        end = sessions[end_i]
        ex_date = pd.Timestamp(date_text)
        volatility_start = i - (273 if rule == "B" else 252)
        ex_i = index.get(ex_date, -1)
        if not volatility_start <= ex_i <= end_i:
            continue
        parent = series_by_canonical[canon]
        child_terms = event.get("children") or [{"child_symbol": event["child_symbol"],
                                                  "child_isin": event["child_isin"],
                                                  "ratio_num": event["ratio_num"],
                                                  "ratio_den": event["ratio_den"],
                                                  "listing_date": event["listing_date"]}]
        children = {terms["child_isin"]: series_by_canonical.get(terms["child_isin"])
                    for terms in child_terms}
        source_event = {**event, "ex_date": date_text}
        if any(frame is None for frame in children.values()):
            return None, {"method": "source_demerger_child_series_missing", "score_status": "UNKNOWN_DATA",
                          "source_demerger": source_event}
        if ex_i < 1:
            return None, {"method": "source_demerger_ex_date_not_on_source_calendar", "score_status": "UNKNOWN_DATA"}
        pre_factor, ex_factor = (float(parent.iloc[position]["adj_factor_cumulative"])
                                 for position in (ex_i - 1, ex_i))
        pre_close, ex_close = (float(parent.iloc[position]["close"]) for position in (ex_i - 1, ex_i))
        pre_adjusted, ex_adjusted = (float(parent.iloc[position]["adj_close"]) for position in (ex_i - 1, ex_i))
        if (not np.isfinite([pre_factor, ex_factor, pre_close, ex_close, pre_adjusted, ex_adjusted]).all()
                or min(pre_factor, ex_factor, pre_close, ex_close) <= 0
                or not np.isclose(ex_factor / pre_factor, 1.0, rtol=1e-8, atol=1e-10)
                or not np.isclose(pre_close * pre_factor, pre_adjusted, rtol=1e-6, atol=0.01)
                or not np.isclose(ex_close * ex_factor, ex_adjusted, rtol=1e-6, atol=0.01)):
            return None, {"method": "source_demerger_provider_factor_or_raw_unit_check_failed",
                          "score_status": "UNKNOWN_DATA"}
        unlisted_at_endpoint = [terms["child_symbol"] for terms in child_terms
                                if end < pd.Timestamp(terms.get("listing_date") or event["listing_date"])]
        if unlisted_at_endpoint:
            return None, {"method": "source_demerger_child_unlisted_at_signal_endpoint",
                          "score_status": "UNKNOWN_DATA", "source_demerger": source_event,
                          "unlisted_children": unlisted_at_endpoint,
                          "endpoint_date": end.date().isoformat()}
        if rule == "A":
            value = demerger_interval_return(parent, children, sessions[i - 252], end, source_event)
            return value, {"method": "source_endpoint_parent_plus_demerger_child_total_wealth",
                           "score_status": "VALID_SCORE", "source_demerger": source_event,
                           "child_endpoint_values": {terms["child_symbol"]: float(
                               children[terms["child_isin"]].at[end, "adj_close"]) for terms in child_terms}}
        ret12 = demerger_interval_return(parent, children, sessions[i - 252], end, source_event)
        ret6 = demerger_interval_return(parent, children, sessions[i - 126], end, source_event)
        numerator = (ret6 + ret12) / 2
        details = {"method": "B_source_total_return_numerator_volatility_unknown_prelisting_child_marks",
                   "score_status": "UNKNOWN_DATA", "source_demerger": source_event,
                   "ret6": ret6, "ret12": ret12, "return_numerator": numerator,
                   "selection_bound": "NONPOSITIVE" if numerator <= 0 else "MATERIAL_UNKNOWN"}
        if numerator > 0:
            volatility_return = demerger_interval_return(
                parent, children, sessions[volatility_start], end, source_event)
            volatility_lower_bound = demerger_volatility_lower_bound(
                parent, children, sessions[volatility_start:end_i + 1], source_event, volatility_return)
            if volatility_lower_bound is not None:
                details.update({"annualized_volatility_lower_bound": volatility_lower_bound,
                                "score_upper_bound": numerator / volatility_lower_bound,
                                "bound_method": "minimum sample volatility: observed pre-ex and listed-child returns fixed; unobserved claim-period returns equalized subject to source-based total wealth over the exact 252-return volatility window"})
        return None, details
    if symbol == "RELCAPITAL":
        parent = series_by_canonical[canon]
        i = index[day]
        end = sessions[i - 21]
        start12 = sessions[i - 252]
        ret12 = interval_return(parent, raw_child, start12, end)
        if candidate.endswith("-Q") or candidate.endswith("-M"):
            if candidate.split("-")[1] == "A":
                return ret12, {"method": "source_total_wealth_parent_plus_1_RHFL_and_reinvested_10_50_dividend",
                               "ret12": ret12, "score_status": "VALID_SCORE"}
            start6 = sessions[i - 126]
            ret6 = interval_return(parent, raw_child, start6, end)
            numerator = (ret6 + ret12) / 2
            return None, {"method": "B_volatility_not_calculated_missing_RHFL_prelisting_daily_marks",
                          "ret6": ret6, "ret12": ret12, "return_numerator": numerator,
                          "selection_bound": "NONPOSITIVE" if numerator <= 0 else "MATERIAL_UNKNOWN",
                          "score_status": "UNKNOWN_DATA"}

    frame = series_by_canonical[canon]
    prices = pd.to_numeric(frame["adj_close"], errors="coerce").to_numpy(dtype=float).copy()
    raw_close = pd.to_numeric(frame["close"], errors="coerce").to_numpy(dtype=float)
    factors = pd.to_numeric(frame["adj_factor_cumulative"], errors="coerce").to_numpy(dtype=float)
    i = index[day]
    offset = 252 if candidate.split("-")[1] == "A" else 273
    first, last = i - offset, i - 21
    corrections = []
    for (event_symbol, date_text), tranches in RIGHTS.items():
        if symbol != event_symbol:
            continue
        ex = pd.Timestamp(date_text)
        ex_i = index.get(ex)
        if ex_i is None or not first <= ex_i <= last:
            continue
        if not np.isfinite(raw_close[ex_i - 1]) or not np.isfinite(factors[[ex_i - 1, ex_i]]).all():
            raise ValueError(f"{symbol} rights source rows missing at {ex.date()}")
        ratio = sum(r for r, _ in tranches)
        cash = sum(r * (0.0 if free_right == (symbol, date_text) else issue) for r, issue in tranches)
        prior = raw_close[ex_i - 1]
        terp = (prior + cash) / (1 + ratio)
        expected = prior / terp
        observed = factors[ex_i] / factors[ex_i - 1]
        adjustment = expected / observed
        prices[ex_i:] *= adjustment
        event = {"candidate_id": candidate, "signal_date": day.date().isoformat(), "symbol": symbol,
                 "ex_date": date_text, "event": "rights", "prior_raw_close_inr": prior,
                 "ratio_new_per_old": ratio, "full_subscription_cash_per_old_share_inr": cash,
                 "terp_inr": terp, "provider_factor_multiplier": observed,
                 "source_factor_multiplier": expected, "applied_signal_multiplier": adjustment}
        corrections.append(event)
    for (event_symbol, date_text), amount in DIVIDENDS.items():
        if symbol != event_symbol:
            continue
        ex = pd.Timestamp(date_text)
        ex_i = index.get(ex)
        if ex_i is None or not first <= ex_i <= last:
            continue
        if not np.isfinite(raw_close[ex_i - 1]) or not np.isfinite(factors[[ex_i - 1, ex_i]]).all():
            raise ValueError(f"{symbol} dividend source rows missing at {ex.date()}")
        prior = raw_close[ex_i - 1]
        expected = prior / (prior - amount)
        observed = factors[ex_i] / factors[ex_i - 1]
        adjustment = expected / observed
        prices[ex_i:] *= adjustment
        corrections.append({"candidate_id": candidate, "signal_date": day.date().isoformat(), "symbol": symbol,
                            "ex_date": date_text, "event": "dividend", "prior_raw_close_inr": prior,
                            "cash_per_share_inr": amount, "provider_factor_multiplier": observed,
                            "source_factor_multiplier": expected, "applied_signal_multiplier": adjustment})
    baseline_prices = pd.to_numeric(frame["adj_close"], errors="coerce").to_numpy(dtype=float)
    baseline, baseline_reason = audit.score_at(baseline_prices, i, rule)
    if baseline_reason or not np.isclose(baseline, float(row["score"]), rtol=1e-8, atol=1e-10):
        raise AssertionError(f"source score does not reproduce for {candidate} {symbol} {day.date()}")
    for (event_symbol, date_text), terms in SOURCE_DEBT_DISTRIBUTIONS.items():
        ex_i = index.get(pd.Timestamp(date_text))
        if symbol != event_symbol or ex_i is None or not first < ex_i <= last:
            continue
        if (ex_i == 0 or not np.isfinite(factors[ex_i - 1:last + 1]).all()
                or not np.isfinite(raw_close[ex_i - 1:last + 1]).all()
                or not np.isclose(factors[ex_i] / factors[ex_i - 1], 1.0, rtol=1e-8, atol=1e-10)
                or not np.allclose(raw_close[ex_i - 1:last + 1] * factors[ex_i - 1:last + 1],
                                   baseline_prices[ex_i - 1:last + 1], rtol=1e-6, atol=0.01)
                or not np.allclose(factors[ex_i:last + 1], factors[ex_i], rtol=1e-8, atol=1e-10)):
            return None, {"method": "source_bonus_debenture_bound_price_or_factor_scope_unverified",
                          "score_status": "UNKNOWN_DATA"}
        max_value = terms["face_value_inr"] * (
            1 + terms["coupon_rate"] * terms["coupon_payments"])
        claim_value = max_value * factors[ex_i]
        event = {"symbol": event_symbol, "ex_date": date_text, "event": "bonus",
                 "security_isin": terms["security_isin"], "maximum_contractual_cashflows_inr": max_value,
                 "adjusted_unit_bound_inr": claim_value, "valuation_bound": terms["valuation_bound"],
                 "source_urls": terms["source_urls"]}
        corrections.append(event)

        def upper_return(start_i: int) -> float:
            bonus_value = claim_value if start_i < ex_i <= last else 0.0
            return float((prices[last] + bonus_value) / prices[start_i] - 1)

        if rule == "A":
            numerator = upper_return(first)
        else:
            numerator = (upper_return(i - 126) + upper_return(i - 252)) / 2
        if numerator <= 0:
            return None, {"method": "source_contractual_debenture_cashflow_upper_bound",
                          "score_status": "UNKNOWN_DATA", "return_numerator": numerator,
                          "selection_bound": "NONPOSITIVE", "corrections": corrections,
                          "source_debt_distributions": [event]}
        return None, {"method": "source_contractual_debenture_cashflow_upper_bound_not_decisive",
                      "score_status": "UNKNOWN_DATA", "return_numerator": numerator,
                      "selection_bound": "MATERIAL_UNKNOWN", "corrections": corrections,
                      "source_debt_distributions": [event]}
    value, reason = audit.score_at(prices, i, rule)
    if reason:
        return None, {"method": reason, "score_status": "UNKNOWN_DATA"}
    event_log.extend(corrections)
    end = i - 21
    base_vol = corrected_vol = None
    if rule == "B":
        base_returns = np.diff(np.log(baseline_prices[i - 273:end + 1]))
        corrected_returns = np.diff(np.log(prices[i - 273:end + 1]))
        base_vol = float(np.std(base_returns, ddof=1) * np.sqrt(252) * 100)
        corrected_vol = float(np.std(corrected_returns, ddof=1) * np.sqrt(252) * 100)
    free_value = None
    free_vol = None
    if free_right is None:
        event_rights = next(((sym, day_text) for (sym, day_text) in RIGHTS
                             if sym == symbol and index.get(pd.Timestamp(day_text), -1) in range(first, last + 1)), None)
        if event_rights:
            free_value, free_details = score_with_corrections(candidate, day, row, sessions, index,
                                                              series_by_canonical, raw_child, [],
                                                              free_right=event_rights)
            free_vol = free_details.get("annualized_volatility_pct")
    return value, {"method": "registered_source_TER P_and_dividend_factor", "corrections": corrections,
                   "score_status": "VALID_SCORE", "free_right_score_sensitivity": free_value,
                   "annualized_volatility_pct": corrected_vol,
                   "baseline_annualized_volatility_pct": base_vol,
                   "corrected_annualized_volatility_pct": corrected_vol,
                   "free_right_annualized_volatility_pct": free_vol,
                   "volatility_delta_pct": corrected_vol - base_vol if base_vol is not None else None}


def exact_dependency_resolutions(candidate: str, row: pd.Series, details: dict,
                                 dependency_records: dict[str, dict]) -> tuple[list[str], list[dict]]:
    resolved = []
    unmatched = []
    corrections = details.get("corrections", [])
    for key in row.get("unresolved_dependency_keys", []):
        dependency = dependency_records.get(key)
        if dependency is None:
            unmatched.append({"key": key, "reason": "dependency key missing from pinned dependency ledger"})
            continue
        symbol = str(dependency.get("entity", "")).split("|", 1)[0].upper()
        kind = str(dependency.get("input", ""))
        event_date = str(dependency.get("date", ""))
        correction_match = any(
            str(item.get("symbol", "")).upper() == symbol
            and str(item.get("ex_date", "")) == event_date
            and (kind == f"signal_{item.get('event', '')}"
                 or (kind == "signal_adjustment_factor" and item.get("event") in {"rights", "dividend"}))
            for item in corrections
        )
        relcapital_match = (
            symbol == "RELCAPITAL" and kind == "signal_other" and event_date == "2017-09-05"
            and (details.get("method", "").startswith("source_total_wealth_parent_plus_1_RHFL")
                 or (details.get("selection_bound") == "NONPOSITIVE"
                     and details.get("method", "").startswith("B_volatility_not_calculated_missing_RHFL")))
        )
        idfc_match = (
            symbol == IDFC_INFERENCE["vendor_symbol"] and kind == "signal_other"
            and event_date == "2017-12-14" and "INE092T01019" in str(dependency.get("entity", ""))
        )
        source_debt_match = (
            IDFC_INFERENCE["vendor_isin"] in str(dependency.get("entity", ""))
            and kind == "signal_other"
            and any(item.get("event_isin") == IDFC_INFERENCE["vendor_isin"]
                    and item.get("ex_date") == event_date
                    for item in details.get("source_debt_events", []))
        )
        source_demerger = details.get("source_demerger", {})
        demerger_match = (
            source_demerger.get("ex_date") == event_date
            and (source_demerger.get("child_isin") or source_demerger.get("children"))
            and kind in {"signal_other", "signal_demerger"}
        )
        if correction_match or relcapital_match or idfc_match or source_debt_match or demerger_match:
            resolved.append(key)
        else:
            unmatched.append({"key": key, "input": kind, "date": event_date,
                              "entity": dependency.get("entity", ""),
                              "reason": dependency.get("reason", "unresolved source dependency")})
    return resolved, unmatched


def choose_target(candidate: str, day: pd.Timestamp, prior: list[str], sessions: list[pd.Timestamp], signals: pd.DataFrame,
                  index: dict, series_by_canonical: dict, child: pd.Series,
                  correction_log: list[dict], dependency_records: dict[str, dict] | None = None) -> dict:
    dependency_records = dependency_records or {}
    rows = signals.loc[signals["candidate_id"].eq(candidate)
                       & signals["signal_date"].eq(day.date().isoformat())].copy()
    entries, unresolved, selection_bounds, bounded_unknown = [], [], [], []
    for _, row in rows.iterrows():
        status = row["score_status"]
        score = row["score"]
        details = {}
        if status == "VALID_SCORE":
            score = float(score)
        elif status == "RULE_INELIGIBLE":
            continue
        elif np.isfinite(score):
            score, details = score_with_corrections(candidate, day, row, sessions, index, series_by_canonical,
                                                    child, correction_log)
            resolved_keys, unmatched_keys = exact_dependency_resolutions(candidate, row, details, dependency_records)
            if details.get("selection_bound") == "NONPOSITIVE" and score is None:
                if resolved_keys and not unmatched_keys:
                    selection_bounds.append({"symbol": row["symbol"], "reason": details["method"],
                                             "return_numerator": details["return_numerator"],
                                             "selection_bound": "NONPOSITIVE; cannot displace a positive target",
                                             "source_debt_distributions": details.get("source_debt_distributions", []),
                                             "resolved_dependency_keys": resolved_keys})
                    continue
                unresolved.append({"symbol": row["symbol"], "reason": row["unresolved_reason"],
                                   "unmatched_dependency_keys": unmatched_keys, **details})
                continue
            if (score is None and details.get("score_upper_bound") is not None
                    and resolved_keys and not unmatched_keys):
                bounded_unknown.append({"row": row, "details": details,
                                        "resolved_dependency_keys": resolved_keys})
                continue
            if details.get("score_status") == "UNKNOWN_DATA" or unmatched_keys or not resolved_keys:
                unresolved.append({"symbol": row["symbol"], "reason": row["unresolved_reason"],
                                   "unmatched_dependency_keys": unmatched_keys, **details})
                continue
            details["resolved_dependency_keys"] = resolved_keys
        else:
            unresolved.append({"symbol": row["symbol"], "reason": row["unresolved_reason"],
                               "unmatched_dependency_keys": [
                                   {"key": key, **dependency_records.get(key, {"reason": "dependency key missing"})}
                                   for key in row.get("unresolved_dependency_keys", [])]})
            continue
        if row["symbol"] == "IDFCBANK" and status == "UNKNOWN_DATA":
            details["classification"] = IDFC_INFERENCE
            details["classification_caveat"] = "exact original vendor event notice not located; event/debt match remains an inference"
        if status == "UNKNOWN_DATA" and np.isfinite(row["score"]):
            details["vendor_score"] = float(row["score"])
            details["corrected_score"] = float(score)
            details["score_delta"] = float(score) - float(row["score"])
            for event in details.get("corrections", []):
                event["vendor_score"] = float(row["score"])
                event["corrected_score"] = float(score)
                event["score_delta"] = float(score) - float(row["score"])
                event["free_right_score_sensitivity"] = details.get("free_right_score_sensitivity")
        entries.append({"canonical": row["canonical"], "symbol": row["symbol"], "isin": row["isin"],
                        "score": float(score), "status": status, **details})
    positive = sorted((r for r in entries if r["score"] > 0), key=lambda r: (-r["score"], r["isin"]))
    rank = {r["canonical"]: n for n, r in enumerate(positive, 1)}
    for item in bounded_unknown:
        row, details = item["row"], item["details"]
        retention_limit = 25 if str(row["canonical"]) in prior else 20
        threshold = positive[retention_limit - 1]["score"] if len(positive) >= retention_limit else None
        score_upper_bound = float(details["score_upper_bound"])
        if threshold is not None and score_upper_bound < threshold:
            selection_bounds.append({"symbol": row["symbol"], "reason": details["method"],
                                     "return_numerator": details["return_numerator"],
                                     "annualized_volatility_lower_bound": details["annualized_volatility_lower_bound"],
                                     "score_upper_bound": score_upper_bound,
                                     "exclusion_threshold": threshold,
                                     "rank_limit": retention_limit,
                                     "selection_bound": "conservative score upper bound below top-20 or held-name rank-25 threshold",
                                     "bound_method": details["bound_method"],
                                     "resolved_dependency_keys": item["resolved_dependency_keys"]})
        else:
            unresolved.append({"symbol": row["symbol"], "reason": row["unresolved_reason"],
                               "unmatched_dependency_keys": [], **details})
    retained = sorted({name for name in prior if name in rank and rank[name] <= 25},
                      key=lambda name: (rank[name], name))[:20]
    target = list(retained)
    for row in positive:
        if len(target) == 20:
            break
        if row["canonical"] not in target:
            target.append(row["canonical"])
    if len(target) != 20:
        unresolved.append({"reason": f"only {len(target)} source-supported positive slots"})
    cutoff = positive[19]["score"] if len(positive) >= 20 else None
    certified = not unresolved and len(target) == 20
    source_exceptions = [{"symbol": r["symbol"], "vendor_score": r.get("vendor_score"),
                          "corrected_score": r.get("corrected_score", r["score"]),
                          "score_delta": r.get("score_delta", 0.0),
                          "method": r.get("method"), "source_debt_events": r.get("source_debt_events"),
                          "source_demerger": r.get("source_demerger"),
                          "free_right_score_sensitivity": r.get("free_right_score_sensitivity"),
                          "baseline_annualized_volatility_pct": r.get("baseline_annualized_volatility_pct"),
                          "corrected_annualized_volatility_pct": r.get("corrected_annualized_volatility_pct"),
                          "free_right_annualized_volatility_pct": r.get("free_right_annualized_volatility_pct"),
                          "volatility_delta_pct": r.get("volatility_delta_pct"),
                          "free_right_sensitivity_crosses_cutoff": bool(
                              cutoff is not None and r.get("free_right_score_sensitivity") is not None
                              and r["free_right_score_sensitivity"] >= cutoff),
                          "classification": r.get("classification"),
                          "classification_caveat": r.get("classification_caveat"),
                          "resolved_dependency_keys": r.get("resolved_dependency_keys", []),
                          "corrections": [{k: v for k, v in event.items() if k not in {"candidate_id", "signal_date"}}
                                          for event in r.get("corrections", [])]}
                         for r in entries if r["status"] == "UNKNOWN_DATA"]
    ineligible = rows.loc[rows["score_status"].eq("RULE_INELIGIBLE"),
                          ["symbol", "isin", "unresolved_reason"]].to_dict(orient="records")
    return {"candidate_id": candidate, "signal_date": day.date().isoformat(),
            "target_status": "CERTIFIED_UNDER_REGISTERED_SOURCE_CORRECTIONS" if certified else "BLOCKED",
            "signal_rows": int(len(rows)), "rule_ineligible_count": int(rows["score_status"].eq("RULE_INELIGIBLE").sum()),
            "resolved_source_exception_count": sum(r["status"] == "UNKNOWN_DATA" for r in entries),
            "twentieth_positive_score": cutoff, "positive_known_scores": len(positive),
            "ineligible": ineligible, "source_resolved_exceptions": source_exceptions,
            "retained_from_prior": [next(r["symbol"] for r in entries if r["canonical"] == name) for name in retained],
            "selected": [{"symbol": next(r["symbol"] for r in entries if r["canonical"] == name),
                          "canonical": name, "score": next(r["score"] for r in entries if r["canonical"] == name)}
                         for name in target],
            "selection_bounds": selection_bounds, "unresolved": unresolved,
            "ranking_policy": "positive score descending; ISIN ascending tie-break; retain prior names ranked 1-25 then fill to 20"}


def action_gate(candidate: str, targets_by_signal: dict, actions: pd.DataFrame,
                data: pd.DataFrame, sessions: list[pd.Timestamp], start: date, end: date,
                claim_scenario: str = "base"):
    wanted = set().union(*(set(items) for items in targets_by_signal.values()))
    action_rows = actions.loc[actions["ex_date"].between(pd.Timestamp(start), pd.Timestamp(end))].copy()
    action_rows = action_rows.drop_duplicates([column for column in
        ("symbol", "isin", "ex_date", "type", "cash_amount", "ratio_num", "ratio_den",
         "face_value_from", "face_value_to") if column in action_rows.columns])
    distributions, payment_dates, claim_events, share_conversions, blockers = [], {}, [], [], []
    term_fields = ["cash_amount", "ratio_num", "ratio_den", "face_value_from", "face_value_to", "raw_subject"]
    active_targets = []
    for signal_text, target in targets_by_signal.items():
        signal_index = sessions.index(pd.Timestamp(signal_text))
        if signal_index + 1 < len(sessions):
            active_targets.append((sessions[signal_index + 1], set(target)))
    for _, event in action_rows.iterrows():
        kind = str(event["type"]).lower()
        if kind in {"agm", "meeting", "buyback"}:
            continue
        event_date = pd.Timestamp(event["ex_date"]).normalize()
        # The schedule limits identity checks; _simulate reads the actual shares before ex-date orders.
        active = [(execution, target) for execution, target in active_targets if execution < event_date]
        if not active:
            continue
        held_before_open = max(active, key=lambda item: item[0])[1]
        symbol = str(event.get("resolved_symbol", "")).upper()
        vendor_symbol = str(event.get("symbol", "")).upper()
        event_isin = str(event.get("isin", "")).upper()
        identity_rows = data.loc[data["date"].lt(event_date)]
        by_symbol = set(identity_rows.loc[identity_rows["symbol"].eq(symbol or vendor_symbol), "canonical"].dropna())
        by_isin = set(identity_rows.loc[identity_rows["isin"].eq(event_isin), "canonical"].dropna())
        identities = (by_symbol | by_isin) & held_before_open
        if not identities:
            continue
        if len(identities) != 1 or (symbol and by_symbol and by_isin and by_symbol.isdisjoint(by_isin)):
            blockers.append({"date": event_date.date().isoformat(), "symbol": vendor_symbol or symbol,
                             "event": kind, "entity": event_isin,
                             "reason": "relevant corporate-action identity is ambiguous against the pre-open held position",
                             "held_candidates": sorted(identities), "input": "action_identity"})
            continue
        canon = next(iter(identities))
        if not symbol and len(by_isin) != 1:
            blockers.append({"date": event_date.date().isoformat(), "symbol": vendor_symbol,
                             "canonical": canon, "event": kind, "entity": event_isin,
                             "reason": "relevant action has no verified date-valid identity",
                             "input": "action_identity"})
            continue
        debt_terms = SOURCE_DEBT_EVENTS.get((symbol, event_date.date().isoformat()))
        record_date = pd.to_datetime(event.get("record_date"), errors="coerce")
        if (debt_terms and kind == "other" and event_isin == "INE092T01019"
                and str(event.get("raw_subject", "")).strip().lower() == "interest payment"
                and pd.notna(record_date) and record_date.date().isoformat() == debt_terms["record_date"]):
            continue
        if kind == "dividend":
            amount = pd.to_numeric(pd.Series([event.get("cash_amount")]), errors="coerce").iloc[0]
            if not np.isfinite(amount) or amount < 0:
                blockers.append({"date": event_date.date().isoformat(), "symbol": vendor_symbol,
                                 "canonical": canon, "event": kind, "entity": event_isin,
                                 "reason": "held dividend has no source-supported non-negative amount",
                                 "input": "dividend_entitlement"})
                continue
            distribution = (canon, event_date.date(), float(amount))
            distributions.append(distribution)
            payment_dates[distribution[:2]] = event_date.date() + timedelta(days=DIVIDEND_DELAY_DAYS)
            continue
        if kind in {"split", "bonus"}:
            term_rows = action_rows.loc[
                action_rows["symbol"].eq(event.get("symbol"))
                & action_rows["isin"].eq(event.get("isin"))
                & action_rows["ex_date"].eq(event["ex_date"])
                & action_rows["type"].eq(event["type"]), [field for field in term_fields if field in action_rows.columns],
            ].drop_duplicates()
            prior_days = [day for day in sessions if day < event_date]
            before = data.loc[data["canonical"].eq(canon) & data["date"].eq(prior_days[-1])] if prior_days else data.iloc[0:0]
            on_ex = data.loc[data["canonical"].eq(canon) & data["date"].eq(event_date)]
            if len(term_rows) != 1 or len(before) != 1 or len(on_ex) != 1:
                blockers.append({"date": event_date.date().isoformat(), "symbol": vendor_symbol,
                                 "canonical": canon, "event": kind, "entity": event_isin,
                                 "reason": "share conversion lacks one unambiguous term and adjacent identity/price/factor rows",
                                 "input": "share_conversion_terms", "term_variants": len(term_rows),
                                 "prior_rows": len(before), "ex_rows": len(on_ex)})
                continue
            prior_row, ex_row = before.iloc[0], on_ex.iloc[0]
            supported, factor_reason = audit.routine_share_factor_check(
                kind, term_rows, float(prior_row["close"]), float(ex_row["close"]),
                float(prior_row["adj_factor_cumulative"]), float(ex_row["adj_factor_cumulative"]))
            if not supported:
                blockers.append({"date": event_date.date().isoformat(), "symbol": vendor_symbol,
                                 "canonical": canon, "event": kind, "entity": event_isin,
                                 "reason": factor_reason, "input": "share_conversion_factor"})
                continue
            term = term_rows.iloc[0]
            availability = SOURCE_CONVERSION_AVAILABILITY.get((vendor_symbol, event_date.date().isoformat()), {})
            if kind == "split":
                split_multiplier = float(term["face_value_from"]) / float(term["face_value_to"])
                subject = str(term.get("raw_subject", ""))
                if "bonus" in subject.lower():
                    bonus_per_split_share = float(term["ratio_num"]) / float(term["ratio_den"])
                    multiplier = split_multiplier * (1 + bonus_per_split_share)
                    conversion_kind = "split_bonus"
                    conversion_fields = {"split_multiplier": split_multiplier,
                                         "bonus_per_split_share": bonus_per_split_share}
                    credit_date, tradable_date = None, availability.get("tradable_date")
                else:
                    multiplier, credit_date, tradable_date = split_multiplier, event_date.date(), event_date.date()
                    conversion_kind, conversion_fields = kind, {}
            else:
                multiplier, credit_date, tradable_date = (
                    1 + float(term["ratio_num"]) / float(term["ratio_den"]), None,
                    availability.get("tradable_date"))
                conversion_kind, conversion_fields = kind, {}
            share_conversions.append({"symbol": canon, "kind": conversion_kind, "ex_date": event_date.date(),
                                      "credit_date": credit_date, "tradable_date": tradable_date,
                                      "share_multiplier": multiplier,
                                      **conversion_fields,
                                      "event_isin": event_isin, "source_subject": str(event.get("raw_subject", "")),
                                      "factor_check": factor_reason,
                                      "tradability_source_status": "verified_ex_date_units" if conversion_kind == "split"
                                      else ("exchange_trading_approval_source_verified" if availability else
                                            "allotment_evidenced_demat_credit_and_exchange_admission_unverified"),
                                      "tradability_source_url": availability.get("source_url", "")})
            continue
        if (vendor_symbol == "ADANIENT" and event_date == pd.Timestamp("2018-04-05")
                and "scheme of arrangement" in str(event.get("raw_subject", "")).lower()):
            parent_rows = data.loc[data["canonical"].eq(canon) & data["date"].le(event_date)].drop_duplicates("date").set_index("date")
            prior_days = [day for day in sessions if day < event_date]
            cum_date = prior_days[-1]
            cum_close = pd.to_numeric(pd.Series([parent_rows["close"].get(cum_date, np.nan)]), errors="coerce").iloc[0]
            ex_close = pd.to_numeric(pd.Series([parent_rows["close"].get(event_date, np.nan)]), errors="coerce").iloc[0]
            if not np.isfinite([cum_close, ex_close]).all() or min(cum_close, ex_close) <= 0:
                blockers.append({"date": event_date.date().isoformat(), "symbol": vendor_symbol,
                                 "canonical": canon, "event": kind, "entity": event_isin,
                                 "reason": "AGEL detached claim needs observed AEL raw closes on 2018-04-04 and 2018-04-05",
                                 "input": "claim_mark"})
                continue
            child_name = AGEL_ISIN
            listing_date = AGEL_LISTING_DATE
            sale_date = AGEL_DISPOSAL_DATE
            detached_mark = (float(cum_close) - float(ex_close)) / float(AGEL_RATIO)
            if detached_mark < 0:
                blockers.append({"date": event_date.date().isoformat(), "symbol": vendor_symbol,
                                 "canonical": canon, "event": "detached_claim_mark",
                                 "reason": "parent cum/ex price difference implies a negative detached mark",
                                 "input": "claim_mark", "cum_close": float(cum_close), "ex_close": float(ex_close)})
                continue
            claim_events.append({"parent_symbol": canon, "child_symbol": child_name,
                                 "ex_date": event_date.date(), "listing_date": listing_date,
                                 "sale_date": sale_date, "ratio": str(AGEL_RATIO),
                                 "detached_unit_mark": detached_mark if claim_scenario == "base" else 0.0,
                                 "base_detached_unit_mark": detached_mark,
                                 "scenario": claim_scenario, "event_isin": event_isin,
                                 "cum_date": cum_date.date().isoformat(),
                                 "cum_close_raw": float(cum_close), "ex_close_raw": float(ex_close)})
            continue
        blockers.append({"date": event_date.date().isoformat(), "symbol": vendor_symbol or symbol,
                         "canonical": canon, "event": kind, "entity": event_isin,
                         "reason": "held-position entitlement or share conversion is not modeled by the cash engine",
                         "source_subject": str(event.get("raw_subject", "")), "input": "held_entitlement"})
    blockers.sort(key=lambda row: (row["date"], row.get("symbol", "")))
    return distributions, payment_dates, claim_events, share_conversions, blockers


def run_account(candidate: str, signals: pd.DataFrame, schedules: list[dict],
                data: pd.DataFrame, actions: pd.DataFrame, sessions: list[pd.Timestamp],
                end_day: str, valuation_scenario: str = "base", slippage_bps: float = SLIPPAGE_BPS,
                signal_blocker: dict | None = None) -> dict:
    if not schedules:
        ending_day = pd.Timestamp(end_day).date().isoformat()
        return {"candidate_id": candidate, "status": "NO_EXECUTION_UNRESOLVED_FIRST_TARGET",
                "actual_order_count": 0, "first_material_blocker": signal_blocker,
                "valuation_scenario": valuation_scenario, "slippage_bps_per_side": slippage_bps,
                "valid_through": ending_day, "starting_capital_inr": CAPITAL,
                "ending_nav_inr": CAPITAL, "ending_cash_inr": CAPITAL, "ending_invested_inr": 0.0,
                "ending_cash_receivable_inr": 0.0, "ending_locked_claim_inr": 0.0,
                "max_drawdown_pct": 0.0, "turnover_inr": 0.0, "fees_inr": 0.0,
                "cagr": "NOT REPORTED: no certified order; cash waiting path only"}
    targets_by_signal = {item["signal_date"]: [r["canonical"] for r in item["selected"]] for item in schedules}
    first_signal_index = sessions.index(pd.Timestamp(schedules[0]["signal_date"]))
    first_fill_index = first_signal_index + 1
    if first_fill_index >= len(sessions):
        return {"candidate_id": candidate, "status": "BLOCKED_BEFORE_FIRST_FILL", "actual_order_count": 0,
                "first_material_blocker": {"date": schedules[0]["signal_date"], "input": "next_session_order",
                                           "reason": "no source-session execution date follows the first signal"},
                "valuation_scenario": valuation_scenario, "slippage_bps_per_side": slippage_bps,
                "valid_through": pd.Timestamp(end_day).date().isoformat(), "starting_capital_inr": CAPITAL,
                "ending_nav_inr": CAPITAL, "ending_cash_inr": CAPITAL, "ending_invested_inr": 0.0,
                "ending_cash_receivable_inr": 0.0, "ending_locked_claim_inr": 0.0,
                "max_drawdown_pct": 0.0, "turnover_inr": 0.0, "fees_inr": 0.0}
    first_fill = sessions[first_fill_index].date()
    distributions, payment_dates, claim_events, share_conversions, blockers = action_gate(
        candidate, targets_by_signal, actions, data, sessions, first_fill,
        pd.Timestamp(end_day).date(), valuation_scenario,
    )
    effective_end = pd.Timestamp(end_day)
    if blockers:
        blocker_date = pd.Timestamp(blockers[0]["date"])
        stop_index = sessions.index(blocker_date)
        effective_end = min(effective_end, sessions[stop_index - 1])
    wanted = (set().union(*map(set, targets_by_signal.values()))
              | {event["child_symbol"] for event in claim_events}
              | {event["symbol"] for event in share_conversions})
    wanted = sorted(wanted)
    quote_window = data["date"].between(pd.Timestamp("2018-01-01"), effective_end)
    quotes = data.loc[quote_window & data["canonical"].isin(wanted),
                      ["date", "canonical", "open", "close"]]
    opens = quotes.pivot_table(index="date", columns="canonical", values="open", aggfunc="first").reindex(
        index=sessions, columns=wanted)
    closes = quotes.pivot_table(index="date", columns="canonical", values="close", aggfunc="first").reindex(
        index=sessions, columns=wanted)
    del quotes, quote_window
    claim_gaps = []
    for event in claim_events:
        child = event["child_symbol"]
        for day, column, label, reason in (
            (pd.Timestamp(event["listing_date"]), closes, "claim_mark", "AGEL listing close is missing when valuation reaches listing"),
            (pd.Timestamp(event["sale_date"]), opens, "claim_disposal", "AGEL disposal open is missing when disposal date is reached"),
        ):
            if day > effective_end:
                continue
            if day not in column.index or child not in column.columns or not np.isfinite(column.at[day, child]) or column.at[day, child] <= 0:
                claim_gaps.append({"date": day.date().isoformat(), "symbol": "ADANIGREEN", "canonical": child,
                                   "event": "detached_claim_listing_mark" if label == "claim_mark" else "detached_claim_disposal",
                                   "reason": reason, "input": label})
    if claim_gaps:
        gap = min(claim_gaps, key=lambda row: (row["date"], row["input"]))
        blockers.append(gap)
        claim_day = pd.Timestamp(gap["date"])
        prior_sessions = [day for day in sessions if day < claim_day]
        effective_end = min(effective_end, prior_sessions[-1] if prior_sessions else pd.Timestamp(sessions[0]))
    rebalance = pd.Series(False, index=sessions)
    targets = pd.DataFrame(0.0, index=sessions, columns=wanted)
    for item in schedules:
        signal = pd.Timestamp(item["signal_date"])
        rebalance.loc[signal] = True
        targets.loc[signal, item["canonical_names"]] = 0.05
    exec_end = effective_end
    end_idx = sessions.index(exec_end)
    relevant = sorted(set(pd.Timestamp(x) for x in targets_by_signal))
    issues = []
    current, executions = set(), {}
    for signal in relevant:
        signal_index = sessions.index(signal)
        if signal_index + 1 < len(sessions):
            executions[sessions[signal_index + 1]] = targets_by_signal[signal.date().isoformat()]
    for day in sessions[first_fill_index:end_idx + 1]:
        day_issues = []
        if day in executions:
            previous = current
            current = set(executions[day])
            for name in previous | current:
                if not np.isfinite(opens.at[day, name]) or opens.at[day, name] <= 0:
                    day_issues.append({"date": day.date().isoformat(), "symbol": name,
                                       "input": "next_session_raw_open", "reason": "missing intended order observation"})
        for name in current:
            if not np.isfinite(closes.at[day, name]) or closes.at[day, name] <= 0:
                day_issues.append({"date": day.date().isoformat(), "symbol": name,
                                   "input": "held_position_raw_close", "reason": "missing or invalid raw close mark"})
        for event in share_conversions:
            if (event["kind"] in {"bonus", "split_bonus"} and event["ex_date"] <= day.date()
                    and (event["tradable_date"] is None or event["tradable_date"] > day.date())):
                name = event["symbol"]
                if not np.isfinite(closes.at[day, name]) or closes.at[day, name] <= 0:
                    day_issues.append({"date": day.date().isoformat(), "symbol": name,
                                       "input": "locked_bonus_raw_close",
                                       "reason": "owned bonus shares remain pending and require an observed raw close mark"})
        if day_issues:
            issues = sorted(day_issues, key=lambda row: (row["input"], row["symbol"]))
            break
    if issues:
        gap = issues[0]
        stop_index = sessions.index(pd.Timestamp(gap["date"]))
        effective_end = min(effective_end, sessions[stop_index - 1])
        exec_end = effective_end
        blockers.append(gap)
    if exec_end < pd.Timestamp(first_fill):
        return {"candidate_id": candidate, "status": "BLOCKED_BEFORE_FIRST_FILL",
                "first_material_blocker": blockers[0] if blockers else signal_blocker,
                "blockers": blockers, "actual_order_count": 0,
                "valuation_scenario": valuation_scenario, "slippage_bps_per_side": slippage_bps,
                "valid_through": exec_end.date().isoformat(), "starting_capital_inr": CAPITAL,
                "ending_nav_inr": CAPITAL, "ending_cash_inr": CAPITAL, "ending_invested_inr": 0.0,
                "ending_cash_receivable_inr": 0.0, "ending_locked_claim_inr": 0.0,
                "max_drawdown_pct": 0.0, "turnover_inr": 0.0, "fees_inr": 0.0}
    equity, orders, stats = cash_engine._simulate(
        {"open": opens, "close": closes}, targets, rebalance, CAPITAL, 1.0, slippage_bps,
        start=date(2018, 1, 1), end=exec_end.date(), drawdown_limit_pct=1000.0,
        cash_distributions=distributions, cash_distribution_payment_dates=payment_dates,
        detached_claim_events=claim_events, share_conversion_events=share_conversions,
        liquidate_terminal=False,
    )
    residual = (equity["nav"] - equity["cash_inr"] - equity["invested_inr"]
                - equity["pending_share_value_inr"] - equity["cash_receivable_inr"]
                - equity["locked_claim_inr"]).abs()
    if residual.max() > 0.05 or not np.isfinite(residual).all():
        raise AssertionError(f"order-to-NAV reconciliation failed for {candidate}")
    retained_resize = []
    prior = set()
    for schedule_index, item in enumerate(schedules):
        day = pd.Timestamp(item["signal_date"])
        if day < exec_end:
            execution = sessions[sessions.index(day) + 1]
            filled = orders.loc[orders["time"].eq(execution)]
            if schedule_index == 0 and len(filled.loc[filled["side"].eq("buy")]) != 20:
                raise AssertionError(f"{candidate} {day.date()} target had fewer than 20 fills")
            retained = set(item["canonical_names"]) & prior
            resized = filled.loc[filled["symbol"].isin(retained), ["symbol", "side", "quantity"]]
            retained_resize.append({"signal_date": day.date().isoformat(), "execution_date": execution.date().isoformat(),
                                    "retained_names": len(retained), "retained_names_with_resize_orders": int(resized["symbol"].nunique()),
                                    "retained_resize_order_count": int(len(resized))})
        prior = set(item["canonical_names"])
    order_frame = orders.copy()
    if not order_frame.empty:
        order_frame["reference_open_raw"] = [opens.at[row.time, row.symbol] for row in order_frame.itertuples()]
        order_frame["slippage_cost_inr"] = order_frame["quantity"] * (
            order_frame["fill_price"] - order_frame["reference_open_raw"]
        ).abs()
        order_frame["candidate_id"] = candidate
    LOCAL.mkdir(parents=True, exist_ok=True)
    output_stem = f"{candidate.lower().replace('-', '_')}_{valuation_scenario}_{int(slippage_bps)}bps"
    order_path = LOCAL / f"{output_stem}_orders.csv"
    equity_path = LOCAL / f"{output_stem}_equity.csv"
    events_path = LOCAL / f"{output_stem}_events.json"
    order_frame.to_csv(order_path, index=False)
    equity.to_csv(equity_path, index_label="date")
    events_path.write_text(json.dumps({"cash_distribution_events": stats["cash_distribution_events"],
                                     "detached_claim_events": stats["detached_claim_events"],
                                     "share_conversion_events": stats["share_conversion_events"],
                                     "valuation_scenario": valuation_scenario}, indent=2) + "\n", encoding="utf-8")
    ending_positions = [{"canonical": row["symbol"], **row} for row in stats["ending_positions"]]
    ending_positions.sort(key=lambda row: (-row["economic_market_value_inr"], row["canonical"]))
    invested_rebuilt = sum(row["tradable_market_value_inr"] for row in ending_positions)
    if abs(invested_rebuilt - float(equity["invested_inr"].iloc[-1])) > 0.05:
        raise AssertionError(f"ending positions do not reconcile for {candidate}")
    economic_invested = sum(row["economic_market_value_inr"] for row in ending_positions)
    for position in ending_positions:
        position["weight_of_invested_pct"] = (
            position["economic_market_value_inr"] / economic_invested * 100 if economic_invested else 0.0
        )
    concentration = {
        "position_count": len(ending_positions),
        "largest_position_pct_of_invested": ending_positions[0]["weight_of_invested_pct"] if ending_positions else 0.0,
        "top_five_pct_of_invested": sum(row["weight_of_invested_pct"] for row in ending_positions[:5]),
        "hhi": sum((row["weight_of_invested_pct"] / 100) ** 2 for row in ending_positions),
        "invested_reconciliation_residual_inr": invested_rebuilt - float(equity["invested_inr"].iloc[-1]),
        "pending_share_value_inr": float(equity["pending_share_value_inr"].iloc[-1]),
    }
    path_nav = [(date(2018, 1, 1), CAPITAL)] + [
        (timestamp.date(), float(nav)) for timestamp, nav in equity["nav"].items()
    ]
    high_water, high_water_day = CAPITAL, date(2018, 1, 1)
    max_dd, max_dd_peak, max_dd_peak_day, max_dd_trough_day = 0.0, CAPITAL, date(2018, 1, 1), date(2018, 1, 1)
    for day, nav in path_nav[1:]:
        if nav > high_water:
            high_water, high_water_day = nav, day
        drawdown = nav / high_water - 1
        if drawdown < max_dd:
            max_dd, max_dd_peak, max_dd_peak_day, max_dd_trough_day = (
                drawdown, high_water, high_water_day, day
            )
    recovery_day = next((day for day, nav in path_nav
                         if day > max_dd_trough_day and nav >= max_dd_peak), None)
    recovery = {
        "max_drawdown_pct": max_dd * 100,
        "peak_date": max_dd_peak_day.isoformat(),
        "trough_date": max_dd_trough_day.isoformat(),
        "recovery_status": "RECOVERED" if recovery_day else "NOT_RECOVERED_BY_PREFIX_END",
        "recovery_date": recovery_day.isoformat() if recovery_day else None,
        "trough_to_recovery_calendar_days": (recovery_day - max_dd_trough_day).days if recovery_day else None,
    }
    if not np.isclose(max_dd * 100, stats["max_drawdown_pct"], atol=1e-9):
        raise AssertionError(f"drawdown path does not reconcile for {candidate}")
    status = ("ACTUAL_PREFIX_STOPPED_AT_FIRST_MATERIAL_GAP" if blockers else
              "ACTUAL_PREFIX_STOPPED_AT_UNRESOLVED_SIGNAL" if signal_blocker else
              "ACTUAL_PREFIX_TO_EVALUATION_CUTOFF")
    result = {"candidate_id": candidate,
              "status": status, "valuation_scenario": valuation_scenario,
              "slippage_bps_per_side": slippage_bps,
              "valid_through": exec_end.date().isoformat(),
              "starting_capital_inr": CAPITAL, "actual_order_count": int(len(orders)),
              "actual_buy_count": int(orders["side"].eq("buy").sum()),
              "actual_sell_count": int(orders["side"].eq("sell").sum()),
              "first_order_date": orders["time"].min().date().isoformat() if len(orders) else None,
              "ending_nav_inr": float(equity["nav"].iloc[-1]),
              "ending_cash_inr": float(equity["cash_inr"].iloc[-1]),
              "ending_invested_inr": float(equity["invested_inr"].iloc[-1]),
              "ending_cash_receivable_inr": float(equity["cash_receivable_inr"].iloc[-1]),
              "ending_locked_claim_inr": float(equity["locked_claim_inr"].iloc[-1]),
              "ending_pending_share_value_inr": float(equity["pending_share_value_inr"].iloc[-1]),
              "max_drawdown_pct": float(stats["max_drawdown_pct"]),
              "drawdown_recovery": recovery, "ending_positions": ending_positions,
              "ending_concentration": concentration,
              "turnover_inr": float(stats["turnover_inr"]), "fees_inr": float(stats["total_fees_inr"]),
              "fees_by_component_inr": stats["fees_by_component_inr"],
              "slippage_cost_inr": float(order_frame["slippage_cost_inr"].sum()) if len(order_frame) else 0.0,
              "max_nav_reconciliation_residual_inr": float(residual.max()),
              "cash_distributions_inr": float(stats["cash_distributions_inr"]),
              "cash_distribution_entitlements_inr": float(stats["cash_distribution_entitlements_inr"]),
              "cash_distribution_events": stats["cash_distribution_events"],
              "detached_claim_events": stats["detached_claim_events"],
              "share_conversion_events": stats["share_conversion_events"],
              "retained_name_resizing_by_rebalance": retained_resize,
              "first_material_blocker": blockers[0] if blockers else signal_blocker,
              "later_material_blockers": blockers[1:] if len(blockers) > 1 else [],
              "orders_file_local": str(order_path.relative_to(ROOT)),
              "equity_file_local": str(equity_path.relative_to(ROOT)),
              "events_file_local": str(events_path.relative_to(ROOT)),
              "cagr": "NOT REPORTED: stopped prefix, not a full-period result"}
    return result


def self_check() -> None:
    global LOCAL
    cash_engine._self_check()
    assert normalize_index_label("Nifty 200") == normalize_index_label("NIFTY 200") == "NIFTY200"
    assert choose_selection_bound(0.1, 0.7, 0.75) is False
    assert choose_selection_bound(0.1, 0.8, 0.75) is True
    assert np.isclose((296.05 / ((296.05 + 0.1 * 207) / 1.1)), 1.0281136543, atol=1e-9)
    assert IDFC_INFERENCE["classification"] == "supported_debt_event_inference"
    dividend_sessions = list(pd.bdate_range("2017-01-02", "2019-06-28"))
    dividend_index = {day: i for i, day in enumerate(dividend_sessions)}
    dividend_cases = [
        ("MINDTREE", "INE018I01017", "2018-10-25", 805.5, 779.7, 3.0, 1.0),
        ("TCS", "INE467B01029", "2018-10-23", 1903.0, 1843.65, 4.0, 1.0),
        ("VAKRANGEE", "INE051B01021", "2018-09-19", 36.8, 36.55, 0.25, 0.973667 / 0.960483),
        ("NHPC", "INE848E01016", "2019-02-18", 23.8, 23.4, 0.71, 1.0),
    ]
    for symbol, isin, ex_text, prior_close, ex_close, cash_amount, observed_factor in dividend_cases:
        dividend_ex_i = dividend_index[pd.Timestamp(ex_text)]
        dividend_closes = np.linspace(700.0, 900.0, len(dividend_sessions))
        dividend_closes[dividend_ex_i - 1] = prior_close
        dividend_closes[dividend_ex_i] = ex_close
        dividend_factor = np.ones(len(dividend_sessions))
        dividend_factor[dividend_ex_i:] = observed_factor
        dividend_prices = pd.DataFrame({"close": dividend_closes, "adj_close": dividend_closes * dividend_factor,
                                       "adj_factor_cumulative": dividend_factor}, index=dividend_sessions)
        for rule in ("A", "B"):
            dividend_candidate = f"NIFTY200-{rule}-M"
            dividend_day = pd.Timestamp("2019-05-01")
            dividend_baseline, _ = audit.score_at(dividend_prices["adj_close"].to_numpy(),
                                                   dividend_index[dividend_day], rule)
            dividend_row = pd.Series({"symbol": symbol, "canonical": isin, "score": dividend_baseline})
            corrected_score, dividend_details = score_with_corrections(
                dividend_candidate, dividend_day, dividend_row, dividend_sessions, dividend_index,
                {isin: dividend_prices}, pd.Series(dtype=float), [])
            correction = next(item for item in dividend_details["corrections"] if item["ex_date"] == ex_text)
            assert corrected_score is not None and np.isclose(
                correction["applied_signal_multiplier"], (prior_close / (prior_close - cash_amount)) / observed_factor)
            dividend_dependency = {"candidate_id": dividend_candidate,
                                   "signal_date": dividend_day.date().isoformat(), "rule": rule,
                                   "date": ex_text, "entity": f"{symbol}|{isin}",
                                   "input": "signal_dividend", "source": "TejHQ", "reason": "factor mismatch"}
            dividend_dependency["dependency_key"] = audit.dependency_key(dividend_dependency)
            dividend_row["unresolved_dependency_keys"] = [dividend_dependency["dependency_key"]]
            resolved, unmatched = exact_dependency_resolutions(
                dividend_candidate, dividend_row, dividend_details,
                {dividend_dependency["dependency_key"]: dividend_dependency})
            assert resolved == [dividend_dependency["dependency_key"]] and not unmatched
    rights_cases = [
        ("IDEA", "INE669E01016", "2019-03-29", 29.0, 87 / 38, 12.50),
        ("BHARTIARTL", "INE397D01024", "2019-04-23", 349.4, 19 / 67, 220.0),
    ]
    for symbol, isin, ex_text, prior_close, ratio, issue_price in rights_cases:
        ex_i = dividend_index[pd.Timestamp(ex_text)]
        closes = np.linspace(12.0, 400.0, len(dividend_sessions))
        closes[ex_i - 1] = prior_close
        closes[ex_i] = prior_close * 0.9
        factors = np.ones(len(dividend_sessions))
        prices = pd.DataFrame({"close": closes, "adj_close": closes,
                               "adj_factor_cumulative": factors}, index=dividend_sessions)
        expected = prior_close / ((prior_close + ratio * issue_price) / (1 + ratio))
        for rule in ("A", "B"):
            candidate = f"NIFTY200-{rule}-Q"
            signal_day = pd.Timestamp("2019-06-28")
            baseline, _ = audit.score_at(prices["adj_close"].to_numpy(), dividend_index[signal_day], rule)
            row = pd.Series({"symbol": symbol, "canonical": isin, "score": baseline})
            corrected, details = score_with_corrections(
                candidate, signal_day, row, dividend_sessions, dividend_index,
                {isin: prices}, pd.Series(dtype=float), [])
            correction = next(item for item in details["corrections"]
                              if item["event"] == "rights" and item["ex_date"] == ex_text)
            assert corrected is not None and np.isclose(correction["source_factor_multiplier"], expected)
            dependency = {"candidate_id": candidate, "signal_date": signal_day.date().isoformat(),
                          "rule": rule, "date": ex_text, "entity": f"{symbol}|{isin}",
                          "input": "signal_rights", "source": "exchange", "reason": "rights terms"}
            dependency["dependency_key"] = audit.dependency_key(dependency)
            row["unresolved_dependency_keys"] = [dependency["dependency_key"]]
            resolved, unmatched = exact_dependency_resolutions(
                candidate, row, details, {dependency["dependency_key"]: dependency})
            assert resolved == [dependency["dependency_key"]] and not unmatched
    demerger_days = pd.to_datetime(["2017-07-18", "2017-07-19", "2017-09-01"])
    parent = pd.DataFrame({"adj_close": [100.0, 90.0, 80.0]}, index=demerger_days)
    child = pd.DataFrame({"adj_close": [np.nan, np.nan, 10.0]}, index=demerger_days)
    source_event = {"ex_date": "2017-07-19", "child_symbol": "ABCAPITAL",
                    "ratio_num": 7, "ratio_den": 5, "listing_date": "2017-09-01"}
    assert np.isclose(demerger_interval_return(parent, child, demerger_days[0], demerger_days[2],
                                               source_event), -0.06)
    assert np.isclose(demerger_interval_return(parent, child, demerger_days[1], demerger_days[2],
                                               source_event), 80 / 90 - 1)
    demerger_sessions = list(pd.bdate_range("2017-01-02", periods=300))
    demerger_index = {day: i for i, day in enumerate(demerger_sessions)}
    parent_prices = np.linspace(100.0, 110.0, len(demerger_sessions))
    parent_frame = pd.DataFrame({"adj_close": parent_prices, "close": parent_prices,
                                 "adj_factor_cumulative": 1.0}, index=demerger_sessions)
    child_prices = np.full(len(demerger_sessions), np.nan)
    child_prices[demerger_index[pd.Timestamp("2017-09-01")]:] = np.linspace(
        20.0, 25.0, len(demerger_sessions) - demerger_index[pd.Timestamp("2017-09-01")])
    child_frame = pd.DataFrame({"adj_close": child_prices}, index=demerger_sessions)
    baseline_b, _ = audit.score_at(parent_prices, 280, "B")
    row = pd.Series({"symbol": "GRASIM", "canonical": "GRASIM", "score": baseline_b})
    bounded_score, bounded_details = score_with_corrections(
        "NIFTY200-B-M", demerger_sessions[280], row, demerger_sessions, demerger_index,
        {"GRASIM": parent_frame, "INE674K01013": child_frame}, pd.Series(dtype=float), [])
    assert bounded_score is None and bounded_details["selection_bound"] == "MATERIAL_UNKNOWN"
    volatility_window = demerger_sessions[280 - 273:280 - 21 + 1]
    total_wealth_return = demerger_interval_return(
        parent_frame, child_frame, demerger_sessions[280 - 273], demerger_sessions[280 - 21], source_event)
    volatility_lower_bound = demerger_volatility_lower_bound(
        parent_frame, child_frame, volatility_window, source_event, total_wealth_return)
    assert volatility_lower_bound is not None and volatility_lower_bound > 0
    volatility_index = pd.DatetimeIndex(volatility_window)
    window_values = parent_frame.loc[volatility_index, "adj_close"].to_numpy(dtype=float).copy()
    window_listed = volatility_index >= pd.Timestamp("2017-09-01")
    window_values[window_listed] += 1.4 * child_frame.loc[
        volatility_index[window_listed], "adj_close"].to_numpy(dtype=float)
    sample_returns = np.diff(np.log(window_values))
    unknown_returns = np.asarray([pd.Timestamp("2017-07-19") <= day <= pd.Timestamp("2017-09-01")
                                  for day in volatility_window[1:]])
    known_returns = sample_returns[~unknown_returns]
    inferred_claim_sum = np.log1p(total_wealth_return) - float(known_returns.sum())
    equalized_claim_returns = np.repeat(inferred_claim_sum / int(unknown_returns.sum()),
                                        int(unknown_returns.sum()))
    perturbed_claim_returns = equalized_claim_returns.copy()
    perturbed_claim_returns[0] += 0.05
    perturbed_claim_returns[1] -= 0.05
    assert (np.std(np.concatenate((known_returns, equalized_claim_returns)), ddof=1)
            <= np.std(np.concatenate((known_returns, perturbed_claim_returns)), ddof=1))
    dependency = {"candidate_id": "NIFTY200-B-M", "signal_date": demerger_sessions[280].date().isoformat(),
                  "rule": "B", "date": "2017-07-19", "entity": "GRASIM|INE047A01021",
                  "input": "signal_other", "source": "exchange", "reason": "demerger terms"}
    dependency["dependency_key"] = audit.dependency_key(dependency)
    row["unresolved_dependency_keys"] = [dependency["dependency_key"]]
    resolved, unmatched = exact_dependency_resolutions("NIFTY200-B-M", row, bounded_details,
                                                       {dependency["dependency_key"]: dependency})
    assert resolved == [dependency["dependency_key"]] and not unmatched

    composite_sessions = list(pd.bdate_range("2018-01-01", "2019-09-30"))
    composite_index = {day: i for i, day in enumerate(composite_sessions)}
    parent_values = np.linspace(100.0, 200.0, len(composite_sessions))
    parent_composite = pd.DataFrame({"close": parent_values, "adj_close": parent_values,
                                     "adj_factor_cumulative": 1.0}, index=composite_sessions)
    list_i = composite_index[pd.Timestamp("2019-01-25")]
    spencers_values = np.full(len(composite_sessions), np.nan)
    ventures_values = np.full(len(composite_sessions), np.nan)
    spencers_values[list_i:] = np.linspace(20.0, 50.0, len(composite_sessions) - list_i)
    ventures_values[list_i:] = np.linspace(10.0, 25.0, len(composite_sessions) - list_i)
    children_composite = {
        "INE020801028": pd.DataFrame({"adj_close": spencers_values}, index=composite_sessions),
        "INE425Y01011": pd.DataFrame({"adj_close": ventures_values}, index=composite_sessions),
    }
    composite_event = {**SOURCE_DEMERGERS[("CESC", "2018-10-30")], "ex_date": "2018-10-30"}
    composite_start, composite_end = composite_sessions[composite_index[pd.Timestamp("2018-09-18")]], composite_sessions[-22]
    composite_return = demerger_interval_return(parent_composite, children_composite,
                                                 composite_start, composite_end, composite_event)
    expected_child_wealth = 0.6 * spencers_values[composite_index[composite_end]] + 0.2 * ventures_values[composite_index[composite_end]]
    assert np.isclose(composite_return,
                      (parent_values[composite_index[composite_end]] + expected_child_wealth)
                      / parent_values[composite_index[composite_start]] - 1)
    post_ex_return = demerger_interval_return(parent_composite, children_composite,
                                               pd.Timestamp("2018-11-01"), composite_end, composite_event)
    assert np.isclose(post_ex_return, parent_values[composite_index[composite_end]]
                      / parent_values[composite_index[pd.Timestamp("2018-11-01")]] - 1)
    composite_day = pd.Timestamp("2019-09-30")
    composite_end_i = composite_index[composite_day] - 21
    for rule in ("A", "B"):
        candidate = f"NIFTY200-{rule}-M"
        composite_score, _ = audit.score_at(parent_values, composite_index[composite_day], rule)
        composite_row = pd.Series({"symbol": "CESC", "canonical": "CESC", "score": composite_score})
        corrected, details = score_with_corrections(
            candidate, composite_day, composite_row, composite_sessions, composite_index,
            {"CESC": parent_composite, **children_composite}, pd.Series(dtype=float), [])
        assert details.get("source_demerger", {}).get("children")
        if rule == "A":
            assert np.isclose(corrected, demerger_interval_return(
                parent_composite, children_composite, composite_sessions[composite_index[composite_day] - 252],
                composite_sessions[composite_end_i], composite_event))
        else:
            assert corrected is None and details.get("annualized_volatility_lower_bound", 0) > 0
        composite_dependency = {"candidate_id": candidate, "signal_date": composite_day.date().isoformat(),
                                "rule": rule, "date": "2018-10-30", "entity": "CESC|INE486A01013",
                                "input": "signal_other", "source": "exchange", "reason": "composite scheme"}
        composite_dependency["dependency_key"] = audit.dependency_key(composite_dependency)
        composite_row["unresolved_dependency_keys"] = [composite_dependency["dependency_key"]]
        resolved, unmatched = exact_dependency_resolutions(
            candidate, composite_row, details,
            {composite_dependency["dependency_key"]: composite_dependency})
        assert resolved == [composite_dependency["dependency_key"]] and not unmatched

    prelisting_day = pd.Timestamp("2018-11-30")
    prelisting_score, _ = audit.score_at(parent_values, composite_index[prelisting_day], "A")
    _, prelisting_details = score_with_corrections(
        "NIFTY200-A-M", prelisting_day,
        pd.Series({"symbol": "CESC", "canonical": "CESC", "score": prelisting_score}),
        composite_sessions, composite_index, {"CESC": parent_composite, **children_composite},
        pd.Series(dtype=float), [])
    assert prelisting_details["method"] == "source_demerger_child_unlisted_at_signal_endpoint"
    assert set(prelisting_details["unlisted_children"]) == {"SPENCERS", "CESCVENT"}
    declining_prices = np.linspace(100.0, 40.0, len(demerger_sessions))
    declining_frame = pd.DataFrame({"adj_close": declining_prices, "close": declining_prices,
                                    "adj_factor_cumulative": 1.0}, index=demerger_sessions)
    small_child_prices = np.full(len(demerger_sessions), np.nan)
    small_child_prices[demerger_index[pd.Timestamp("2017-09-01")]:] = 0.01
    small_child = pd.DataFrame({"adj_close": small_child_prices}, index=demerger_sessions)
    declining_score, _ = audit.score_at(declining_prices, 280, "B")
    _, declining_details = score_with_corrections(
        "NIFTY200-B-M", demerger_sessions[280], pd.Series({"symbol": "GRASIM", "canonical": "GRASIM",
                                                             "score": declining_score}),
        demerger_sessions, demerger_index, {"GRASIM": declining_frame,
                                           "INE674K01013": small_child}, pd.Series(dtype=float), [])
    assert declining_details["selection_bound"] == "NONPOSITIVE"
    sessions = list(pd.to_datetime(["2018-04-02", "2018-04-03", "2018-04-04", "2018-04-05", "2018-04-06"]))
    action = pd.DataFrame([{"ex_date": pd.Timestamp("2018-04-05"), "resolved_symbol": "PARENT",
                            "symbol": "PARENT", "isin": "INE000A01001", "type": "dividend",
                            "raw_subject": "Dividend", "cash_amount": 2.0}])
    data = pd.DataFrame([{"date": day, "symbol": "PARENT", "isin": "INE000A01001", "canonical": "INE000A01001"}
                         for day in sessions])
    exit_targets = {"2018-04-02": ["INE000A01001"], "2018-04-04": []}
    distributions, payment_dates, claims, conversions, blockers = action_gate(
        "NIFTY200-A-Q", exit_targets, action, data, sessions, date(2018, 4, 2), date(2018, 4, 5))
    assert distributions == [("INE000A01001", date(2018, 4, 5), 2.0)] and not blockers and not claims
    assert payment_dates[("INE000A01001", date(2018, 4, 5))] == date(2018, 5, 5)
    entry_targets = {"2018-04-02": [], "2018-04-04": ["INE000A01001"]}
    distributions, _, _, _, blockers = action_gate(
        "NIFTY200-A-Q", entry_targets, action, data, sessions, date(2018, 4, 2), date(2018, 4, 5))
    assert not distributions and not blockers

    conversion_sessions = list(pd.to_datetime(["2018-06-22", "2018-06-25", "2018-06-26", "2018-06-27"]))
    conversion_action = pd.DataFrame([{"ex_date": conversion_sessions[2], "record_date": "2018-06-27",
                                       "resolved_symbol": "AVANTIFEED", "symbol": "AVANTIFEED",
                                       "isin": "INE871C01012", "type": "split", "ratio_num": 1.0,
                                       "ratio_den": 2.0, "face_value_from": 2.0, "face_value_to": 1.0,
                                       "raw_subject": "Bonus 1:2/Face Value Split"}])
    conversion_data = pd.DataFrame([
        {"date": conversion_sessions[1], "symbol": "AVANTIFEED", "isin": "INE871C01020",
         "canonical": "AVANTIFEED_TEST", "close": 1563.35, "adj_factor_cumulative": 0.298405},
        {"date": conversion_sessions[2], "symbol": "AVANTIFEED", "isin": "INE871C01020",
         "canonical": "AVANTIFEED_TEST", "close": 599.30, "adj_factor_cumulative": 0.895216},
    ])
    _, _, _, combined_conversions, conversion_blockers = action_gate(
        "NIFTY200-A-M", {"2018-06-22": ["AVANTIFEED_TEST"]}, conversion_action, conversion_data,
        conversion_sessions, date(2018, 6, 25), date(2018, 6, 26))
    assert not conversion_blockers and len(combined_conversions) == 1
    assert combined_conversions[0]["kind"] == "split_bonus"
    assert np.isclose(combined_conversions[0]["share_multiplier"], 3.0)
    assert np.isclose(combined_conversions[0]["split_multiplier"], 2.0)
    assert np.isclose(combined_conversions[0]["bonus_per_split_share"], 0.5)
    assert combined_conversions[0]["tradable_date"] == date(2018, 7, 5)

    buyback_sessions = list(pd.to_datetime(["2018-08-10", "2018-08-13", "2018-08-14"]))
    buyback_action = pd.DataFrame([{"ex_date": buyback_sessions[2], "resolved_symbol": "TCS",
                                    "symbol": "TCS", "isin": "INE467B01029", "type": "buyback",
                                    "raw_subject": "Buyback"}])
    buyback_data = pd.DataFrame([{"date": buyback_sessions[1], "symbol": "TCS",
                                  "isin": "INE467B01029", "canonical": "TCS"}])
    _, _, _, _, buyback_blockers = action_gate(
        "NIFTY200-A-M", {"2018-08-10": ["TCS"]}, buyback_action, buyback_data,
        buyback_sessions, date(2018, 8, 13), date(2018, 8, 14))
    assert not buyback_blockers

    debt_sessions = list(pd.to_datetime(["2018-02-01", "2018-02-02", "2018-02-28"]))
    debt_action = pd.DataFrame([{"ex_date": pd.Timestamp("2018-02-28"), "record_date": "2018-03-01",
                                 "resolved_symbol": "IDFCBANK", "symbol": "IDFCFIRSTB",
                                 "isin": "INE092T01019", "type": "other", "raw_subject": "Interest Payment"}])
    debt_data = pd.DataFrame([{"date": debt_sessions[i], "symbol": "IDFCBANK", "isin": "INE092T01019",
                               "canonical": "INE092T01019"} for i in range(2)])
    _, _, _, _, debt_blockers = action_gate("NIFTY200-A-M", {"2018-02-01": ["INE092T01019"]},
                                            debt_action, debt_data, debt_sessions,
                                            date(2018, 2, 2), date(2018, 2, 28))
    assert not debt_blockers

    for (debt_symbol, event_date), terms in SOURCE_DEBT_EVENTS.items():
        if event_date < "2019-01-01":
            continue
        event_day = pd.Timestamp(event_date)
        debt_sessions = list(pd.bdate_range(event_day - pd.Timedelta(days=6), event_day))
        debt_action = pd.DataFrame([{"ex_date": event_day, "record_date": terms["record_date"],
                                     "resolved_symbol": debt_symbol, "symbol": "IDFCFIRSTB",
                                     "isin": IDFC_INFERENCE["vendor_isin"], "type": "other",
                                     "raw_subject": "Interest Payment"}])
        debt_data = pd.DataFrame([{"date": day, "symbol": "IDFCBANK",
                                   "isin": IDFC_INFERENCE["vendor_isin"],
                                   "canonical": IDFC_INFERENCE["vendor_isin"]}
                                  for day in debt_sessions[:-1]])
        debt_signal = debt_sessions[-3].date().isoformat()
        _, _, _, _, debt_blockers = action_gate(
            "NIFTY200-A-M", {debt_signal: [IDFC_INFERENCE["vendor_isin"]]}, debt_action,
            debt_data, debt_sessions, debt_sessions[0].date(), event_day.date())
        assert not debt_blockers, (event_date, debt_blockers)

    debt_sessions = list(pd.bdate_range("2017-01-02", "2018-05-31"))
    debt_index = {day: i for i, day in enumerate(debt_sessions)}
    debt_day = pd.Timestamp("2018-04-30")
    debt_prices = np.linspace(10.0, 30.0, len(debt_sessions))
    debt_score, _ = audit.score_at(debt_prices, debt_index[debt_day], "A")
    debt_row = pd.Series({"symbol": "IDFCFIRSTB", "canonical": "INE092T01019", "score": debt_score})
    _, debt_details = score_with_corrections("NIFTY200-A-M", debt_day, debt_row,
                                              debt_sessions, debt_index, {}, pd.Series(dtype=float), [])
    assert [event["series"] for event in debt_details["source_debt_events"]] == ["HB", "HD"]
    debt_dependencies = [{"candidate_id": "NIFTY200-A-M", "signal_date": debt_day.date().isoformat(),
                          "rule": "A", "date": event["ex_date"], "entity": "IDFCFIRSTB|INE092T01019",
                          "input": "signal_other", "source": "NSE", "reason": "debt series interest"}
                         for event in debt_details["source_debt_events"]]
    for dependency_row in debt_dependencies:
        dependency_row["dependency_key"] = audit.dependency_key(dependency_row)
    debt_row["unresolved_dependency_keys"] = [row["dependency_key"] for row in debt_dependencies]
    resolved, unmatched = exact_dependency_resolutions("NIFTY200-A-M", debt_row, debt_details,
                                                       {row["dependency_key"]: row for row in debt_dependencies})
    assert len(resolved) == 2 and not unmatched

    debt_2019_sessions = list(pd.bdate_range("2018-01-01", "2019-09-30"))
    debt_2019_index = {day: i for i, day in enumerate(debt_2019_sessions)}
    debt_2019_day = pd.Timestamp("2019-06-28")
    debt_2019_prices = np.linspace(10.0, 30.0, len(debt_2019_sessions))
    debt_2019_score, _ = audit.score_at(debt_2019_prices, debt_2019_index[debt_2019_day], "A")
    debt_2019_row = pd.Series({"symbol": "IDFCFIRSTB", "canonical": IDFC_INFERENCE["vendor_isin"],
                               "score": debt_2019_score})
    _, debt_2019_details = score_with_corrections(
        "NIFTY200-A-M", debt_2019_day, debt_2019_row, debt_2019_sessions, debt_2019_index,
        {}, pd.Series(dtype=float), [])
    debt_2019_events = {(event["ex_date"], event["series"])
                        for event in debt_2019_details["source_debt_events"]}
    assert {("2019-02-28", "HB"), ("2019-03-14", "HD")} <= debt_2019_events
    debt_2019_dependencies = [{"candidate_id": "NIFTY200-A-M", "signal_date": debt_2019_day.date().isoformat(),
                               "rule": "A", "date": event["ex_date"], "entity": "IDFCFIRSTB|INE092T01019",
                               "input": "signal_other", "source": "NSE", "reason": "debt series interest"}
                              for event in debt_2019_details["source_debt_events"]
                              if event["ex_date"] in {"2019-02-28", "2019-03-14"}]
    for dependency_row in debt_2019_dependencies:
        dependency_row["dependency_key"] = audit.dependency_key(dependency_row)
    debt_2019_row["unresolved_dependency_keys"] = [row["dependency_key"] for row in debt_2019_dependencies]
    resolved, unmatched = exact_dependency_resolutions(
        "NIFTY200-A-M", debt_2019_row, debt_2019_details,
        {row["dependency_key"]: row for row in debt_2019_dependencies})
    assert len(resolved) == 2 and not unmatched

    bonus_sessions = list(pd.bdate_range("2018-01-01", "2019-09-30"))
    bonus_index = {day: i for i, day in enumerate(bonus_sessions)}
    bonus_prices = np.linspace(1000.0, 800.0, len(bonus_sessions))
    bonus_frame = pd.DataFrame({"close": bonus_prices, "adj_close": bonus_prices,
                                "adj_factor_cumulative": 1.0}, index=bonus_sessions)
    bonus_day = pd.Timestamp("2019-09-30")
    bonus_dependency = {"candidate_id": "NIFTY200-A-M", "signal_date": bonus_day.date().isoformat(),
                        "rule": "A", "date": "2019-08-22", "entity": "BRITANNIA|INE216A01030",
                        "input": "signal_bonus", "source": "NSE/issuer", "reason": "unpriced NCD bonus"}
    bonus_dependency["dependency_key"] = audit.dependency_key(bonus_dependency)
    for rule in ("A", "B"):
        candidate = f"NIFTY200-{rule}-M"
        bonus_score, _ = audit.score_at(bonus_prices, bonus_index[bonus_day], rule)
        bonus_row = pd.Series({"symbol": "BRITANNIA", "canonical": "INE216A01030", "score": bonus_score,
                               "unresolved_dependency_keys": [bonus_dependency["dependency_key"]]})
        bounded_score, bounded_details = score_with_corrections(
            candidate, bonus_day, bonus_row, bonus_sessions, bonus_index,
            {"INE216A01030": bonus_frame}, pd.Series(dtype=float), [])
        assert bounded_score is None and bounded_details["selection_bound"] == "NONPOSITIVE"
        assert bounded_details["source_debt_distributions"][0]["maximum_contractual_cashflows_inr"] == 37.2
        resolved, unmatched = exact_dependency_resolutions(
            candidate, bonus_row, bounded_details,
            {bonus_dependency["dependency_key"]: bonus_dependency})
        assert resolved == [bonus_dependency["dependency_key"]] and not unmatched

    # Entitlement changes at the event open; the engine must use the actual pre-open quantity.
    trade_days = pd.to_datetime(["2018-04-03", "2018-04-04", "2018-04-05", "2018-05-07",
                                "2018-06-18", "2018-06-19"])
    names = ["PARENT", "CHILD"]
    opens = pd.DataFrame({"PARENT": [100, 100, 90, 92, 95, 96],
                          "CHILD": [np.nan, np.nan, np.nan, np.nan, 20, 22]}, index=trade_days)
    closes = opens.copy()
    targets = pd.DataFrame(0.0, index=trade_days, columns=names)
    targets.loc[trade_days[0], "PARENT"] = 0.5
    rebalance = pd.Series(False, index=trade_days)
    rebalance.loc[trade_days[:2]] = True
    claim_event = {"parent_symbol": "PARENT", "child_symbol": "CHILD", "ex_date": date(2018, 4, 5),
                   "listing_date": date(2018, 6, 18), "sale_date": date(2018, 6, 19), "ratio": "0.761",
                   "detached_unit_mark": 10.0, "base_detached_unit_mark": 10.0, "scenario": "base"}
    dividend = [("PARENT", date(2018, 4, 5), 2.0)]
    payment_day = {("PARENT", date(2018, 4, 5)): date(2018, 5, 5)}
    equity, orders, stats = cash_engine._simulate(
        {"open": opens, "close": closes}, targets, rebalance, 10_000.0, 1.0, 50.0,
        start=date(2018, 4, 4), end=date(2018, 6, 19), drawdown_limit_pct=1000.0,
        cash_distributions=dividend, cash_distribution_payment_dates=payment_day,
        detached_claim_events=[claim_event], liquidate_terminal=False,
    )
    record = stats["detached_claim_events"][0]
    assert record["parent_quantity_before_ex_open"] > 0
    assert Decimal(record["entitlement_exact"]) == Decimal(record["parent_quantity_before_ex_open"]) * AGEL_RATIO
    assert int(orders.loc[orders["time"].eq(pd.Timestamp("2018-04-05")) & orders["side"].eq("sell"), "quantity"].sum()) == record["parent_quantity_before_ex_open"]
    ex_row, paid_row, listing_row, sale_row = (equity.loc[pd.Timestamp(day)] for day in
                                               ("2018-04-05", "2018-05-07", "2018-06-18", "2018-06-19"))
    assert ex_row["cash_receivable_inr"] == record["parent_quantity_before_ex_open"] * 2.0
    assert ex_row["cash_distribution_paid_inr"] == 0 and ex_row["locked_claim_inr"] > 0
    assert paid_row["cash_distribution_paid_inr"] == ex_row["cash_receivable_inr"] and paid_row["cash_receivable_inr"] == 0
    assert listing_row["locked_claim_inr"] == float(Decimal(record["entitlement_exact"])) * 20.0
    assert record["whole_units_sold"] == record["whole_units"]
    disposal = orders.loc[orders.get("order_type", pd.Series(index=orders.index, dtype=object)).eq(
        "corporate_action_whole_claim_disposal")]
    assert len(disposal) == 1 and disposal.iloc[0]["time"] == pd.Timestamp("2018-06-19")
    assert sale_row["locked_claim_inr"] == float(Decimal(record["fractional_units_exact"])) * 20.0

    entry_targets = pd.DataFrame(0.0, index=trade_days, columns=names)
    entry_targets.loc[trade_days[1], "PARENT"] = 0.5
    entry_rebalance = pd.Series(False, index=trade_days)
    entry_rebalance.loc[trade_days[1]] = True
    entry_equity, _, entry_stats = cash_engine._simulate(
        {"open": opens, "close": closes}, entry_targets, entry_rebalance, 10_000.0, 1.0, 50.0,
        start=date(2018, 4, 5), end=date(2018, 4, 5), drawdown_limit_pct=1000.0,
        detached_claim_events=[claim_event], liquidate_terminal=False,
    )
    assert entry_stats["detached_claim_events"][0]["parent_quantity_before_ex_open"] == 0
    assert entry_stats["detached_claim_events"][0]["entitlement_exact"] == "0.000"
    assert entry_equity.iloc[0]["locked_claim_inr"] == 0

    # RELCAPITAL carries RHFL only across the ex-date, never for a post-ex-date entry.
    rel_days = pd.to_datetime(["2017-09-04", "2017-09-05", "2017-09-08", "2017-09-21",
                               "2017-09-25", "2017-10-02"])
    rel_parent = pd.DataFrame({"close": [100.0, 70.0, 75.0, 70.0, 72.0, 80.0]}, index=rel_days)
    rhfl = pd.Series({rel_days[2]: 20.0, rel_days[5]: np.nan})
    assert np.isclose(interval_return(rel_parent, rhfl, rel_days[0], rel_days[2]), -0.05)
    assert np.isclose(interval_return(rel_parent, rhfl, rel_days[1], rel_days[2]), 75.0 / 70.0 - 1)
    assert np.isclose(interval_return(rel_parent, rhfl, rel_days[4], rel_days[5]), 80.0 / 72.0 - 1)

    # A finite score cannot clear an unmatched merger dependency.
    score_sessions = list(pd.date_range("2017-01-02", periods=300, freq="B"))
    score_index = {day: i for i, day in enumerate(score_sessions)}
    signal_day = score_sessions[280]
    price_values = np.linspace(10.0, 20.0, len(score_sessions))
    finite_score, _ = audit.score_at(price_values, 280, "A")
    dep = {"candidate_id": "NIFTY200-A-M", "signal_date": signal_day.date().isoformat(), "rule": "A",
           "date": "2017-09-05", "entity": "UNKNOWN|INE000A01001", "input": "signal_merger",
           "source": "NSE corporate-action feed", "reason": "unreviewed merger entitlement"}
    dep_key = audit.dependency_key(dep)
    unknown = pd.DataFrame([{"candidate_id": dep["candidate_id"], "signal_date": dep["signal_date"],
                             "symbol": "UNKNOWN", "isin": "INE000A01001", "canonical": "INE000A01001",
                             "score": finite_score, "rank": 1, "score_status": "UNKNOWN_DATA",
                             "unresolved_reason": dep["reason"], "unresolved_dependency_keys": [dep_key]}])
    dep["dependency_key"] = dep_key
    score_frame = pd.DataFrame({"adj_close": price_values, "close": price_values,
                                "adj_factor_cumulative": np.ones(len(score_sessions))}, index=score_sessions)
    unresolved_target = choose_target(dep["candidate_id"], signal_day, [], score_sessions, unknown, score_index,
                                      {"INE000A01001": score_frame}, pd.Series(dtype=float), [], {dep_key: dep})
    assert unresolved_target["target_status"] == "BLOCKED"
    assert unresolved_target["unresolved"][0]["unmatched_dependency_keys"][0]["reason"] == dep["reason"]

    # An actual later raw-open gap keeps the earlier executed prefix and its capital path.
    gap_days = list(pd.to_datetime(["2018-01-30", "2018-01-31", "2018-02-01", "2018-02-02", "2018-02-05"]))
    gap_names = [f"ISIN{i:02d}" for i in range(20)]
    gap_rows = [{"date": day, "canonical": name, "isin": name, "symbol": f"S{i:02d}",
                 "open": (np.nan if day == gap_days[-1] and i == 0 else 100.0), "close": 100.0}
                for day in gap_days for i, name in enumerate(gap_names)]
    gap_data = pd.DataFrame(gap_rows)
    gap_actions = pd.DataFrame(columns=["ex_date", "symbol", "resolved_symbol", "isin", "type", "raw_subject", "cash_amount"])
    first_schedule = {"signal_date": gap_days[0].date().isoformat(), "canonical_names": gap_names,
                      "selected": [{"canonical": name} for name in gap_names]}
    second_schedule = {"signal_date": gap_days[3].date().isoformat(), "canonical_names": gap_names,
                       "selected": [{"canonical": name} for name in gap_names]}
    with tempfile.TemporaryDirectory(dir=ROOT) as temp_dir:
        previous_local = LOCAL
        LOCAL = Path(temp_dir) / "ledgers"
        try:
            prefix = run_account("NIFTY200-A-M", pd.DataFrame(), [first_schedule, second_schedule], gap_data,
                                 gap_actions, gap_days, "2018-02-05")
        finally:
            LOCAL = previous_local
    assert prefix["status"] == "ACTUAL_PREFIX_STOPPED_AT_FIRST_MATERIAL_GAP"
    assert prefix["actual_order_count"] >= 20 and prefix["valid_through"] == "2018-02-02"
    assert prefix["ending_positions"] and prefix["ending_concentration"]["invested_reconciliation_residual_inr"] < 0.05
    assert np.isclose(prefix["drawdown_recovery"]["max_drawdown_pct"], prefix["max_drawdown_pct"])

    # Future data cannot change an account stopped before a detached claim's listing.
    causal_end = pd.Timestamp("2018-04-06")
    causal_sessions = list(pd.to_datetime(["2018-04-02", "2018-04-03", "2018-04-04", "2018-04-05",
                                           "2018-04-06", "2018-06-18", "2018-06-19"]))
    causal_names = ["INE423A01024"] + [f"TEST{i:02d}" for i in range(19)]
    causal_rows = []
    for day in causal_sessions:
        for i, name in enumerate(causal_names):
            symbol = "ADANIENT" if i == 0 else f"S{i:02d}"
            close = 90.0 if i == 0 and day >= pd.Timestamp("2018-04-05") else 100.0
            open_price = 98.0 if day == pd.Timestamp("2018-04-03") else close
            causal_rows.append({"date": day, "symbol": symbol, "isin": name, "canonical": name,
                                "open": open_price, "close": close})
    causal_rows.extend([
        {"date": pd.Timestamp("2018-06-18"), "symbol": "ADANIGREEN", "isin": AGEL_ISIN,
         "canonical": AGEL_ISIN, "open": 20.0, "close": 20.0},
        {"date": pd.Timestamp("2018-06-19"), "symbol": "ADANIGREEN", "isin": AGEL_ISIN,
         "canonical": AGEL_ISIN, "open": 22.0, "close": 22.0},
    ])
    causal_data = pd.DataFrame(causal_rows)
    causal_actions = pd.DataFrame([{"ex_date": pd.Timestamp("2018-04-05"), "resolved_symbol": "ADANIENT",
                                    "symbol": "ADANIENT", "isin": "INE423A01024", "type": "demerger",
                                    "raw_subject": "Scheme of arrangement - Adani Green Energy", "cash_amount": np.nan}])
    causal_schedule = [{"signal_date": "2018-04-02", "canonical_names": causal_names,
                        "selected": [{"canonical": name} for name in causal_names]}]
    removed_future_data = causal_data.loc[causal_data["date"].le(causal_end)].copy()
    perturbed_future_data = causal_data.copy()
    future_rows = perturbed_future_data["date"].gt(causal_end)
    perturbed_future_data.loc[future_rows, ["open", "close"]] = 1_000_000.0
    perturbed_future_data.loc[future_rows, ["symbol", "isin", "canonical"]] = "FUTURE_ALIAS"
    future_action = {"ex_date": pd.Timestamp("2018-06-20"), "resolved_symbol": "ADANIENT",
                     "symbol": "ADANIENT", "isin": "INE423A01024", "type": "dividend",
                     "raw_subject": "Future action", "cash_amount": 1_000_000.0}
    causal_variants = [
        (causal_data, causal_actions, causal_sessions),
        (removed_future_data, causal_actions, causal_sessions[:5]),
        (perturbed_future_data, pd.concat([causal_actions, pd.DataFrame([future_action])], ignore_index=True), causal_sessions),
    ]
    causal_snapshots = []
    with tempfile.TemporaryDirectory(dir=ROOT) as temp_dir:
        previous_local = LOCAL
        try:
            for variant_index, (variant_data, variant_actions, variant_sessions) in enumerate(causal_variants):
                LOCAL = Path(temp_dir) / f"claim_causality_{variant_index}"
                account = run_account("NIFTY200-A-M", pd.DataFrame(), causal_schedule, variant_data,
                                      variant_actions, variant_sessions, causal_end.date().isoformat())
                causal_snapshots.append((account,
                                         pd.read_csv(account["orders_file_local"]),
                                         pd.read_csv(account["equity_file_local"])))
        finally:
            LOCAL = previous_local
    baseline, baseline_orders, baseline_equity = causal_snapshots[0]
    assert baseline["actual_order_count"] == len(baseline_orders) == 20
    assert int(baseline_orders.loc[baseline_orders["symbol"].eq("INE423A01024"), "quantity"].sum()) == 499
    assert np.isclose(baseline["ending_locked_claim_inr"], 4_990.0, atol=1e-8)
    invariant_fields = ("status", "valid_through", "actual_order_count", "ending_nav_inr", "ending_cash_inr",
                        "ending_invested_inr", "ending_cash_receivable_inr", "ending_locked_claim_inr",
                        "max_drawdown_pct", "turnover_inr", "fees_inr", "ending_positions",
                        "ending_concentration", "drawdown_recovery", "first_material_blocker", "later_material_blockers")
    for account, account_orders, account_equity in causal_snapshots[1:]:
        assert {key: baseline[key] for key in invariant_fields} == {key: account[key] for key in invariant_fields}
        pd.testing.assert_frame_equal(baseline_orders, account_orders, check_dtype=False)
        pd.testing.assert_frame_equal(baseline_equity, account_equity, check_dtype=False)


def choose_selection_bound(lower: float, upper: float, cutoff: float) -> bool:
    return upper >= cutoff


def normalize_index_label(value: object) -> str:
    return "".join(str(value).upper().split())


def matched_tri_results(accounts: list[dict]) -> tuple[list[dict], str]:
    tri_path = ROOT / "work" / "data" / "index_daily" / "nifty200_tri_raw_2017_2026.json"
    source = json.loads(tri_path.read_text(encoding="utf-8"))
    if normalize_index_label(source.get("index", "")) != "NIFTY200" or "Gross Total Return" not in source.get("series", ""):
        raise ValueError("registered NIFTY 200 Gross TRI source metadata mismatch")
    values = {}
    for request in source.get("requests", []):
        if request.get("httpStatus") != 200:
            raise ValueError("registered NIFTY 200 TRI capture contains a failed request")
        for row in request.get("rows", []):
            if normalize_index_label(row.get("Index Name", "")) != "NIFTY200":
                raise ValueError(f"unexpected index in registered TRI capture: {row.get('Index Name')!r}")
            day = pd.to_datetime(row["Date"], format="%d %b %Y").date()
            value = float(row["TotalReturnsIndex"])
            if day in values or not np.isfinite(value) or value <= 0:
                raise ValueError(f"invalid or duplicate registered TRI row: {row}")
            values[day] = value
    results = []
    common_anchor = max(day for day in values if day <= date(2018, 1, 1))
    for account in accounts:
        end_day = date.fromisoformat(account["valid_through"])
        start_day = date.fromisoformat(account["first_order_date"]) if account.get("first_order_date") else None
        if end_day not in values:
            results.append({"candidate_id": account["candidate_id"],
                            "valuation_scenario": account["valuation_scenario"],
                            "slippage_bps_per_side": account["slippage_bps_per_side"],
                            "status": "BLOCKED_NO_EXACT_MATCHED_TRI_DATE", "matched_through": end_day.isoformat()})
            continue
        common_return = values[end_day] / values[common_anchor] - 1
        if start_day is None:
            tri_return = 0.0
            tri_nav = CAPITAL
            cash_wait_days = (end_day - date(2018, 1, 1)).days
            prior_day = None
            prior_return = 0.0
        elif start_day not in values:
            results.append({"candidate_id": account["candidate_id"],
                            "valuation_scenario": account["valuation_scenario"],
                            "slippage_bps_per_side": account["slippage_bps_per_side"],
                            "status": "BLOCKED_NO_EXACT_TRI_ENTRY_DATE", "entry_date": start_day.isoformat()})
            continue
        else:
            tri_return = values[end_day] / values[start_day] - 1
            tri_nav = CAPITAL * (1 + tri_return)
            cash_wait_days = (start_day - date(2018, 1, 1)).days
            prior_day = max((day for day in values if day < start_day), default=None)
            prior_return = values[end_day] / values[prior_day] - 1 if prior_day else 0.0
        strategy_return = float(account["ending_nav_inr"]) / CAPITAL - 1
        results.append({"candidate_id": account["candidate_id"],
                        "valuation_scenario": account["valuation_scenario"],
                        "slippage_bps_per_side": account["slippage_bps_per_side"],
                        "status": "PREFIX_GROSS_TRI_TIMING_SENSITIVITIES",
                        "cash_wait_days": cash_wait_days,
                        "tri_entry_date": start_day.isoformat() if start_day else None,
                        "matched_through": end_day.isoformat(),
                        "tri_start_value": values[start_day] if start_day else None,
                        "tri_end_value": values[end_day],
                        "tri_gross_return_pct": tri_return * 100,
                        "tri_reference_ending_nav_inr": tri_nav,
                        "strategy_net_return_pct": strategy_return * 100,
                        "excess_vs_gross_tri_pct_points": (strategy_return - tri_return) * 100,
                        "entry_close_reference_tri_return_pct": tri_return * 100,
                        "entry_close_reference_excess_pct_points": (strategy_return - tri_return) * 100,
                        "prior_close_eod_proxy_date": prior_day.isoformat() if prior_day else None,
                        "prior_close_eod_proxy_tri_return_pct": prior_return * 100,
                        "prior_close_eod_proxy_excess_pct_points": (strategy_return - prior_return) * 100,
                        "common_start_anchor_date": common_anchor.isoformat(),
                        "common_start_anchor_value": values[common_anchor],
                        "common_start_buy_hold_tri_return_pct": common_return * 100,
                        "common_start_excess_pct_points": (strategy_return - common_return) * 100,
                        "tri_execution_assumption": "Gross NIFTY 200 TRI. Common reference is buy/hold from the last official EOD close on or before 2018-01-01 through this prefix endpoint. Entry-close reference begins at the first order date close; prior-close EOD proxy begins at the prior TRI close and includes the overnight move. Neither reproduces an open fill or is a guaranteed bound; no investable-wrapper fees/tracking are modeled."})
    return results, audit.sha256_file(tri_path)


def run() -> dict:
    global LOCAL
    sessions, data, actions, signals, index, series_by_canonical, child, dependency_records, cache_manifest = setup()
    cache_manifest_artifact = ROOT / "outputs" / "nifty200_signal_cache_manifest_cycle4_2026-11-03.json"
    cache_manifest_artifact.write_text(json.dumps(cache_manifest, indent=2) + "\n", encoding="utf-8")
    for (symbol, date_text) in RIGHTS:
        identity = actions["resolved_symbol"].eq(symbol) | actions["symbol"].eq(symbol)
        if not identity.where(actions["ex_date"].eq(pd.Timestamp(date_text)), False).any():
            raise ValueError(f"registered rights source event missing for {symbol} {date_text}")
    for (symbol, date_text), amount in DIVIDENDS.items():
        rows = actions.loc[actions["symbol"].eq(symbol) & actions["ex_date"].eq(pd.Timestamp(date_text))]
        if rows.empty or not pd.to_numeric(rows["cash_amount"], errors="coerce").eq(amount).any():
            raise ValueError(f"registered dividend source event/amount missing for {symbol} {date_text}")
    all_certificates, first_blockers, correction_log = {}, {}, []
    for candidate in CONFIGURATIONS:
        all_certificates[candidate] = []
        prior = []
        dates = sorted(signals.loc[signals["candidate_id"].eq(candidate), "signal_date"].drop_duplicates())
        for date_text in dates:
            day = pd.Timestamp(date_text)
            cert = choose_target(candidate, day, prior, sessions, signals, index,
                                 series_by_canonical, child, correction_log, dependency_records)
            if cert["target_status"].startswith("CERTIFIED") and index[day] + 1 >= len(sessions):
                cert["target_status"] = "BLOCKED"
                cert["unresolved"].append({"input": "next_session_order",
                                           "reason": "no source-session execution date follows this certified decision"})
            cert["canonical_names"] = [r["canonical"] for r in cert["selected"]]
            all_certificates[candidate].append(cert)
            if cert["target_status"] != "CERTIFIED_UNDER_REGISTERED_SOURCE_CORRECTIONS":
                first_blockers[candidate] = {"date": date_text, "kind": "signal_or_order",
                                             "unresolved": cert["unresolved"]}
                break
            prior = [r["canonical"] for r in cert["selected"]]
    correction_path = ROOT / "outputs" / "nifty200_source_corrections_cycle4_2026-11-03.csv"
    pd.DataFrame(correction_log).drop_duplicates().to_csv(correction_path, index=False)
    cutoff = max(day for day in sessions if day <= audit.CUTOFF)
    accounts, cost_sensitivities, native_base = [], [], {}
    for candidate in CONFIGURATIONS:
        certified = [item for item in all_certificates[candidate]
                     if item["target_status"] == "CERTIFIED_UNDER_REGISTERED_SOURCE_CORRECTIONS"]
        end_day = first_blockers.get(candidate, {}).get("date", cutoff.date().isoformat())
        signal_blocker = first_blockers.get(candidate)
        for scenario in ("base", "zero_mark_stress"):
            result = run_account(candidate, signals, certified, data, actions, sessions,
                                 end_day, scenario, SLIPPAGE_BPS, signal_blocker)
            result["comparison_scope"] = "native_stop"
            accounts.append(result)
            if scenario == "base":
                native_base[candidate] = result
    common_supported_end = min(result["valid_through"] for result in native_base.values())
    previous_local = LOCAL
    LOCAL = DETAIL / "sequential_cash_prefixes_cycle4_2026-11-03_common_costs"
    try:
        for candidate in CONFIGURATIONS:
            certified = [item for item in all_certificates[candidate]
                         if item["target_status"] == "CERTIFIED_UNDER_REGISTERED_SOURCE_CORRECTIONS"]
            for bps in (10.0, 50.0, 100.0, 200.0):
                if bps == SLIPPAGE_BPS and native_base[candidate]["valid_through"] == common_supported_end:
                    native_base[candidate]["comparison_scope"] = "native_stop_and_common_supported_dates"
                    continue
                result = run_account(candidate, signals, certified, data, actions, sessions,
                                     common_supported_end, "base", bps, None)
                result["comparison_scope"] = "common_supported_dates"
                result["requested_common_end"] = common_supported_end
                if result["valid_through"] == common_supported_end:
                    result["status"] = "ACTUAL_PREFIX_TO_COMMON_SUPPORTED_END"
                cost_sensitivities.append(result)
    finally:
        LOCAL = previous_local
    all_accounts = accounts + cost_sensitivities
    tri_results, tri_sha256 = matched_tri_results(all_accounts)
    tri_by_case = {(row["candidate_id"], row["valuation_scenario"], row["slippage_bps_per_side"]): row
                   for row in tri_results}
    common_date_cost_comparison = []
    for candidate in CONFIGURATIONS:
        for bps in (10.0, 50.0, 100.0, 200.0):
            if bps == SLIPPAGE_BPS and native_base[candidate]["valid_through"] == common_supported_end:
                account = native_base[candidate]
            else:
                account = next(item for item in cost_sensitivities
                               if item["candidate_id"] == candidate
                               and item["slippage_bps_per_side"] == bps)
            tri = tri_by_case[(candidate, "base", bps)]
            common_date_cost_comparison.append({
                "candidate_id": candidate, "requested_common_end": common_supported_end,
                "valid_through": account["valid_through"],
                "fully_matches_common_end": account["valid_through"] == common_supported_end,
                "slippage_bps_per_side": bps, "status": account["status"],
                "actual_order_count": account["actual_order_count"],
                "ending_nav_inr": account["ending_nav_inr"], "fees_inr": account["fees_inr"],
                "slippage_cost_inr": account["slippage_cost_inr"],
                "max_drawdown_pct": account["max_drawdown_pct"],
                "common_start_buy_hold_tri_return_pct": tri.get("common_start_buy_hold_tri_return_pct"),
                "common_start_excess_pct_points": tri.get("common_start_excess_pct_points"),
                "prior_close_eod_proxy_tri_return_pct": tri.get("prior_close_eod_proxy_tri_return_pct"),
                "prior_close_eod_proxy_excess_pct_points": tri.get("prior_close_eod_proxy_excess_pct_points"),
            })
    blocker_summary = []
    for candidate, certificates in all_certificates.items():
        blocked = next((item for item in certificates
                        if item["target_status"] != "CERTIFIED_UNDER_REGISTERED_SOURCE_CORRECTIONS"), None)
        if blocked is None:
            blocker_summary.append({"candidate_id": candidate, "certified_signal_count": len(certificates),
                                    "first_signal_blocker": None})
            continue
        grouped = {}
        for issue in blocked["unresolved"]:
            refs = issue.get("unmatched_dependency_keys", [])
            if not refs:
                refs = [{"key": "", "entity": issue.get("symbol", ""),
                         "input": issue.get("input", "unknown"), "date": blocked["signal_date"],
                         "reason": issue.get("reason", "unresolved dependency")}]
            for ref in refs:
                key = ref.get("key", "")
                dependency = dependency_records.get(key, ref)
                group_key = tuple(str(dependency.get(field, "")) for field in
                                  ("entity", "input", "reason", "source", "resolution_attempt", "impact"))
                group = grouped.setdefault(group_key, {"keys": set(), "dates": set()})
                if key:
                    group["keys"].add(key)
                if dependency.get("date"):
                    group["dates"].add(str(dependency["date"]))
        group_rows = []
        for group_key, group in sorted(grouped.items()):
            entity, input_name, reason, source, attempt, impact = group_key
            keys = sorted(group["keys"])
            dates = sorted(group["dates"])
            group_rows.append({"entity": entity, "input": input_name, "reason": reason,
                               "source": source, "resolution_attempt": attempt, "impact": impact,
                               "dependency_count": len(keys), "date_start": dates[0] if dates else None,
                               "date_end": dates[-1] if dates else None,
                               "dependency_keys_sha256": hashlib.sha256("\n".join(keys).encode()).hexdigest(),
                               "dependency_key_samples": keys[:3]})
        blocker_summary.append({"candidate_id": candidate,
                                "certified_signal_count": sum(
                                    item["target_status"] == "CERTIFIED_UNDER_REGISTERED_SOURCE_CORRECTIONS"
                                    for item in certificates),
                                "first_signal_blocker": {"signal_date": blocked["signal_date"],
                                                         "status": blocked["target_status"],
                                                         "unresolved_dependency_groups": group_rows}})
    experiment_rows = []
    for account in all_accounts:
        tri = tri_by_case.get((account["candidate_id"], account["valuation_scenario"],
                               account["slippage_bps_per_side"]), {})
        experiment_rows.append({"cycle_id": "2026-11-03-cycle4", "candidate_id": account["candidate_id"],
                                "comparison_scope": account.get("comparison_scope", "native_stop"),
                                "requested_common_end": account.get("requested_common_end", ""),
                                "valuation_scenario": account["valuation_scenario"],
                                "slippage_bps_per_side": account["slippage_bps_per_side"],
                                "valid_through": account.get("valid_through", ""), "status": account["status"],
                                "orders": account.get("actual_order_count", 0),
                                "turnover_inr": account.get("turnover_inr", ""),
                                "fees_inr": account.get("fees_inr", ""),
                                "slippage_cost_inr": account.get("slippage_cost_inr", ""),
                                "ending_nav_inr": account.get("ending_nav_inr", ""),
                                "max_drawdown_pct": account.get("max_drawdown_pct", ""),
                                "entry_close_reference_tri_return_pct": tri.get("entry_close_reference_tri_return_pct", ""),
                                "entry_close_reference_excess_pct_points": tri.get("entry_close_reference_excess_pct_points", ""),
                                "prior_close_eod_proxy_tri_return_pct": tri.get("prior_close_eod_proxy_tri_return_pct", ""),
                                "prior_close_eod_proxy_excess_pct_points": tri.get("prior_close_eod_proxy_excess_pct_points", ""),
                                "common_start_buy_hold_tri_return_pct": tri.get("common_start_buy_hold_tri_return_pct", ""),
                                "common_start_excess_pct_points": tri.get("common_start_excess_pct_points", ""),
                                "cagr": "NOT REPORTED: stopped/provisional prefix"})
    experiment_path = ROOT / "outputs" / "experiment_register_cycle4_2026-11-03.csv"
    pd.DataFrame(experiment_rows).to_csv(experiment_path, index=False)
    common_cost_path = ROOT / "outputs" / "nifty200_cycle4_common_date_cost_comparison_2026-11-03.csv"
    pd.DataFrame(common_date_cost_comparison).to_csv(common_cost_path, index=False)
    pd.DataFrame(tri_results).to_csv(
        ROOT / "outputs" / "nifty200_cycle4_benchmark_timing_2026-11-03.csv", index=False)
    cumulative_experiment_path = ROOT / "outputs" / "experiment_register_cumulative_cycle4_2026-11-03.csv"
    previous_experiment_path = ROOT / "outputs" / "experiment_register_cumulative_2026-11-02.csv"
    previous_experiments = pd.read_csv(previous_experiment_path) if previous_experiment_path.is_file() else pd.DataFrame()
    cumulative = pd.concat([previous_experiments, pd.DataFrame(experiment_rows)], ignore_index=True, sort=False)
    cumulative.to_csv(cumulative_experiment_path, index=False)
    ledger_bundle_path = ROOT / "outputs" / "nifty200_cycle4_actual_ledgers_2026-11-03.json"
    actual_results_path = ROOT / "outputs" / "nifty200_cycle4_actual_results_2026-11-03.json"
    blocker_summary_path = ROOT / "outputs" / "nifty200_cycle4_dependency_blockers_2026-11-03.json"
    ledgers = []
    for account in accounts + cost_sensitivities:
        ledger = {key: account.get(key) for key in
                  ("candidate_id", "comparison_scope", "requested_common_end", "valuation_scenario",
                   "slippage_bps_per_side", "status", "valid_through")}
        ledger["ending_positions"] = account.get("ending_positions", [])
        ledger["ending_concentration"] = account.get("ending_concentration", {})
        ledger["drawdown_recovery"] = account.get("drawdown_recovery", {})
        for field, key in (("orders", "orders_file_local"), ("equity", "equity_file_local"),
                           ("events", "events_file_local")):
            local_path = account.get(key)
            if not local_path:
                ledger[field] = [] if field != "events" else {}
                continue
            path = ROOT / local_path
            if field == "events":
                ledger[field] = json.loads(path.read_text(encoding="utf-8"))
            else:
                ledger[field] = json.loads(pd.read_csv(path).to_json(orient="records", date_format="iso"))
        ledgers.append(ledger)
    ledger_bundle_path.write_text(json.dumps(ledgers, indent=2) + "\n", encoding="utf-8")
    blocker_summary_path.write_text(json.dumps({
        "protocol_id": "NIFTY200-v1.8-combined-share-conversion-and-account-causality",
        "signal_schedule_blockers": blocker_summary,
        "account_stop_blockers": [{"candidate_id": account["candidate_id"],
                                   "valuation_scenario": account["valuation_scenario"],
                                   "slippage_bps_per_side": account["slippage_bps_per_side"],
                                   "valid_through": account.get("valid_through"),
                                   "blocker": ({key: account["first_material_blocker"].get(key)
                                                for key in ("date", "kind", "symbol", "canonical", "event",
                                                            "entity", "input", "reason", "source_subject")}
                                               if account.get("first_material_blocker") and
                                               "unresolved" not in account["first_material_blocker"] else
                                               {"date": account.get("valid_through"), "kind": "signal_or_order",
                                                "reason": "Ranking-changing signal dependencies remain unresolved; see grouped signal schedule blockers."})}
                                   for account in all_accounts]}, indent=2) + "\n", encoding="utf-8")
    result = {
        "protocol_id": "NIFTY200-v1.8-combined-share-conversion-and-account-causality",
        "evaluation": {"start": "2018-01-01", "full_end": audit.CUTOFF.date().isoformat(),
                       "matched_through": {row["candidate_id"]: row.get("valid_through") for row in accounts},
                       "common_cost_comparison_end": common_supported_end},
        "capital_inr": CAPITAL, "cash_yield": "zero", "base_slippage_bps_per_side": SLIPPAGE_BPS,
        "score_certificates": all_certificates, "accounts": accounts,
        "cost_sensitivities": cost_sensitivities,
        "common_date_cost_comparison": common_date_cost_comparison,
        "common_date_cost_comparison_local": str(common_cost_path.relative_to(ROOT)),
        "matched_tri_benchmark": {"series": "official NIFTY 200 Gross TRI",
                                  "source_sha256": tri_sha256,
                                  "cash_waiting_time_included": True, "results": tri_results},
        "source_cache_schema": cache_manifest,
        "correction_log_local": str(correction_path.relative_to(ROOT)),
        "experiment_register_local": str(experiment_path.relative_to(ROOT)),
        "cumulative_experiment_register_local": str(cumulative_experiment_path.relative_to(ROOT)),
        "actual_ledgers_bundle": str(ledger_bundle_path.relative_to(ROOT)),
        "actual_results_summary": str(actual_results_path.relative_to(ROOT)),
        "dependency_blockers_summary": str(blocker_summary_path.relative_to(ROOT)),
        "signal_cache_manifest_artifact": str(cache_manifest_artifact.relative_to(ROOT)),
        "performance_gate": "NO FULL-PERIOD CAGR; no short-prefix 20% claim; no ranking or deployment",
        "research_limits": [
            "IDFC event classification remains an evidence-supported inference, not a located exact original notice.",
            "The AGEL prelisting value is an MSCI-inspired model convention using raw AEL cum/ex closes; it is not observed market price or proof of 2018 NIFTY index treatment.",
            "AGEL fractional trustee sale date, fill, fees, and cash payment are not evidenced; residual fractions are nonspendable fixed-mark receivables.",
            "Unobserved dividend pay dates use the registered 30-calendar-day delayed cash assumption; no interest is credited.",
            "Costs remain uncalibrated. Zero-mark stress is not a proven final-wealth lower bound because sizing can change.",
        ],
    }
    summary_fields = ("candidate_id", "comparison_scope", "requested_common_end", "status",
                      "valuation_scenario", "slippage_bps_per_side",
                      "valid_through", "starting_capital_inr", "actual_order_count", "actual_buy_count",
                      "actual_sell_count", "first_order_date", "ending_nav_inr", "ending_cash_inr",
                      "ending_invested_inr", "ending_cash_receivable_inr", "ending_locked_claim_inr",
                      "ending_pending_share_value_inr",
                      "max_drawdown_pct", "drawdown_recovery", "turnover_inr", "fees_inr",
                      "fees_by_component_inr", "slippage_cost_inr", "cash_distributions_inr",
                      "cash_distribution_entitlements_inr", "max_nav_reconciliation_residual_inr",
                      "ending_positions", "ending_concentration", "cagr")
    actual_results_path.write_text(json.dumps({
        "protocol_id": result["protocol_id"], "capital_inr": CAPITAL,
        "cash_yield": "zero", "performance_gate": result["performance_gate"],
        "accounts": [{key: account.get(key) for key in summary_fields} for account in accounts],
        "cost_sensitivities": [{key: account.get(key) for key in summary_fields} for account in cost_sensitivities],
        "common_date_cost_comparison": common_date_cost_comparison,
        "matched_tri_benchmark": result["matched_tri_benchmark"],
        "research_limits": result["research_limits"],
        "candidate_dependency_audit": "nifty200_candidate_dependency_audit_2026-11-03.json",
        "dependency_blockers": blocker_summary_path.name,
        "actual_ledgers": ledger_bundle_path.name,
    }, indent=2) + "\n", encoding="utf-8")
    OUT.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    output_paths = [OUT, correction_path, experiment_path, common_cost_path, cumulative_experiment_path,
                    ledger_bundle_path, actual_results_path, blocker_summary_path, cache_manifest_artifact]
    for account in accounts + cost_sensitivities:
        for key in ("orders_file_local", "equity_file_local", "events_file_local"):
            if account.get(key):
                output_paths.append(ROOT / account[key])
    manifest_path = ROOT / "outputs" / "nifty200_cycle4_source_code_schema_manifest_2026-11-03.json"
    manifest = {
        "cycle_id": "2026-11-03-cycle4", "protocol_id": result["protocol_id"],
        "generation_command": "python work/audit_strategy_dependencies.py; python work/advance_nifty200_cash_prefixes.py",
        "audit_code_sha256": audit.sha256_file(ROOT / "work" / "audit_strategy_dependencies.py"),
        "runner_code_sha256": audit.sha256_file(Path(__file__)),
        "account_engine_code_sha256": audit.sha256_file(ROOT / "work" / "upstox_quant.py"),
        "signal_cache_schema": cache_manifest["schema_version"],
        "signal_cache_manifest_sha256": audit.sha256_file(audit.SIGNAL_CACHE / "signal_cache_manifest.json"),
        "signal_cache_sources": cache_manifest["sources"],
        "signal_cache_outputs": cache_manifest["output_sha256"],
        "matched_tri_source_sha256": tri_sha256,
        "curated_output_sha256": {path.relative_to(ROOT).as_posix(): audit.sha256_file(path)
                                   for path in sorted(set(output_paths)) if path.is_file()},
    }
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    result["source_code_schema_manifest"] = str(manifest_path.relative_to(ROOT))
    OUT.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    manifest["curated_output_sha256"][OUT.relative_to(ROOT).as_posix()] = audit.sha256_file(OUT)
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))
    return result


if __name__ == "__main__":
    self_check()
    run()
