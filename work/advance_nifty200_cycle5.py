"""Advance the four frozen NIFTY 200 cash paths with resumable account cases."""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "work"))
import advance_nifty200_cash_prefixes as advance
import audit_strategy_dependencies as audit

PROTOCOL = "NIFTY200-v1.10-dated-eligibility-multichild-demergers-and-debenture-bound"
CYCLE = "2026-11-03-cycle5"
TAG = "cycle5_cesc_2026-11-03"
CHECKPOINT = ROOT / "outputs" / f"nifty200_{TAG}_checkpoint.json"
DETAIL = advance.DETAIL / f"sequential_cash_prefixes_{TAG}"
CAPITAL = 1_000_000.0


def self_check() -> None:
    assert advance.CONFIGURATIONS == ("NIFTY200-A-M", "NIFTY200-A-Q", "NIFTY200-B-M", "NIFTY200-B-Q")
    assert CAPITAL == advance.CAPITAL and PROTOCOL.startswith("NIFTY200-v1.10-")
    assert {10, 50, 100, 200} == {int(value) for value in (10.0, 50.0, 100.0, 200.0)}
    gruh = compact_blocker({"date": "2019-10-16", "symbol": "INE580B01029",
                            "input": "locked_bonus_raw_close", "reason": "missing close"})
    assert gruh["identity"] == "GRUH Finance" and gruh["date"] == "2019-10-16"
    cesc = compact_blocker({"date": "2019-09-30", "unresolved": [{
        "symbol": "CESC", "method": "B_source_total_return_numerator_volatility_unknown_prelisting_child_marks",
        "score_status": "UNKNOWN_DATA", "selection_bound": "MATERIAL_UNKNOWN",
        "score_upper_bound": 2.18, "unmatched_dependency_keys": [{"date": "2018-10-30", "entity": "CESC",
            "input": "signal_demerger", "source": "issuer and exchange filings", "reason": "child claim volatility unknown",
            "resolution_attempt": "minimum volatility bound"}]}]})
    assert cesc["unresolved"][0]["dependencies"][0]["resolution_attempt"] == "minimum volatility bound"
    assert "unmatched_dependency_keys" not in cesc["unresolved"][0]


def compact_blocker(blocker: dict | None) -> dict | None:
    if not blocker:
        return None
    summary = {key: blocker[key] for key in ("date", "kind", "input", "reason", "event", "entity", "symbol")
               if key in blocker}
    if summary.get("symbol") == "INE580B01029":
        summary["identity"] = "GRUH Finance"
    if "unresolved" in blocker:
        rows = []
        for item in blocker["unresolved"]:
            row = {key: item[key] for key in ("symbol", "method", "score_status", "reason", "selection_bound",
                                               "return_numerator", "annualized_volatility_lower_bound",
                                               "score_upper_bound", "bound_method") if key in item}
            if item.get("source_demerger"):
                event = item["source_demerger"]
                row["source_demerger"] = {key: event[key] for key in
                    ("ex_date", "record_date", "allotment_date", "listing_date", "children") if key in event}
            if item.get("unmatched_dependency_keys"):
                row["dependencies"] = [{key: dependency[key] for key in
                    ("date", "entity", "input", "source", "reason", "resolution_attempt", "impact") if key in dependency}
                    for dependency in item["unmatched_dependency_keys"]]
            rows.append(row)
        summary["unresolved"] = rows
    return summary


def save_checkpoint(stage: str, certificates: dict, signal_blockers: dict,
                    accounts: dict, common_end: str | None) -> None:
    payload = {"cycle_id": CYCLE, "protocol_id": PROTOCOL, "stage": stage,
               "common_supported_end": common_end, "signal_blockers": signal_blockers,
               "certified_signal_counts": {name: len(rows) for name, rows in certificates.items()},
               "accounts": accounts}
    temporary = CHECKPOINT.with_suffix(".tmp")
    temporary.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    temporary.replace(CHECKPOINT)


