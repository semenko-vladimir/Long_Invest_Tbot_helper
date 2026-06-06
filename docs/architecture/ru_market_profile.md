# Russian Market Data Profile

Status: proposed source profile  
Scope: future DataHubLite Russian-market coverage  
Created: 2026-05-31  
Implementation status: not implemented

## Purpose

This document defines the Russian market profile that future DataHubLite work
should target. It is a source and topic plan, not an implementation.

The profile is focused on a private long-term investor using Tbot v1 locally.
It prioritizes MOEX-listed instruments, T-Invest broker-facing data, CBR macro
context, and later issuer disclosures.

## Safety Boundary

All sources in this profile are read-only. They must not create trading signals,
ratings, recommendations, order previews, or broker orders.

Data from this profile may support educational research, charts, portfolio
views, and data-quality notes. It must not be turned into BUY/HOLD/SELL/WATCH/
AVOID logic or auto-trading.

## Source Roles

| Source | Role | Runtime status |
| --- | --- | --- |
| T-Invest | Primary broker-facing source for portfolio, current/last prices, instruments, dividends/coupons when available, trading status, and current broker availability. | Already used in Tbot. |
| MOEX ISS | Public exchange source for MOEX reference data, board/classcode mapping, historical daily candles, index context, and fallback/verification. | Already partially implemented. |
| CBR | Macro source for key rate and official FX rates such as USD/RUB and CNY/RUB. | Planned. |
| Issuer disclosures | Later source for issuer profile, reports, corporate actions, and disclosure freshness. | Planned later. |
| Local curated data | Small owner-maintained facts where public adapters are incomplete. | Already partially represented by local fundamentals. |

Implementation tasks must verify current official API documentation before
adding new source clients.

## Market Assumptions

The first profile should assume:

- market scope: Russian instruments available through MOEX and/or T-Invest;
- main currency: RUB;
- important FX context: USD/RUB and CNY/RUB;
- main equity index context: IMOEX;
- optional index context: RTSI, RGBI, sector indexes later;
- ticker normalization: uppercase MOEX-style ticker strings;
- primary board for ordinary shares: `TQBR` unless metadata says otherwise;
- missing or delayed public data is normal and must be visible.

## Topic Catalog

### Instrument Topics

| Topic | Description | Preferred source |
| --- | --- | --- |
| `ru:instrument:{ticker}` | Instrument identity: name, ticker, FIGI, ISIN, lot size, exchange, board, currency. | T-Invest, then MOEX ISS |
| `ru:issuer:{ticker}:profile` | Issuer profile, sector, industry, description, website if available. | Local curated data, issuer source later |
| `ru:issuer:{ticker}:dividends` | Dividend history and expected events where available. | T-Invest, issuer source later |

### Market Data Topics

| Topic | Description | Preferred source |
| --- | --- | --- |
| `ru:quote:{ticker}` | Latest available quote or last price with freshness metadata. | T-Invest |
| `ru:candles:{ticker}:1d` | Daily historical candles. | T-Invest, then MOEX ISS |
| `ru:macro:moex:index:IMOEX` | MOEX Russia Index context. | MOEX ISS |
| `ru:macro:moex:index:RTSI` | RTS Index context. | MOEX ISS |
| `ru:macro:moex:index:RGBI` | Government bond index context, later. | MOEX ISS |

### Portfolio Topics

| Topic | Description | Preferred source |
| --- | --- | --- |
| `ru:portfolio:summary:default` | Current portfolio summary for the single configured owner. | T-Invest + local DB |
| `ru:portfolio:position:{ticker}` | Current quantity, average position metadata if available, valuation context. | T-Invest + local DB |
| `ru:watchlist:default` | Local watchlist tickers. | Local SQLite |

Portfolio topics are read-only data topics. They must never issue orders.

### CBR Macro Topics

| Topic | Description | Preferred source |
| --- | --- | --- |
| `ru:macro:cbr:key_rate` | CBR key rate and decision date. | CBR |
| `ru:macro:cbr:usd_rub` | Official USD/RUB reference rate. | CBR |
| `ru:macro:cbr:cny_rub` | Official CNY/RUB reference rate. | CBR |

CBR topics should expose `as_of_date` clearly because official macro and FX data
are date-based rather than live market ticks.

## Freshness Profile

Freshness values should be explicit and user-visible:

| Freshness | Meaning |
| --- | --- |
| `current` | Broker-facing source reports current or latest available value. |
| `latest_available` | Source has a latest observation, but it is not real-time. |
| `delayed_public_data` | Public exchange data with expected delay. |
| `stale` | Cache entry is older than TTL but may be shown as fallback. |
| `partial` | Some fields are present, but important fields are missing. |
| `unavailable` | Source could not provide usable data. |

`delay_status` should distinguish broker API data, delayed public MOEX data,
official date-based CBR data, local curated data, and cache fallback.

## Data Quality Rules

Adapters should:

- validate ticker format before network calls;
- normalize currencies, especially legacy `SUR`/`RUR` values to `RUB`;
- include source-specific `as_of_date`;
- preserve board and classcode metadata where available;
- report empty source tables as data gaps;
- sanitize network and parsing errors;
- redact environment secret values from errors;
- avoid raw external payloads in service return objects;
- keep source-specific uncertainty visible.

## Source Priority Rules

Suggested source priority:

1. T-Invest for broker-facing portfolio, operational instrument identity, quotes,
   trading status, and dividends/coupons when available.
2. MOEX ISS for public MOEX reference data, historical daily candles, index
   context, and verification/fallback.
3. CBR for official macro and FX context.
4. Local curated data for owner-maintained issuer facts and missing profile
   fields.
5. Issuer disclosures later for primary issuer filings and corporate actions.

Source priority does not override freshness metadata. A stale primary source
should be labeled stale, not silently treated as current.

## Initial Implementation Candidate

The safest first useful slice is:

```text
ru:instrument:{ticker}
ru:candles:{ticker}:1d
ru:macro:moex:index:IMOEX
ru:macro:cbr:key_rate
ru:macro:cbr:usd_rub
ru:macro:cbr:cny_rub
```

This slice stays read-only and mostly builds on existing MOEX/chart/research
patterns. It does not require order-flow changes.

## Later Expansion

Later phases can add:

- issuer disclosure adapters;
- richer dividend/corporate-action history;
- bond-specific topics;
- OFZ/RGBI context;
- sector/index comparison topics;
- local manually curated issuer notes;
- data-quality dashboards in the web terminal.

Each expansion should include explicit source metadata and should remain
non-advisory.

## Open Questions

1. Which official CBR endpoint shape should be used for the first adapter?
2. Should CBR data be stored in the generic DataHub cache only, or also in a
   dedicated macro table later?
3. Which MOEX indexes should be default besides `IMOEX` and `RTSI`?
4. Should issuer disclosures wait until the generic cache and topic registry are
   stable?
5. Should local curated issuer facts remain JSON, move to SQLite, or support
   both?

