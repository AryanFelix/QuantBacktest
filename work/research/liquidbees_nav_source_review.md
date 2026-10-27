# LIQUIDBEES daily NAV source review

**Checked:** 2026-10-26  
**Question:** Can official AMFI or Nippon India data supply a daily LIQUIDBEES return history suitable for cash accruals in the backtests?

## Verified from first-party sources

- AMFI's NAV History page offers a text-format query with fund, type, start date, and end date inputs. It states that one download may cover at most 90 days. The visible page does not specify the underlying request parameter names or an API contract. [AMFI NAV Download / History](https://www.amfiindia.com/net-asset-value/nav-download)
- AMFI's public latest-NAV text file identifies the ETF as scheme code `140086`, ISIN `INF732E01037`, name `Nippon India ETF Nifty 1D Rate Liquid BeES`. It separately lists Nippon's newer Growth ETF as scheme `153725`, ISIN `INF204KC1FU1`; that is a different scheme and cannot extend the legacy ETF history. [AMFI latest NAV text](https://www.amfiindia.com/spages/NAVAll.txt)
- Nippon's product page links both **NAV History** and **Dividends**. It describes LIQUIDBEES as a daily-IDCW scheme with compulsory reinvestment; the scheme's stated objective is to track the Nifty 1D Rate Index before expenses, with no guarantee. Its performance disclosure says reported performance uses IDCW-reinvestment NAVs and is based on gross IDCW per unit for this ETF. [Nippon product page](https://mf.nipponindiaim.com/FundsAndPerformance/Pages/NipponIndia-ETF-Nifty-1D-Rate-Liquid-BeES.aspx), [scheme information document](https://mf.nipponindiaim.com/InvestorServices/SIDETF/NipponIndia-ETF-Nifty-1D-Rate-Liquid-BeES.pdf)
- The fund's product page identifies July 8, 2003 as the ETF inception date. The separate Growth ETF page identifies a July 23, 2025 inception, so its Growth NAV is only a short recent series. [Growth ETF page](https://mf.nipponindiaim.com/FundsAndPerformance/Pages/NipponIndia-Nifty-1D-Rate-Liquid-ETF-Growth.aspx)

## What is not yet verified

- The AMFI page is public and renders without a sign-in prompt, but I did not verify whether its historical download endpoint requires cookies or other headers. The page itself documents the 90-day limit, not the wire-level query fields.
- A direct call to the AMFI portal history endpoint was not accessible through the web retrieval tool, and the browser session was already in use. Therefore no historical AMFI payload was downloaded or checked for scheme-code coverage, date gaps, or response format in this review.
- Nippon's web-rendered NAV History link and its downloadable output were not exercised. It is not yet verified whether that history returns only the ₹1,000 daily-IDCW NAV, an adjusted/reinvestment NAV, or both.

## Backtest implications

The flat LIQUIDBEES exchange-price candles are not a total-return series. A raw daily IDCW-option NAV can also be insufficient if it is held near face value: a faithful investor return needs the declared IDCW, its ex/record date and reinvestment/allotment treatment, including fractional units. Nippon's published reinvestment-basis performance can serve as a reconciliation target, but the public page does not establish that its downloadable daily NAV history is itself a total-return series.

The next source check should request the AMFI historical text in consecutive windows of at most 90 days, retain the raw responses, filter scheme code `140086` / ISIN `INF732E01037`, and reconcile date coverage and NAV behavior against Nippon's disclosed IDCW and reinvestment terms. Until that is verified, keep the backtests' existing 0% cash-yield treatment; do not fill the 2020 Nifty 1D Rate gap with assumed or synthetic returns. The 2025-launched Growth ETF is useful only for a short recent cross-check, not the multi-year cash series.
