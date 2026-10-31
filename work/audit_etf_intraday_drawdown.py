"""Re-mark frozen ETF portfolios against daily OHLC ranges."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
CAPITAL = 1_000_000.0
SLIPPAGE_BPS = 50.0
LIMIT_PCT = 20.0
BARS = {
    "NIFTYBEES": "work/data/etf_daily/NSE_EQ_INF204KB14I2-days-1-2014-01-01-2026-10-23.csv",
    "GOLDBEES": "work/data/etf_daily/GOLDBEES-days-1-2014-01-01-2026-10-23.csv",
    "BANKBEES": "work/data/etf_daily/NSE_EQ_INF204KB15I9-days-1-2014-01-01-2026-10-23.csv",
    "ITBEES": "work/data/etf_daily/NSE_EQ_INF204KB15V2-days-1-2014-01-01-2026-10-23.csv",
    "AUTOBEES": "work/data/etf_daily/NSE_EQ_INF204KC1337-days-1-2014-01-01-2026-10-23.csv",
    "PHARMABEES": "work/data/etf_daily/NSE_EQ_INF204KC1089-days-1-2014-01-01-2026-10-23.csv",
    "PSUBNKBEES": "work/data/etf_daily/NSE_EQ_INF204KB16I7-days-1-2014-01-01-2026-10-23.csv",
}
CASES = (
    ("Quarterly fixed 50/50 control", "work/backtests/volatility_weighted_blend/fixed_50_50_quarterly__full_2014_plus__50bps"),
    ("Quarterly inverse-vol; 50/50 active sleeves", "work/backtests/volatility_weighted_blend/inverse_vol_63d_quarterly__full_2014_plus__50bps"),
    ("Quarterly inverse-vol; 65% solo / 16% target", "work/backtests/joint_exposure_volatility_sensitivity/solo65_vol16__full_2014_plus__50bps"),
    ("Quarterly inverse-vol; 80% solo / 16% target", "work/backtests/joint_exposure_volatility_sensitivity/solo80_vol16__full_2014_plus__50bps"),
    ("Quarterly inverse-vol; 50% solo sleeve", "work/backtests/single_sleeve_deployment/inverse_vol_quarterly_single_50__full_2014_plus__50bps"),
    ("Quarterly inverse-vol; 55% solo sleeve", "work/backtests/single_sleeve_deployment/inverse_vol_quarterly_single_55__full_2014_plus__50bps"),
    ("Post-hoc D55/30 parameter challenger", "work/backtests/etf_parameter_sensitivity/channel_exit_D55_30_SMA200__full_2014_plus__50bps"),
    ("Post-hoc D40/20 parameter challenger", "work/backtests/etf_parameter_sensitivity/channel_entry_D40_20_SMA200__full_2014_plus__50bps"),
    ("Walk-forward blend; 95% cap, 2020+ holdout at 50 bps", "work/backtests/donchian_gold_clean/holdout_2020_plus_95cap_50bps"),
    ("Walk-forward blend; 95% cap, 2023+ holdout at 50 bps", "work/backtests/donchian_gold_clean/holdout_recent_95cap_50bps"),
    ("Quarterly inverse-vol; 100% solo, 2020+ flat-start", "work/backtests/single_sleeve_deployment/inverse_vol_quarterly_single_100__full_2020_plus__50bps"),
    ("Monthly inverse-vol; 100% solo, 2020+ flat-start", "work/backtests/single_sleeve_deployment/inverse_vol_monthly_single_100__full_2020_plus__50bps"),
    ("Quarterly inverse-vol; 100% solo, 2023+ flat-start", "work/backtests/single_sleeve_deployment/inverse_vol_quarterly_single_100__holdout_2023_plus__50bps"),
    ("Monthly inverse-vol; 100% solo, 2023+ flat-start", "work/backtests/single_sleeve_deployment/inverse_vol_monthly_single_100__holdout_2023_plus__50bps"),
    ("Quarterly inverse-vol; 100% solo, continuous 2014+", "work/backtests/single_sleeve_deployment/inverse_vol_quarterly_single_100__full_2014_plus__50bps"),
    ("Monthly inverse-vol; 100% solo, continuous 2014+", "work/backtests/single_sleeve_deployment/inverse_vol_monthly_single_100__full_2014_plus__50bps"),
)
OUTPUT = ROOT / "outputs" / "etf_intraday_drawdown_audit.csv"


def read_daily(path: Path, index: pd.Index, columns: tuple[str, ...]) -> pd.DataFrame:
    frame = pd.read_csv(path)
    frame["date"] = frame["time"].astype(str).str[:10]
    if frame.duplicated("date", keep=False).any():
        repeated = frame.loc[frame.duplicated("date", keep=False)]
        if (repeated.groupby("date")[list(columns)].nunique(dropna=False) > 1).any().any():
            raise ValueError(f"Conflicting OHLC bars within a daily session: {path}")
    frame = frame.drop_duplicates("date").set_index("date")
    return frame.reindex(index)[list(columns)]


def mark_prices(index: pd.Index) -> dict[str, pd.DataFrame]:
    result = {}
    for symbol, path in BARS.items():
        bars = read_daily(ROOT / path, index, ("open", "high", "low", "close"))
        prior_close = bars["close"].ffill().shift(1)
        bars["close"] = bars["close"].ffill()
        for field in ("open", "high", "low"):
            bars[field] = bars[field].fillna(prior_close)
        bars = bars.fillna(0.0)
        if not np.isfinite(bars.to_numpy()).all() or (bars < 0).any().any():
            raise ValueError(f"Missing or invalid OHLC marks for {symbol}")
        result[symbol] = bars.astype(float)
    return result


def run_case(
    label: str,
    relative: str,
    starting_balance: float = CAPITAL,
    prior_peak_nav: float | None = None,
    prior_close_peak_nav: float | None = None,
    prior_peak_date: str | None = None,
    prior_close_peak_date: str | None = None,
    slippage_bps: float = SLIPPAGE_BPS,
) -> dict:
    run = ROOT / relative
    if not np.isfinite(starting_balance) or starting_balance <= 0:
        raise ValueError("starting balance must be finite and positive")
    if not np.isfinite(slippage_bps) or slippage_bps < 0:
        raise ValueError("slippage must be finite and nonnegative")
    if prior_peak_nav is not None and (not np.isfinite(prior_peak_nav) or prior_peak_nav <= 0):
        raise ValueError("prior OHLC peak must be finite and positive")
    if prior_close_peak_nav is not None and (not np.isfinite(prior_close_peak_nav) or prior_close_peak_nav <= 0):
        raise ValueError("prior close peak must be finite and positive")
    equity = pd.read_csv(run / "equity.csv")
    equity["date"] = equity["time"].astype(str).str[:10]
    equity = equity.set_index("date")
    if not equity.index.is_unique or not equity.index.is_monotonic_increasing:
        raise ValueError(f"Invalid equity dates in {run}")
    bars = mark_prices(equity.index)
    orders = pd.read_csv(run / "orders.csv")
    orders["date"] = orders["time"].astype(str).str[:10]
    order_groups = {key: part for key, part in orders.groupby("date", sort=False)}
    slip = slippage_bps / 10_000
    cash = starting_balance
    quantity = dict.fromkeys(BARS, 0)
    if prior_peak_nav is not None and prior_peak_nav >= starting_balance:
        running_peak, peak_date = prior_peak_nav, prior_peak_date or "starting_capital"
    else:
        running_peak, peak_date = starting_balance, "starting_capital"
    worst_dd = 0.0
    worst_peak_date = peak_date
    worst_trough_date = peak_date
    fold_peak = starting_balance
    fold_worst_dd = 0.0
    if prior_close_peak_nav is not None and prior_close_peak_nav >= starting_balance:
        running_close_peak, close_peak_date = prior_close_peak_nav, prior_close_peak_date or "starting_capital"
    else:
        running_close_peak, close_peak_date = starting_balance, "starting_capital"
    worst_close_dd = 0.0
    worst_close_peak_date = close_peak_date
    worst_close_trough_date = close_peak_date
    close_nav = []

    for date_key, saved in equity.iterrows():
        cash += float(saved.get("cash_yield_inr", 0.0) or 0.0)
        cash += float(saved.get("cash_distribution_inr", 0.0) or 0.0)
        for symbol, amount in quantity.items():
            if amount and (bars[symbol].loc[date_key, ["open", "high", "low", "close"]] <= 0).any():
                raise AssertionError(f"Position held without valid OHLC marks for {symbol} on {date_key}")
        pretrade_open_nav = cash + sum(quantity[symbol] * float(bars[symbol].loc[date_key, "open"]) for symbol in quantity)
        day_orders = order_groups.get(date_key)
        terminal_orders = []
        if day_orders is not None:
            for order in day_orders.itertuples(index=False):
                symbol, side = order.symbol, order.side
                amount, notional = int(order.quantity), float(order.notional)
                fee, fill = float(order.total), float(order.fill_price)
                if symbol not in quantity or amount <= 0:
                    raise ValueError(f"Invalid order in {run}: {order}")
                is_last_day = date_key == equity.index[-1]
                terminal_price = float(bars[symbol].loc[date_key, "close"]) * (1 - slip)
                # The CSV omits terminal_liquidation; infer its final close sale from the simulator's price rule.
                if is_last_day and side == "sell" and np.isclose(fill, terminal_price, atol=1e-6, rtol=0):
                    if quantity[symbol] == amount:
                        terminal_orders.append(order)
                        continue
                if side == "buy":
                    quantity[symbol] += amount
                    cash -= notional + fee
                elif side == "sell":
                    if amount > quantity[symbol]:
                        raise ValueError(f"Sell exceeds reconstructed position in {run}: {order}")
                    quantity[symbol] -= amount
                    cash += notional - fee
                else:
                    raise ValueError(f"Unknown side in {run}: {side}")

        for symbol, amount in quantity.items():
            if amount and (bars[symbol].loc[date_key, ["high", "low", "close"]] <= 0).any():
                raise AssertionError(f"Position held without valid OHLC marks for {symbol} on {date_key}")
        high_nav = max(pretrade_open_nav, cash + sum(quantity[symbol] * float(bars[symbol].loc[date_key, "high"]) for symbol in quantity))
        low_nav = min(pretrade_open_nav, cash + sum(quantity[symbol] * float(bars[symbol].loc[date_key, "low"]) for symbol in quantity))
        if terminal_orders:
            for order in terminal_orders:
                amount, notional, fee = int(order.quantity), float(order.notional), float(order.total)
                if amount != quantity[order.symbol]:
                    raise ValueError(f"Ambiguous inferred terminal liquidation in {run}: {order}")
                quantity[order.symbol] -= amount
                cash += notional - fee
            low_nav = min(low_nav, cash)
            high_nav = max(high_nav, cash)

        nav = cash + sum(quantity[symbol] * float(bars[symbol].loc[date_key, "close"]) for symbol in quantity)
        if terminal_orders:
            nav = cash
        expected = float(saved["nav"])
        if abs(nav - expected) > 0.03:
            raise AssertionError(f"Order replay differs from saved close NAV in {run} on {date_key}: {nav} vs {expected}")
        close_nav.append(nav)

        if nav > running_close_peak:
            running_close_peak, close_peak_date = nav, date_key
        close_dd_since_peak = nav / running_close_peak - 1
        if close_dd_since_peak < worst_close_dd:
            worst_close_dd = close_dd_since_peak
            worst_close_peak_date, worst_close_trough_date = close_peak_date, date_key

        if high_nav > running_peak:
            running_peak, peak_date = high_nav, date_key
        intraday_dd = low_nav / running_peak - 1
        if intraday_dd < worst_dd:
            worst_dd = intraday_dd
            worst_peak_date, worst_trough_date = peak_date, date_key
        if high_nav > fold_peak:
            fold_peak = high_nav
        fold_intraday_dd = low_nav / fold_peak - 1
        if fold_intraday_dd < fold_worst_dd:
            fold_worst_dd = fold_intraday_dd

    if any(quantity.values()):
        raise AssertionError(f"Final positions were not liquidated in {run}: {quantity}")
    full_nav = np.r_[starting_balance, equity["nav"].to_numpy(dtype=float)]
    close_dd = full_nav / np.maximum.accumulate(full_nav) - 1
    replay_error = float(np.max(np.abs(np.asarray(close_nav) - equity["nav"].to_numpy(dtype=float))))
    assert replay_error <= 0.03 and len(close_nav) == len(equity)
    return {
        "portfolio": label,
        "start_date": equity.index[0],
        "end_date": equity.index[-1],
        "sessions": len(equity),
        "starting_balance_inr": starting_balance,
        "ending_balance_inr": float(equity["nav"].iloc[-1]),
        "total_fees_inr": float(orders["total"].sum()),
        "close_max_drawdown_pct": float(close_dd.min() * 100),
        "simultaneous_ohlc_drawdown_bound_pct": float(worst_dd * 100),
        "fold_ohlc_drawdown_bound_pct": float(fold_worst_dd * 100),
        "bound_peak_date": worst_peak_date,
        "bound_trough_date": worst_trough_date,
        "running_peak_nav_inr": float(running_peak),
        "running_peak_date": peak_date,
        "running_close_peak_nav_inr": float(running_close_peak),
        "running_close_peak_date": close_peak_date,
        "close_drawdown_since_prior_peak_pct": float(worst_close_dd * 100),
        "close_bound_peak_date": worst_close_peak_date,
        "close_bound_trough_date": worst_close_trough_date,
        "headroom_to_20pct_bound_pp": LIMIT_PCT + float(worst_dd * 100),
        "within_20pct_under_bound": bool(worst_dd >= -LIMIT_PCT / 100),
        "max_close_replay_error_inr": replay_error,
        "cash_distributions_credited_inr": float(equity.get("cash_distribution_inr", pd.Series(0.0, index=equity.index)).sum()),
        "slippage_bps_per_side": slippage_bps,
    }


def main() -> None:
    rows = [run_case(label, path) for label, path in CASES]
    result = pd.DataFrame(rows)
    assert len(result) == len(CASES) and result["max_close_replay_error_inr"].max() <= 0.03
    result.to_csv(OUTPUT, index=False)
    print(f"Wrote {len(result)} OHLC drawdown bounds; all order ledgers reconcile to saved NAV.")


if __name__ == "__main__":
    main()

