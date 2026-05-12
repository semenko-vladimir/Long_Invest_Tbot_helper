# Research Terminal Foundation

This proposal defines the next architecture phase for Tbot v1: a local long-term investment research terminal. It follows the sandbox-first investor-assistant rules in `README.md` and `PROJECT_INSTRUCTIONS.md`.

## Target Workflow

1. User enters a ticker in Telegram or the local web terminal.
2. The app resolves instrument identity through available local and broker data.
3. Data adapters collect available long-term research inputs.
4. The research layer records data freshness, gaps, and confidence.
5. The UI shows a structured long-term research summary.

The workflow must not create broker orders, generate runtime trading signals, or provide personal investment advice.

## Proposed Modules

- `TickerResearchService`: validates and resolves a ticker, coordinates data collection, and returns normalized research inputs.
- `ResearchReportService`: builds the final structured report from normalized data, gaps, and optional future analysis layers.
- `DataSourceAdapter`: interface for source adapters with source name, freshness metadata, and structured result/error output.
- `TInvestDataAdapter`: first adapter for instrument identity, current market price, portfolio/watchlist context, and dividends available through T-Invest.
- Future `LocalLLMAdapter`: optional local-only analysis adapter behind an explicit service boundary; it must produce structured output with confidence, data gaps, freshness notes, and hallucination-safety checks.
- Future `CrucixAdapter` or `MacroAnalysisService`: optional macro/sector/risk context provider, kept separate from broker/order services.

These modules should live outside manual order execution paths and should not import or call broker order placement APIs.

## Local LLM Model Decision

Decision date: 2026-05-11.

Preferred future model for `LocalLLMAdapter`:

- `Qwen/Qwen3-235B-A22B-Instruct-2507-FP8`

This is a recorded architecture preference only. It does not enable LLM runtime
behavior, add a dependency, create ratings, generate trading signals, or connect
LLM output to broker orders. When implemented later, serve it behind an
OpenAI-compatible local or private VM endpoint, preferably via vLLM or SGLang.

## Data Categories

Research reports should be designed to support these categories as sources become available:

- company profile;
- instrument identity;
- current market price;
- financials;
- dividends;
- sector and industry;
- competitors;
- macro context;
- news and OSINT;
- risks;
- data gaps;
- freshness metadata.

Missing data is acceptable and should be shown explicitly instead of guessed.

## Structured Report Shape

Future implementations should return a structured report similar to:

```text
ResearchReport
- ticker
- instrument_identity
- generated_at
- sources[]
- freshness
- company_profile
- market_snapshot
- financials
- dividends
- sector_industry
- competitors
- macro_context
- news_osint
- risks[]
- data_gaps[]
- errors[]
- educational_rating: null by default
- confidence
- disclaimer
```

The first implementation should keep `educational_rating` empty or absent. Ratings are a future capability, not part of the current v1 runtime.

Implemented foundation entries:

- `GET /api/research/{ticker}` returns this report shape as JSON.
- `GET /api/research` provides a minimal local read-only web entry with a ticker input and JSON report display.
- Telegram supports `/research <TICKER>` and `research <TICKER>` for a compact read-only text summary.
- Local SQLite research snapshots store generated report JSON, source names, gap/error counts, and timestamps when persistence is available.
- `GET /api/research/snapshots` and `GET /api/research/snapshots/{id}` expose read-only snapshot history.

These entries return partial reports with explicit `data_gaps` and `errors` when a source is missing or fails, rather than guessing unavailable data. They do not create broker orders, provide trading signals, or compute ratings.

## Future Educational Ratings

Long-term educational ratings may be added later:

- `BUY`;
- `HOLD`;
- `SELL`;
- `WATCH`;
- `AVOID`.

They must be educational analytical labels only, not personal investment advice. They must never trigger broker orders and must never be wired into `OrderService`, manual order handlers, strategy schedulers, or broker adapters.

If ratings are added later, they should include rationale, confidence, time horizon, source freshness, and data gaps.

## Safety Boundaries

- No auto-trading.
- No broker orders from research reports.
- No runtime trading signals in the current v1.
- No personal investment advice.
- Manual buy/sell remains a separate user-confirmed path.
- Do not weaken `APP_MODE`, production `TOKEN`, or `ALLOW_PROD_TRADING` guards.
- Do not weaken `ModeService`, `OrderService`, `TInvestBroker`, or manual order safety checks.
- Do not reactivate legacy signal/strategy/ML/GPT/LSTM/chart modules for this foundation work.

## Test Strategy

Future implementation PRs should add focused unit tests for:

- ticker normalization and not-found/ambiguous handling;
- adapter success, partial data, stale data, and source errors;
- report assembly with explicit data gaps;
- no calls into order placement services;
- rating fields remaining absent/empty until a dedicated rating PR;
- local snapshot save/list/detail behavior without storing tokens or secrets;
- stable rendering in Telegram/web handlers once UI is added.

Use:

```powershell
.\venv312\Scripts\python.exe -m unittest discover -q
```

## Phased Implementation Plan

1. Add pure schemas/dataclasses and adapter interface with unit tests; no UI and no broker orders.
2. Add `TInvestDataAdapter` for identity, price, and dividend inputs using read-only broker APIs.
3. Add `TickerResearchService` and `ResearchReportService` to assemble reports with gaps and freshness metadata.
4. Add read-only web endpoint/page for ticker research. Implemented for the first API/web entry.
5. Add minimal read-only Telegram ticker research command. Implemented for compact summaries.
6. Add optional local persistence for report snapshots if useful. Implemented for local SQLite snapshots and read-only history endpoints.
7. Add optional macro/OSINT adapters behind the same `DataSourceAdapter` contract.
8. Add optional local LLM analysis adapter only after structured output, freshness, confidence, and hallucination-safety rules are implemented.
9. Add educational ratings only in a separate explicit PR with no broker-order integration.
