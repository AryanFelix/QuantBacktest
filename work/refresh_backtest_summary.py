import csv
import json
import os
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
LEDGER = ROOT / "outputs" / "backtest_summary.csv"
MANIFEST = ROOT / "outputs" / "data_manifest.csv"
WALKFORWARD = {
    "work/backtests/latest_buyhold/summary.json",
    "work/backtests/latest_trend/summary.json",
    "work/backtests/latest_donchian/summary.json",
    "work/backtests/latest_sector_momentum/summary.json",
    "work/backtests/robust_2020_buyhold/summary.json",
    "work/backtests/robust_2020_trend200/summary.json",
    "work/backtests/robust_2020_donchian55_20/summary.json",
    "work/backtests/robust_2020_momentum12_1/summary.json",
}


def read_csv(path):
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path, rows, fields):
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", newline="", delete=False, dir=path.parent, suffix=".tmp") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
        temporary = Path(handle.name)
    os.replace(temporary, path)


rows = read_csv(LEDGER)
updated = 0
for row in rows:
    artifact = row["source_artifact"]
    if row["simulation_type"] == "walkforward_holdout" and artifact in WALKFORWARD:
        stats = json.loads((ROOT / artifact).read_text(encoding="utf-8"))["test_result"]
    elif row["simulation_type"] == "intraday_orb" and artifact in {
        "work/backtests/orb_long_train/summary.json",
        "work/backtests/orb_long_validation/summary.json",
        "work/backtests/orb_long_holdout/summary.json",
        "work/backtests/orb_long_short_train/summary.json",
        "work/backtests/orb_long_short_validation/summary.json",
        "work/backtests/orb_long_short_holdout/summary.json",
    }:
        stats = json.loads((ROOT / artifact).read_text(encoding="utf-8"))
    elif row["simulation_type"] == "expired_options_slippage_sensitivity":
        summary = json.loads((ROOT / artifact).read_text(encoding="utf-8"))
        sensitivity = summary["slippage_sensitivity_bps_per_leg_per_side"][str(float(row["slippage_bps_per_side"]))]
        stats = sensitivity["full_sample" if row["period"] == "full_sample" else "holdout"]
    elif row["simulation_type"] in {
        "etf_absolute_momentum_sensitivity",
        "etf_absolute_momentum_cashflow_sensitivity",
    }:
        summary_path = artifact.split(";", 1)[0]
        stats = json.loads((ROOT / summary_path).read_text(encoding="utf-8"))
    else:
        continue

    for target, source in (
        ("ending_balance_inr", "ending_balance_inr"),
        ("total_return_pct", "total_return_pct"),
        ("cagr_pct", "cagr_pct"),
        ("max_drawdown_pct", "max_drawdown_pct"),
        ("sharpe_zero_rf", "sharpe_zero_rf"),
        ("fees_inr", "total_fees_inr"),
        ("slippage_cost_inr", "total_slippage_inr"),
        ("order_count", "order_count"),
    ):
        if source in stats:
            row[target] = str(stats[source])
    if "within_drawdown_limit" in stats:
        row["within_20pct"] = str(stats["within_drawdown_limit"])
    if "trade_count" in stats:
        row["trade_count"] = str(stats["trade_count"])
    updated += 1

assert updated == 32, f"Expected to refresh 8 walk-forward, 6 ORB, 6 options, and 12 ETF momentum rows; refreshed {updated}"

clean_holdouts = {
    "Walk-forward blend; 95% cap, 2020+ holdout at 50 bps": (
        "2020_plus", "work/backtests/donchian_gold_clean/holdout_2020_plus_95cap_50bps/summary.json",
        "work/backtests/donchian_gold_clean/walkforward_2020_plus/summary.json",
    ),
    "Walk-forward blend; 95% cap, 2023+ holdout at 50 bps": (
        "recent", "work/backtests/donchian_gold_clean/holdout_recent_95cap_50bps/summary.json",
        "work/backtests/donchian_gold_clean/walkforward_recent/summary.json",
    ),
}
ohlc_audits = {
    row["portfolio"]: row for row in read_csv(ROOT / "outputs" / "etf_intraday_drawdown_audit.csv")
}
assert set(clean_holdouts).issubset(ohlc_audits), "Missing NIFTY/Gold holdout OHLC audit rows"
rows = [row for row in rows if row["simulation_type"] != "clean_month_end_oos_ohlc_audit"]
for label, (period, result_path, selection_path) in clean_holdouts.items():
    audit = ohlc_audits[label]
    result = json.loads((ROOT / result_path).read_text(encoding="utf-8"))
    selection = json.loads((ROOT / selection_path).read_text(encoding="utf-8"))
    assert selection["selected_exposure_pct"] == result["exposure_cap_pct"] == 95
    assert result["slippage_bps_per_side"] == 50
    assert abs(float(audit["ending_balance_inr"]) - float(result["ending_balance_inr"])) <= 0.03
    rows.append({
        "simulation_type": "clean_month_end_oos_ohlc_audit",
        "strategy": result["strategy"],
        "universe": "NIFTYBEES + GOLDBEES",
        "period": period,
        "period_start": audit["start_date"],
        "period_end": audit["end_date"],
        "starting_balance_inr": result["starting_balance_inr"],
        "ending_balance_inr": result["ending_balance_inr"],
        "total_return_pct": result["total_return_pct"],
        "cagr_pct": result["cagr_pct"],
        "max_drawdown_pct": audit["simultaneous_ohlc_drawdown_bound_pct"],
        "sharpe_zero_rf": result["sharpe_zero_rf"],
        "gross_exposure_cap_pct": result["exposure_cap_pct"],
        "slippage_bps_per_side": result["slippage_bps_per_side"],
        "fees_inr": result["total_fees_inr"],
        "slippage_cost_inr": result["total_slippage_inr"],
        "trade_count": "",
        "order_count": result["order_count"],
        "within_20pct": audit["within_20pct_under_bound"],
        "selection_or_sizing": (
            f"95% exposure cap selected from the frozen grid using training/validation data through "
            f"{result['training_cutoff']}; replayed at 50 bps per-side slippage"
        ),
        "source_artifact": (
            f"{result_path};{selection_path};outputs/etf_intraday_drawdown_audit.csv;"
            "work/replay_donchian_gold_blend.py;work/audit_etf_intraday_drawdown.py"
        ),
        "notes": (
            f"Close MDD {float(audit['close_max_drawdown_pct']):.2f}%; conservative same-day OHLC bound "
            f"{float(audit['simultaneous_ohlc_drawdown_bound_pct']):.2f}%; "
            f"bound trough {audit['bound_trough_date']}. Historical fold was previously inspected; "
            "0% cash yield, no cash distributions credited, and modeled next-open fills."
        ),
    })
clean_holdout_keys = [
    row["period"] for row in rows if row["simulation_type"] == "clean_month_end_oos_ohlc_audit"
]
assert sorted(clean_holdout_keys) == ["2020_plus", "recent"]

blend_path = ROOT / "outputs" / "volatility_weighted_blend_screen.csv"
if blend_path.exists():
    blend_rows = read_csv(blend_path)
    assert len(blend_rows) == 40, f"Expected 40 corrected ETF blend cases; found {len(blend_rows)}"
    strategy_names = {
        "fixed_50_50": "etf_blend_fixed_50_50_control",
        "inverse_vol_63d": "etf_blend_inverse_vol_63d",
        "fixed_50_50_quarterly": "etf_blend_fixed_50_50_quarterly",
        "inverse_vol_63d_quarterly": "etf_blend_inverse_vol_63d_quarterly",
    }
    old_blend_rows = {
        (row["strategy"], row["period"], str(float(row["slippage_bps_per_side"]))): row
        for row in rows if row["simulation_type"] == "volatility_weighted_etf_blend"
    }
    assert len(old_blend_rows) == 40, f"Expected 40 prior ETF blend ledger keys; found {len(old_blend_rows)}"
    rows = [row for row in rows if row["simulation_type"] != "volatility_weighted_etf_blend"]
    for result in blend_rows:
        strategy = strategy_names[result["portfolio"]]
        key = (strategy, result["period"], str(float(result["slippage_bps_per_side"])))
        row = old_blend_rows[key].copy()
        for target, source in (
            ("period_start", "period_start"),
            ("period_end", "period_end"),
            ("starting_balance_inr", "starting_balance_inr"),
            ("ending_balance_inr", "ending_balance_inr"),
            ("total_return_pct", "total_return_pct"),
            ("cagr_pct", "cagr_pct"),
            ("max_drawdown_pct", "max_drawdown_pct"),
            ("sharpe_zero_rf", "sharpe_zero_rf"),
            ("gross_exposure_cap_pct", "exposure_cap_pct"),
            ("slippage_bps_per_side", "slippage_bps_per_side"),
            ("fees_inr", "total_fees_inr"),
            ("slippage_cost_inr", "total_slippage_inr"),
            ("order_count", "order_count"),
            ("within_20pct", "within_drawdown_limit"),
        ):
            row[target] = result[source]
        row["strategy"] = strategy
        row["source_artifact"] = "outputs/volatility_weighted_blend_screen.csv;outputs/volatility_weighted_blend_method.md"
        rows.append(row)
    assert len([row for row in rows if row["simulation_type"] == "volatility_weighted_etf_blend"]) == 40

rsi25_path = ROOT / "outputs" / "niftybees_rsi25_sensitivity.csv"
if rsi25_path.exists():
    rsi25 = read_csv(rsi25_path)
    assert len(rsi25) == 108, f"Expected 108 RSI(4) and comparator scenarios; found {len(rsi25)}"
    rows = [row for row in rows if row["simulation_type"] != "niftybees_rsi25_mean_reversion"]
    for result in rsi25:
        rule = result["strategy"]
        sizing = (
            "buy-and-hold benchmark" if rule == "benchmark_buyhold" else
            "SMA200 long/flat benchmark" if rule == "benchmark_trend200" else
            "Donchian 55/20 long/flat benchmark" if rule == "benchmark_donchian55_20" else
            f"RSI(4) <25 with close above 200DMA; exit >55; "
            f"starter {result['starter_exposure_pct']}%, add {result['add_exposure_pct']}%; next-open execution"
        )
        rows.append({
            "simulation_type": "niftybees_rsi25_mean_reversion",
            "strategy": f"{rule} | {result['action_case']}",
            "universe": "NIFTYBEES",
            "period": result["period"],
            "period_start": result["period_start"],
            "period_end": result["period_end"],
            "starting_balance_inr": result["starting_balance_inr"],
            "ending_balance_inr": result["ending_balance_inr"],
            "total_return_pct": result["total_return_pct"],
            "cagr_pct": result["cagr_pct"],
            "max_drawdown_pct": result["max_drawdown_pct"],
            "sharpe_zero_rf": result["sharpe_zero_rf"],
            "gross_exposure_cap_pct": 100,
            "slippage_bps_per_side": result["slippage_bps_per_side"],
            "fees_inr": result["fees_inr"],
            "slippage_cost_inr": result["slippage_cost_inr"],
            "trade_count": "",
            "order_count": result["order_count"],
            "within_20pct": result["within_20pct"],
            "selection_or_sizing": sizing,
            "source_artifact": result["source_artifact"],
            "notes": (
                f"{result['action_case']} signal/NAV treatment; current NSE/Upstox delivery fees and next-open slippage. "
                "Fixed published RSI(4) rule and sizing ablations on inspected history; not an independent lockbox."
            ),
        })
    rsi25_keys = [
        (row["strategy"], row["period"], row["slippage_bps_per_side"])
        for row in rows if row["simulation_type"] == "niftybees_rsi25_mean_reversion"
    ]
    assert len(rsi25_keys) == len(set(rsi25_keys)) == 108

sensitivity_path = ROOT / "outputs" / "etf_parameter_sensitivity.csv"
if sensitivity_path.exists():
    sensitivity = read_csv(sensitivity_path)
    assert len(sensitivity) == 105, f"Expected 105 ETF sensitivity cases; found {len(sensitivity)}"
    parameter_ohlc_labels = {
        "channel_exit_D55_30_SMA200": "Post-hoc D55/30 parameter challenger",
        "channel_entry_D40_20_SMA200": "Post-hoc D40/20 parameter challenger",
    }
    parameter_ohlc = {}
    for audit_row in read_csv(ROOT / "outputs" / "etf_intraday_drawdown_audit.csv"):
        for variant, label in parameter_ohlc_labels.items():
            if audit_row["portfolio"] == label:
                bound = float(audit_row["simultaneous_ohlc_drawdown_bound_pct"])
                assert bound < -20, f"Expected {variant} to fail the 20% OHLC screen; got {bound}%"
                parameter_ohlc[variant] = bound
    assert set(parameter_ohlc) == set(parameter_ohlc_labels), "Missing audited parameter challengers"
    rows = [row for row in rows if row["simulation_type"] != "etf_parameter_sensitivity"]
    for result in sensitivity:
        ohlc_failure = (
            result["variant"] in parameter_ohlc
            and result["period"] == "full_2014_plus"
            and float(result["slippage_bps_per_side"]) == 50
        )
        rows.append({
            "simulation_type": "etf_parameter_sensitivity",
            "strategy": result["variant"],
            "universe": "NIFTYBEES + GOLDBEES",
            "period": result["period"],
            "period_start": result["first_bar"][:10],
            "period_end": result["last_bar"][:10],
            "starting_balance_inr": result["starting_balance_inr"],
            "ending_balance_inr": result["ending_balance_inr"],
            "total_return_pct": result["total_return_pct"],
            "cagr_pct": result["cagr_pct"],
            "max_drawdown_pct": result["max_drawdown_pct"],
            "sharpe_zero_rf": result["sharpe_zero_rf"],
            "gross_exposure_cap_pct": result["exposure_cap_pct"],
            "slippage_bps_per_side": result["slippage_bps_per_side"],
            "fees_inr": result["total_fees_inr"],
            "slippage_cost_inr": result["total_slippage_inr"],
            "trade_count": "",
            "order_count": result["order_count"],
            "within_20pct": bool(result["within_drawdown_limit"]) and not ohlc_failure,
            "selection_or_sizing": (
                f"50% per active trend sleeve; {result['nifty_donchian_entry_sessions']}/"
                f"{result['nifty_donchian_exit_sessions']} NIFTY channel; "
                f"{result['gold_sma_sessions']}-session Gold SMA; next-open execution"
            ),
            "source_artifact": (
                "outputs/etf_parameter_sensitivity.csv;outputs/etf_parameter_sensitivity_method.md;"
                "outputs/etf_intraday_drawdown_audit.csv;work/sensitivity_nifty_gold_parameters.py;"
                "work/audit_etf_intraday_drawdown.py"
            ),
            "notes": (
                "Local parameter-stability diagnostic on inspected history; current delivery charges applied uniformly; not an independent holdout or selected winner."
                + (f" Close-only drawdown passes, but OHLC envelope is {parameter_ohlc[result['variant']]:.2f}% and fails 20%." if ohlc_failure else "")
            ),
        })
    sensitivity_keys = [
        (row["simulation_type"], row["strategy"], row["period"], row["slippage_bps_per_side"])
        for row in rows if row["simulation_type"] == "etf_parameter_sensitivity"
    ]
    assert len(sensitivity_keys) == len(set(sensitivity_keys)) == 105