def prepare() -> tuple:
    sessions, data, actions, signals, index, series, child, dependencies, cache_manifest = advance.setup()
    for symbol, date_text in advance.RIGHTS:
        identity = actions["resolved_symbol"].eq(symbol) | actions["symbol"].eq(symbol)
        if not identity.where(actions["ex_date"].eq(pd.Timestamp(date_text)), False).any():
            raise ValueError(f"registered rights source event missing for {symbol} {date_text}")
    for (symbol, date_text), amount in advance.DIVIDENDS.items():
        rows = actions.loc[actions["symbol"].eq(symbol) & actions["ex_date"].eq(pd.Timestamp(date_text))]
        if rows.empty or not pd.to_numeric(rows["cash_amount"], errors="coerce").eq(amount).any():
            raise ValueError(f"registered dividend source event/amount missing for {symbol} {date_text}")

    certificates, signal_blockers, correction_log = {}, {}, []
    for candidate in advance.CONFIGURATIONS:
        certificates[candidate], prior = [], []
        dates = sorted(signals.loc[signals["candidate_id"].eq(candidate), "signal_date"].drop_duplicates())
        for date_text in dates:
            day = pd.Timestamp(date_text)
            cert = advance.choose_target(candidate, day, prior, sessions, signals, index,
                                         series, child, correction_log, dependencies)
            if cert["target_status"] == "CERTIFIED_UNDER_REGISTERED_SOURCE_CORRECTIONS" and index[day] + 1 >= len(sessions):
                cert["target_status"] = "BLOCKED"
                cert["unresolved"].append({"input": "next_session_order",
                                           "reason": "no source-session execution date follows this certified decision"})
            cert["canonical_names"] = [row["canonical"] for row in cert["selected"]]
            certificates[candidate].append(cert)
            if cert["target_status"] != "CERTIFIED_UNDER_REGISTERED_SOURCE_CORRECTIONS":
                signal_blockers[candidate] = {"date": date_text, "kind": "signal_or_order",
                                              "unresolved": cert["unresolved"]}
                break
            prior = cert["canonical_names"]
    return sessions, data, actions, signals, certificates, signal_blockers, correction_log, cache_manifest


def run_case(candidate: str, certificates: list[dict], signals: pd.DataFrame, data: pd.DataFrame,
             actions: pd.DataFrame, sessions: list[pd.Timestamp], end_day: str,
             scenario: str, bps: float, blocker: dict | None, scope: str,
             requested_common_end: str | None) -> dict:
    advance.LOCAL = DETAIL / f"{candidate.lower().replace('-', '_')}_{scenario}_{int(bps)}bps_{scope}"
    certified = [row for row in certificates
                 if row["target_status"] == "CERTIFIED_UNDER_REGISTERED_SOURCE_CORRECTIONS"]
    result = advance.run_account(candidate, signals, certified, data, actions, sessions,
                                 end_day, scenario, bps, blocker)
    result["comparison_scope"] = scope
    if requested_common_end:
        result["requested_common_end"] = requested_common_end
    if scope == "common_supported_dates" and result["valid_through"] == requested_common_end:
        result["status"] = "ACTUAL_PREFIX_TO_COMMON_SUPPORTED_END"
    return result


def summary_row(account: dict) -> dict:
    fields = ("candidate_id", "comparison_scope", "requested_common_end", "status",
              "valuation_scenario", "slippage_bps_per_side", "valid_through", "starting_capital_inr",
              "actual_order_count", "actual_buy_count", "actual_sell_count", "first_order_date",
              "ending_nav_inr", "ending_cash_inr", "ending_invested_inr", "ending_cash_receivable_inr",
              "ending_locked_claim_inr", "ending_pending_share_value_inr", "max_drawdown_pct",
              "drawdown_recovery", "turnover_inr", "fees_inr", "fees_by_component_inr",
              "slippage_cost_inr", "cash_distributions_inr", "cash_distribution_entitlements_inr",
              "max_nav_reconciliation_residual_inr", "ending_concentration", "first_material_blocker")
    result = {key: account.get(key) for key in fields}
    result["first_material_blocker"] = compact_blocker(account.get("first_material_blocker"))
    return result


