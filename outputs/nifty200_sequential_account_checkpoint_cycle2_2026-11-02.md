# NIFTY 200 cash-account checkpoint — 2026-11-02, cycle 2

**Protocol:** `NIFTY200-v1.6-AGEL-locked-claim-base-zero-stress`  
**Status:** four frozen configurations executed through their first unresolved dependency; provisional prefixes only.

## Four frozen configurations

Returns below are cumulative account returns from the common ₹10 lakh start on 2018-01-01 through each account's last valid close. The matched reference is official NIFTY 200 Gross TRI with zero-yield cash until the account's first order. These short prefixes are not annualized or ranked.

| Configuration | Valid through | Account NAV | Net prefix return | Matched TRI return | Excess vs TRI | Max drawdown | Orders |
|---|---:|---:|---:|---:|---:|---:|---:|
| A-M | 2018-04-30 | ₹9,65,402 | −3.460% | −1.489% | −1.970 pp | −11.483% | 66 |
| A-Q | 2018-06-20 | ₹9,98,749 | −0.125% | +3.930% | −4.055 pp | −9.249% | 21 |
| B-M | 2018-04-30 | ₹9,86,752 | −1.325% | −1.489% | +0.165 pp | −9.759% | 62 |
| B-Q | 2018-06-20 | ₹10,41,316 | +4.132% | +3.930% | +0.202 pp | −5.645% | 21 |

The drawdown troughs were 2018-03-07 for the monthly cases, 2018-06-05 for A-Q, and 2018-05-21 for B-Q. None had recovered its prior high-water mark by its prefix end. All four ended with 20 positions. The largest position was 6.20–6.59% of invested value; the top five were 28.84–30.81%. Position market values reconcile to invested NAV with zero reported residual; total NAV reconciliation residuals were below ₹0.000000001.

## Costs, cash and sensitivity

| Configuration | Turnover | Fees | Slippage | Ending cash receivable | Ending locked claim |
|---|---:|---:|---:|---:|---:|
| A-M | ₹17,74,591 | ₹4,149 | ₹8,848 | ₹116.00 | ₹1,033.20 |
| A-Q | ₹10,05,424 | ₹1,712 | ₹5,003 | ₹727.50 | ₹23.91 |
| B-M | ₹20,36,229 | ₹4,345 | ₹10,157 | ₹118.00 | ₹1,058.40 |
| B-Q | ₹10,02,482 | ₹1,708 | ₹4,988 | ₹820.50 | ₹23.91 |

The matched-index excess at each modeled one-way slippage assumption was:

| Configuration | 10 bps/side | 50 bps/side | 100 bps/side | 200 bps/side |
|---|---:|---:|---:|---:|
| A-M | −1.218 pp | −1.970 pp | −2.901 pp | −4.866 pp |
| A-Q | −3.655 pp | −4.055 pp | −4.549 pp | −5.526 pp |
| B-M | +0.999 pp | +0.165 pp | −0.896 pp | −3.056 pp |
| B-Q | +0.601 pp | +0.202 pp | −0.296 pp | −1.271 pp |

Within this tested grid, A-M and A-Q remained below the gross TRI even at 10 bps/side. B-M and B-Q changed from positive to negative excess between 50 and 100 bps/side. No interpolated break-even is claimed: integer-share order counts and sizing changed across cost runs, and the prefixes are too short to calibrate a strategy-level cost threshold. Costs remain uncalibrated.

## AGEL claim treatment

The account held 287 AEL shares in A-M, 294 in B-M, and 319 in each quarterly case immediately before the 2018-04-05 ex-date. At the registered ratio of 761 AGEL shares per 1,000 AEL shares, those positions created exact claims of 218.407, 223.734, and 242.759 shares. The base prelisting model mark was ₹4.7306176084 per AGEL share, from the observed AEL raw closes on 2018-04-04 and 2018-04-05. The separate zero-mark stress uses zero through listing.

The quarterly accounts sold 242 whole AGEL shares on 2018-06-19 at the next session's raw open of ₹32.70, modeled fill ₹32.5365 after 50 bps slippage and ₹55.37 fees. The remaining 0.759-share claim is a nonspendable receivable marked at the 2018-06-18 listing close of ₹31.50 (₹23.91). The monthly accounts end before listing and retain 218 or 223 whole claim units plus the fractional claim at the registered mark. No fractional trustee sale or cash settlement is invented. Dividends with no verified pay date remain receivables for 30 calendar days, then become spendable on the next source session; cash earns zero.