deployment_path = ROOT / "outputs" / "single_sleeve_deployment_sensitivity.csv"
if deployment_path.exists():
    deployment = read_csv(deployment_path)
    assert len(deployment) == 140, f"Expected 140 single-sleeve deployment cases; found {len(deployment)}"
    audited_solo_labels = {
        "Quarterly inverse-vol; 50% solo sleeve": "inverse_vol_quarterly_single_50",
        "Quarterly inverse-vol; 55% solo sleeve": "inverse_vol_quarterly_single_55",
    }
    solo_ohlc = {
        audited_solo_labels[audit_row["portfolio"]]: float(audit_row["simultaneous_ohlc_drawdown_bound_pct"])
        for audit_row in read_csv(ROOT / "outputs" / "etf_intraday_drawdown_audit.csv")
        if audit_row["portfolio"] in audited_solo_labels
    }
    assert set(solo_ohlc) == set(audited_solo_labels.values()), "Missing audited solo-sleeve paths"
    rows = [row for row in rows if row["simulation_type"] != "etf_single_sleeve_deployment_sensitivity"]
    for result in deployment:
        ohlc_failure = (
            result["portfolio"] in solo_ohlc
            and result["period"] == "full_2014_plus"
            and float(result["slippage_bps_per_side"]) == 50
        )
        rows.append({
            "simulation_type": "etf_single_sleeve_deployment_sensitivity",
            "strategy": result["portfolio"],
            "universe": "NIFTYBEES + GOLDBEES",
            "period": result["period"],
            "period_start": result["period_start"],
            "period_end": result["period_end"],
            "starting_balance_inr": result["starting_balance_inr"],
            "ending_balance_inr": result["ending_balance_inr"],
            "total_return_pct": result["total_return_pct"],
            "cagr_pct": result["cagr_pct"],
            "max_drawdown_pct": result["max_drawdown_pct"],
            "sharpe_zero_rf": result["sharpe_zero_rf"],
            "gross_exposure_cap_pct": result["exposure_cap_pct"],
            "slippage_bps_per_side": result["slippage_bps_per_side"],
            "fees_inr": result["total_fees_inr"],
            "slippage_cost_inr": result["total_slippage_inr"],
            "trade_count": "",
            "order_count": result["order_count"],
            "within_20pct": bool(result["within_drawdown_limit"]) and not ohlc_failure,
            "selection_or_sizing": (
                f"63-session inverse-vol split when both sleeves active; "
                f"{result['single_sleeve_exposure_pct']}% gross when one sleeve active; "
                "quarterly/monthly schedule; next-open execution"
            ),
            "source_artifact": (
                "outputs/single_sleeve_deployment_sensitivity.csv;"
                "outputs/single_sleeve_deployment_method.md;"
                "work/sensitivity_single_sleeve_deployment.py;"
                "outputs/etf_intraday_drawdown_audit.csv;work/audit_etf_intraday_drawdown.py"
            ),
            "notes": (
                "Retrospective deployment sensitivity across inspected history; no leverage; current delivery charges and 10/50 bps slippage; 50% baseline reproduces the established reference; not independent validation."
                + (f" Close-only drawdown passes, but conservative daily OHLC bound is {solo_ohlc[result['portfolio']]:.2f}% and fails 20%." if ohlc_failure else "")
            ),
        })
    deployment_keys = [
        (row["strategy"], row["period"], row["slippage_bps_per_side"])
        for row in rows if row["simulation_type"] == "etf_single_sleeve_deployment_sensitivity"
    ]
    assert len(deployment_keys) == len(set(deployment_keys)) == 140
volatility_path = ROOT / "outputs" / "volatility_target_sensitivity.csv"
if volatility_path.exists():
    volatility = read_csv(volatility_path)
    assert len(volatility) == 60, f"Expected 60 volatility-throttle cases; found {len(volatility)}"
    rows = [row for row in rows if row["simulation_type"] != "etf_volatility_target_sensitivity"]
    for result in volatility:
        rows.append({
            "simulation_type": "etf_volatility_target_sensitivity",
            "strategy": result["strategy"],
            "universe": "NIFTYBEES + GOLDBEES",
            "period": result["period"],
            "period_start": result["period_start"],
            "period_end": result["period_end"],
            "starting_balance_inr": result["starting_balance_inr"],
            "ending_balance_inr": result["ending_balance_inr"],
            "total_return_pct": result["total_return_pct"],
            "cagr_pct": result["cagr_pct"],
            "max_drawdown_pct": result["max_drawdown_pct"],
            "sharpe_zero_rf": result["sharpe_zero_rf"],
            "gross_exposure_cap_pct": result["exposure_cap_pct"],
            "slippage_bps_per_side": result["slippage_bps_per_side"],
            "fees_inr": result["total_fees_inr"],
            "slippage_cost_inr": result["total_slippage_inr"],
            "trade_count": "",
            "order_count": result["order_count"],
            "within_20pct": result["within_drawdown_limit"],
            "selection_or_sizing": result["selection_or_sizing"],
            "source_artifact": (
                "outputs/volatility_target_sensitivity.csv;"
                "outputs/volatility_target_sensitivity_method.md;"
                "work/sensitivity_volatility_target.py"
            ),
            "notes": "Retrospective trailing-volatility exposure-throttle screen on inspected history; current delivery fees and 10/50 bps slippage; no future risk bound or independent validation.",
        })
    volatility_keys = [
        (row["strategy"], row["period"], row["slippage_bps_per_side"])
        for row in rows if row["simulation_type"] == "etf_volatility_target_sensitivity"
    ]
    assert len(volatility_keys) == len(set(volatility_keys)) == 60

vix_path = ROOT / "outputs" / "india_vix_overlay_sensitivity.csv"
if vix_path.exists():
    vix_rows = read_csv(vix_path)
    assert len(vix_rows) == 90, f"Expected 90 India VIX overlay cases; found {len(vix_rows)}"
    rows = [row for row in rows if row["simulation_type"] != "etf_india_vix_overlay_sensitivity"]
    for result in vix_rows:
        rows.append({
            "simulation_type": "etf_india_vix_overlay_sensitivity",
            "strategy": result["strategy"],
            "universe": "NIFTYBEES + GOLDBEES; India VIX signal",
            "period": result["period"],
            "period_start": result["period_start"],
            "period_end": result["period_end"],
            "starting_balance_inr": result["starting_balance_inr"],
            "ending_balance_inr": result["ending_balance_inr"],
            "total_return_pct": result["total_return_pct"],
            "cagr_pct": result["cagr_pct"],
            "max_drawdown_pct": result["max_drawdown_pct"],
            "sharpe_zero_rf": result["sharpe_zero_rf"],
            "gross_exposure_cap_pct": result["exposure_cap_pct"],
            "slippage_bps_per_side": result["slippage_bps_per_side"],
            "fees_inr": result["total_fees_inr"],
            "slippage_cost_inr": result["total_slippage_inr"],
            "trade_count": "",
            "order_count": result["order_count"],
            "within_20pct": result["within_drawdown_limit"],
            "selection_or_sizing": result["selection_or_sizing"],
            "source_artifact": (
                "outputs/india_vix_overlay_sensitivity.csv;"
                "outputs/india_vix_overlay_method.md;"
                "outputs/india_vix_nse_conflict_reconciliation.json;"
                "work/sensitivity_india_vix_overlay.py"
            ),
            "notes": "Three conflicting Upstox sessions are replaced with NSE official daily OHLC. No 50 bps full-history VIX overlay satisfies the 20% close-drawdown screen; at 10 bps, no overlay has the highest full-history return and the same drawdown.",
        })
    vix_keys = [
        (row["strategy"], row["period"], row["slippage_bps_per_side"])
        for row in rows if row["simulation_type"] == "etf_india_vix_overlay_sensitivity"
    ]
    assert len(vix_keys) == len(set(vix_keys)) == 90

joint_path = ROOT / "outputs" / "joint_exposure_volatility_sensitivity.csv"
if joint_path.exists():
    joint = read_csv(joint_path)
    assert len(joint) == 130, f"Expected 130 joint sizing cases; found {len(joint)}"
    rows = [row for row in rows if row["simulation_type"] != "etf_joint_exposure_volatility_sensitivity"]
    for result in joint:
        rows.append({
            "simulation_type": "etf_joint_exposure_volatility_sensitivity",
            "strategy": result["strategy"],
            "universe": "NIFTYBEES + GOLDBEES",
            "period": result["period"],
            "period_start": result["period_start"],
            "period_end": result["period_end"],
            "starting_balance_inr": result["starting_balance_inr"],
            "ending_balance_inr": result["ending_balance_inr"],
            "total_return_pct": result["total_return_pct"],
            "cagr_pct": result["cagr_pct"],
            "max_drawdown_pct": result["max_drawdown_pct"],
            "sharpe_zero_rf": result["sharpe_zero_rf"],
            "gross_exposure_cap_pct": result["exposure_cap_pct"],
            "slippage_bps_per_side": result["slippage_bps_per_side"],
            "fees_inr": result["total_fees_inr"],
            "slippage_cost_inr": result["total_slippage_inr"],
            "trade_count": "",
            "order_count": result["order_count"],
            "within_20pct": result["within_drawdown_limit"],
            "selection_or_sizing": result["selection_or_sizing"],
            "source_artifact": (
                "outputs/joint_exposure_volatility_sensitivity.csv;"
                "outputs/joint_exposure_volatility_method.md;"
                "work/sensitivity_joint_exposure_volatility.py"
            ),
            "notes": "Corrected 50 bps continuous results breach the 20% close-drawdown screen: 65%/16% reaches -23.80%; 80%/16% reaches -28.03%. Revision 5 is a pre-correction experiment, not a risk-qualified candidate.",
        })
    joint_keys = [
        (row["strategy"], row["period"], row["slippage_bps_per_side"])
        for row in rows if row["simulation_type"] == "etf_joint_exposure_volatility_sensitivity"
    ]
    assert len(joint_keys) == len(set(joint_keys)) == 130

cost_path = ROOT / "outputs" / "cost_stress_sensitivity.csv"
if cost_path.exists():
    cost_stress = read_csv(cost_path)
    assert len(cost_stress) == 125, f"Expected 125 cost-stress cases; found {len(cost_stress)}"
    rows = [row for row in rows if row["simulation_type"] != "etf_execution_cost_stress_sensitivity"]
    for result in cost_stress:
        rows.append({
            "simulation_type": "etf_execution_cost_stress_sensitivity",
            "strategy": result["strategy"],
            "universe": "NIFTYBEES + GOLDBEES",
            "period": result["period"],
            "period_start": result["period_start"],
            "period_end": result["period_end"],
            "starting_balance_inr": result["starting_balance_inr"],
            "ending_balance_inr": result["ending_balance_inr"],
            "total_return_pct": result["total_return_pct"],
            "cagr_pct": result["cagr_pct"],
            "max_drawdown_pct": result["max_drawdown_pct"],
            "sharpe_zero_rf": result["sharpe_zero_rf"],
            "gross_exposure_cap_pct": result["exposure_cap_pct"],
            "slippage_bps_per_side": result["slippage_bps_per_side"],
            "fees_inr": result["total_fees_inr"],
            "slippage_cost_inr": result["total_slippage_inr"],
            "trade_count": "",
            "order_count": result["order_count"],
            "within_20pct": result["within_drawdown_limit"],
            "selection_or_sizing": result["selection_or_sizing"],
            "source_artifact": (
                "outputs/cost_stress_sensitivity.csv;outputs/cost_stress_method.md;"
                "work/sensitivity_cost_stress.py"
            ),
            "notes": "Retrospective cost stress; 10–200 bps fixed slippage per side is not measured spread; all history was previously inspected; see method for drawdown and validation limits.",
        })
    cost_keys = [
        (row["strategy"], row["period"], row["slippage_bps_per_side"])
        for row in rows if row["simulation_type"] == "etf_execution_cost_stress_sensitivity"
    ]
    assert len(cost_keys) == len(set(cost_keys)) == 125

ohlc_path = ROOT / "outputs" / "intraday_ohlc_exposure_sensitivity.csv"
if ohlc_path.exists():
    ohlc_exposure = read_csv(ohlc_path)
    assert len(ohlc_exposure) == 20, f"Expected 20 OHLC exposure cases; found {len(ohlc_exposure)}"
    rows = [row for row in rows if row["simulation_type"] != "etf_intraday_ohlc_exposure_sensitivity"]
    for result in ohlc_exposure:
        rows.append({
            "simulation_type": "etf_intraday_ohlc_exposure_sensitivity",
            "strategy": result["portfolio"],
            "universe": "NIFTYBEES + GOLDBEES",
            "period": "full_2014_plus",
            "period_start": result["start_date"],
            "period_end": result["end_date"],
            "starting_balance_inr": result["starting_balance_inr"],
            "ending_balance_inr": result["ending_balance_inr"],
            "total_return_pct": result["total_return_pct"],
            "cagr_pct": result["cagr_pct"],
            "max_drawdown_pct": result["close_max_drawdown_pct"],
            "sharpe_zero_rf": "",
            "gross_exposure_cap_pct": result["gross_exposure_cap_pct"],
            "slippage_bps_per_side": result["slippage_bps_per_side"],
            "fees_inr": result["fees_inr"],
            "slippage_cost_inr": "",
            "trade_count": "",
            "order_count": result["order_count"],
            "within_20pct": result["within_20pct_under_bound"],
            "selection_or_sizing": (
                f"Quarterly fixed 50/50 NIFTY/Gold trend sleeves; {result['gross_exposure_cap_pct']}% gross cap; "
                f"same-day OHLC envelope {result['simultaneous_ohlc_drawdown_bound_pct']}%"
            ),
            "source_artifact": (
                "outputs/intraday_ohlc_exposure_sensitivity.csv;"
                "outputs/etf_intraday_drawdown_audit.csv;"
                "outputs/etf_daily_timestamp_and_intraday_risk_audit.md;"
                "work/sensitivity_intraday_ohlc_exposure.py"
            ),
            "notes": "Historical stress only. Envelope assumes all holdings' daily highs precede all lows; it is not an observed synchronized path or future loss limit.",
        })
    ohlc_keys = [
        (row["strategy"], row["period"], row["slippage_bps_per_side"])
        for row in rows if row["simulation_type"] == "etf_intraday_ohlc_exposure_sensitivity"
    ]
    assert len(ohlc_keys) == len(set(ohlc_keys)) == 20

intraday_range_path = ROOT / "outputs" / "intraday_orb_range_sensitivity.csv"
if intraday_range_path.exists():
    intraday_range = read_csv(intraday_range_path)
    assert len(intraday_range) == 64
    rows = [row for row in rows if row["simulation_type"] != "intraday_orb_range_sensitivity"]
    for result in intraday_range:
        rows.append({
            "simulation_type": "intraday_orb_range_sensitivity",
            "strategy": f"NIFTY 30m ORB long min range {float(result['min_opening_range_pct']):.2f}%",
            "universe": "NIFTY 50 signal; NIFTYBEES intraday execution",
            "period": result["period"],
            "period_start": result["period_start"],
            "period_end": result["period_end"],
            "starting_balance_inr": result["starting_balance_inr"],
            "ending_balance_inr": result["ending_balance_inr"],
            "total_return_pct": result["total_return_pct"],
            "cagr_pct": result["cagr_pct"],
            "max_drawdown_pct": result["max_drawdown_pct"],
            "sharpe_zero_rf": result["sharpe_zero_rf"],
            "gross_exposure_cap_pct": "95",
            "slippage_bps_per_side": result["slippage_bps_per_side"],
            "fees_inr": result["fees_inr"],
            "slippage_cost_inr": result["slippage_cost_inr"],
            "trade_count": result["trade_count"],
            "order_count": result["order_count"],
            "within_20pct": result["within_20pct"],
            "selection_or_sizing": (
                f"0.5% equity risk per trade; 95% exposure cap; minimum opening range "
                f"{float(result['min_opening_range_pct']):.2f}%"
            ),
            "source_artifact": (
                f"{result['source_artifact']};outputs/intraday_orb_range_sensitivity.csv;"
                "outputs/intraday_orb_range_method.md;work/sensitivity_intraday_orb_range.py"
            ),
            "notes": (
                f"{int(result['range_filtered_sessions'])} of {int(result['eligible_sessions'])} sessions filtered by range. "
                "Current equity-intraday charges; fixed slippage is not measured spread. Retrospective; "
                "2025+ was already inspected; see method for fill and validation limits."
            ),
        })
    intraday_range_keys = [
        (row["strategy"], row["period"], row["slippage_bps_per_side"])
        for row in rows if row["simulation_type"] == "intraday_orb_range_sensitivity"
    ]
    assert len(intraday_range_keys) == len(set(intraday_range_keys)) == 64

