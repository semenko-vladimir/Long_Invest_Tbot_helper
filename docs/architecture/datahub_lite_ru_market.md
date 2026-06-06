# DataHubLite Russian Market Architecture

Status: proposed architecture  
Scope: future Tbot v1 data-access layer for Russian market research  
Created: 2026-05-31  
Implementation status: not implemented

## Purpose

DataHubLite is a small Python-native data layer for Tbot v1. It is inspired only
by the architectural pattern of topic-based data access and adapter-based data
retrieval. It must be implemented from scratch inside this repository.

The purpose is to centralize read-only market, portfolio, macro, and issuer data
access so Telegram handlers and FastAPI routers do not call external APIs
directly. DataHubLite should make the same market data reusable across Telegram,
the local web terminal, portfolio views, charts, and research summaries.

## Non-goals

DataHubLite must not:

- copy code from FinceptTerminal or any other external project;
- add FinceptTerminal as a submodule or runtime dependency;
- add AGPL source files or copied snippets;
- integrate the C++/Qt application;
- add trading signals;
- add BUY/HOLD/SELL/WATCH/AVOID runtime logic;
- add auto-trading;
- create broker order previews or broker orders;
- weaken `ModeService`, `OrderService`, `TradingPolicyService`,
  Telegram order handlers, or `TInvestBroker`;
- enable production trading;
- add heavy dependencies by default.

## Current Repository Fit

The repository already has pieces that should be preserved and reused:

| Existing area | Current role | Future fit |
| --- | --- | --- |
| `app/research/` | Read-only ticker research adapters and schemas. | Keep deterministic research assembly; DataHubLite can feed it or reuse its adapters. |
| `app/integrations/moex_iss.py` | Small read-only MOEX ISS client. | Candidate adapter behind a `MOEXISSAdapter` topic provider. |
| `app/charts/` | Read-only candle adapters, chart services, and SQLite candle cache. | Candidate first cache-backed topic area for `ru:candles:*`. |
| `app/services/` | Shared business logic used by Telegram and web. | DataHubLite should live as service-layer infrastructure, not inside handlers/routes. |
| `app/backend/web/` and `app/client/handlers/` | Thin UI entrypoints. | Should consume service methods, not adapters directly. |
| SQLite user database | Local single-owner storage. | Store cache rows and freshness metadata scoped to the selected local user database. |

## Concept

DataHubLite should expose topic-based data access:

```text
UI or service asks for topic -> DataHubLite checks cache -> adapter fetches if needed -> typed result returned
```

Topic examples:

```text
ru:instrument:SBER
ru:quote:SBER
ru:candles:SBER:1d
ru:portfolio:summary:default
ru:macro:cbr:key_rate
ru:macro:cbr:usd_rub
ru:macro:cbr:cny_rub
ru:macro:moex:index:IMOEX
ru:issuer:SBER:profile
ru:issuer:SBER:dividends
```

Every returned result should carry metadata:

- `topic`;
- `source`;
- `fetched_at`;
- `as_of_date`;
- `freshness`;
- `delay_status`;
- `ttl_seconds`;
- `data_gaps`;
- `errors`;
- `cached`;
- `cache_key`.

Missing values must be reported as data gaps, not guessed.

## Proposed Package Layout

Initial implementation should be small and dependency-free:

```text
app/datahub/
  __init__.py
  topics.py
  schemas.py
  service.py
  cache.py
  policies.py
  adapters/
    __init__.py
    base.py
    tinvest.py
    moex_iss.py
    cbr.py
```

This layout is a planning target, not a current implementation requirement. A
future task may adjust names to match local conventions.

## Boundaries

DataHubLite should be read-only by default. It may read portfolio data through
existing services or broker adapters, but it must not create order previews,
confirmations, or executions.

Forbidden imports in `app/datahub/`:

- `app.services.orders`;
- `app.services.trading_policy`;
- Telegram order handlers;
- legacy signal or strategy modules;
- LLM/provider modules;
- heavy analytics/ML packages.

Allowed dependencies:

- existing typed schemas where they fit;
- `app.integrations.moex_iss` for public MOEX data;
- read-only parts of `app.integrations.tinvest` only through a narrow adapter;
- selected user database session factory;
- standard-library HTTP tools unless a future task explicitly approves another dependency.

## Topic Registry

Topics should be declared in one place instead of scattered string formatting.

Suggested topic groups:

| Group | Example | Primary source | Fallback source |
| --- | --- | --- | --- |
| Instrument identity | `ru:instrument:SBER` | T-Invest | MOEX ISS |
| Current quote | `ru:quote:SBER` | T-Invest | MOEX ISS delayed data |
| Daily candles | `ru:candles:SBER:1d` | T-Invest | MOEX ISS |
| Portfolio summary | `ru:portfolio:summary:default` | T-Invest + local DB | local DB snapshot later |
| CBR macro | `ru:macro:cbr:key_rate` | CBR adapter | cache only |
| FX rates | `ru:macro:cbr:usd_rub` | CBR adapter | cache only |
| MOEX index | `ru:macro:moex:index:IMOEX` | MOEX ISS | cache only |
| Issuer profile | `ru:issuer:SBER:profile` | local data / issuer adapter later | MOEX metadata |
| Issuer dividends | `ru:issuer:SBER:dividends` | T-Invest | issuer/MOEX source later |

