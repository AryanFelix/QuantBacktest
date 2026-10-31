# Indian Market Quant Research

## Current decision — 2026-10-31

No current unlevered cash strategy has demonstrated the target of **20% annual CAGR after modeled trading costs**, before personal tax. The former 20% drawdown ceiling has been removed; actual close drawdown and the separate conservative OHLC envelope are reported. The reference account is ₹10 lakh.

The leading research case is monthly NIFTY 50 12–1 momentum, top 15, chosen on 2021–2023 training data. It earned 23.88% in training, then 11.87% in 2024 and -4.94% in 2025–October 2026. Its corrected continuous full-period CAGR is 11.90% versus 9.66% for matched NIFTY 50 TRI. It is not a winner or deployment recommendation. See the [top-five leaderboard and full report](outputs/quant_research_report.md).

This cycle corrected terminal liquidation and calendar-time CAGR, replayed the selected stock rule’s order ledger, and reran the highlighted Donchian/Gold case. The broad-stock point-in-time data gate failed: existing coverage is not NIFTY 200/500, so none of the preregistered broad-universe configurations ran. The exact gaps and licensed acquisition route are in the [data-gate report](outputs/broad_stock_data_gate_2026-10-31.md). The synthetic 2× index is a diagnostic only; no leverage was used for this cycle.

The API token has not been rotated, so this cycle made no Upstox API requests. No live orders were placed, and the existing frozen paper paths were left unchanged.

## Cycle records

- [24-hour governor checkpoint](outputs/24_hour_checkpoint_2026-10-31.md)
- [Experiment register](outputs/experiment_register_2026-10-31.csv)
- [Terminal liquidation and saved held-mark audit](outputs/terminal_liquidation_audit_2026-10-31.md)
- [Stock momentum attribution](outputs/stock_momentum_attribution_2026-10-31.md)
- [Matched NIFTYBEES passive baseline](outputs/stock_momentum_passive_comparison_2026-10-31.csv)
- [Next-cycle specification](outputs/next_cycle_spec_2026-10-31.md)
- [Elapsed-calendar CAGR and Donchian fee correction](outputs/measurement_correction_2026-10-31.csv)

## How to reproduce

Run from the repository root:

```powershell
python work/check_terminal_liquidation.py
python work/audit_stored_position_gaps.py
python work/attribute_stock_momentum_leader.py
python work/replay_donchian_gold_blend.py
python work/write_research_data_fingerprint.py
python work/write_research_code_fingerprint.py
```

Most source data and per-run histories stay local under `work/data/` and `work/backtests/`; `outputs/data_manifest.csv` records coverage and paths. The repository contains methods and aggregate results. Upstox credentials must remain in the local environment or user registry, never in source, logs, or commits.

Past 20% drawdown screens and NIFTY/Gold ratio sweeps are historical comparisons. They do not constrain the current strategy selection, and the NIFTY/Gold family is no longer the primary route to the return objective. A historical return or bootstrap does not limit future losses.