gap_fade_path = ROOT / "outputs" / "intraday_gap_fade_sensitivity.csv"
if gap_fade_path.exists():
    gap_fade = read_csv(gap_fade_path)
    assert len(gap_fade) == 144, f"Expected 144 gap-fade cases; found {len(gap_fade)}"
    rows = [row for row in rows if row["simulation_type"] != "intraday_gap_fade_sensitivity"]
    for result in gap_fade:
        rows.append({
            "simulation_type": "intraday_gap_fade_sensitivity",
            "strategy": f"NIFTY gap fade {result['mode']} {float(result['gap_threshold_pct']):.2f}%",
            "universe": "NIFTY 50 signal; NIFTYBEES intraday execution",
            "period": result["period"],
            "period_start": result["period_start"],
            "period_end": result["period_end"],
            "starting_balance_inr": result["starting_balance_inr"],
            "ending_balance_inr": result["ending_balance_inr"],
            "total_return_pct": result["total_return_pct"],
            "cagr_pct": result["cagr_pct"],
            "max_drawdown_pct": result["max_drawdown_pct"],
            "sharpe_zero_rf": result["sharpe_zero_rf"],
            "gross_exposure_cap_pct": "100",
            "slippage_bps_per_side": result["slippage_bps_per_side"],
            "fees_inr": result["fees_inr"],
            "slippage_cost_inr": result["slippage_cost_inr"],
            "trade_count": result["trade_count"],
            "order_count": result["order_count"],
            "within_20pct": result["within_20pct"],
            "selection_or_sizing": f"{result['mode']}; {float(result['gap_threshold_pct']):.2f}% gap; 0.5% NAV stop risk; 100% gross cap",
            "source_artifact": (
                f"{result['source_artifact']};outputs/intraday_gap_fade_sensitivity.csv;"
                "outputs/intraday_gap_fade_method.md;work/backtest_intraday_gap_fade.py"
            ),
            "notes": "Current NSE equity-intraday charges; fixed 10/25/50/100 bps adverse slippage per side. Stop first when both stop and target trade inside one 30-minute bar; session alignment and retrospective limits are documented in the method.",
        })
    gap_fade_keys = [
        (row["strategy"], row["period"], row["slippage_bps_per_side"])
        for row in rows if row["simulation_type"] == "intraday_gap_fade_sensitivity"
    ]
    assert len(gap_fade_keys) == len(set(gap_fade_keys)) == 144

sector_rotation_path = ROOT / "outputs" / "sector_rotation_sensitivity.csv"
if sector_rotation_path.exists():
    sector_rotation = read_csv(sector_rotation_path)
    assert len(sector_rotation) == 384, f"Expected 384 sector-rotation cases; found {len(sector_rotation)}"
    sector_rotation_ohlc = read_csv(ROOT / "outputs" / "sector_rotation_ohlc_audit.csv")
    assert len(sector_rotation_ohlc) == 96, f"Expected 96 sector OHLC audits; found {len(sector_rotation_ohlc)}"
    sector_ohlc = {
        (row["strategy"], row["period"], float(row["exposure_cap_pct"])): row
        for row in sector_rotation_ohlc
    }
    assert len(sector_ohlc) == 96
    rows = [row for row in rows if row["simulation_type"] != "etf_sector_rotation_sensitivity"]
    for result in sector_rotation:
        risk = sector_ohlc.get((result["strategy"], result["period"], float(result["exposure_cap_pct"]))) if int(float(result["slippage_bps_per_side"])) == 50 else None
        sizing = (
            f"Top {int(float(result['top_n']))} monthly sector ETFs by 12–1 momentum with positive return and above-200DMA"
            if result["top_n"] else
            "50/50 NIFTY/Gold control" if result["strategy"] == "nifty_gold_50_50_control" else
            "Monthly equal-weight sector control" if result["strategy"] == "sector_equal_weight_control" else
            "25% NIFTY Donchian + 50% equal-weight sectors + 25% Gold SMA200"
        )
        rows.append({
            "simulation_type": "etf_sector_rotation_sensitivity",
            "strategy": result["strategy"],
            "universe": "BANKBEES; ITBEES; AUTOBEES; PHARMABEES; PSUBNKBEES; NIFTYBEES; GOLDBEES",
            "period": result["period"],
            "period_start": result["period_start"],
            "period_end": result["period_end"],
            "starting_balance_inr": result["starting_balance_inr"],
            "ending_balance_inr": result["ending_balance_inr"],
            "total_return_pct": result["total_return_pct"],
            "cagr_pct": result["cagr_pct"],
            "max_drawdown_pct": result["max_drawdown_pct"],
            "sharpe_zero_rf": result["sharpe_zero_rf"],
            "gross_exposure_cap_pct": result["exposure_cap_pct"],
            "slippage_bps_per_side": result["slippage_bps_per_side"],
            "fees_inr": result["fees_inr"],
            "slippage_cost_inr": result["slippage_cost_inr"],
            "trade_count": "",
            "order_count": result["order_count"],
            "within_20pct": risk["within_20pct_under_bound"] if risk else result["within_20pct"],
            "selection_or_sizing": sizing,
            "source_artifact": (
                f"{result['source_artifact']};outputs/sector_rotation_sensitivity.csv;"
                "outputs/sector_rotation_training_selection.json;outputs/sector_rotation_method.md;"
                "outputs/sector_rotation_primary_sources.md;outputs/sector_rotation_ohlc_audit.csv;"
                "work/sensitivity_sector_rotation.py;work/audit_sector_rotation_ohlc.py"
            ),
            "notes": (
                f"Current modeled ETF charges; {result['slippage_bps_per_side']} bps per-side slippage. "
                + (f"Conservative same-day OHLC bound {float(risk['simultaneous_ohlc_drawdown_bound_pct']):.2f}%; " if risk else "Close drawdown only; OHLC audit is at 50 bps. ")
                + "ETF histories are price-only, launch dates differ, and later periods were inspected. Distributions remain incomplete; see the method and primary-source memos."
            ),
        })
    sector_rotation_keys = [
        (row["strategy"], row["period"], row["gross_exposure_cap_pct"], row["slippage_bps_per_side"])
        for row in rows if row["simulation_type"] == "etf_sector_rotation_sensitivity"
    ]
    assert len(sector_rotation_keys) == len(set(sector_rotation_keys)) == 384

sector_tri_path = ROOT / "outputs" / "sector_tri_signal_momentum_sensitivity.csv"
if sector_tri_path.exists():
    sector_tri = read_csv(sector_tri_path)
    assert len(sector_tri) == 144, f"Expected 144 TRI-signal sector cases; found {len(sector_tri)}"
    sector_tri_ohlc_rows = read_csv(ROOT / "outputs" / "sector_tri_signal_momentum_ohlc_audit.csv")
    assert len(sector_tri_ohlc_rows) == 48, f"Expected 48 TRI-signal sector OHLC audits; found {len(sector_tri_ohlc_rows)}"
    sector_tri_ohlc = {
        (row["strategy"], row["period"], float(row["exposure_cap_pct"])): row
        for row in sector_tri_ohlc_rows
    }
    rows = [row for row in rows if row["simulation_type"] != "etf_sector_tri_signal_momentum"]
    for result in sector_tri:
        risk = sector_tri_ohlc.get((result["strategy"], result["period"], float(result["exposure_cap_pct"]))) if int(float(result["slippage_bps_per_side"])) == 50 else None
        rows.append({
            "simulation_type": "etf_sector_tri_signal_momentum",
            "strategy": result["strategy"],
            "universe": "BANKBEES; ITBEES; AUTOBEES; PHARMABEES; PSUBNKBEES",
            "period": result["period"],
            "period_start": result["period_start"],
            "period_end": result["period_end"],
            "starting_balance_inr": result["starting_balance_inr"],
            "ending_balance_inr": result["ending_balance_inr"],
            "total_return_pct": result["total_return_pct"],
            "cagr_pct": result["cagr_pct"],
            "max_drawdown_pct": result["max_drawdown_pct"],
            "sharpe_zero_rf": result["sharpe_zero_rf"],
            "gross_exposure_cap_pct": result["exposure_cap_pct"],
            "slippage_bps_per_side": result["slippage_bps_per_side"],
            "fees_inr": result["fees_inr"],
            "slippage_cost_inr": result["slippage_cost_inr"],
            "trade_count": "",
            "order_count": result["order_count"],
            "within_20pct": risk["within_20pct_under_bound"] if risk else result["within_20pct_close"],
            "selection_or_sizing": (
                f"Top {int(float(result['top_n']))} by official gross sector TRI 12–1 momentum; positive score and above 200-session TRI average; "
                f"next-open ETF fills; {result['exposure_cap_pct']}% gross cap"
            ),
            "source_artifact": (
                f"{result['source_artifact']};outputs/sector_tri_signal_momentum_sensitivity.csv;"
                "outputs/sector_tri_signal_momentum_selection.json;outputs/sector_tri_signal_momentum_method.md;"
                "outputs/sector_tri_signal_momentum_ohlc_audit.csv;work/sensitivity_sector_tri_signal.py"
            ),
            "notes": (
                f"Current modeled ETF charges; {result['slippage_bps_per_side']} bps per-side slippage. "
                + (f"Conservative same-day OHLC bound {float(risk['simultaneous_ohlc_drawdown_bound_pct']):.2f}%; " if risk else "Close drawdown only; OHLC audit is at 50 bps. ")
                + "Official TRI is a ranking signal only; simulated P&L uses ETF prices and credits no cash distributions. Unequal ETF inception dates and prior inspection prevent an investable winner claim."
            ),
        })
    tri_keys = [
        (row["strategy"], row["period"], row["gross_exposure_cap_pct"], row["slippage_bps_per_side"])
        for row in rows if row["simulation_type"] == "etf_sector_tri_signal_momentum"
    ]
    assert len(tri_keys) == len(set(tri_keys)) == 144

sector_distribution_path = ROOT / "outputs" / "sector_distribution_cashflow_sensitivity.csv"
if sector_distribution_path.exists():
    sector_distribution = read_csv(sector_distribution_path)
    assert len(sector_distribution) == 144, f"Expected 144 secondary-only sector distribution cases; found {len(sector_distribution)}"
    rows = [row for row in rows if row["simulation_type"] != "etf_sector_distribution_claim_sensitivity"]
    for result in sector_distribution:
        rows.append({
            "simulation_type": "etf_sector_distribution_claim_sensitivity",
            "strategy": f"{result['strategy']} | {result['cashflow_scenario']}",
            "universe": "BANKBEES; ITBEES; AUTOBEES; PHARMABEES; PSUBNKBEES",
            "period": result["period"],
            "period_start": result["period_start"],
            "period_end": result["period_end"],
            "starting_balance_inr": 1_000_000,
            "ending_balance_inr": 1_000_000 * (1 + float(result["scenario_total_return_pct"]) / 100),
            "total_return_pct": result["scenario_total_return_pct"],
            "cagr_pct": "",
            "max_drawdown_pct": result["scenario_close_mdd_pct"],
            "sharpe_zero_rf": "",
            "gross_exposure_cap_pct": result["exposure_cap_pct"],
            "slippage_bps_per_side": result["slippage_bps_per_side"],
            "fees_inr": result["fees_inr"],
            "slippage_cost_inr": result["slippage_cost_inr"],
            "trade_count": "",
            "order_count": result["order_count"],
            "within_20pct": result["within_20pct_under_ohlc"],
            "selection_or_sizing": (
                f"{result['signal_source']} signal; top {int(float(result['top_n']))}; "
                f"{result['exposure_cap_pct']}% gross cap; conditional {result['cashflow_scenario']} event-credit case"
            ),
            "source_artifact": (
                f"{result['source_artifact']};outputs/sector_distribution_cashflow_sensitivity.csv;"
                "outputs/sector_distribution_cashflow_method.md;work/sensitivity_sector_distribution_cashflow.py"
            ),
            "notes": (
                f"Current modeled ETF charges and {result['slippage_bps_per_side']} bps per-side slippage. "
                f"Conditional secondary-source-only cash credit of ₹{float(result['total_cash_credited_inr']):.2f}; "
                f"OHLC bound {float(result['scenario_ohlc_bound_pct']):.2f}%. The claimed distributions remain unverified; "
                "do not interpret as confirmed ETF total return."
            ),
        })
    distribution_keys = [
        (row["strategy"], row["period"], row["gross_exposure_cap_pct"], row["slippage_bps_per_side"])
        for row in rows if row["simulation_type"] == "etf_sector_distribution_claim_sensitivity"
    ]
    assert len(distribution_keys) == len(set(distribution_keys)) == 144

walk_forward_path = ROOT / "outputs" / "nifty_gold_walk_forward.csv"
if walk_forward_path.exists():
    walk_forward = read_csv(walk_forward_path)
    assert len(walk_forward) == 14, f"Expected 14 annual walk-forward rows; found {len(walk_forward)}"
    rows = [row for row in rows if row["simulation_type"] != "nifty_gold_expanding_walk_forward"]
    for result in walk_forward:
        rows.append({
            "simulation_type": "nifty_gold_expanding_walk_forward",
            "strategy": f"{result['role']} | {result['strategy']}",
            "universe": "NIFTYBEES + GOLDBEES",
            "period": str(result["test_year"]),
            "period_start": result["test_start"],
            "period_end": result["test_end"],
            "starting_balance_inr": result["starting_balance_inr"],
            "ending_balance_inr": result["ending_balance_inr"],
            "total_return_pct": result["total_return_pct"],
            "cagr_pct": result["cagr_pct"],
            "max_drawdown_pct": result["stitched_close_mdd_pct"],
            "sharpe_zero_rf": "",
            "gross_exposure_cap_pct": result["gross_exposure_cap_pct"],
            "slippage_bps_per_side": result["slippage_bps_per_side"],
            "fees_inr": result["total_fees_inr"],
            "slippage_cost_inr": result["total_slippage_inr"],
            "trade_count": "",
            "order_count": result["order_count"],
            "within_20pct": result["within_20pct_ohlc"],
            "selection_or_sizing": (
                f"{result['selection_rule']}; selected rule {result['strategy']} "
                f"after training through {result['training_end']}"
            ),
            "source_artifact": (
                "outputs/nifty_gold_walk_forward.csv;outputs/nifty_gold_walk_forward_method.md;"
                "work/walk_forward_nifty_gold.py;work/audit_etf_intraday_drawdown.py"
            ),
            "notes": (
                f"Training OHLC bound {float(result['training_ohlc_bound_pct']):.2f}%; "
                f"annual OHLC bound {float(result['annual_ohlc_bound_pct']):.2f}%; "
                f"full sequence OHLC bound through this fold {float(result['ohlc_bound_pct']):.2f}%. Annual pseudo-OOS fold "
                "with 45% cap, corrected ETF-unit fees, 50 bps per-side slippage, and terminal liquidation; "
                "historical prices have been inspected and ETF cash distributions/cash yield are incomplete."
            ),
        })
    walk_forward_keys = [
        (row["strategy"], row["period"])
        for row in rows if row["simulation_type"] == "nifty_gold_expanding_walk_forward"
    ]
    assert len(walk_forward_keys) == len(set(walk_forward_keys)) == 14