Topics should be normalized to uppercase Russian-market ticker symbols. Invalid
tickers should fail before adapter calls and return a high-severity data gap.

## TTL Policy

TTL should be explicit and conservative. The first implementation can keep
policy in Python constants:

| Topic group | Suggested TTL | Notes |
| --- | --- | --- |
| `ru:instrument:*` | 7 days | Identity/reference data changes rarely. |
| `ru:quote:*` | 30-120 seconds | T-Invest may be current; MOEX ISS remains delayed public data. |
| `ru:candles:*:1d` | 6-24 hours | Daily history can refresh after close or on demand. |
| `ru:portfolio:*` | 15-60 seconds | Broker-facing portfolio state should stay fresh. |
| `ru:macro:cbr:key_rate` | 12-24 hours | Changes on scheduled CBR decisions. |
| `ru:macro:cbr:*_rub` | 12-24 hours | Daily official rates; implementation must verify source freshness. |
| `ru:macro:moex:index:*` | 5-15 minutes | Delayed public index context. |
| `ru:issuer:*:profile` | 7-30 days | Later issuer-disclosure source should set `as_of_date`. |
| `ru:issuer:*:dividends` | 12-24 hours | Should expose source and data gaps. |

TTL expiration allows refetch. It must not imply real-time quality.

## SQLite Cache

Use the selected local user's SQLite database. Avoid global `SessionLocal()` in
new service code. Cache tables should be separate from existing domain tables.

Suggested table shape:

```text
datahub_cache
  id
  topic
  source
  payload_json
  fetched_at
  as_of_date
  freshness
  delay_status
  ttl_seconds
  expires_at
  data_gaps_json
  errors_json
  created_at
  updated_at
```

Cache keys should include:

- normalized topic;
- source;
- adapter version when relevant;
- owner database scope implicitly through the selected SQLite file.

Do not cache secrets, tokens, raw broker responses, or cookies.

## Adapter Contract

Adapters should return typed DataHub results, not raw external payloads.

Suggested interface:

```python
class DataHubAdapter(Protocol):
    source_name: str

    def supports(self, topic: DataHubTopic) -> bool:
        ...

    def fetch(self, topic: DataHubTopic) -> DataHubResult:
        ...
```

Adapter rules:

- sanitize errors before returning them;
- include source and freshness metadata;
- never import order services;
- never place or preview broker orders;
- return data gaps for missing fields;
- keep raw external payloads out of UI templates.

## Service Contract

`DataHubLiteService` should be the only normal read path:

```python
class DataHubLiteService:
    def get(self, topic: str, *, refresh: bool = False) -> DataHubResult:
        ...

    def get_many(self, topics: Sequence[str], *, refresh: bool = False) -> list[DataHubResult]:
        ...
```

The service should:

- parse and validate topic names;
- apply TTL policy;
- read valid cache entries first;
- call one adapter at a time according to source priority;
- persist cacheable results;
- return structured gaps/errors when no source can satisfy the topic.

## UI Integration Pattern

Telegram handlers and FastAPI routes should remain thin:

```text
Telegram/FastAPI -> existing service method -> DataHubLiteService -> adapters/cache
```

The first UI integrations should be read-only displays only. Do not add
automatic actions based on DataHubLite output.

## Relationship To Research

`app/research/` should remain deterministic and read-only. Future implementation
can either:

- have research adapters call DataHubLite for shared topics; or
- have DataHubLite wrap existing research/MOEX/T-Invest adapters.

The first implementation should avoid large rewrites. Prefer wrapping existing
adapters and moving shared behavior only after tests prove the boundary.

## Relationship To Charts

The existing `price_candles` cache already covers a useful subset of DataHubLite
behavior. A future implementation should not duplicate candle storage
unnecessarily. It can treat chart candle cache as the first backing store for
`ru:candles:{ticker}:1d` and add a generic cache only for non-candle topics.

## Relationship To Tagged Factor Terminal

A future web-terminal direction is owner-managed ticker tagging for long-term
monitoring factors. DataHubLite can later provide the read-only data links behind
those tags without making tags into signals.

Examples:

- a tag dictionary entry such as `aluminum`, `coal`, `molybdenum`, `rates`,
  `fx`, `china`, or `sanctions`;
- many tags attached to one ticker;
- a company-specific ticker-tag note explaining why the factor matters for that
  ticker;
- read-only data coverage for a tag, such as LME, SMM, MOEX, T-Invest, local
  files, or other structured datasets;
- tag views that show related tickers, portfolio/watchlist exposure, source
  freshness, data gaps, and cached result status.

DataHubLite outputs used by tagged views must remain observational. They must
not create broker previews, broker orders, runtime trading signals, or personal
investment recommendations.

## Safety Tests To Add

Future implementation should add tests that assert:

- `app/datahub/` imports no order, strategy, signal, ML, or LLM modules;
- invalid tickers do not call external adapters;
- adapter errors are sanitized and do not leak secrets;
- cache TTL behavior is deterministic;
- Telegram/web consumers do not receive raw external API payloads;
- DataHubLite output never calls `OrderService.preview()` or
  `OrderService.execute()`;
- production trading flags are unchanged by DataHubLite.

## Implementation Principles

1. Start with topic parsing and schemas.
2. Add cache after schemas are stable.
3. Wrap one existing read-only adapter first.
4. Keep UI changes separate from adapter/cache changes.
5. Add focused tests at each step.
6. Run the full unittest suite before merging shared service changes.
