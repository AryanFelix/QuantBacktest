# CESC composite-scheme signal dependency — 2018-10-30

The TejHQ CESC action is `Composite Scheme Of Arrangement`, ex-date 2018-10-30 and record date 2018-10-31. CESC's 12 October 2018 exchange filing says the approved effective part was the non-power retail and venture businesses: each 10 CESC shares entitled the holder to six ₹5 Spencer's Retail shares and two ₹10 CESC Ventures shares. The generation-business demerger remained conditional on regulatory approval and is not included in this event.

CESC's FY2018-19 annual report says the two entitlements were allotted on 2018-11-14. NSE's January 2019 Market Pulse lists both resulting shares as available for trading on 2019-01-25: Spencer's Retail (ISIN INE020801028) and CESC Ventures (ISIN INE425Y01011, later renamed RPSG Ventures). Thus the share claim is source-backed, while its market value was unobserved between the scheme ex-date and the child listings.

Signal handling uses the source entitlement ratios only for return windows that begin before the ex-date. After both children list, A uses observed parent-plus-child adjusted endpoint wealth; B keeps its frozen return numerator and uses a conservative volatility lower bound while daily child marks were unavailable. A signal endpoint before 2019-01-25 remains unresolved; no future listing quote is pulled backward. The account engine still blocks if an owned CESC position crosses the event without a funded entitlement and mark model.

Sources:

- [MSE CESC corporate-action history](https://www.msei.in/corporates/corporate-securities-information/corporate-update/default?symbol=CESC&type=4&vmode=vm): 2018-10-30 ex-date and 2018-10-31 record date.
- [CESC 12 October 2018 exchange filing](https://www.cesc.co.in/storage/uploads/stock_exchange_intimation/NSE_PRESS_121018.pdf): effective businesses and 6:10 / 2:10 share ratios.
- [CESC FY2018-19 annual report](https://www.cesc.co.in/storage/uploads/annreport/CESC_AR_2019.pdf): 2018-11-14 allotment and subsequent exchange listing.
- [NSE January 2019 Market Pulse](https://nsearchives.nseindia.com/web/sites/default/files/inline-files/NSE_Market_Pulse_Jan2019_2.pdf): both shares available for trading from 2019-01-25.
