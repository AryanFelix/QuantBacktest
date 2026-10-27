"""Reconcile ETF cash distributions and split-unit conventions for the NIFTY/Gold blend."""

from __future__ import annotations

from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
RUNS = ROOT / "work" / "backtests" / "volatility_weighted_blend"
DATA = ROOT / "work" / "data" / "etf_daily"
OUT = ROOT / "outputs" / "etf_corporate_action_audit.csv"
PORTFOLIOS = ("fixed_50_50", "inverse_vol_63d", "fixed_50_50_quarterly", "inverse_vol_63d_quarterly")
SLIPPAGE = (10, 50)
NIPPON_NIFTY_ACTIONS = "https://investeasy.nipponindiaim.com/rmfGsamnew/Products/NiftyBeES/CorporateAction.aspx"
NIPPON_GOLD_ACTIONS = "https://investeasy.nipponindiaim.com/rmfGsamnew/Products/GoldBeES/CorporateAction.aspx"
NSE_NIFTY = "https://www.nseindia.com/get-quote/equity/NIFTYBEES/Nippon-India-ETF-Nifty-50-BeES"
NSE_GOLD = "https://www.nseindia.com/get-quote/equity/GOLDBEES/NIPPON-INDIA-ETF-GOLD-BEES?series=EQ"


def close_on_or_before(symbol: str, day: str) -> tuple[float, float]:
    if symbol == "NIFTYBEES":
        path = DATA / "NSE_EQ_INF204KB14I2-days-1-2014-01-01-2026-10-23.csv"
    else:
        path = DATA / "GOLDBEES-days-1-2014-01-01-2026-10-23.csv"
    bars = pd.read_csv(path, parse_dates=["time"]).set_index("time")
    timestamp = pd.Timestamp(day, tz="Asia/Kolkata")
    prior = bars.loc[bars.index < timestamp, "close"]
    current = bars.loc[bars.index == timestamp, "close"]
    assert not prior.empty and len(current) == 1
    return float(prior.iloc[-1]), float(current.iloc[0])


def shares_held_before_exdate(portfolio: str, slip: int, ex_date: str) -> int:
    orders = pd.read_csv(RUNS / f"{portfolio}__full_2014_plus__{slip}bps" / "orders.csv", parse_dates=["time"])
    cutoff = pd.Timestamp(ex_date, tz="Asia/Kolkata")
    prior = orders[(orders.symbol == "NIFTYBEES") & (orders.time < cutoff)]
    quantity = int(prior.loc[prior.side == "buy", "quantity"].sum() - prior.loc[prior.side == "sell", "quantity"].sum())
    assert quantity >= 0
    return quantity


def main() -> None:
    rows = []
    for ex_date, record_date, historic_rate, data_unit_factor in (
        ("2014-03-10", "2014-03-11", 7.0, 0.1),
        ("2015-02-18", "2015-02-20", 8.0, 0.1),
    ):
        quantities = [shares_held_before_exdate(name, slip, ex_date) for name in PORTFOLIOS for slip in SLIPPAGE]
        assert max(quantities) == 0
        rows.append({
            "symbol": "NIFTYBEES", "isin": "INF204KB14I2", "action": "cash distribution",
            "ex_date": ex_date, "record_date": record_date, "historic_rate_inr_per_unit": historic_rate,
            "historic_to_saved_unit_factor": data_unit_factor,
            "rate_in_saved_price_units_inr_per_unit": historic_rate * data_unit_factor,
            "tested_paths": len(quantities), "eligible_quantity_min": min(quantities),
            "eligible_quantity_max": max(quantities), "distribution_income_min_inr": 0.0,
            "distribution_income_max_inr": 0.0, "price_continuity_change_pct": None,
            "source_1": NIPPON_NIFTY_ACTIONS, "source_2": NSE_NIFTY,
            "finding": "No candidate path held units at the prior close; modeled distribution income is zero.",
        })

    for symbol, isin, factor, source, nse_source in (
        ("NIFTYBEES", "INF204KB14I2", 10, NIPPON_NIFTY_ACTIONS, NSE_NIFTY),
        ("GOLDBEES", "INF204KB17I5", 100, NIPPON_GOLD_ACTIONS, NSE_GOLD),
    ):
        prior, current = close_on_or_before(symbol, "2019-12-19")
        change = (current / prior - 1) * 100
        assert abs(change) < 15, f"unexpected split-date price discontinuity for {symbol}: {change:.2f}%"
        rows.append({
            "symbol": symbol, "isin": isin, "action": f"face-value split 1:{factor}",
            "ex_date": "2019-12-19", "record_date": "2019-12-20",
            "historic_rate_inr_per_unit": None, "historic_to_saved_unit_factor": None,
            "rate_in_saved_price_units_inr_per_unit": None, "tested_paths": 8,
            "eligible_quantity_min": None, "eligible_quantity_max": None,
            "distribution_income_min_inr": None, "distribution_income_max_inr": None,
            "price_continuity_change_pct": change, "source_1": source, "source_2": nse_source,
            "finding": f"Saved Upstox close series is continuous across the {factor}:1 unit split; split normalization is inferred from prices, not an API guarantee.",
        })

    rows.append({
        "symbol": "GOLDBEES", "isin": "INF204KB17I5", "action": "AMC corporate-action history coverage",
        "ex_date": None, "record_date": None, "historic_rate_inr_per_unit": None,
        "historic_to_saved_unit_factor": None, "rate_in_saved_price_units_inr_per_unit": None,
        "tested_paths": 8, "eligible_quantity_min": None, "eligible_quantity_max": None,
        "distribution_income_min_inr": 0.0, "distribution_income_max_inr": 0.0,
        "price_continuity_change_pct": None, "source_1": NIPPON_GOLD_ACTIONS, "source_2": NSE_GOLD,
        "finding": "Official AMC history lists the 2019 split and no cash distributions; this source-history observation is not a provider completeness guarantee.",
    })
    result = pd.DataFrame(rows)
    assert len(result) == 5 and result.loc[result.action == "cash distribution", "eligible_quantity_max"].eq(0).all()
    result.to_csv(OUT, index=False)
    print(f"Wrote {len(result)} source-linked action rows; both cash events have zero eligible units in all eight candidate paths.")


if __name__ == "__main__":
    main()