benchmark_sets = (
    ("outputs/nifty_gold_2020_benchmarks.csv", "nifty_gold_2020_benchmark", 7),
    ("outputs/nifty_gold_full_history_benchmarks.csv", "nifty_gold_full_history_benchmark", 5),
    ("outputs/nifty_gold_common_history_benchmarks.csv", "nifty_gold_common_history_benchmark", 5),
)
descriptions = {
    "walk_forward_selected": "Annual expanding-window selector; annual liquidation and actual cash carry-forward",
    "fixed_D55_20_control": "Annual fixed D55/20 control; annual liquidation and actual cash carry-forward",
    "quarterly_D55_20_fixed_45pct": "Fixed quarterly D55/20 + Gold SMA200; 45% gross target",
    "quarterly_static_50_50_45pct": "Quarterly-rebalanced 50/50 NIFTY/Gold target; aggregate 45% exposure",
    "passive_NIFTYBEES_45pct": "Passive NIFTYBEES buy-and-hold; 45% initial allocation",
    "passive_GOLDBEES_45pct": "Passive GOLDBEES buy-and-hold; 45% initial allocation",
    "passive_NIFTY_Gold_22_5pct_each": "Passive NIFTYBEES/GOLDBEES buy-and-hold; 22.5% initial allocation each",
}
benchmark_types = {item[1] for item in benchmark_sets}
rows = [row for row in rows if row["simulation_type"] not in benchmark_types]
for benchmark_path, simulation_type, expected_count in benchmark_sets:
    path = ROOT / benchmark_path
    if not path.exists():
        continue
    benchmarks = read_csv(path)
    assert len(benchmarks) == expected_count, f"Expected {expected_count} paths in {benchmark_path}; found {len(benchmarks)}"
    for result in benchmarks:
        assert result["strategy"] in descriptions
        if simulation_type == "nifty_gold_2020_benchmark":
            artifacts = (
                "outputs/nifty_gold_2020_benchmarks.csv;outputs/nifty_gold_2020_benchmarks_method.md;"
                "work/benchmark_nifty_gold_2020.py;work/backtests/nifty_gold_2020_benchmarks/;"
                "outputs/nifty_gold_walk_forward.csv;outputs/nifty_gold_walk_forward_method.md"
            )
        else:
            artifacts = (
                f"{benchmark_path};outputs/nifty_gold_history_benchmarks_method.md;"
                "work/benchmark_nifty_gold_2020.py;work/backtests/nifty_gold_full_history_benchmarks/;"
                "work/backtests/nifty_gold_common_history_benchmarks/;work/research/etf_total_return_source_audit.md"
            )
        cash_note = (
            f"Known NIFTYBEES distributions credited: ₹{float(result.get('cash_distributions_inr') or 0.0):.2f}; "
            "GoldBeES distribution history is not proven complete. "
        )
        rows.append({
            "simulation_type": simulation_type,
            "strategy": result["strategy"],
            "universe": "NIFTYBEES + GOLDBEES",
            "period": f"{result['period_start']} to {result['period_end']}",
            "period_start": result["period_start"],
            "period_end": result["period_end"],
            "starting_balance_inr": result["starting_balance_inr"],
            "ending_balance_inr": result["ending_balance_inr"],
            "total_return_pct": result["total_return_pct"],
            "cagr_pct": result["cagr_pct"],
            "max_drawdown_pct": result["close_mdd_pct"],
            "sharpe_zero_rf": "",
            "gross_exposure_cap_pct": result["gross_exposure_cap_pct"],
            "slippage_bps_per_side": result["slippage_bps_per_side"],
            "fees_inr": result["total_fees_inr"],
            "slippage_cost_inr": result["total_slippage_inr"],
            "trade_count": "",
            "order_count": result["order_count"],
            "within_20pct": result["within_20pct_ohlc"],
            "selection_or_sizing": descriptions[result["strategy"]],
            "source_artifact": artifacts,
            "notes": (
                f"Conservative same-day high-before-low OHLC bound {float(result['ohlc_drawdown_bound_pct']):.2f}%; "
                f"{cash_note}20% is a historical screen only. Price-based ETF candles, current modeled fees, "
                "50 bps per-side slippage, zero cash yield, terminal liquidation, and previously inspected dates. "
                "Passive allocation exposure can drift above the initial target; see method and source audit."
            ),
        })
    benchmark_keys = [
        (row["strategy"], row["period"])
        for row in rows if row["simulation_type"] == simulation_type
    ]
    assert len(benchmark_keys) == len(set(benchmark_keys)) == expected_count

exposure_selection = json.loads((ROOT / "outputs" / "static_mix_training_selection.json").read_text(encoding="utf-8"))
exposure_files = (
    ("outputs/static_mix_exposure_training.csv", "static_mix_exposure_training", 19),
    ("outputs/static_mix_exposure_oos_test.csv", "static_mix_exposure_oos_test", 19),
)
exposure_types = {item[1] for item in exposure_files}
rows = [row for row in rows if row["simulation_type"] not in exposure_types]
for exposure_path, simulation_type, expected_count in exposure_files:
    exposure_results = read_csv(ROOT / exposure_path)
    assert len(exposure_results) == expected_count, f"Expected {expected_count} cases in {exposure_path}; found {len(exposure_results)}"
    for result in exposure_results:
        cap = float(result["gross_exposure_cap_pct"])
        selected = simulation_type == "static_mix_exposure_training" and cap == exposure_selection["selected_cap_pct"]
        selected = selected or (
            simulation_type == "static_mix_exposure_oos_test" and result["selected_by_training_rule"] == "True"
        )
        rows.append({
            "simulation_type": simulation_type,
            "strategy": result["strategy"],
            "universe": "NIFTYBEES + GOLDBEES",
            "period": f"{result['period_start']} to {result['period_end']}",
            "period_start": result["period_start"],
            "period_end": result["period_end"],
            "starting_balance_inr": result["starting_balance_inr"],
            "ending_balance_inr": result["ending_balance_inr"],
            "total_return_pct": result["total_return_pct"],
            "cagr_pct": result["cagr_pct"],
            "max_drawdown_pct": result["close_mdd_pct"],
            "sharpe_zero_rf": "",
            "gross_exposure_cap_pct": cap,
            "slippage_bps_per_side": result["slippage_bps_per_side"],
            "fees_inr": result["total_fees_inr"],
            "slippage_cost_inr": result["total_slippage_inr"],
            "trade_count": "",
            "order_count": result["order_count"],
            "within_20pct": result["within_20pct_ohlc"],
            "selection_or_sizing": (
                f"Quarterly static 50/50 NIFTY/Gold mix; {cap:.0f}% gross exposure cap; "
                f"{'selected from training' if selected else 'fixed sensitivity case'}"
            ),
            "source_artifact": (
                f"{exposure_path};outputs/static_mix_training_selection.json;"
                "outputs/static_mix_exposure_method.md;work/select_static_mix_exposure.py;"
                "work/backtests/static_mix_exposure_training/;work/backtests/static_mix_exposure_test/"
            ),
            "notes": (
                f"Conservative same-day high-before-low OHLC bound {float(result['ohlc_drawdown_bound_pct']):.2f}%; "
                f"training rule selected {exposure_selection['selected_cap_pct']:.0f}% from 2015–2019. "
                "The 2020–2026 grid is post-hoc because those dates were inspected; only the training-selected cap "
                f"is the chronological pseudo-OOS row (passed screen: {exposure_selection['selected_cap_test_passed_20pct']}). "
                "Each path starts with ₹10 lakh, rebalances quarterly, uses 50 bps per-side slippage, zero cash yield, "
                "current modeled fees, and terminal liquidation; cap can drift between rebalances."
            ),
        })
    exposure_keys = [
        row["strategy"] for row in rows if row["simulation_type"] == simulation_type
    ]
    assert len(exposure_keys) == len(set(exposure_keys)) == expected_count

passive_exposure_path = "outputs/passive_mix_exposure_sensitivity.csv"
passive_exposure_type = "etf_passive_mix_exposure_sensitivity"
passive_exposure = read_csv(ROOT / passive_exposure_path)
assert len(passive_exposure) == 30, f"Expected 30 passive mix exposure rows; found {len(passive_exposure)}"
rows = [row for row in rows if row["simulation_type"] != passive_exposure_type]
for result in passive_exposure:
    exposure_pct = float(result["tested_initial_exposure_pct"])
    selected = result["training_selected"] == "True"
    full_period = result["period"] == "continuous_2015_plus"
    oos_return = result.get("post_2019_oos_return_pct", "")
    bound = float(result["ohlc_drawdown_bound_pct"])
    notes = (
        f"Conservative daily OHLC bound {bound:.2f}%; passive 50/50 NIFTY/Gold units held without rebalancing; "
        "2015–2019 exposure selector and continuous 2015–2026 path; current fees, 50 bps per-side slippage, "
        "zero cash yield, and previously inspected history. Exposure drifts from the initial target."
    )
    if full_period:
        notes += f" Return from the 2019 training-end NAV through terminal liquidation: {float(oos_return):.2f}%."
    if selected and full_period:
        notes += " The training-selected 100% initial exposure fails the full-history 20% OHLC screen."
    rows.append({
        "simulation_type": passive_exposure_type,
        "strategy": result["strategy"],
        "universe": "NIFTYBEES + GOLDBEES",
        "period": result["period"],
        "period_start": result["period_start"],
        "period_end": result["period_end"],
        "starting_balance_inr": result["starting_balance_inr"],
        "ending_balance_inr": result["ending_balance_inr"],
        "total_return_pct": result["total_return_pct"],
        "cagr_pct": result["cagr_pct"],
        "max_drawdown_pct": result["close_mdd_pct"],
        "sharpe_zero_rf": "",
        "gross_exposure_cap_pct": exposure_pct,
        "slippage_bps_per_side": 50,
        "fees_inr": result["total_fees_inr"],
        "slippage_cost_inr": result["total_slippage_inr"],
        "trade_count": "",
        "order_count": result["order_count"],
        "within_20pct": result["within_20pct_ohlc"] == "True",
        "selection_or_sizing": (
            f"Passive equal-weight NIFTY/Gold; {exposure_pct:.0f}% initial gross exposure; no rebalancing; "
            f"{'selected on 2015–2019 training' if selected else 'fixed sensitivity'}"
        ),
        "source_artifact": (
            f"{passive_exposure_path};outputs/passive_mix_exposure_method.md;"
            "work/sensitivity_passive_mix_exposure.py;work/backtests/passive_mix_exposure/"
        ),
        "notes": notes,
    })
passive_keys = [
    (row["period"], row["strategy"])
    for row in rows if row["simulation_type"] == passive_exposure_type
]
assert len(passive_keys) == len(set(passive_keys)) == 30

drawdown_control_path = "outputs/passive_drawdown_control_sensitivity.csv"
drawdown_control_type = "etf_passive_mix_drawdown_control"
drawdown_control = read_csv(ROOT / drawdown_control_path)
assert len(drawdown_control) == 15, f"Expected 15 passive drawdown-control cases; found {len(drawdown_control)}"
rows = [row for row in rows if row["simulation_type"] != drawdown_control_type]
for result in drawdown_control:
    exposure_pct = float(result["initial_exposure_pct"])
    trigger_pct = result["drawdown_trigger_pct"]
    slip = float(result["slippage_bps_per_side"])
    if trigger_pct:
        selection = (
            f"60% initial exposure; cut to 30% after {float(trigger_pct):.0f}% close drawdown; "
            f"restore at {float(trigger_pct) / 2:.0f}% drawdown; next-open trades"
        )
    else:
        selection = f"Passive 50/50 NIFTY/Gold; fixed {exposure_pct:.0f}% initial exposure; no rebalance"
    notes = (
        f"Conservative same-day OHLC drawdown bound {float(result['ohlc_drawdown_bound_pct']):.2f}%; "
        f"{int(result['trigger_count'])} cuts and {int(result['recovery_count'])} recoveries; "
        f"current fees, {slip:.0f} bps per-side slippage, zero cash yield, and known NIFTYBEES distributions. "
        "2015–2026 history was previously inspected; drawdown threshold sensitivity is retrospective, not a forecast."
    )
    rows.append({
        "simulation_type": drawdown_control_type,
        "strategy": result["strategy"],
        "universe": "NIFTYBEES + GOLDBEES",
        "period": "common_2015_plus",
        "period_start": result["period_start"],
        "period_end": result["period_end"],
        "starting_balance_inr": result["starting_balance_inr"],
        "ending_balance_inr": result["ending_balance_inr"],
        "total_return_pct": result["total_return_pct"],
        "cagr_pct": result["cagr_pct"],
        "max_drawdown_pct": result["close_mdd_pct"],
        "sharpe_zero_rf": "",
        "gross_exposure_cap_pct": exposure_pct,
        "slippage_bps_per_side": slip,
        "fees_inr": result["total_fees_inr"],
        "slippage_cost_inr": result["total_slippage_inr"],
        "trade_count": "",
        "order_count": result["order_count"],
        "within_20pct": result["within_20pct_ohlc"] == "True",
        "selection_or_sizing": selection,
        "source_artifact": (
            f"{drawdown_control_path};outputs/passive_drawdown_control_method.md;"
            "work/backtest_passive_mix_drawdown_control.py;work/backtests/passive_drawdown_control/"
        ),
        "notes": notes,
    })
drawdown_control_keys = [
    (row["strategy"], row["slippage_bps_per_side"])
    for row in rows if row["simulation_type"] == drawdown_control_type
]
assert len(drawdown_control_keys) == len(set(drawdown_control_keys)) == 15

ratio_path = "outputs/nifty_gold_allocation_ratio_sensitivity.csv"
ratio_type = "nifty_gold_allocation_ratio_sensitivity"
ratio_grid = read_csv(ROOT / ratio_path)
ratio_selection_path = "outputs/nifty_gold_allocation_ratio_selection.json"
ratio_selection = json.loads((ROOT / ratio_selection_path).read_text(encoding="utf-8"))
selected_ratio_rule = ratio_selection["selected"]["rule_id"]
ratio_ohlc_path = "outputs/nifty_gold_allocation_ratio_training_ohlc.csv"
ratio_oos_ohlc_path = "outputs/nifty_gold_allocation_ratio_oos_ohlc.csv"
ratio_cost_path = "outputs/nifty_gold_allocation_ratio_cost_sensitivity.csv"
ratio_types = {ratio_type, "nifty_gold_allocation_ratio_ohlc_audit", "nifty_gold_allocation_ratio_cost_sensitivity"}
rows = [row for row in rows if row["simulation_type"] not in ratio_types]
ratio_by_key = {(row["rule_id"], row["period"]): row for row in ratio_grid}
assert len(ratio_grid) == 990 and len(ratio_by_key) == 990
for result in ratio_grid:
    training_bound = float(result["training_ohlc_bound_pct"])
    rows.append({
        "simulation_type": ratio_type,
        "strategy": result["rule_id"],
        "universe": "NIFTYBEES + GOLDBEES",
        "period": result["period"],
        "period_start": result["period_start"],
        "period_end": result["period_end"],
        "starting_balance_inr": result["starting_balance_inr"],
        "ending_balance_inr": result["ending_balance_inr"],
        "total_return_pct": result["total_return_pct"],
        "cagr_pct": result["cagr_pct"],
        "max_drawdown_pct": result["max_drawdown_pct"],
        "sharpe_zero_rf": result["sharpe_zero_rf"],
        "gross_exposure_cap_pct": result["gross_exposure_cap_pct"],
        "slippage_bps_per_side": result["slippage_bps_per_side"],
        "fees_inr": result["fees_inr"],
        "slippage_cost_inr": result["slippage_cost_inr"],
        "trade_count": "",
        "order_count": result["order_count"],
        "within_20pct": result["within_20pct_close"],
        "selection_or_sizing": (
            f"{result['rebalance_frequency']}; {float(result['nifty_share_pct']):.0f}% NIFTY / "
            f"{float(result['gold_share_pct']):.0f}% Gold active-sleeve shares; "
            f"{float(result['gross_exposure_cap_pct']):.0f}% exposure cap; 50 bps per-side slippage; "
            f"{'training-selected' if result['rule_id'] == selected_ratio_rule else 'grid sensitivity'}"
        ),
        "source_artifact": (
            f"{ratio_path};outputs/nifty_gold_allocation_ratio_method.md;"
            "work/sensitivity_nifty_gold_allocation_ratio.py"
        ),
        "notes": (
            f"Close MDD only in this row. Training OHLC bound was {training_bound:.2f}% "
            f"({'pass' if result['training_pass_20pct_ohlc'] == 'True' else 'fail'}); only the frozen "
            "selection and monthly 50/50 reference have later-window OHLC audits. Post-hoc history, "
            "50-bps primary cost, zero cash yield, and incomplete ETF distribution coverage."
        ),
    })

