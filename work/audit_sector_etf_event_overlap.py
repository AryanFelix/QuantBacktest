"""Check candidate ETF event dates against saved prices and replay fills."""

import csv
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ORDERS = ROOT / "work/backtests/nifty_sector_gold_composites/orders.csv"
EVENTS = {
    ("AUTOBEES", date(2025, 7, 14)): "unverified bonus-date lead",
    ("AUTOBEES", date(2026, 6, 9)): "unverified distribution-date lead",
    ("PHARMABEES", date(2026, 6, 11)): "unverified distribution-date lead",
}

with ORDERS.open(newline="", encoding="utf-8-sig") as f:
    orders = list(csv.DictReader(f))

print("Order fields:", ",".join(orders[0]))
positions = defaultdict(int)
for (symbol, event_date), lead in EVENTS.items():
    path = ROOT / f"work/data/etf_daily/NSE_EQ_{ {'AUTOBEES':'INF204KC1337','PHARMABEES':'INF204KC1089'}[symbol] }-days-1-2014-01-01-2026-10-23.csv"
    with path.open(newline="", encoding="utf-8-sig") as f:
        prices = list(csv.DictReader(f))
    print(f"\n{symbol} {event_date} ({lead})")
    print("Price fields:", ",".join(prices[0]))
    date_field = next(k for k in prices[0] if k.lower() in {"date", "time", "timestamp"})
    for row in prices:
        row_date = date.fromisoformat(row[date_field][:10])
        if event_date - timedelta(days=3) <= row_date <= event_date + timedelta(days=2):
            print("PRICE", row)
    path_keys = {
        (order["portfolio"], order["period"], order["exposure_cap_pct"])
        for order in orders if order["symbol"] == symbol
    }
    groups = {key: 0 for key in path_keys}
    for order in orders:
        if order["symbol"] != symbol or date.fromisoformat(order["time"][:10]) >= event_date:
            continue
        key = (order["portfolio"], order["period"], order["exposure_cap_pct"])
        groups[key] += int(order["quantity"]) * (1 if order["side"] == "buy" else -1)
    held = {key: qty for key, qty in groups.items() if qty > 0}
    print(f"paths={len(groups)} held_paths={len(held)} held_qty_min={min(held.values(), default=0)} held_qty_max={max(held.values(), default=0)}")
    print("PATHS", sorted((key, qty) for key, qty in groups.items()))
    assert groups and prices
