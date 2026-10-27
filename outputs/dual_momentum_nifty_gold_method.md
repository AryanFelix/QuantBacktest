# NIFTYBEES + GOLDBEES absolute-momentum control

**Run date:** 2026-10-27  
**Capital:** ₹10,00,000 per run  
**Market data:** 2014-01-01 to 2026-10-23  
**Status:** retrospective price-only baseline plus a one-event cash-distribution sensitivity; not a selected or validated winner

## Rule

At each month-end, compute each ETF’s 12–1 price momentum as `close[t-21] / close[t-252] - 1`. An ETF is eligible only when that score is positive and its month-end close is above its 200-session simple moving average. Equal-weight the eligible assets, up to `top_n=2`; otherwise hold cash. Apply the signal at the next session’s open, capped at the scenario’s maximum gross exposure. The first eligible trade was NIFTYBEES on 2015-02-02; GOLDBEES history begins 2015-01-01 and it becomes eligible only after its own history is long enough. The run starts at the NIFTYBEES cache’s 2014-01-01 first bar, so the initial momentum warm-up is part of the reported cash return.

## Data and execution

- NIFTYBEES: 3,167 daily bars, `NSE_EQ|INF204KB14I2`, `work/data/etf_daily/NSE_EQ_INF204KB14I2-days-1-2014-01-01-2026-10-23.csv`.
- GOLDBEES: 2,922 daily bars, alias-key cache, `work/data/etf_daily/GOLDBEES-days-1-2014-01-01-2026-10-23.csv` (first actual bar 2015-01-01).
- Signals use only the prior completed session; integer shares execute at the next open. Buys and sells include modeled Upstox/NSE delivery charges and adverse slippage at the stated basis points per side. Equity-oriented NIFTYBEES units use nil buy-side and 0.001% sell-side delivery STT; GOLDBEES uses no STT. Other current delivery charges are applied uniformly to historical trades; residual cash earns 0%; open positions are liquidated at the final close with sell charges and slippage. Fee sources and the correction are in [the fee-model audit](../work/research/fee_model_audit.md).
- Starting capital is ₹10 lakh in every run. Exposure caps are 60%, 70%, 80%, or 95%; tested slippage is 10 or 50 bps per side. No leverage is used.
- The tested return is price-based and does not include investor income/capital-gains tax. A known NIFTYBEES distribution went ex on 2015-02-18 while every scenario held NIFTYBEES. The corporate-action audit’s candidate saved-unit conversion is ₹0.80 per saved price unit, but this replay does not credit the distribution because historical unit conversion and entitlement reconciliation remain unresolved. The mechanical cash sensitivity below is not applied; these are not fully adjusted total returns. The 2014 distribution predates the first position. Split normalization is also inferred from price continuity, not guaranteed by Upstox.

| Run | NIFTYBEES quantity held before 2015-02-18 ex-date | Indicative cash at ₹0.80 per saved unit |
|---|---:|---:|
| `10bps` | 10,614 | ₹8,491.20 |
| `50bps` | 10,614 | ₹8,491.20 |
| `60cap_50bps` | 6,703 | ₹5,362.40 |
| `70cap_10bps` | 7,821 | ₹6,256.80 |
| `70cap_50bps` | 7,821 | ₹6,256.80 |
| `80cap_50bps` | 8,938 | ₹7,150.40 |

The source distribution date/rate and candidate unit factor are documented in [`etf_corporate_action_audit.csv`](etf_corporate_action_audit.csv); the quantities above are calculated from these six run order ledgers. Confirm units and entitlement before treating the cash figures as actual total-return adjustments.
- CAGR and drawdown include the full run interval and warm-up. The 20% drawdown flag is a historical screen, not a prospective loss cap. Slippage is in execution prices; run summaries do not separately emit aggregate slippage rupees, so `slippage_cost_inr` remains blank in the consolidated ledger.

## Corporate-action source and adjusted replay

