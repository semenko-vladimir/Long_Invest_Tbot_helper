# DataHubLite Russian Market Task Backlog

Status: proposed implementation backlog  
Scope: future incremental implementation of DataHubLite for Tbot v1  
Created: 2026-05-31  
Implementation status: not implemented

## Guardrails

This backlog is documentation for future tasks. Do not implement these items
unless a later task explicitly asks for a specific scope.

Every task must preserve:

- sandbox-first defaults;
- manual `preview -> confirmation -> execute` order flow;
- production trading blocks;
- read-only adapter behavior;
- CSRF protection for web POST routes;
- single-owner `users.json` / `UserContext` database routing;
- default dependency isolation.

Do not add:

- trading signals;
- BUY/HOLD/SELL/WATCH/AVOID runtime logic;
- auto-trading;
- broker order execution from analysis, reminders, or DataHubLite output;
- copied FinceptTerminal code;
- AGPL source files;
- heavy dependencies by default.

## Execution Order

Recommended order:

1. R1, R2, R3
2. F1, F2
3. F3
4. F4, F5
5. F6
6. F7, F8
7. R4
8. F9

Run focused tests after each item. Run the full suite after shared service,
cache, or UI integration changes:

```powershell
.\venv312\Scripts\python.exe -m unittest discover -q
```

## Refactor Items

### R1 - Define DataHubLite Schemas And Topic Parser

Goal: add dependency-free schemas for topics, results, freshness metadata, data
gaps, and cache policy.

Affected modules/files:

- new `app/datahub/__init__.py`
- new `app/datahub/topics.py`
- new `app/datahub/schemas.py`
- new tests under `tests/`

Risk level: low

Dependencies: none

Acceptance checks:

- valid examples such as `ru:instrument:SBER` and
  `ru:macro:cbr:usd_rub` parse deterministically;
- invalid tickers return validation errors without network calls;
- schemas do not import order, signal, strategy, LLM, or ML modules.

### R2 - Add TTL Policy And Cache Interface

Goal: define topic-group TTL defaults and a cache protocol before adding
persistence.

Affected modules/files:

- new `app/datahub/policies.py`
- new `app/datahub/cache.py`
- tests for TTL selection and cache-key normalization

Risk level: low

Dependencies: R1

Acceptance checks:

- topic groups map to explicit TTL values;
- cache keys include normalized topic and source;
- stale values are detectable without refetching;
- no SQLite migration is required yet if the first cache is in-memory/fake for tests.

### R3 - Add Import-Boundary Safety Tests

Goal: prevent DataHubLite from becoming a trading, signal, strategy, LLM, or ML
boundary.

Affected modules/files:

- new or updated tests such as `tests/test_datahub_boundaries.py`

Risk level: low

Dependencies: R1

Acceptance checks:

- `app/datahub/**` imports no `OrderService`, order handlers, signal modules,
  strategy modules, `g4f`, TensorFlow/Keras, or broker order methods;
- future violations fail tests quickly.

### R4 - Consolidate Shared Metadata Conventions

Goal: align DataHubLite result metadata with existing research/chart metadata
without forcing a broad schema rewrite.

Affected modules/files:

- `app/datahub/schemas.py`
- possibly `app/data_sources/schemas.py`
- selected research/chart tests if adapters are wrapped

Risk level: medium

Dependencies: F1, F2, F3

Acceptance checks:

- source, fetched/as-of dates, freshness, delay status, gaps, and errors are
  named consistently;
- existing research and chart tests remain green;
- raw external API payloads stay out of templates.

## Feature Items

### F1 - Wrap Existing MOEX ISS Read-Only Data

Goal: add a DataHubLite adapter for existing MOEX ISS instrument metadata,
market data, index context, and daily candles.

Affected modules/files:

- new `app/datahub/adapters/base.py`
- new `app/datahub/adapters/moex_iss.py`
- existing `app/integrations/moex_iss.py`
- existing `app/research/moex_iss_adapter.py` only if wrapping is cleaner
- tests for adapter success, empty data, invalid ticker, and sanitized errors

Risk level: medium

Dependencies: R1, R2, R3

Acceptance checks:

- supports `ru:instrument:{ticker}`, `ru:candles:{ticker}:1d`, and
  `ru:macro:moex:index:{ticker}`;
- no broker token is used;
- MOEX ISS delayed public data is labeled explicitly;
- invalid tickers do not call `urlopen`;
- sanitized errors do not leak environment secrets.

### F2 - Add DataHubLite Service Orchestrator

Goal: implement `DataHubLiteService.get()` and `get_many()` over topic parsing,
TTL policy, cache lookup, adapter selection, and structured fallback errors.

Affected modules/files:

- new `app/datahub/service.py`
- new service tests with fake adapters/cache

Risk level: medium

Dependencies: R1, R2, R3

Acceptance checks:

- valid fresh cache entries avoid adapter calls;
- `refresh=True` bypasses valid cache;
- adapter errors become structured result errors;
- unsupported topics return data gaps without crashing;
- service does not import UI handlers or order services.

### F3 - Add SQLite Cache Persistence