def main() -> None:
    self_check()
    advance.self_check()
    if CHECKPOINT.is_file():
        payload = json.loads(CHECKPOINT.read_text(encoding="utf-8"))
        if payload.get("protocol_id") != PROTOCOL:
            raise ValueError("cycle-5 checkpoint protocol mismatch")
        cases = payload["accounts"]
    else:
        cases = {}

    sessions, data, actions, signals, certificates, signal_blockers, correction_log, cache_manifest = prepare()
    cutoff = max(day for day in sessions if day <= audit.CUTOFF).date().isoformat()
    save_checkpoint("certificates_ready", certificates, signal_blockers, cases, None)

    native = {}
    for candidate in advance.CONFIGURATIONS:
        end_day = signal_blockers.get(candidate, {}).get("date", cutoff)
        native[candidate] = {}
        for scenario in ("base", "zero_mark_stress"):
            key = f"{candidate}|{scenario}|50|native_stop"
            if key not in cases:
                result = run_case(candidate, certificates[candidate], signals, data, actions, sessions,
                                  end_day, scenario, 50.0, signal_blockers.get(candidate),
                                  "native_stop", None)
                cases[key] = result
                save_checkpoint("native_accounts", certificates, signal_blockers, cases, None)
                print(json.dumps({"case": key, "valid_through": result["valid_through"],
                                  "ending_nav_inr": result["ending_nav_inr"]}), flush=True)
            native[candidate][scenario] = cases[key]

    common_end = min(row["base"]["valid_through"] for row in native.values())
    for candidate in advance.CONFIGURATIONS:
        for bps in (10.0, 50.0, 100.0, 200.0):
            key = f"{candidate}|base|{int(bps)}|common_supported_dates"
            if key in cases:
                continue
            if bps == 50.0 and native[candidate]["base"]["valid_through"] == common_end:
                result = dict(native[candidate]["base"])
                result["comparison_scope"] = "common_supported_dates"
                result["requested_common_end"] = common_end
            else:
                result = run_case(candidate, certificates[candidate], signals, data, actions, sessions,
                                  common_end, "base", bps, None, "common_supported_dates", common_end)
            cases[key] = result
            save_checkpoint("common_cost_sensitivities", certificates, signal_blockers, cases, common_end)
            print(json.dumps({"case": key, "valid_through": result["valid_through"],
                              "ending_nav_inr": result["ending_nav_inr"]}), flush=True)

    accounts = [native[name][scenario] for name in advance.CONFIGURATIONS
                for scenario in ("base", "zero_mark_stress")]
    costs = [cases[f"{name}|base|{int(bps)}|common_supported_dates"]
             for name in advance.CONFIGURATIONS for bps in (10.0, 50.0, 100.0, 200.0)]
    tri_results, tri_sha256 = advance.matched_tri_results(accounts + costs)

    def benchmark_for(account: dict) -> dict:
        return next(row for row in tri_results
                    if row["candidate_id"] == account["candidate_id"]
                    and row["valuation_scenario"] == account["valuation_scenario"]
                    and row["slippage_bps_per_side"] == account["slippage_bps_per_side"]
                    and row.get("matched_through") == account["valid_through"])

    output = ROOT / "outputs"
    signal_manifest_path = output / f"nifty200_{TAG}_signal_cache_manifest.json"
    signal_manifest_path.write_text(json.dumps(cache_manifest, indent=2) + "\n", encoding="utf-8")
    cost_rows = []
    for result in costs:
        benchmark = benchmark_for(result)
        cost_rows.append({key: result.get(key) for key in (
            "candidate_id", "requested_common_end", "valid_through", "status", "slippage_bps_per_side",
            "actual_order_count", "ending_nav_inr", "fees_inr", "slippage_cost_inr", "turnover_inr",
            "max_drawdown_pct", "drawdown_recovery")}
            | {key: benchmark.get(key) for key in (
                "common_start_buy_hold_tri_return_pct", "common_start_excess_pct_points",
                "prior_close_eod_proxy_tri_return_pct", "prior_close_eod_proxy_excess_pct_points")})
    cost_path = output / f"nifty200_{TAG}_common_date_cost_comparison.csv"
    pd.DataFrame(cost_rows).to_csv(cost_path, index=False)
    tri_path = output / f"nifty200_{TAG}_benchmark_timing.csv"
    pd.DataFrame(tri_results).to_csv(tri_path, index=False)

    blocker_rows = []
    for candidate in advance.CONFIGURATIONS:
        first_signal = signal_blockers.get(candidate)
        blocker_rows.append({"candidate_id": candidate,
                             "certified_signal_count": sum(
                                 row["target_status"] == "CERTIFIED_UNDER_REGISTERED_SOURCE_CORRECTIONS"
                                 for row in certificates[candidate]),
                             "first_signal_blocker": compact_blocker(first_signal),
                             "native_account_stop": compact_blocker(native[candidate]["base"].get("first_material_blocker")),
                             "valid_through": native[candidate]["base"]["valid_through"]})
    blocker_path = output / f"nifty200_{TAG}_dependency_blockers.json"
    blocker_path.write_text(json.dumps({"cycle_id": CYCLE, "protocol_id": PROTOCOL,
                                        "signal_and_account_stops": blocker_rows}, indent=2) + "\n",
                            encoding="utf-8")

    coverage = json.loads((output / "nifty200_candidate_dependency_audit_2026-11-03.json").read_text(encoding="utf-8"))
    calendar_path = output / "nifty200_benchmark_calendar_reconciliation_2026-11-01.json"
    replay_path = output / "nifty200_replay_residual_delta_2026-11-01.json"
    coverage_ledger_path = output / "nifty200_source_extraction_coverage_2026-10-31.csv"
    cholafin_path = output / "nifty200_cholafin_source_extraction_coverage_2026-11-03.json"
    r1_path = output / "experiment_register_R1_2026-11-02.csv"
    listing_path = output / "nifty200_listing_evidence_2026-11-03.csv"
    selection_bounds = []
    for candidate in advance.CONFIGURATIONS:
        for cert in certificates[candidate]:
            for bound in cert.get("selection_bounds", []):
                if bound.get("source_debt_distributions"):
                    selection_bounds.append({"candidate_id": candidate, "signal_date": cert["signal_date"],
                                             "symbol": bound["symbol"], "method": bound["reason"],
                                             "return_numerator_upper_bound": bound["return_numerator"],
                                             "source_debt_distributions": bound["source_debt_distributions"]})

    strategy_definitions = {
        "NIFTY200-A-M": "Rule A: 12-month total return ending 21 source sessions before the signal; monthly decisions.",
        "NIFTY200-A-Q": "Rule A: 12-month total return ending 21 source sessions before the signal; quarterly decisions.",
        "NIFTY200-B-M": "Rule B: mean of lagged 6- and 12-month returns divided by annualized volatility over the exact 252-return window; monthly decisions.",
        "NIFTY200-B-Q": "Rule B: mean of lagged 6- and 12-month returns divided by annualized volatility over the exact 252-return window; quarterly decisions.",
    }
    results = {"cycle_id": CYCLE, "protocol_id": PROTOCOL, "capital_inr": CAPITAL,
               "cash_yield": "zero", "evaluation_start": "2018-01-01", "full_evaluation_end": audit.CUTOFF.date().isoformat(),
               "common_cost_end": common_end,
               "performance_gate": "NO FULL-PERIOD CAGR; no short-prefix 20% claim; no ranking or deployment",
               "strategy_definitions": strategy_definitions,
               "portfolio_rule": "At each frozen decision, select 20 positive-score names with prior holdings retained through rank 25 before filling; target 5% per name; execute at the next source-session raw open.",
               "accounts": [summary_row(row) for row in accounts],
               "cost_sensitivities": [summary_row(row) for row in costs],
               "matched_tri": {"series": "official NIFTY 200 Gross TRI", "sha256": tri_sha256,
                               "cash_waiting_time_included": True, "results": tri_results},
               "dependency_coverage": {key: coverage.get(key) for key in (
                   "protocol_id", "audit_type", "evaluation_start", "evaluation_cutoff",
                   "working_calendar_sessions_with_warmup", "evaluation_source_calendar_sessions",
                   "dependency_rows", "dependency_path_incidence_counts", "unique_source_entity_date_type_counts",
                   "conditional_target_close_gap_unique_entity_dates",
                   "conditional_target_open_gap_unique_entity_dates", "schedule_sweep_semantics")},
               "new_listing_classifications": {"evidence_ledger_local": listing_path.name,
                   "newly_reviewed_names": ["ABCAPITAL", "GICRE", "GODREJAGRO", "ICICIGI", "SBILIFE", "DALBHARAT"],
                   "dalbharat_rule": "ineligible until its sourced 2019-01-25 listing clears the unchanged full lookback; no OCL predecessor prices are joined"},
               "source_bound_resolutions": selection_bounds,
               "source_demerger_review": {"CESC": {"ex_date": "2018-10-30", "record_date": "2018-10-31",
                   "allotment_date": "2018-11-14", "child_listing_date": "2019-01-25",
                   "entitlements_per_10_CESC_shares": {"SPENCERS": 6, "CESCVENT": 2},
                   "signal_endpoint_before_listing": "UNKNOWN_DATA; no later listing price is backfilled"}},
               "source_merger_review": {"GRUH": {"bonus_ex_date": "2018-06-06", "bonus_allotment_date": "2018-06-08",
                   "merger_effective_date": "2019-10-17", "record_date": "2019-10-17",
                   "exchange_ratio": "568 Bandhan shares per 1,000 GRUH shares", "successor_allotment_date": "2019-10-21",
                   "accounting_status": "unresolved; merger claim and successor-share listing/trading permission are not modeled; no missing GRUH mark or successor entitlement is invented",
                   "source_note": "nifty200_gruh_merger_position_mark_review_2026-11-03.md"}},
               "calendar_reconciliation": calendar_path.name, "replay_residual_delta": replay_path.name,
               "source_extraction_coverage": [coverage_ledger_path.name, cholafin_path.name],
               "R1_status": "NOTRUN; preregistered fixed 200-source-session NIFTY 200 TRI regime proposal retained",
               "research_limits": [
                   "Stopped prefixes do not support CAGR or the 20% objective.",
                   "A positive contractual debenture bound or a failed price/factor scope check remains unresolved; held NCD marks are not modeled.",
                   "GRUH's bonus was allotted on 2018-06-08, but its 2019-10-17 Bandhan merger claim and successor-share trading admission are not modeled; A-M stops at the last observed GRUH close.",
                   "IDFC bond-interest dates remain an evidence-supported inference without the exact original notice.",
                   "AGEL prelisting value, trustee disposal timing, and unobserved dividend cash dates retain the prior registered assumptions.",
                   "Costs are uncalibrated; zero-mark stress is not a proven final-wealth lower bound."]}
    result_path = output / f"nifty200_{TAG}_actual_results.json"
    result_path.write_text(json.dumps(results, indent=2) + "\n", encoding="utf-8")

    register_rows = []
    for result in accounts + costs:
        benchmark = benchmark_for(result)
        register_rows.append({"cycle_id": CYCLE, "protocol_id": PROTOCOL,
                              "candidate_id": result["candidate_id"],
                              "comparison_scope": result["comparison_scope"],
                              "requested_common_end": result.get("requested_common_end", ""),
                              "valuation_scenario": result["valuation_scenario"],
                              "slippage_bps_per_side": result["slippage_bps_per_side"],
                              "valid_through": result["valid_through"], "status": result["status"],
                              "orders": result["actual_order_count"], "turnover_inr": result["turnover_inr"],
                              "fees_inr": result["fees_inr"], "slippage_cost_inr": result["slippage_cost_inr"],
                              "ending_nav_inr": result["ending_nav_inr"],
                              "max_drawdown_pct": result["max_drawdown_pct"],
                              "common_start_buy_hold_tri_return_pct": benchmark.get("common_start_buy_hold_tri_return_pct"),
                              "common_start_excess_pct_points": benchmark.get("common_start_excess_pct_points"),
                              "cagr": "NOT REPORTED: stopped prefix"})
    register_path = output / f"experiment_register_{TAG}.csv"
    pd.DataFrame(register_rows).to_csv(register_path, index=False)
    previous_register = output / "experiment_register_cumulative_cycle4_2026-11-03.csv"
    previous = pd.read_csv(previous_register) if previous_register.is_file() else pd.DataFrame()
    cumulative_path = output / f"experiment_register_cumulative_{TAG}.csv"
    pd.concat([previous, pd.DataFrame(register_rows)], ignore_index=True, sort=False).to_csv(cumulative_path, index=False)

    top = []
    for candidate in advance.CONFIGURATIONS:
        account = native[candidate]["base"]
        benchmark = benchmark_for(account)
        top.append(f"| {candidate} — {strategy_definitions[candidate]} | {account['valid_through']} | ₹{account['ending_nav_inr']:,.0f} | "
                   f"{account['max_drawdown_pct']:.2f}% | {benchmark.get('common_start_excess_pct_points', float('nan')):.2f} pp |")
    markdown = (f"# NIFTY 200 cycle 5 checkpoint — 2026-11-03\n\n"
                f"## Four fixed candidates — no rankable winner\n\nNo full-period leader is established: all four paths stop on unresolved dependencies, so the 20% CAGR objective is untested. NAV is after registered fees and slippage at 50 bps per side. The portfolio selects 20 positive-score names, retains prior names through rank 25, targets 5% each, and executes next-session raw opens.\n\n"
                f"| Candidate and frozen signal | Valid through | Ending NAV | Max drawdown | Excess vs matched gross TRI |\n"
                f"|---|---:|---:|---:|---:|\n" + "\n".join(top) + "\n\n"
                f"The common cost endpoint is {common_end}. The fixed 10/50/100/200 bps cases, timing sensitivities, costs, turnover, recovery, concentration, and finite blockers are in the result JSON/CSVs. R1 remains NOTRUN.\n\n"
                f"## Protocol and evidence\n\nProtocol: `{PROTOCOL}`. Capital is ₹10 lakh continuous, unlevered, zero cash yield, next-session raw-open integer-share execution, and the existing four frozen schedules. Calendar and membership replay evidence remain in `{calendar_path.name}` and `{replay_path.name}`. CHOLAFIN extraction coverage is `{cholafin_path.name}`. The listing ledger and detailed source rows remain local; aggregate classifications and SHA-256 manifest are published.\n\n"
                f"CESC's October 2018 scheme grants 6 Spencer's Retail and 2 CESC Ventures shares per 10 CESC shares. Both children first traded on 2019-01-25, so a signal endpoint before that date remains unresolved. See `nifty200_cesc_composite_scheme_2018-10-30.md`.\n\n"
                f"GRUH's 1:1 bonus shares were allotted on 2018-06-08. Its merger into Bandhan was effective 2019-10-17 with 568 Bandhan shares per 1,000 GRUH shares; successor shares were allotted October 21, but the current account model does not resolve successor-share listing permission and claim marking. The A-M held-position path therefore stops at the last observed GRUH close. See `nifty200_gruh_merger_position_mark_review_2026-11-03.md`.\n\n"
                f"The Britannia 2019-08-22 bonus debenture has a ₹37.20 undiscounted contract upper bound at non-negative yield. It only clears signal contributions whose maximum return numerator is non-positive and does not value a held NCD. Source terms are documented in `nifty200_britannia_debt_distribution_bound_2026-11-03.md`.\n\n"
                f"## Remaining blockers\n\nSee `{blocker_path.name}` for each path's first signal and account stop, exact date, identity, input, and reason. Raw price rows, order traces, and detailed source records remain local.\n")
    markdown_path = output / f"nifty200_{TAG}_checkpoint.md"
    markdown_path.write_text(markdown, encoding="utf-8")

    manifest_files = [result_path, blocker_path, cost_path, tri_path, register_path, cumulative_path,
                      markdown_path, signal_manifest_path, ROOT / "work" / "advance_nifty200_cycle5.py",
                      ROOT / "work" / "advance_nifty200_cash_prefixes.py",
                      ROOT / "work" / "audit_strategy_dependencies.py", ROOT / "work" / "upstox_quant.py",
                      calendar_path, replay_path,
                      coverage_ledger_path, cholafin_path,
                      ROOT / "outputs" / "nifty200_britannia_debt_distribution_bound_2026-11-03.md",
                      ROOT / "outputs" / "nifty200_cesc_composite_scheme_2018-10-30.md",
                      ROOT / "outputs" / "nifty200_gruh_merger_position_mark_review_2026-11-03.md",
                      r1_path]
    manifest_path = output / f"nifty200_{TAG}_source_code_schema_manifest.json"
    manifest = {"cycle_id": CYCLE, "protocol_id": PROTOCOL,
                "generation_command": "python work/audit_strategy_dependencies.py; python work/advance_nifty200_cycle5.py",
                "matched_tri_sha256": tri_sha256,
                "native_accounts": len(accounts), "common_cost_cases": len(costs),
                "common_cost_end": common_end,
                "dependency_audit_sha256": audit.sha256_file(output / "nifty200_candidate_dependency_audit_2026-11-03.json"),
                "listing_evidence_sha256_local": audit.sha256_file(listing_path),
                "files_sha256": {path.relative_to(ROOT).as_posix(): audit.sha256_file(path)
                                 for path in manifest_files if path.is_file()}}
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    result = json.loads(result_path.read_text(encoding="utf-8"))
    result["source_code_schema_manifest"] = manifest_path.name
    result_path.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    manifest["files_sha256"][result_path.relative_to(ROOT).as_posix()] = audit.sha256_file(result_path)
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    assert len(accounts) == 8 and len(costs) == 16 and len(tri_results) == 24
    save_checkpoint("complete", certificates, signal_blockers, cases, common_end)
    print(json.dumps({"protocol_id": PROTOCOL, "native_accounts": len(accounts),
                      "common_cost_cases": len(costs), "common_cost_end": common_end,
                      "results": result_path.name}), flush=True)


if __name__ == "__main__":
    main()