ratio_ohlc_rows = []
for risk_path, period, training in (
    (ratio_ohlc_path, "train_2015_2019", True),
    (ratio_oos_ohlc_path, None, False),
):
    for risk in read_csv(ROOT / risk_path):
        period_name = period or risk["period"]
        result = ratio_by_key[(risk["rule_id"], period_name)]
        run_subdir = (
            f"training/{risk['rule_id']}__{period_name}__50bps" if training else
            f"{risk['role']}/{risk['rule_id']}__{period_name}__50bps"
        )
        ratio_ohlc_rows.append({
            "simulation_type": "nifty_gold_allocation_ratio_ohlc_audit",
            "strategy": risk["rule_id"],
            "universe": "NIFTYBEES + GOLDBEES",
            "period": period_name,
            "period_start": result["period_start"],
            "period_end": result["period_end"],
            "starting_balance_inr": risk["starting_balance_inr"],
            "ending_balance_inr": risk["ending_balance_inr"],
            "total_return_pct": (float(risk["ending_balance_inr"]) / float(risk["starting_balance_inr"]) - 1) * 100,
            "cagr_pct": result["cagr_pct"],
            "max_drawdown_pct": risk["simultaneous_ohlc_drawdown_bound_pct"],
            "sharpe_zero_rf": result["sharpe_zero_rf"],
            "gross_exposure_cap_pct": result["gross_exposure_cap_pct"],
            "slippage_bps_per_side": risk["slippage_bps_per_side"],
            "fees_inr": risk["total_fees_inr"],
            "slippage_cost_inr": result["slippage_cost_inr"],
            "trade_count": "",
            "order_count": result["order_count"],
            "within_20pct": risk["within_20pct_under_bound"],
            "selection_or_sizing": "Training-only OHLC screen" if training else f"Frozen {risk['role']} path; 50-bps OHLC audit",
            "source_artifact": (
                f"{risk_path};outputs/nifty_gold_allocation_ratio_selection.json;"
                f"work/backtests/nifty_gold_allocation_ratio/{run_subdir}/orders.csv;"
                "work/audit_etf_intraday_drawdown.py"
            ),
            "notes": (
                f"Conservative same-session high-before-low OHLC envelope {float(risk['simultaneous_ohlc_drawdown_bound_pct']):.2f}%; "
                f"saved close NAV replay error ₹{float(risk['max_close_replay_error_inr']):.6g}. "
                "Historical envelope is not a future loss limit."
            ),
        })
rows.extend(ratio_ohlc_rows)
assert len(ratio_ohlc_rows) == 206

ratio_costs = read_csv(ROOT / ratio_cost_path)
assert len(ratio_costs) == 18
for result in ratio_costs:
    rows.append({
        "simulation_type": "nifty_gold_allocation_ratio_cost_sensitivity",
        "strategy": f"{result['role']} | {result['rule_id']}",
        "universe": "NIFTYBEES + GOLDBEES",
        "period": result["period"],
        "period_start": result["period_start"],
        "period_end": result["period_end"],
        "starting_balance_inr": 1_000_000,
        "ending_balance_inr": 1_000_000 * (1 + float(result["total_return_pct"]) / 100),
        "total_return_pct": result["total_return_pct"],
        "cagr_pct": "",
        "max_drawdown_pct": result["max_drawdown_pct"],
        "sharpe_zero_rf": "",
        "gross_exposure_cap_pct": result["gross_exposure_cap_pct"],
        "slippage_bps_per_side": result["slippage_bps_per_side"],
        "fees_inr": result["fees_inr"],
        "slippage_cost_inr": result["slippage_cost_inr"],
        "trade_count": "",
        "order_count": result["order_count"],
        "within_20pct": float(result["max_drawdown_pct"]) >= -20,
        "selection_or_sizing": f"{float(result['nifty_share_pct']):.0f}% NIFTY / {100-float(result['nifty_share_pct']):.0f}% Gold; close-drawdown cost sensitivity",
        "source_artifact": f"{ratio_cost_path};outputs/nifty_gold_allocation_ratio_method.md",
        "notes": "10/50/100-bps per-side cost sensitivity. Close MDD only; OOS OHLC audits were done at 50 bps. 100-bps close breach, if any, is not replaced by an OHLC audit.",
    })

credit_costs = read_csv(ROOT / "outputs" / "monthly_nifty_credit_spread" / "cost_screen.csv")
credit_trades = read_csv(ROOT / "outputs" / "monthly_nifty_credit_spread" / "trades_50bps.csv")
assert len(credit_costs) == 12
rows = [row for row in rows if row["simulation_type"] != "expired_credit_options_slippage_sensitivity"]
for result in credit_costs:
    period = result["period"]
    trades = [trade for trade in credit_trades if trade["period"] == period]
    rows.append({
        "simulation_type": "expired_credit_options_slippage_sensitivity",
        "strategy": "NIFTY 200DMA monthly 200-point credit vertical",
        "universe": "NIFTY 50 monthly PE/CE verticals",
        "period": period,
        "period_start": min((trade["entry_date"] for trade in trades), default=""),
        "period_end": max((trade["exit_date"] for trade in trades), default=""),
        "starting_balance_inr": result["starting_balance_inr"],
        "ending_balance_inr": result["ending_balance_inr"],
        "total_return_pct": result["total_return_pct"],
        "cagr_pct": result.get("cagr_pct", ""),
        "max_drawdown_pct": result.get("max_close_drawdown_pct", ""),
        "sharpe_zero_rf": result.get("sharpe_zero_rf", ""),
        "gross_exposure_cap_pct": "",
        "slippage_bps_per_side": result["slippage_bps_per_leg_per_side"],
        "fees_inr": result.get("total_fees_inr", 0),
        "slippage_cost_inr": result.get("total_slippage_inr", 0),
        "trade_count": result["trade_count"],
        "order_count": result["order_count"],
        "within_20pct": result.get("within_20pct_close_limit", False),
        "selection_or_sizing": "One lot; open gross spread width limited to 2% of prior-close NAV; exit five sessions before expiry",
        "source_artifact": "outputs/monthly_nifty_credit_spread/cost_screen.csv;outputs/monthly_nifty_credit_spread_method.md",
        "notes": (f"Daily OHLC stress envelope {result.get('max_ohlc_envelope_drawdown_pct', 0)}%; "
                  "current options fees applied uniformly and slippage is per leg/side. "
                  "Margin not reconstructed; 2026 later segment was previously inspected."),
    })

write_csv(LEDGER, rows, list(rows[0]))

manifest = read_csv(MANIFEST)
for row in manifest:
    if row["dataset"] == "Consolidated backtest metric ledger":
        row["bar_count"] = str(len(rows))
        row["notes"] = (
            "Includes the fee-corrected strategy rows, 40 NIFTY/Gold blend scenarios, "
            "12 restored-universe stock sensitivity rows, local ETF parameter-stability cases, "
            "six price-only plus six distribution-adjusted NIFTYBEES/GOLDBEES momentum cases, "
            "the 140-case single-sleeve deployment screen, the 60-case volatility-throttle screen, "
            "the 90-case India VIX overlay screen, the 130-case joint exposure/throttle screen, "
            "the 125-case execution-cost stress, the 64-case intraday ORB opening-range sensitivity, "
            "the 144-case NIFTY opening-gap fade sensitivity, the 384-case sector ETF rotation screen with 96 OHLC audits, the 144-case official-TRI sector signal challenger with 48 OHLC audits, and 144 secondary-only sector distribution sensitivities with OHLC audits; "
            "14 annual expanding-window NIFTY/Gold parameter-selection replay rows; "
            "47 NIFTY/Gold passive, active, and exposure-sensitivity rows across 2020+, full available history, and a shared 2015+ window, including 30 passive-mix exposure cases; "
            "15 passive drawdown-control cases across 10/50/100 bps; "
            "19 training-selected static-mix exposure cases and 19 chronological test-period sensitivity cases; "
            "990 NIFTY/Gold active-sleeve allocation-ratio rows, 206 order-ledger OHLC audits, and 18 cost-sensitivity rows; "
            "12 monthly NIFTY credit-spread fee/slippage scenarios across four chronological periods; "
            "method and source artifacts "
            "are linked in the research report."
        )
    elif row["dataset"] == "Forward paper NIFTY/Gold ETF control plan":
        row.update({
            "bar_count": "11 paths; 0 post-freeze sessions",
            "file_count": "plan + 3 output ledgers + revision 1-7 freezes",
            "purpose": "Freeze and track eleven NIFTY/Gold ETF controls prospectively on new Upstox candles",
            "cache_paths": (
                "outputs/forward_paper_plan.md;outputs/forward_paper_ledger.csv;"
                "outputs/forward_paper_equity.csv;outputs/forward_paper_orders.csv;"
                "work/backtests/forward_paper/frozen_config_v5.json;"
                "work/backtests/forward_paper/frozen_config_v6.json;"
                "work/backtests/forward_paper/frozen_config_v7.json"
            ),
            "notes": "Revision 7 preserves the eight revision-6 paths and adds the 8/10/12% passive drawdown-control threshold frontier, frozen before the 2026-10-27 close. Paper starts 2026-10-28. Revisions 1-6 remain preserved for lineage. Zero paper sessions at freeze; ₹10 lakh per path; paper only, no broker orders.",
        })
    elif row["dataset"] == "Forward paper NIFTY/Gold Upstox seed probe":
        paper_probe = json.loads((ROOT / "work" / "data" / "api_probes" / "forward_paper_latest.json").read_text(encoding="utf-8"))
        paper_status = json.loads((ROOT / "work" / "backtests" / "forward_paper" / "latest_status.json").read_text(encoding="utf-8"))
        paper_results = paper_probe["results"]
        assert paper_results and all(result.get("token_value_saved") is False for result in paper_results)
        paper_start, paper_end = paper_probe["request_window"]
        paper_bars = sum(int(result.get("bars_received", 0)) for result in paper_results)
        paper_sources = "; ".join(
            f"{result['symbol']}={result['status']} ({int(result.get('bars_received', 0))} bars)"
            for result in paper_results
        )
        row.update({
            "first_bar": paper_start,
            "last_bar": paper_end,
            "bar_count": f"{len(paper_results)} requests; {paper_bars} bars",
            "file_count": "latest probe + request history + status + 2 incremental bars + 2 snapshots + 2 raw candle checks",
            "cache_paths": (
                "work/data/api_probes/forward_paper_latest.json;"
                "work/data/api_probes/forward_paper_history.jsonl;"
                "work/backtests/forward_paper/latest_status.json;"
                "work/data/forward_paper/incremental/NIFTYBEES.csv;"
                "work/data/forward_paper/incremental/GOLDBEES.csv;"
                "work/data/forward_paper/snapshots/NIFTYBEES.csv;"
                "work/data/forward_paper/snapshots/GOLDBEES.csv;"
                "work/data/api_probes/market_session_check_2026-10-26/NSE_EQ_INF204KB14I2-days-1-2026-10-26-2026-10-26.csv;"
                "work/data/api_probes/market_session_check_2026-10-26/NSE_EQ_INF204KB17I5-days-1-2026-10-26-2026-10-26.csv"
            ),
            "purpose": "Record completed-session Upstox candle availability for the eleven-path prospective paper test",
            "notes": (
                f"Latest exact-key requests through {paper_end}: {paper_sources}. "
                f"Latest common history bar: {paper_status['latest_common_history_bar']}; "
                f"post-freeze common sessions: {paper_status['new_common_sessions']}. "
                "The runner requests through the prior calendar date to exclude partial daily candles. "
                "No paper return was synthesized; token values are not saved. "
                "Earlier wider query returned Oct 22–23 for NIFTYBEES and NIFTY 50."
            ),
        })
    elif row["dataset"] == "Sector ETF corporate-action evidence matrix":
        row["cache_paths"] = "outputs/sector_etf_corporate_action_audit.csv;outputs/sector_rotation_primary_sources.md"
        row["notes"] = (
            "BANKBEES payout values were corrected to NSE-listed ₹11/unit (2014) and ₹13/unit (2015); "
            "the prior ₹7/₹8 values belong to NIFTYBEES. All listed BANKBEES events predate the 2020+ replay. "
            "AMFI/AMC completeness for AUTOBEES and PHARMABEES remains unresolved; empty Upstox responses are not proof of no events."
        )
