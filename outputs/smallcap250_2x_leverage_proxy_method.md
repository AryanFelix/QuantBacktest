# Synthetic Smallcap 250 daily-2x funding sensitivity — 2026-10-31

## Question and result

Does daily-resetting a 2x long position in NIFTY Smallcap 250 total return produce a reliable 20% result if we accept a much larger drawdown? `smallcap250_2x_leverage_proxy.csv` compares the official Smallcap 250 TRI, a synthetic 2x daily path, NIFTY 50 TRI, and an independently generated 2x NIFTY proxy over matched segments. The daily proxy formula is twice the underlying TRI simple return less financing return. It is an index-level sensitivity, not an executable Indian product or a completed broker backtest.

Funding uses the first-party NIFTY 1D Rate Index daily change wherever both neighboring market sessions exist. During its missing source interval, funding uses the latest previously issued RBI 91-day T-bill cut-off yield on actual calendar days / 360. The transition-day fallback and source coverage are recorded in `work/data/index_daily/smallcap250_2x_proxy_2016_2026.csv`.

Sources: NSE [Nifty Smallcap 250 factsheet](https://www.niftyindices.com/Factsheet/ind_Nifty_Smallcap_250.pdf), [Nifty 1D Rate methodology](https://www.niftyindices.com/Methodology/Method_Nifty_1D_Rate.pdf), and [Nifty50 TR 2x factsheet](https://www.niftyindices.com/Factsheet/Nifty50_TR_2X_Leverage.pdf); RBI [91-day T-bill auction data](https://data-api.dbie.rbihub.in/api/tables/public_finance/r307_auctions_of_91_day_government_of_india_treasury_bills/csv).

## Calibration against the live NIFTY 2x index

The identical formula was calibrated against NSE's live Nifty50 TR 2x Leverage Index from 2016-04-01 through 2026-10-23. Diagnostics: {"funding_source_counts": {"NIFTY_1D_RATE_INDEX": 2434, "RBI_91D_TBILL_PROXY": 182}, "nifty_2x_validation": {"matched_sessions": 2617, "proxy_end_value_indexed_1000": 4812.041670507215, "official_end_value_indexed_1000": 4784.509492474094, "endpoint_difference_pct": 0.5754441092953755, "max_path_difference_pct": 0.5835481419964816, "annualized_daily_tracking_error_pct": 0.03264240771289016}}. The proxy is accepted only if its ending normalized value stays within 3% of the official live index; the path difference and annualized daily tracking error show the remaining model error. This calibration does not validate Smallcap 250 funding when its rate source is missing.

## Execution limits

No Indian Smallcap 250 2x instrument is modeled. A hypothetical MTF purchase would use a different financing rate and stock-level eligibility/margin, plus brokerage, pledge/unpledge, and liquidation rules. Upstox's [Standard MTF price](https://upstox.com/help-center/t-251427/) is ₹20/day per ₹40,000 borrowed, equivalent to 18.25% simple annualized; substituting overnight NIFTY funding materially overstates financed returns. Upstox's [MTF terms](https://upstox.com/help-center/t-251427/) permit positions to be fully or partially squared off for a margin or MTM shortfall. The synthetic index omits management fees, tracking error, ETF premium/discount, market impact, taxes, and actual collateral calls; its drawdown is a loss of index level, not proof that borrowed exposure could be held through it.

An additional `smallcap_mtf_2x` sensitivity charges 18.25% simple annual financing on debt reset to equal account equity at each close, with daily 2x exposure and actual calendar days / 365. This is today's Upstox Standard MTF rate applied uniformly across the full history, not a reconstruction of historical broker bills. The rate converts the published charge of ₹20 per ₹40,000 borrowed per day. It excludes brokerage, pledge/unpledge fees, taxes, margin changes, and forced liquidation; the index-level path assumes those do not interrupt trading. The product is equity-delivery MTF for eligible stocks, not a Smallcap 250 2x instrument.

The full NIFTY Smallcap 250 index launched on 2016-04-01. Its history before the live ETF sample is index evidence, not an investable ETF backtest. The low-cost overnight-funding proxy and MTF sensitivity are research comparisons only; neither establishes a tradeable 20% strategy.