The [NSE NIFTYBEES quote and corporate-action page](https://www.nseindia.com/get-quote/equity/NIFTYBEES/Nippon-India-ETF-Nifty-50-BeES) records an ₹8/unit distribution with ex-date 2015-02-18 and record date 2015-02-20. Nippon’s [historical ETF factsheet](https://mf.nipponindiaim.com/investorservices/factsheetsdocuments/fundamentals-august-2021/Innerpage/ETF-Nifty-BeES.html) confirms the ₹8 rate and gives cum/ex NAVs of ₹893.3096/₹885.3096. The [NSE 2019 split circular](https://archives.nseindia.com/content/circulars/CML42888.pdf) documents subdivision from ₹10 to ₹1, or 10:1. The cached Upstox series is continuous across that split date, consistent with historical prices being in post-split units; this is empirical evidence, not a provider guarantee. I therefore ran a separate sensitivity at ₹0.80 per normalized share (`₹8 / 10`).

The simulator credits this amount on the ex-date against units held at the prior close, before that session’s open execution. The credit stays in cash and can affect sizing at later scheduled rebalances. The actual payment date is not modeled, cash is treated as available immediately, and tax is excluded. Keep these runs labeled as a one-event, ex-date cash-flow adjustment rather than fully audited total-return history. The source records establish the corporate action; the split-adjusted unit mapping and immediate availability remain assumptions.

## Results — price-only baseline

| Exposure cap | Slippage / side | Ending value | Return | CAGR | Max drawdown | Fees | Within 20% screen |
|---:|---:|---:|---:|---:|---:|---:|:---|
| 95% | 10 bps | ₹18.63L | +86.26% | 5.08% | -25.08% | ₹13,997 | Fail |
| 95% | 50 bps | ₹15.21L | +52.09% | 3.39% | -29.14% | ₹13,371 | Fail |
| 60% | 50 bps | ₹13.24L | +32.40% | 2.26% | -19.39% | ₹11,233 | Pass, 0.61 pp headroom |
| 70% | 10 bps | ₹16.04L | +60.44% | 3.83% | -19.08% | ₹12,154 | Pass, 0.92 pp headroom |
| 70% | 50 bps | ₹13.80L | +38.03% | 2.60% | -22.28% | ₹11,878 | Fail |
| 80% | 50 bps | ₹14.36L | +43.64% | 2.92% | -25.08% | ₹12,435 | Fail |

## Results — ex-date cash-flow sensitivity

| Exposure cap | Slippage / side | Price-only end value | Adjusted end value | Cash credited | Adjusted return | Adjusted max drawdown | Fees | Within 20% screen |
|---:|---:|---:|---:|---:|---:|---:|---:|:---|
| 60% | 50 bps | ₹13.24L | ₹13.31L | ₹5,362.40 | +33.12% | -19.39% | ₹11,229 | Pass, 0.61 pp headroom |
| 70% | 10 bps | ₹16.04L | ₹16.15L | ₹6,256.80 | +61.45% | -19.08% | ₹12,113 | Pass, 0.92 pp headroom |
| 70% | 50 bps | ₹13.80L | ₹13.89L | ₹6,256.80 | +38.92% | -22.27% | ₹11,835 | Fail |
| 80% | 50 bps | ₹14.36L | ₹14.47L | ₹7,150.40 | +44.69% | -25.08% | ₹12,471 | Fail |
| 95% | 10 bps | ₹18.63L | ₹18.79L | ₹8,491.20 | +87.86% | -25.08% | ₹14,008 | Fail |
| 95% | 50 bps | ₹15.21L | ₹15.34L | ₹8,491.20 | +53.39% | -29.13% | ₹13,398 | Fail |

The adjusted ending values differ from the price-only baseline by more than the cash credit alone where the cash changes share sizing at a later rebalance; fees and subsequent holdings are replayed, not added arithmetically after the fact.

## Readout and limitations

The 12 scenarios were regenerated after normalizing daily timestamps and correcting ETF-unit STT; these replace earlier tables and ledger values. At 50 bps, the 60% cap passes the close-drawdown screen with -19.39% but only 0.61 pp of headroom. The 70% and 95% cases fail at -22.28% and -29.14%. The 70% case passes at 10 bps with -19.08% drawdown, leaving 0.92 pp; this friction case is not robust to realistic spread uncertainty. This price-based retrospective control is not a winner.

This is a single full-history retrospective screen on two surviving ETF price series; all observations have been inspected. It is not an independent holdout. The strategy has only two instruments, the first year has a warm-up cash position, Gold history starts later than NIFTYBEES, and only the known 2015 NIFTYBEES distribution has been credited. Other corporate-action completeness, realistic spreads/market impact, payment timing, and tax treatment are not established. Run-level `summary.json`, `equity.csv`, and `orders.csv` are preserved in each directory below. Reproduce with `python work/upstox_quant.py backtest --data "NIFTYBEES=work/data/etf_daily/NSE_EQ_INF204KB14I2-days-1-2014-01-01-2026-10-23.csv" --data "GOLDBEES=work/data/etf_daily/GOLDBEES-days-1-2014-01-01-2026-10-23.csv" --strategy momentum12_1 --top-n 2 --capital 1000000 --max-exposure <cap> --slippage-bps <bps> --drawdown-limit 20 --out-dir work/backtests/<scenario>`.

For the ex-date cash-flow cases, add `--cash-distribution NIFTYBEES 2015-02-18 0.8` to the reproduction command and use the matching `dual_momentum_nifty_gold_dividend_adjusted_*` output directory. The run summary records eligible prior-close quantity and cash credited.

## Run directories

### Price-only baseline

- `work/backtests/dual_momentum_nifty_gold_10bps/` — cap 95%, 10 bps per side.
- `work/backtests/dual_momentum_nifty_gold_50bps/` — cap 95%, 50 bps per side.
- `work/backtests/dual_momentum_nifty_gold_60cap_50bps/` — cap 60%, 50 bps per side.
- `work/backtests/dual_momentum_nifty_gold_70cap_10bps/` — cap 70%, 10 bps per side.
- `work/backtests/dual_momentum_nifty_gold_70cap_50bps/` — cap 70%, 50 bps per side.
- `work/backtests/dual_momentum_nifty_gold_80cap_50bps/` — cap 80%, 50 bps per side.

### Ex-date cash-flow sensitivity

- `work/backtests/dual_momentum_nifty_gold_dividend_adjusted_60cap_50bps/`
- `work/backtests/dual_momentum_nifty_gold_dividend_adjusted_70cap_10bps/`
- `work/backtests/dual_momentum_nifty_gold_dividend_adjusted_70cap_50bps/`
- `work/backtests/dual_momentum_nifty_gold_dividend_adjusted_80cap_50bps/`
- `work/backtests/dual_momentum_nifty_gold_dividend_adjusted_95cap_10bps/`
- `work/backtests/dual_momentum_nifty_gold_dividend_adjusted_95cap_50bps/`