for metadata in (
    {
        "dataset": "Fee-corrected consolidated backtest ledger refresh",
        "ticker": "walk-forward; ORB holdout; monthly NIFTY options",
        "instrument_key": "",
        "bar_interval": "summary refresh",
        "first_bar": "2020-01-01",
        "last_bar": "2026-10-23",
        "bar_count": str(updated),
        "file_count": "1",
        "empty_files": "0",
        "cache_paths": Path(__file__).relative_to(ROOT).as_posix(),
        "purpose": "Sync rerun fee-corrected metrics into the consolidated backtest ledger",
        "notes": "Reads existing run summaries only; does not calculate returns or fetch market data.",
    },
    {
        "dataset": "NIFTY/Gold single-sleeve deployment sensitivity",
        "ticker": "NIFTYBEES; GOLDBEES",
        "instrument_key": "NSE_EQ|INF204KB14I2; GOLDBEES alias cache",
        "bar_interval": "daily strategy; 10/50 bps per-side slippage",
        "first_bar": "2014-01-01",
        "last_bar": "2026-10-23",
        "bar_count": "140 scenarios",
        "file_count": "140 equity/order pairs + summary.csv + strategy.json",
        "empty_files": "0",
        "cache_paths": "outputs/single_sleeve_deployment_sensitivity.csv",
        "purpose": "Measure the return/drawdown effect of deploying 50–100% when one NIFTY/Gold trend sleeve is active while preserving inverse-vol weights when both are active",
        "notes": "Two schedules × seven solo weights × five periods × two cost levels; all 20 baseline cases matched established results; all 28 continuous run paths held zero NIFTYBEES units at the two known ex-dates.",
    },
    {
        "dataset": "NIFTY/Gold trailing-volatility throttle sensitivity",
        "ticker": "NIFTYBEES; GOLDBEES",
        "instrument_key": "NSE_EQ|INF204KB14I2; NSE_EQ|INF204KB17I5",
        "bar_interval": "daily close-to-close; 10/50 bps per-side slippage",
        "first_bar": "2014-01-01",
        "last_bar": "2026-10-23",
        "bar_count": "60 scenarios",
        "file_count": "60 equity/order pairs + summary.csv + strategy.json",
        "empty_files": "0",
        "cache_paths": "outputs/volatility_target_sensitivity.csv",
        "purpose": "Measure return/drawdown tradeoffs from scaling the quarterly NIFTY/Gold trend portfolio against trailing 63-session realized volatility",
        "notes": "Five volatility thresholds plus no-throttle baseline; five chronological windows; 10/50 bps per-side slippage; 100% gross cap; no leverage; retrospective and not independent validation.",
    },
    {
        "dataset": "India VIX daily candles",
        "ticker": "India VIX",
        "instrument_key": "NSE_INDEX|India VIX",
        "bar_interval": "1 day",
        "first_bar": "2014-01-01",
        "last_bar": "2026-10-23",
        "bar_count": "3,172 raw rows; 3,169 unique dates",
        "file_count": "1",
        "empty_files": "0",
        "cache_paths": "work/data/index_daily/IndiaVIX-days-1-2014-01-01-2026-10-23.csv",
        "purpose": "Close-known India VIX risk signal for the retrospective NIFTYBEES exposure-overlay screen",
        "notes": "Original Upstox response retained unchanged and contains three conflicting duplicate dates. The analysis uses a separate reconciled file with NSE official OHLC on those dates; see the saved source response. No VIX contract is traded.",
    },
    {
        "dataset": "India VIX daily research input (NSE-reconciled)",
        "ticker": "India VIX",
        "instrument_key": "NSE_INDEX|India VIX",
        "bar_interval": "1 day; Upstox except three NSE-source replacements",
        "first_bar": "2014-01-01",
        "last_bar": "2026-10-23",
        "bar_count": "3,169 unique sessions",
        "file_count": "1 generated CSV + 3 NSE source records",
        "empty_files": "0",
        "cache_paths": "work/data/index_daily/IndiaVIX-NSE-reconciled-days-1-2014-01-01-2026-10-23.csv;outputs/india_vix_nse_conflict_reconciliation.json;work/sensitivity_india_vix_overlay.py",
        "purpose": "Close-known India VIX signal input for the corrected NIFTYBEES exposure-overlay sensitivity",
        "notes": "The three duplicate Upstox sessions are replaced with NSE daily OHLC for 2015-06-29, 2015-07-02, and 2015-08-10. Original Upstox observations remain preserved in the source CSV.",
    },
    {
        "dataset": "India VIX observation quality audit",
        "ticker": "India VIX aligned to NIFTYBEES sessions",
        "instrument_key": "NSE_INDEX|India VIX; NSE_EQ|INF204KB14I2",
        "bar_interval": "daily session alignment",
        "first_bar": "2015-06-29",
        "last_bar": "2019-07-02",
        "bar_count": "1 issue session",
        "file_count": "1",
        "empty_files": "0",
        "cache_paths": "outputs/india_vix_daily_quality.csv",
        "purpose": "Record duplicate or missing VIX rows and the conservative prior-close carry treatment",
        "notes": "The missing 2019-07-02 NIFTY/ETF session carries the previous confirmed VIX close; the three conflicting dates are reconciled from NSE.",
    },
    {
        "dataset": "NIFTY/Gold India VIX overlay sensitivity",
        "ticker": "NIFTYBEES; GOLDBEES; India VIX",
        "instrument_key": "NSE_EQ|INF204KB14I2; NSE_EQ|INF204KB17I5; NSE_INDEX|India VIX",
        "bar_interval": "daily; close signal / next-open fills; 10/50 bps per-side slippage",
        "first_bar": "2014-01-01",
        "last_bar": "2026-10-23",
        "bar_count": "90 scenarios",
        "file_count": "90 equity/order pairs + summary.csv + strategy.json + quality audit",
        "empty_files": "0",
        "cache_paths": "outputs/india_vix_overlay_sensitivity.csv;outputs/india_vix_overlay_method.md",
        "purpose": "Test whether confirmed India VIX levels can reduce NIFTYBEES exposure without changing the Gold sleeve",
        "notes": "Corrected 90-case overlay uses normalized ETF sessions and NSE-authoritative OHLC on three conflicting VIX dates. No 50 bps full-history variant meets the 20% drawdown limit; at 10 bps the no-overlay baseline has higher return and equal drawdown.",
    },
    {
        "dataset": "NIFTY/Gold joint exposure-volatility sensitivity",
        "ticker": "NIFTYBEES; GOLDBEES",
        "instrument_key": "NSE_EQ|INF204KB14I2; NSE_EQ|INF204KB17I5",
        "bar_interval": "daily; close signal / next-open fills; 10/50 bps per-side slippage",
        "first_bar": "2014-01-01",
        "last_bar": "2026-10-23",
        "bar_count": "130 scenarios",
        "file_count": "130 equity/order pairs + summary.csv + strategy.json",
        "empty_files": "0",
        "cache_paths": "outputs/joint_exposure_volatility_sensitivity.csv;outputs/joint_exposure_volatility_method.md",
        "purpose": "Measure the return and drawdown frontier when higher solo-sleeve exposure is paired with an event-based trailing-volatility throttle",
        "notes": "Four solo weights × three volatility targets plus the 65% no-throttle control; five chronological windows and 10/50 bps. Seven baseline metrics matched. The 80%/16% path held zero NIFTYBEES units on both known distribution ex-dates at both cost levels; the rule is a retrospective paper challenger, not a proven optimum.",
    },
    {
        "dataset": "NIFTY/Gold execution-cost stress sensitivity",
        "ticker": "NIFTYBEES; GOLDBEES",
        "instrument_key": "NSE_EQ|INF204KB14I2; NSE_EQ|INF204KB17I5",
        "bar_interval": "daily; close signal / next-open fills; 10/50/100/150/200 bps per-side slippage",
        "first_bar": "2014-01-01",
        "last_bar": "2026-10-23",
        "bar_count": "125 scenarios",
        "file_count": "125 equity/order pairs + summary.csv + strategy.json",
        "empty_files": "0",
        "cache_paths": "outputs/cost_stress_sensitivity.csv;outputs/cost_stress_method.md",
        "purpose": "Measure how execution friction changes return and historical drawdown for five NIFTY/Gold quarterly sizing rules",
        "notes": "Five rules × five periods × five per-side slippage levels; 175 metrics match the 50 bps joint-screen baselines. The 65%/16% rule alone passed all five windows at 100 bps; 150/200 bps are severe stress settings, not spread forecasts. Retrospective, not independent validation.",
    },
    {
        "dataset": "Offline cached monthly-options replay runner",
        "ticker": "NIFTY 50 monthly options",
        "instrument_key": "NSE_INDEX|Nifty 50",
        "bar_interval": "runner",
        "first_bar": "2024-10-01",
        "last_bar": "2026-09-30",
        "bar_count": "22 cached expiries",
        "file_count": "1",
        "empty_files": "0",
        "cache_paths": "work/replay_monthly_options_cached.py",
        "purpose": "Replay monthly options from saved Upstox contract and candle caches without expiry discovery",
        "notes": "Missing cached option candles still require API access; no token value is stored.",
    },
    {
        "dataset": "Upstox and NSE fee-model audit",
        "ticker": "ETFs; NIFTY 50 derivatives",
        "instrument_key": "",
        "bar_interval": "method note",
        "first_bar": "2020-01-01",
        "last_bar": "2026-10-23",
        "bar_count": "fee sources and corrected rate",
        "file_count": "1",
        "empty_files": "0",
        "cache_paths": "work/research/fee_model_audit.md",
        "purpose": "Document charge formulas, primary rate sources, correction, and rerun scope",
        "notes": "SEBI fee is ₹10/crore. On 2026-10-27 ETF STT was corrected by instrument: equity-fund units nil on buys/0.001% sell, other fund units nil; all saved ETF-dependent screens were replayed. Current derivatives tariffs were rechecked: the NIFTY futures calculator applies dated 2026 STT/transaction changes, while the shared options model applies current rates uniformly as a cost stress.",
    },
    {
        "dataset": "Upstox read-only credential and candle verification",
        "ticker": "NIFTYBEES",
        "instrument_key": "NSE_EQ|INF204KB14I2",
        "bar_interval": "1 day; authenticated historical-candle probe",
        "first_bar": "2026-10-23",
        "last_bar": "2026-10-23",
        "bar_count": "1 bar; exact OHLCV match to saved cache",
        "file_count": "1",
        "empty_files": "0",
        "cache_paths": "work/data/api_probes/NIFTYBEES_token_visibility_check_2026-10-23.csv",
        "purpose": "Verify the configured Upstox token can access historical candles and that the fetched bar matches the local series",
        "notes": "Read-only request succeeded; the token value is not stored. The check verifies access for this process, not full-history completeness or a newer completed session.",
    },
    {
        "dataset": "Stock total-return source review",
        "ticker": "NIFTY 50 constituent stocks",
        "instrument_key": "",
        "bar_interval": "primary-source review",
        "first_bar": "2020-01-01",
        "last_bar": "2026-10-23",
        "bar_count": "646 dividend events; 7 reorganizations reviewed",
        "file_count": "1",
        "empty_files": "0",
        "cache_paths": "outputs/stock_total_return_source_review.md",
        "purpose": "Document corporate-action accounting and benchmark limitations in exploratory stock momentum research",
        "notes": "Upstox candle contract does not guarantee corporate-action adjustment; rights, successor entitlements and delayed quotes remain unresolved. Source memo is not a stock backtest or investable validation.",
    },
    {
        "dataset": "Official NIFTY 50 TR/NTR history and stock benchmark comparison",
        "ticker": "NIFTY 50 TR; NIFTY 50 NTR; restored-universe stock momentum",
        "instrument_key": "NIFTY 50 Total Return Index",
        "bar_interval": "daily",
        "first_bar": "2014-01-01",
        "last_bar": "2026-10-23",
        "bar_count": "3,170 matched dates; 20 matched-period comparison rows for 2020+",
        "file_count": "6 annual 2014–2019 raw windows + 2020–2026 raw + combined raw + 2 normalized CSVs + comparison + normalizer",
        "empty_files": "0",
        "cache_paths": "work/data/index_daily/nifty50_tri_nse_ui_2014.json;work/data/index_daily/nifty50_tri_nse_ui_2015.json;work/data/index_daily/nifty50_tri_nse_ui_2016.json;work/data/index_daily/nifty50_tri_nse_ui_2017.json;work/data/index_daily/nifty50_tri_nse_ui_2018.json;work/data/index_daily/nifty50_tri_nse_ui_2019.json;work/data/index_daily/nifty50_tri_raw_2020_2026.json;work/data/index_daily/nifty50_tri_raw_2014_2026.json;work/data/index_daily/NIFTY50TR-days-1-2014-01-01-2026-10-23.csv;work/data/index_daily/NIFTY50TR-days-1-2020-01-01-2026-10-23.csv;outputs/stock_momentum_benchmark_comparison.csv;work/normalize_nifty50_tri.py",
        "purpose": "Benchmark restored-universe stock momentum against the official NIFTY 50 total-return series over matched dates",
        "notes": "TR/NTR values were retrieved from the first-party historical-data page route, not a documented public API contract. Full 2014–2026 dates match the saved NIFTY 50 price index exactly; the preserved stock benchmark comparisons use 2020+ dates. Stock results remain exploratory because position-level rights/reorganization accounting is unresolved.",
    },
    {
        "dataset": "NIFTY 30-minute ORB opening-range filter sensitivity",
        "ticker": "NIFTY 50; NIFTYBEES",
        "instrument_key": "NSE_INDEX|Nifty 50; NSE_EQ|INF204KB14I2",
        "bar_interval": "30 minutes",
        "first_bar": "2022-01-03T09:15:00+05:30",
        "last_bar": "2026-10-23T15:15:00+05:30",
        "bar_count": "64 cases; 4 continuous paths",
        "file_count": "64 equity/trade/summary triplets + sensitivity CSV + method + runner",
        "empty_files": "0",
        "cache_paths": "outputs/intraday_orb_range_sensitivity.csv;outputs/intraday_orb_range_method.md;work/sensitivity_intraday_orb_range.py;work/backtests/intraday_orb_range_sensitivity/",
        "purpose": "Test whether a minimum opening-range width filter improves NIFTY intraday ORB net returns under realistic fee and slippage scenarios",
        "notes": "Long-only, 0.5% risk per trade, 95% exposure cap; four predeclared width thresholds and 10/25/50/100 bps per-side slippage. No continuous path was profitable; holdout history was already inspected. Slippage is not measured spread.",
    },
    {
        "dataset": "Upstox authenticated read-only candle probe",
        "ticker": "NIFTY 50",
        "instrument_key": "NSE_INDEX|Nifty 50",
        "bar_interval": "30 minutes",
        "first_bar": "2026-10-23T09:15:00+05:30",
        "last_bar": "2026-10-23T15:15:00+05:30",
        "bar_count": "13 returned; 13 matched cache",
        "file_count": "1 metadata JSON",
        "empty_files": "0",
        "cache_paths": "work/data/api_probes/upstox_auth_probe_2026-10-27.json",
        "purpose": "Verify the configured Upstox Analytics credential with one read-only historical-candle request and compare against cached data",
        "notes": "All 13 timestamped OHLCV bars matched exactly; token value was not saved and no orders were placed.",
    },
    {
        "dataset": "NIFTY/Gold ETF stationary-bootstrap drawdown stress",
        "ticker": "NIFTYBEES; GOLDBEES",
        "instrument_key": "NSE_EQ|INF204KB14I2; NSE_EQ|INF204KB17I5",
        "bar_interval": "daily net NAV returns",
        "first_bar": "2014-01-02",
        "last_bar": "2026-10-23",
        "bar_count": "5,000 bootstrap paths per scenario; 192 horizon/cost/block-length summaries",
        "file_count": "16 corrected source equity paths + runner + output CSV + method note",
        "empty_files": "0",
        "cache_paths": "outputs/etf_drawdown_bootstrap.csv;outputs/etf_drawdown_bootstrap_method.md;work/bootstrap_etf_drawdown_risk.py;work/backtests/volatility_weighted_blend/fixed_50_50_quarterly__full_2014_plus__50bps/equity.csv;work/backtests/intraday_ohlc_exposure/gross_cap_45pct__50bps/equity.csv;work/backtests/intraday_ohlc_exposure/gross_cap_70pct__50bps/equity.csv;work/backtests/cost_stress_sensitivity/solo65_vol16__full_2014_plus__50bps/equity.csv;work/backtests/cost_stress_sensitivity/solo80_vol16__full_2014_plus__50bps/equity.csv;work/backtests/cost_stress_sensitivity/solo65_vol16__full_2014_plus__100bps/equity.csv;work/backtests/cost_stress_sensitivity/solo80_vol16__full_2014_plus__100bps/equity.csv;work/backtests/volatility_weighted_blend/inverse_vol_63d_quarterly__full_2014_plus__50bps/equity.csv;work/backtests/nifty_gold_full_history_benchmarks/passive_NIFTY_Gold_22_5pct_each/equity.csv;work/backtests/passive_mix_exposure/continuous_2015_plus/passive_equal_045_continuous_2015_plus/equity.csv;work/backtests/passive_mix_exposure/continuous_2015_plus/passive_equal_050_continuous_2015_plus/equity.csv;work/backtests/passive_mix_exposure/continuous_2015_plus/passive_equal_055_continuous_2015_plus/equity.csv;work/backtests/passive_mix_exposure/continuous_2015_plus/passive_equal_060_continuous_2015_plus/equity.csv;work/backtests/passive_drawdown_control/dd_8pct_cut_60_to_30_recover_4pct__50bps/equity.csv;work/backtests/passive_drawdown_control/dd_10pct_cut_60_to_30_recover_5pct__50bps/equity.csv;work/backtests/passive_drawdown_control/dd_12pct_cut_60_to_30_recover_6pct__50bps/equity.csv",
        "purpose": "Stress maximum drawdown and terminal-return distributions for leading NIFTY/Gold ETF rules by resampling historical net return blocks",
        "notes": "ETF-unit STT-corrected source paths were regenerated after session-date normalization. Passive NIFTY/Gold mix 10-year 20% breach frequency is 1.62–3.40% across block lengths (2.40% at 63 sessions); passive mix OHLC bound is -17.36% but exposure drifts from 45% initial. Common 2015+ 45/50/55/60% initial exposure variants have 63-session breach estimates of 3.58/4.90/7.28/10.00%, while historical OHLC bounds are -17.37/-18.04/-18.63/-19.23%. Drawdown-triggered 60-to-30% paths at 8/10/12% triggers have 63-session 10-year breach estimates 1.46/1.96/6.70%, fifth-percentile drawdowns -17.36/-17.83/-20.83%, and historical OHLC bounds -16.83/-16.83/-17.97%. At 50 bps, other 10-year frequencies: fixed 100% gross 7.82–10.66%, inverse-vol 50/50 7.58–10.66%, fixed 45% cap 3.12–3.86%, fixed 70% cap 5.80–7.92%, 65%/16% throttle 20.32–25.66%, 80%/16% throttle 34.94–43.60%. At 100 bps, throttle cases were 51.12–68.16% and 71.30–86.64%. Inverse-vol OHLC bound is -25.55%. Conditional historical-return resampling, not a forecast or strategy re-simulation.",
    },
    {
        "dataset": "Upstox daily session timestamp integrity audit",
        "ticker": "NIFTYBEES; GOLDBEES; sector ETFs; India VIX; other daily caches",
        "instrument_key": "Exact keys in daily cache filenames and source manifest",
        "bar_interval": "daily candle session-date normalization",
        "first_bar": "2014-01-01",
        "last_bar": "2026-10-23",
        "bar_count": "95 days-1 CSV paths; 94 OHLC files; 11 non-midnight duplicate-session paths",
        "file_count": "session-date loader change + OHLC audit + corrected NIFTY/Gold runs",
        "empty_files": "0",
        "cache_paths": "outputs/etf_daily_timestamp_and_intraday_risk_audit.md;work/upstox_quant.py;work/audit_etf_intraday_drawdown.py;outputs/etf_intraday_drawdown_audit.csv",
        "purpose": "Prevent exact-timestamp joins from treating daily bars stamped at different times as separate trading sessions",
        "notes": "Same-day identical ETF OHLCV duplicates are collapsed after date normalization. The listed NIFTY/Gold, sector, composite, parameter, RSI, momentum, and VIX overlay screens have been regenerated. The raw VIX source conflicts are resolved in a separate NSE-reconciled input without modifying the Upstox source cache.",
    },
    {
        "dataset": "NIFTY/Gold daily OHLC-envelope exposure sensitivity",
        "ticker": "NIFTYBEES; GOLDBEES",
        "instrument_key": "NSE_EQ|INF204KB14I2; NSE_EQ|INF204KB17I5",
        "bar_interval": "daily OHLC stress envelope; 50 bps per-side slippage",
        "first_bar": "2014-01-01",
        "last_bar": "2026-10-23",
        "bar_count": "20 gross exposure caps; 10 order-ledger OHLC audits, including two chronological 95% holdout paths",
        "file_count": "20 exposure order/equity pairs + 10 OHLC-audited ledgers + 2 holdout replay pairs + method and runners",
        "empty_files": "0",
        "cache_paths": "outputs/intraday_ohlc_exposure_sensitivity.csv;outputs/etf_intraday_drawdown_audit.csv;outputs/etf_daily_timestamp_and_intraday_risk_audit.md;outputs/etf_parameter_sensitivity_method.md;outputs/single_sleeve_deployment_method.md;work/sensitivity_intraday_ohlc_exposure.py;work/audit_etf_intraday_drawdown.py;work/replay_donchian_gold_blend.py;work/backtests/donchian_gold_clean/holdout_2020_plus_95cap_50bps/;work/backtests/donchian_gold_clean/holdout_recent_95cap_50bps/;work/backtests/intraday_ohlc_exposure/;work/backtests/etf_parameter_sensitivity/;work/backtests/single_sleeve_deployment/",
        "purpose": "Screen NIFTY/Gold exposure and replay selected candidate orders against a conservative same-day high-before-low OHLC drawdown envelope",
        "notes": "After the ETF-unit STT correction, 74% was the highest tested gross cap within -20%, but had only 0.009 pp headroom; 70% left 0.935 pp and returned +107.75%; 45% left 3.849 pp and returned +77.77%. The 100% quarterly inverse-vol candidate returned +139.85% but its OHLC envelope was -25.55%. The 50% and 55% quarterly solo-sleeve cases returned +139.85% and +150.94%, but both OHLC bounds were about -25.55%, so they fail. The post-hoc 55/30 and 40/20 channel challengers returned +155.50% and +154.61%, but both OHLC bounds were -25.53%. At 50 bps, the selected 95% NIFTY/Gold monthly blend passed the 2023+ holdout at -16.28% (3.72 pp headroom) but failed the 2020+ fold at -24.41%, troughing 2020-09-04. Both holdouts were previously inspected; the 2023+ path is already in paper revision 7. OHLC envelope assumes highs precede lows and is not a future loss guarantee.",
    },
    {
        "dataset": "NIFTYBEES RSI(4) pullback swing screen",
        "ticker": "NIFTYBEES",
        "instrument_key": "NSE_EQ|INF204KB14I2",
        "bar_interval": "daily",
        "first_bar": "2014-01-01T00:00:00+05:30",
        "last_bar": "2026-10-23T00:00:00+05:30",
        "bar_count": "3,167 daily bars; 108 backtest scenarios",
        "file_count": "96 RSI scenarios + 12 control scenarios; per-run equity/orders/summary + method + runner",
        "empty_files": "0",
        "cache_paths": "work/data/etf_daily/NSE_EQ_INF204KB14I2-days-1-2014-01-01-2026-10-23.csv;outputs/niftybees_rsi25_sensitivity.csv;outputs/niftybees_rsi25_method.md;work/backtest_niftybees_rsi25.py;work/backtests/niftybees_rsi25/",
        "purpose": "Test a published RSI(4) oversold pullback swing rule on NIFTYBEES with current fees, next-open execution, and chronological periods",
        "notes": "All continuous RSI variants lost at 10–100 bps and breached 20% drawdown; 2023+ results were negative at 50 bps. Candidate ₹0.70/₹0.80 dividend units are inferred and no tested RSI path held shares on those ex-dates. Rejected on current evidence.",
    },
    {
        "dataset": "NIFTY intraday opening-gap fade sensitivity",
        "ticker": "NIFTY 50; NIFTYBEES",
        "instrument_key": "NSE_INDEX|Nifty 50; NSE_EQ|INF204KB14I2",
        "bar_interval": "30 minutes",
        "first_bar": "2022-01-03T09:15:00+05:30",
        "last_bar": "2026-10-23T15:15:00+05:30",
        "bar_count": "1,181 complete aligned sessions; 144 cases",
        "file_count": "144 equity/trade/summary triplets + sensitivity CSV + method + runner",
        "empty_files": "0",
        "cache_paths": "outputs/intraday_gap_fade_sensitivity.csv;outputs/intraday_gap_fade_method.md;work/backtest_intraday_gap_fade.py;work/backtests/intraday_gap_fade/",
        "purpose": "Test first-30-minute opening-gap reversal signals on NIFTY 50 with same-day NIFTYBEES execution, fees, stops, targets, and slippage stress",
        "notes": "Long, short, and combined modes; 0.30/0.50/0.75% gap thresholds; 10/25/50/100 bps adverse slippage per side; 0.5% stop risk and 100% gross cap. All 36 continuous cases lost money. Eleven special/misaligned sessions excluded from signal generation; stop-first OHLC assumption; not a validated strategy.",
    },
    {
        "dataset": "Indian sector ETF rotation sensitivity",
        "ticker": "BANKBEES; ITBEES; AUTOBEES; PHARMABEES; PSUBNKBEES; NIFTYBEES; GOLDBEES",
        "instrument_key": "NSE_EQ|INF204KB15I9; NSE_EQ|INF204KB15V2; NSE_EQ|INF204KC1337; NSE_EQ|INF204KC1089; NSE_EQ|INF204KB16I7; NSE_EQ|INF204KB14I2; NSE_EQ|INF204KB17I5",
        "bar_interval": "daily; month-end signals / next-open execution",
        "first_bar": "2022-01-03",
        "last_bar": "2026-10-23",
        "bar_count": "1,176 common five-sector sessions; 384 scenarios + 96 OHLC audits",
        "file_count": "384 equity/order/summary triplets + sensitivity + training selection + method + source memo + runner + OHLC audit",
        "empty_files": "0",
        "cache_paths": "outputs/sector_rotation_sensitivity.csv;outputs/sector_rotation_training_selection.json;outputs/sector_rotation_method.md;outputs/sector_rotation_primary_sources.md;outputs/sector_rotation_ohlc_audit.csv;work/sensitivity_sector_rotation.py;work/audit_sector_rotation_ohlc.py;work/backtests/sector_rotation/",
        "purpose": "Compare monthly 12–1 sector momentum, equal-weight sector exposure, a NIFTY/sector/Gold mix, and the frozen NIFTY/Gold control under fees, slippage, and the 20% historical drawdown screen",
        "notes": "Five current sector ETFs; unequal inceptions and survivor bias. At 50 bps the 25/50/25 NIFTY/sector/Gold mix returned +72.92% / -12.51% close drawdown in 2022–2026, versus +64.18% / -14.22% for NIFTY/Gold; in 2025+ it returned +17.05% versus +32.24%. Price-signal top-3 at 75% returned +41.16% continuously with -19.67% conservative OHLC bound; price-only ETF P&L and incomplete distributions prevent a total-return or winner claim.",
    },
    {
        "dataset": "Official NSE sector gross TRI signal history",
        "ticker": "Nifty Bank; Nifty IT; Nifty Auto; Nifty Pharma; Nifty PSU Bank",
        "instrument_key": "NSE Indices historical-data report page-backed route; not a documented public API",
        "bar_interval": "daily total returns index values",
        "first_bar": "2014-01-01",
        "last_bar": "2026-10-23",
        "bar_count": "5 indexes × 3,170 rows; 65 one-year-or-shorter queries",
        "file_count": "raw JSON capture + capture script + signal comparison method",
        "empty_files": "0",
        "cache_paths": "work/data/index_daily/sector_tri_raw_2014_2026.json;work/capture_sector_tri_signal_history.py;outputs/sector_tri_signal_momentum_method.md",
        "purpose": "Supply pre-2022 warm-up for official gross TRI momentum and 200-session trend signals on actual sector ETF launch dates",
        "notes": "All five official TRI series cover 3,170 daily dates. Four NSE special sessions in 2015–2018 have no corresponding saved ETF panel date and are omitted when aligned to the execution panel. Historical-data page route observed in first-party JavaScript; no stable API contract or NTR claim is made.",
    },
    {
        "dataset": "Sector ETF rotation with official TRI signals",
        "ticker": "BANKBEES; ITBEES; AUTOBEES; PHARMABEES; PSUBNKBEES",
        "instrument_key": "NSE_EQ|INF204KB15I9; NSE_EQ|INF204KB15V2; NSE_EQ|INF204KC1337; NSE_EQ|INF204KC1089; NSE_EQ|INF204KB16I7",
        "bar_interval": "daily; month-end TRI signals / next-open ETF fills; 10/50/100 bps",
        "first_bar": "2022-01-03",
        "last_bar": "2026-10-23",
        "bar_count": "144 sensitivity cases; 48 order-ledger OHLC audits at 50 bps",
        "file_count": "144 equity/order/summary triplets + sensitivity + selection + method + OHLC audit + runner",
        "empty_files": "0",
        "cache_paths": "outputs/sector_tri_signal_momentum_sensitivity.csv;outputs/sector_tri_signal_momentum_selection.json;outputs/sector_tri_signal_momentum_method.md;outputs/sector_tri_signal_momentum_ohlc_audit.csv;work/sensitivity_sector_tri_signal.py;work/backtests/sector_tri_signal_momentum/",
        "purpose": "Compare official gross TRI 12–1 momentum and 200-session trend signals with actual ETF prices for fills, NAV, modeled fees, slippage, and conservative daily OHLC drawdown bounds",
        "notes": "The training-only 50-bps/OHLC selector chose TRI top-2 at 75%: +42.37% training / -17.22% OHLC, then -15.49% in 2025+ and -22.86% OHLC continuously, so it fails the 20% full-period screen. The highest full-period tested TRI return that passed OHLC was top-3 at 75% (+45.96%, -19.90% bound), with negligible headroom; all returns omit ETF distributions and all periods were previously inspected.",
    },
    {
        "dataset": "Indian sector ETF rotation primary-source memo",
        "ticker": "BANKBEES; ITBEES; AUTOBEES; PHARMABEES; PSUBNKBEES",
        "instrument_key": "ISIN mappings in source memo and ETF candle rows",
        "bar_interval": "source review",
        "first_bar": "2004-05-27",
        "last_bar": "2026-10-27",
        "bar_count": "5 ETFs; official sources and coverage limits",
        "file_count": "1 Markdown memo",
        "empty_files": "0",
        "cache_paths": "outputs/sector_rotation_primary_sources.md",
        "purpose": "Record official NIFTY TRI, ETF launch, instrument, fee, Upstox API, and corporate-action sources for sector research",
        "notes": "Confirms BANKBEES ₹11/₹13 cash actions and distinguishes them from NIFTYBEES ₹7/₹8. Official sector PR/TR and AMFI NAV comparisons are saved; direct AMFI scheme-event queries returned empty records, which do not prove complete event coverage.",
    },
    {
        "dataset": "Official NSE sector PR/TR and ETF market-price reconciliation",
        "ticker": "BANKBEES; ITBEES; AUTOBEES; PHARMABEES; PSUBNKBEES; Nifty Bank; Nifty IT; Nifty Auto; Nifty Pharma; Nifty PSU Bank",
        "instrument_key": "NSE Indices historical-data report page-backed routes; matching Upstox ETF keys in ETF cache",
        "bar_interval": "daily",
        "first_bar": "2022-01-25",
        "last_bar": "2026-10-23",
        "bar_count": "5 indices × 1,176 matched dates; 20 return-period comparisons",
        "file_count": "2 raw JSON captures + aligned panel + comparison CSV + normalizer",
        "empty_files": "0",
        "cache_paths": "work/data/index_daily/sector_price_index_raw_2022_2026.json;work/data/index_daily/sector_tri_raw_2022_2026.json;work/data/index_daily/sector_etf_price_pr_tri_panel_2022_2026.csv;outputs/sector_etf_index_total_return_comparison.csv;work/normalize_sector_index_history.py",
        "purpose": "Compare official Nifty sector price-index and gross TRI histories with matching Upstox sector ETF closes on identical dates",
        "notes": "All five price-index and TRI histories exactly match ETF dates. NTR is unavailable ('-' for all rows). ETF close return trails gross TRI by 1.61–7.79 pp over the common period; this does not reconstruct ETF cash distributions. The first-party report's page-backed POST routes are observed but are not a documented API contract.",
    },
    {
        "dataset": "Official AMFI sector ETF NAV and index comparison",
        "ticker": "BANKBEES; ITBEES; AUTOBEES; PHARMABEES; PSUBNKBEES",
        "instrument_key": "AMFI Nippon scheme NAV joined by ISIN to Upstox ETF candles and NSE Indices sector PR/TR",
        "bar_interval": "daily; up to 90 days per AMFI report request",
        "first_bar": "2023-04-03",
        "last_bar": "2026-10-23",
        "bar_count": "4,400 AMFI NAV rows; 877 exact ETF/NAV/index matches per fund",
        "file_count": "15 report windows + raw selected NAV JSON + aligned panel + 20 period comparisons + capture script",
        "empty_files": "0",
        "cache_paths": "work/data/api_probes/amfi_sector_etf_nav_2023_2026.json;work/data/index_daily/sector_etf_nav_price_tri_panel_2023_2026.csv;outputs/sector_etf_nav_price_tri_comparison.csv;work/capture_amfi_sector_etf_nav.py",
        "purpose": "Cross-check official Nippon ETF NAV with market-price closes and sector PR/TR on exact shared dates",
        "notes": "AMFI history requests before 2023-04-01 redirected to the landing page. Five ETF market sessions lack NAV; three NAV-only quarter ends have no matching market bar. Comparison uses matched dates without interpolation and does not constitute a cash-distribution-adjusted strategy backtest.",
    },
    {
        "dataset": "Official AMFI sector ETF scheme-dividend query audit",
        "ticker": "BANKBEES; ITBEES; AUTOBEES; PHARMABEES; PSUBNKBEES",
        "instrument_key": "Nippon AMFI MF_ID=21; selected scheme IDs in raw mapping",
        "bar_interval": "five scheme-year queries per ETF; 2022–2026",
        "first_bar": "2022",
        "last_bar": "2026",
        "bar_count": "25 HTTP 200 responses; all data arrays empty",
        "file_count": "25 query records + scheme-ID mapping + corporate-action audit + primary-source update",
        "empty_files": "0",
        "cache_paths": "work/data/api_probes/amfi_sector_etf_scheme_dividends_2022_2026.json;work/data/api_probes/amfi_nippon_sector_scheme_ids.json;outputs/sector_etf_corporate_action_audit.csv;outputs/sector_rotation_primary_sources.md;work/research/sector_distribution_primary_source_update_2026-10-27.md",
        "purpose": "Check AMFI's selected scheme-dividend records for five sector ETFs and assess disputed third-party distribution claims",
        "notes": "Empty first-party responses do not prove that no distributions occurred. AUTOBEES ₹10.50 (ex 2026-06-09) and PHARMABEES ₹6.50 (ex 2026-06-11) secondary claims lack matching primary event notices and remain outside the base strategy P&L.",
    },
    {
        "dataset": "Sector ETF distribution primary-source update",
        "ticker": "AUTOBEES; PHARMABEES",
        "instrument_key": "NSE ISIN INF204KC1337; INF204KC1089",
        "bar_interval": "cash-distribution event-source review",
        "first_bar": "2026-06-09",
        "last_bar": "2026-06-11",
        "bar_count": "2 secondary event claims reviewed; 0 matched primary notices found",
        "file_count": "1 source memo; AMFI/Upstox probes cross-referenced",
        "empty_files": "0",
        "cache_paths": "work/research/sector_distribution_primary_source_update_2026-10-27.md;work/data/api_probes/amfi_sector_etf_scheme_dividends_2022_2026.json;work/data/api_probes/sector_etf_corporate_actions_2026-10-26.json",
        "purpose": "Document the exact 2026 cash-event claims and first-party source-verification limits before use in ETF return accounting",
        "notes": "The ₹10.50 AUTOBEES and ₹6.50 PHARMABEES claims are not verified; empty AMFI/Upstox responses and a BSE retrieval failure do not prove that the events did not occur. Keep the base ledger unadjusted and label any credited cash as secondary-source-only.",
    },
    {
        "dataset": "Sector ETF secondary-claim cash-flow sensitivity",
        "ticker": "BANKBEES; ITBEES; AUTOBEES; PHARMABEES; PSUBNKBEES",
        "instrument_key": "NSE_EQ sector ETFs; see data manifest and source memo",
        "bar_interval": "daily close NAV; monthly signals / next-open fills; 50 bps per-side slippage",
        "first_bar": "2022-01-03",
        "last_bar": "2026-10-23",
        "bar_count": "144 conditional cases; all have order-ledger OHLC replays",
        "file_count": "144 equity/order/summary triplets + sensitivity + method + runner",
        "empty_files": "0",
        "cache_paths": "outputs/sector_distribution_cashflow_sensitivity.csv;outputs/sector_distribution_cashflow_method.md;work/sensitivity_sector_distribution_cashflow.py;work/backtests/sector_distribution_cashflow_sensitivity/",
        "purpose": "Measure the return and OHLC risk sensitivity to disputed AUTOBEES and PHARMABEES cash-payment claims, using prior-close holdings and separate/combined inclusion cases",
        "notes": "Secondary-source-only, not accepted event cash flows. No tested path held AUTOBEES at its claimed ex-date; all effect came from the unverified PHARMABEES ₹6.50 claim. Conditional PHARMABEES credits ranged from ₹1.2–4.6 lakh; the training-selected official-TRI top-2/75% path still failed the continuous 20% OHLC screen.",
    },
    {
        "dataset": "NIFTY/Gold expanding-window annual walk-forward",
        "ticker": "NIFTYBEES; GOLDBEES",
        "instrument_key": "NSE_EQ|INF204KB14I2; NSE_EQ|INF204KB17I5",
        "bar_interval": "daily; close signals / next-open fills; 50 bps per-side slippage",
        "first_bar": "2014-01-01",
        "last_bar": "2026-10-23",
        "bar_count": "7 annual pseudo-OOS folds; 14 selected/control replays",
        "file_count": "49 training screens + 14 test replays; 126 equity/order files + CSV + method + runner",
        "empty_files": "0",
        "cache_paths": "outputs/nifty_gold_walk_forward.csv;outputs/nifty_gold_walk_forward_method.md;work/walk_forward_nifty_gold.py;work/backtests/nifty_gold_walk_forward/",
        "purpose": "Select among seven predeclared NIFTY/Gold trend parameterizations using expanding historical training windows and test each selection on the next calendar year",
        "notes": "Every training candidate passed the 20% close/OHLC screen at 45% gross cap. With actual capital and all-time peaks carried forward, the selected sequence returned +54.89% versus +62.56% for fixed D55/20; the full-sequence OHLC bounds were -14.86% for both. The 45% cap was selected from an earlier full-history sweep, and all periods were inspected. ETF distributions, tax, cash yield, and live market impact remain incomplete.",
    },
    {
        "dataset": "NIFTY/Gold passive and active benchmark comparison",
        "ticker": "NIFTYBEES; GOLDBEES",
        "instrument_key": "NSE_EQ|INF204KB14I2; NSE_EQ|INF204KB17I5",
        "bar_interval": "daily; 2020+, full available history, and common 2015+ window",
        "first_bar": "2014-01-01",
        "last_bar": "2026-10-23",
        "bar_count": "3 benchmark windows; 17 benchmark paths + 30 passive exposure cases",
        "file_count": "47 equity/order pairs + 4 result CSVs + 3 method notes + 2 runners",
        "empty_files": "0",
        "cache_paths": "outputs/nifty_gold_2020_benchmarks.csv;outputs/nifty_gold_full_history_benchmarks.csv;outputs/nifty_gold_common_history_benchmarks.csv;outputs/passive_mix_exposure_sensitivity.csv;outputs/nifty_gold_2020_benchmarks_method.md;outputs/nifty_gold_history_benchmarks_method.md;outputs/passive_mix_exposure_method.md;work/benchmark_nifty_gold_2020.py;work/sensitivity_passive_mix_exposure.py;work/backtests/nifty_gold_2020_benchmarks/;work/backtests/nifty_gold_full_history_benchmarks/;work/backtests/nifty_gold_common_history_benchmarks/;work/backtests/passive_mix_exposure/;outputs/nifty_gold_walk_forward.csv;work/research/etf_total_return_source_audit.md",
        "purpose": "Compare passive NIFTY/Gold allocations, quarterly static mix, quarterly trend, and annual selector/control across 2020+, full available history, and common 2015+ dates",
        "notes": "The 2014-2026 initial 22.5%/22.5% passive mix returned +145.62% with -17.36% OHLC bound, but exposure drifted from 45% to about 76% final and 79.45% peak. On the common 2015-2026 exposure grid, 60% initial exposure was the highest 5-point cap that passed historical OHLC (+172.02%, -19.23%); 65% failed at -20.37%. A training-only selector chose 100%, then failed the full path at -26.69%. The passive 45/50/55/60% 10-year bootstrap breach estimates at 63-session blocks were 3.58/4.90/7.28/10.00%. The quarterly static 50/50 mix at a 45% cap returned +103.18% with -12.91% bound; quarterly D55/20 returned +77.77% with -16.15% bound. GoldBeES candles start in 2015; Gold distribution history is incomplete. Known NIFTYBEES payouts were credited using the inferred post-split unit conversion. All results use price-based ETF candles, prior-inspected dates, current modeled fees, 50 bps per-side slippage, zero cash yield, and terminal liquidation. Historical OHLC and bootstrap screens are not future loss guarantees.",
    },
    {
        "dataset": "Passive NIFTY/Gold drawdown-trigger control sensitivity",
        "ticker": "NIFTYBEES; GOLDBEES",
        "instrument_key": "NSE_EQ|INF204KB14I2; NSE_EQ|INF204KB17I5",
        "bar_interval": "daily close drawdown signal; next-open trades; 10/50/100 bps per-side slippage",
        "first_bar": "2015-01-02",
        "last_bar": "2026-10-23",
        "bar_count": "15 strategy/cost cases; three trigger levels and two fixed controls at 10/50/100 bps",
        "file_count": "15 equity/order pairs + sensitivity CSV + method + runner + 3 bootstrap sources",
        "empty_files": "0",
        "cache_paths": "outputs/passive_drawdown_control_sensitivity.csv;outputs/passive_drawdown_control_method.md;work/backtest_passive_mix_drawdown_control.py;work/backtests/passive_drawdown_control/;outputs/etf_drawdown_bootstrap.csv;work/bootstrap_etf_drawdown_risk.py",
        "purpose": "Test a pre-declared high-water drawdown throttle on a passive NIFTY/Gold portfolio with a next-open response and compare it with fixed 45% and 60% exposure",
        "notes": "All three 60%-to-30% throttle cases passed the historical daily OHLC screen at 10/50/100 bps. At 50 bps, net returns were +138.78%, +141.16%, and +133.01% for 8/10/12% triggers, with OHLC bounds -16.83%, -16.83%, and -17.97%; at 10 bps returns were +140.47%, +143.31%, and +135.68%. 8/10/12% trigger bootstrap 63-session 10-year breach estimates are 1.46/1.96/6.70%, but the bootstrap does not resimulate the path-dependent trigger. All dates were previously inspected; the full frontier is frozen for paper-only prospective observation and no live orders were placed.",
    },
    {
        "dataset": "NIFTY/Gold quarterly static-mix exposure selection",
        "ticker": "NIFTYBEES; GOLDBEES",
        "instrument_key": "NSE_EQ|INF204KB14I2; NSE_EQ|INF204KB17I5",
        "bar_interval": "daily; quarter-end signal / next-session-open fills; 50 bps per-side slippage",
        "first_bar": "2015-01-02",
        "last_bar": "2026-10-23",
        "bar_count": "19 training caps + 19 test-period sensitivity cases",
        "file_count": "38 equity/order pairs + 2 CSVs + selection JSON + method + runner",
        "empty_files": "0",
        "cache_paths": "outputs/static_mix_exposure_training.csv;outputs/static_mix_exposure_oos_test.csv;outputs/static_mix_training_selection.json;outputs/static_mix_exposure_method.md;outputs/static_mix_exposure_methodology_review.md;work/select_static_mix_exposure.py;work/backtests/static_mix_exposure_training/;work/backtests/static_mix_exposure_test/",
        "purpose": "Select a quarterly static NIFTY/Gold exposure cap using 2015-2019 and replay the frozen choice on 2020-2026, with the later cap grid retained as a post-hoc diagnostic",
        "notes": "The 2015-2019 training rule selected 100% cap (+45.98%, -18.62% OHLC bound), but the frozen 2020-2026 replay returned +169.22% and failed the 20% bound at -26.02%. The 45% control returned +58.82% / -12.91% and passed. A post-hoc test-period grid found 70% was the highest 5-point cap passing at +102.80% / -19.06%; 65% returned +93.26% / -17.88%. All dates have been inspected; no prospective validation or future drawdown guarantee. Gold distributions remain incomplete; fees are modeled, cash yield is zero, and targets can drift between quarterly rebalances.",
    },
    {
        "dataset": "ETF total-return and dividend-source audit",
        "ticker": "NIFTYBEES; GOLDBEES; NIFTY 50 TRI",
        "instrument_key": "NSE_EQ|INF204KB14I2; NSE_EQ|INF204KB17I5; NIFTY 50 TRI",
        "bar_interval": "official source and coverage review",
        "first_bar": "2014-01-01",
        "last_bar": "2026-10-27",
        "bar_count": "source coverage and corporate-action evidence review",
        "file_count": "1 Markdown memo",
        "empty_files": "0",
        "cache_paths": "work/research/etf_total_return_source_audit.md",
        "purpose": "Document primary-source coverage, NIFTYBEES distributions/split, GoldBeES corporate-action limits, AMFI NAV extraction, and official NIFTY TRI availability",
        "notes": "NSE TRI reinvests index constituent dividends; that index is not an ETF cash-flow reconstruction. AMFI requests are limited to 90-day windows. Upstox candles provide OHLC but do not guarantee dividend-adjusted returns. The GoldBeES event list's lack of cash rows is not proof of complete event history.",
    },
    {
        "dataset": "NIFTY/Gold active-sleeve allocation-ratio sensitivity",
        "ticker": "NIFTYBEES; GOLDBEES",
        "instrument_key": "NSE_EQ|INF204KB14I2; NSE_EQ|INF204KB17I5",
        "bar_interval": "daily; close signals / next-open fills; monthly or quarterly; 50 bps per-side slippage",
        "first_bar": "2015-01-02",
        "last_bar": "2026-10-23",
        "bar_count": "198 rules × 5 windows = 990; 198 training and 8 frozen/reference OOS OHLC audits; 18 cost cases",
        "file_count": "198 training equity/order/summary triplets + 8 OOS triplets + 4 CSVs + selection JSON + method + results note + runner",
        "empty_files": "0",
        "cache_paths": "outputs/nifty_gold_allocation_ratio_sensitivity.csv;outputs/nifty_gold_allocation_ratio_training_ohlc.csv;outputs/nifty_gold_allocation_ratio_oos_ohlc.csv;outputs/nifty_gold_allocation_ratio_cost_sensitivity.csv;outputs/nifty_gold_allocation_ratio_selection.json;outputs/nifty_gold_allocation_ratio_method.md;outputs/nifty_gold_allocation_ratio_results.md;work/sensitivity_nifty_gold_allocation_ratio.py;work/backtests/nifty_gold_allocation_ratio/",
        "purpose": "Select NIFTY versus Gold active-sleeve weights, rebalance frequency, and exposure cap on 2015–2019, then measure the frozen rule against a fixed 50/50 reference",
        "notes": "All 198 2015–2019 training returns were negative. The least-negative OHLC-passing rule was quarterly NIFTY-only at a 30% cap (-0.60% training), but it returned +23.41% in 2020+ versus +77.52% for the 50/50 monthly 45% reference. Both passed the historical 50-bps OHLC screen. Results are post-hoc price-based ETF evidence; Gold distributions, cash yield, tax, and market impact are unresolved. Not a strategy recommendation or future drawdown guarantee.",
    },
):
    matches = [row for row in manifest if row["dataset"] == metadata["dataset"]]
    if matches:
        matches[0].update(metadata)
    else:
        manifest.append(metadata)
write_csv(MANIFEST, manifest, list(manifest[0]))
print(f"refreshed_rows={updated} ledger={LEDGER}")