Goal: persist generic non-candle DataHubLite results in the selected local
user database.

Affected modules/files:

- `app/backend/models/trading.py` or a new model module if local convention
  supports it
- new Alembic migration
- `app/datahub/cache.py`
- tests using temporary SQLite databases

Risk level: medium

Dependencies: F2

Acceptance checks:

- cache reads/writes use the selected user's `SessionFactory`;
- no new direct global `SessionLocal()` calls are introduced in service code;
- payload JSON stores only sanitized typed results;
- expired cache entries can be returned only as stale fallback when policy
  allows it;
- migration is reversible through normal Alembic flow.

### F4 - Route Daily Candle Topics Through Existing Candle Cache

Goal: avoid duplicating candle storage by using the existing `price_candles`
repository for `ru:candles:{ticker}:1d`.

Affected modules/files:

- `app/datahub/adapters/moex_iss.py`
- `app/charts/repository.py`
- `app/charts/services.py` if a small service seam is needed
- tests around candle-cache reuse

Risk level: medium

Dependencies: F1, F2

Acceptance checks:

- daily candles can be served from existing cache when fresh enough;
- MOEX/T-Invest source metadata remains visible;
- no chart behavior changes unless a later task asks for UI changes.

### F5 - Add CBR Read-Only Adapter

Goal: add official date-based macro topics for CBR key rate, USD/RUB, and
CNY/RUB after verifying current official CBR API documentation.

Affected modules/files:

- new `app/datahub/adapters/cbr.py`
- `app/datahub/topics.py`
- tests with mocked HTTP responses

Risk level: medium

Dependencies: F2, F3 preferred

Acceptance checks:

- supports `ru:macro:cbr:key_rate`, `ru:macro:cbr:usd_rub`, and
  `ru:macro:cbr:cny_rub`;
- returns `as_of_date` and official/date-based freshness metadata;
- network errors are sanitized and reported as data gaps;
- no heavy dependencies are added.

### F6 - Add T-Invest Read-Only Adapter Wrapper

Goal: expose broker-facing read-only topics through a narrow adapter without
making DataHubLite an order boundary.

Affected modules/files:

- new `app/datahub/adapters/tinvest.py`
- existing `app/integrations/tinvest.py`
- possibly existing portfolio/research services
- tests with fake broker adapter

Risk level: high

Dependencies: F2, R3

Acceptance checks:

- supports read-only identity, quote, portfolio summary, and position topics;
- adapter exposes no `preview`, `execute`, `buy`, `sell`, or `post_order`
  methods;
- production trading settings are not modified;
- order safety tests remain green.

### F7 - Use DataHubLite In Research Internals

Goal: let read-only research reuse DataHubLite topics without changing
research output semantics.

Affected modules/files:

- `app/research/services.py`
- selected research adapters or a new bridge adapter
- `tests/test_research_*`

Risk level: medium

Dependencies: F1, F2, F5 optional, F6 optional

Acceptance checks:

- `/research` Telegram and API outputs stay non-advisory;
- educational rating remains empty/null unless a later task explicitly changes
  it;
- data gaps and source metadata remain visible;
- no LLM/order/signal imports enter `app/research/`.

### F8 - Add Read-Only Web Diagnostics For DataHubLite

Goal: show cache/source diagnostics in the local web terminal settings or a
read-only diagnostics page.

Affected modules/files:

- `app/backend/web/routes.py`
- `app/backend/web/templates/pages/settings.html` or a new diagnostics page
- `app/services/settings_view.py` if using Settings
- tests for web route rendering and CSRF unaffected

Risk level: medium

Dependencies: F2, F3

Acceptance checks:

- diagnostics are read-only;
- no secrets are displayed;
- no POST route is added unless protected by CSRF;
- source freshness, cache age, and data gaps are visible.

### F9 - Add Issuer Disclosure Adapter Planning Spike

Goal: inspect official issuer disclosure source options and produce a follow-up
design before implementation.

Affected modules/files:

- new planning doc under `docs/architecture/` or `docs/roadmap/`

Risk level: low

Dependencies: F1, F5 preferred

Acceptance checks:

- no runtime code changes;
- no copied external code;
- source license/terms are reviewed;
- proposed topics, TTL, and data quality rules are documented.

## Verification Matrix

| Change type | Minimum verification |
| --- | --- |
| Schemas/topic parser only | Focused unit tests. |
| Adapter addition | Focused adapter tests with mocked network and sanitized errors. |
| Cache persistence | Temporary SQLite tests plus migration check. |
| Service orchestration | Fake adapter/cache tests plus boundary tests. |
| Research integration | Research API/Telegram tests. |
| Web integration | Web route, settings view, and CSRF tests. |
| T-Invest adapter | Existing order/mode/trading policy/manual order tests plus focused fake-broker tests. |

## First Safe Task Prompt

Recommended first implementation request:

```text
Implement R1 and R3 only: add DataHubLite topic parsing/schemas and import-boundary tests.
Do not add adapters, cache persistence, UI changes, trading signals, ratings, or broker order behavior.
```

