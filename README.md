# Indian Market Quant Research

## Current decision — 2026-11-02

No unlevered cash strategy has demonstrated the **20% full-period annual CAGR after modeled costs** objective on ₹10 lakh. The former hard drawdown ceiling remains retired. The current NIFTY 200 work completed only short 2018 account prefixes; it does not establish a full-period CAGR or durable index excess.

The four frozen configurations remain unranked. At 50 bps per side, A-M returned −3.460% through 2018-04-30 versus −1.489% matched gross NIFTY 200 TRI; A-Q returned −0.125% through 2018-06-20 versus +3.930% TRI; B-M returned −1.325% versus −1.489%; and B-Q returned +4.132% versus +3.930%. A-M/B-M stop at ranking-changing signal dependencies on April 30; A-Q/B-Q stop before a held JUBLFOOD 1:1 bonus on June 21. See the [cycle 2 account checkpoint](outputs/nifty200_sequential_account_checkpoint_cycle2_2026-11-02.md) and its [actual results summary](outputs/nifty200_cycle2_actual_results_2026-11-02.json).

The earlier [top-five research overview](outputs/quant_research_report.md) remains dated 2026-10-31. Its NIFTY 50 momentum lead returned 11.90% full-period CAGR versus 9.66% matched TRI; it is not a current deployment recommendation. The NIFTY 200 membership replay now has zero failed batches, and the corrected 2,183-session cash calendar matches the official TRI date set. The finite candidate-specific signal and held-position dependencies are recorded in the [blocker ledger](outputs/nifty200_cycle2_dependency_blockers_2026-11-02.json) and [candidate audit](outputs/nifty200_candidate_dependency_audit_2026-11-02.json).

This cycle used no Upstox credentials, made no API requests, placed no live orders, and did not alter frozen paper paths.

## Cycle records

- [Current four-configuration checkpoint](outputs/nifty200_sequential_account_checkpoint_cycle2_2026-11-02.md)
- [Compact 20-case actual results and matched TRI](outputs/nifty200_cycle2_actual_results_2026-11-02.json)
- Detailed order, daily equity, account-position, and event ledgers remain local; their hashes are recorded in the [source and output manifest](outputs/nifty200_cycle2_source_code_schema_manifest_2026-11-02.json).
- [Grouped candidate-specific dependency blockers](outputs/nifty200_cycle2_dependency_blockers_2026-11-02.json)
- [Source, code, schema, and result hash manifest](outputs/nifty200_cycle2_source_code_schema_manifest_2026-11-02.json)
- [AGEL valuation protocol](outputs/nifty200_agel_valuation_protocol_2026-11-02.md)
- [Archived April 4 pre-AGEL checkpoint](outputs/archive/nifty200_sequential_account_checkpoint_pre_agel_2026-11-02.md)
- [24-hour governor checkpoint](outputs/24_hour_checkpoint_2026-10-31.md)
- [NIFTY 200 replay and L500 gate checkpoint](outputs/nifty200_cycle_checkpoint_2026-10-31.md)
- [Frozen universe and strategy protocol](outputs/next_cycle_spec_2026-10-31.md)
- [NIFTY 200 replay summary and source-specific residual manifest](outputs/nifty200_membership_replay_summary_2026-10-31.json)
- [L500 pre-performance data gate](outputs/l500_data_gate_2026-10-31.json)
- [Experiment register](outputs/experiment_register_2026-10-31.csv)
- [Historical search-family inventory](outputs/historical_search_inventory_2026-10-31.csv)
- [Terminal liquidation and saved held-mark audit](outputs/terminal_liquidation_audit_2026-10-31.md)
- [Stock momentum attribution](outputs/stock_momentum_attribution_2026-10-31.md)
- [Matched NIFTYBEES passive baseline](outputs/stock_momentum_passive_comparison_2026-10-31.csv)
- [Next-cycle specification](outputs/next_cycle_spec_2026-10-31.md)
- [Elapsed-calendar CAGR and Donchian fee correction](outputs/measurement_correction_2026-10-31.csv)

## How to reproduce

Run from the repository root:

```powershell
python work/audit_strategy_dependencies.py
python work/advance_nifty200_cash_prefixes.py
python work/check_terminal_liquidation.py
python work/audit_stored_position_gaps.py
python work/attribute_stock_momentum_leader.py
python work/replay_donchian_gold_blend.py
python work/write_research_data_fingerprint.py
python work/write_research_code_fingerprint.py
```

Most source data and per-run histories stay local under `work/data/` and `work/backtests/`; `outputs/data_manifest.csv` records coverage and paths. The repository contains methods and aggregate results. Upstox credentials must remain in the local environment or user registry, never in source, logs, or commits.

Past 20% drawdown screens and NIFTY/Gold ratio sweeps are historical comparisons. They do not constrain the current strategy selection, and the NIFTY/Gold family is no longer the primary route to the return objective. A historical return or bootstrap does not limit future losses.