The scheme terms and ratio are in the [issuer information memorandum](https://www.adanigreenenergy.com/-/media/Project/GreenEnergy/Corporate-Governance/Others/Adani_Green_Energy_Limited_-_Information_Memorandum.pdf) and [issuer explanatory statement, clauses 10.3 and 10.11](https://www.adanigreenenergy.com/-/media/Project/GreenEnergy/Corporate-Governance/scheme-of-Arrangement-2018/Notice-and-Explanatory-Statement-UnSecured-Creditors.pdf). The issuer lists the [final NCLT order](https://www.adanienterprises.com/-/media/Project/Enterprises/Investors/corporate-governance/Scheme-of-Arrangement-between-AEL-and-AGEL/NCLT-Order-dated-16022018.pdf); the NCLT case record identifies the petition [here](https://archive.nclt.gov.in/content/ms-adani-green-energy-ltd). NSE's [June 2018 market review](https://nsearchives.nseindia.com/web/sites/default/files/inline-files/NSE_Market_Pulse_Jun2018_0.pdf) records AGEL's 18 June listing. The detached prelisting value is an MSCI-inspired model convention, not an observed claim price or evidence of NIFTY's 2018 treatment; the [MSCI January 2020 methodology](https://www.msci.com/eqb/methodology/meth_docs/MSCI_CEMethodology_Jan2020.pdf) is cited only for that modeling convention.

## Exact remaining blockers

- **A-M and B-M:** the 2018-04-30 signal cannot certify a ranking. The blocker summary identifies missing adjusted-close windows from TejHQ for ABCAPITAL, GICRE, GODREJAGRO, ICICIGI and SBILIFE, plus unresolved signal events for GRASIM (2017-07-19; vendor event ISIN differs from the active identity), HINDPETRO (2018-02-28 dividend has no verified amount), IBVENTURES (2018-02-09 rights terms/factor treatment unresolved), and IDFCBANK (2018-02-28 and 2018-03-08; debt-event classification remains an inference). Each row records source, entity/ISIN, rule input, date span, attempted resolution, impact, and hashed dependency keys in [the grouped blocker ledger](nifty200_cycle2_dependency_blockers_2026-11-02.json). The full row-level dependency cache remains local.
- **A-Q and B-Q:** account execution stops before the 2018-06-21 JUBLFOOD 1:1 bonus. The accounts held 19 and 21 JUBLFOOD shares, respectively, at the 2018-06-20 close. No bonus fill or post-event mark is fabricated. Their 2018-06-29 signal schedule also remains blocked by the listed signal dependencies.

The non-P&L [candidate dependency audit](nifty200_candidate_dependency_audit_2026-11-02.json) contains 156,381 exact dependency rows over the four frozen schedules. The 2018-04-30 monthly and 2018-06-29 quarterly blockers are candidate-specific. There is no blanket status-column or market-wide corporate-action gate. The corrected calendar comparison has 2,183 cash sessions and 2,183 NIFTY 200 TRI sessions with an exact date-set match; its 18 official NSE EOD additions and special sessions are documented in the [calendar reconciliation](nifty200_benchmark_calendar_reconciliation_2026-11-01.json). Membership replay has zero failed batches in this run's audit.

## Decision and reproduction

No configuration establishes the 20% CAGR objective or a full-period result. The B cases are only slightly ahead of the matched TRI in their short 50 bps prefixes and fall behind at 100 bps; this is not evidence of a durable edge. Annual/fold returns, full-period CAGR, recovery after the prefix, capacity, and a calibrated break-even cost remain unmeasured. No ranking or deployment recommendation is made.

Reproduce from the repository root after making the source caches named in the manifest available locally:

```powershell
python work/audit_strategy_dependencies.py
python work/advance_nifty200_cash_prefixes.py
```

The [compact actual-results summary](nifty200_cycle2_actual_results_2026-11-02.json), [20-case experiment register](experiment_register_cycle2_2026-11-02.csv), [cumulative register](experiment_register_cumulative_2026-11-02.csv), [cache manifest](nifty200_signal_cache_manifest_cycle2_2026-11-02.json), and [code/schema/source hash manifest](nifty200_cycle2_source_code_schema_manifest_2026-11-02.json) preserve the reviewed aggregate outputs. Raw source bars, detailed signal-dependency rows, and row-level account order/equity/event/position ledgers remain local; the manifest records hashes for the local artifacts.

The prior 2018-04-04 checkpoint is preserved at [the archived pre-AGEL stop](archive/nifty200_sequential_account_checkpoint_pre_agel_2026-11-02.md). The AGEL valuation convention and source caveats are preregistered in the [valuation protocol](nifty200_agel_valuation_protocol_2026-11-02.md).
