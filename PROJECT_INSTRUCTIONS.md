# Tbot v1 Project Instructions

These instructions define the durable project rules for future Codex work in Tbot v1.

## Product Framing

Tbot v1 is a local, sandbox-first assistant for one unique private long-term investor. It is a Telegram bot and FastAPI web terminal backed by SQLite and the T-Invest API.

The product direction is a calm local research terminal for long-term investing. It is not an auto-trading bot, signal bot, scalping tool, or investment adviser.

The product is not designed as a multi-user SaaS or shared bot. There is one
unique local owner. `users.json` and `UserContext` are retained as the local
configuration shell for that owner: Telegram chat ID, T-Invest tokens, broker
fee, and the configured SQLite `db_path`. The web terminal selects that single
user through `DEFAULT_WEB_USER_ID` and supports a single local owner token via
`WEB_AUTH_ENABLED` / `WEB_AUTH_TOKEN`. Auth may stay disabled only for a
localhost-only `API_HOST`; non-localhost FastAPI binding must fail startup
unless the owner token is configured. Runtime services and mounted user-data API
endpoints must use the selected single user's configured SQLite database; avoid adding new direct
`SessionLocal()` calls in service code.

## Current V1 Runtime

The active v1 runtime is limited to:

- portfolio and current positions;
- watchlist management;
- dividend information for watched instruments;
- manual buy and sell orders by ticker and lot count;
- local manual order history and basic statistics;
- investment plans, anti-greedy sell proposals, and reminders for manual review;
- local settings and mode visibility;
- read-only ticker research in the web terminal and Telegram;
- read-only chart data and on-demand PNG rendering for educational price review.

Manual orders and explicitly confirmed plan/anti-greedy prompts are the only active broker order paths.

The default dependency set for v1 is `requirements-base.txt`. The
`requirements.txt` and `requirements-v1.txt` files are compatibility aliases to
that active runtime set. Matplotlib is part of active runtime only for
on-demand, read-only PNG chart rendering. Legacy analytics, heavier charting,
signal, ML, and GPT dependencies belong only in `requirements-optional.txt`
and must remain explicitly opt-in.

## Safety Rules

- Keep the app sandbox-first by default.
- Keep manual orders manual.
- Do not add broad auto-trading.
- Do not add strategy runtime, strategy auto-execution, or strategy dashboards unless a future task explicitly reintroduces them with a dedicated safety design.
- Do not add runtime trading signals to the current v1 runtime.
- Scheduled investment plans may check price conditions and send Telegram confirmation prompts, but broker orders must still require explicit confirmation and a fresh condition check immediately before execution.
- Anti-greedy policy may detect positions above the configured profit threshold and send Telegram sell confirmation prompts, but broker orders must still require explicit confirmation and a fresh position/preview check immediately before execution.
- Do not create broker orders from analysis, ratings, signals, reminders, plans, or LLM output.
- Production trading must remain blocked unless all are explicitly configured:
  - `APP_MODE="prod"`;
  - production token for the active user;
  - `ALLOW_PROD_TRADING="true"`.
- Do not weaken safety guards in `ModeService`, `OrderService`, `TInvestBroker`, manual order handlers, or broker integration helpers.
- Keep server-rendered web form POST routes protected by CSRF tokens.
- Do not mount or enable legacy signal routers unless a future task explicitly reactivates them with a new safety design.
- Local LLM / research / rating output (educational BUY/HOLD/SELL/WATCH/AVOID labels are allowed only as non-advisory educational analysis) must never call `OrderService.preview()` or `OrderService.execute()` directly and must never create broker orders.

## Legacy Status

Signal, ML, GPT, LSTM, chart, market-notification, and old trading-bot modules are legacy/non-runtime for investor v1. Runtime strategy services, strategy web UI, examples, tests, and legacy local-write API endpoints are not part of the single-owner active runtime.

They may remain in the repository for migration safety and reversibility. Do not delete or reactivate them unless the task explicitly asks for that and includes a safety plan.

## Future Research-Terminal Direction

Future work may add long-term research workflows such as:

- ticker research;
- company profiles;
- financial statement and valuation data;
- dividend history and forecasts;
- sector and competitor comparison;
- macro context;
- risk summaries and data-quality notes.

Local LLM support may be added later only through explicit adapter/service layers. Future LLM work must use structured outputs and include confidence, data gaps, freshness metadata, source attribution where available, and hallucination-safety checks.

Preferred future local/private-VM LLM for the research adapter:
`Qwen/Qwen3-235B-A22B-Instruct-2507-FP8`. This records the model choice only;
it must not enable runtime LLM behavior, trading signals, ratings, or broker
order integration by itself.

## Data Source Architecture

T-Invest API is the primary source for current and broker-facing operational
data: current/last prices, order book, last trades, trading status, streaming
market data, portfolio positions, broker availability, and dividends/coupons
when available through T-Invest.

MOEX ISS is the secondary public exchange-data source for MOEX reference data,
secid/board/classcode mapping, historical daily candles, index market context,
listing/status metadata, and fallback/verification when T-Invest candles or
metadata are unavailable. Free MOEX ISS data must be treated as delayed public
data, not real-time.

External data results should expose source metadata where practical:
`source`, `fetched_at`, `as_of_date`, `freshness`, `delay_status`,
`data_gaps`, and `errors`. Missing data must be reported as data gaps, not
guessed. Data adapters must remain read-only and must not import order services
or call broker order placement APIs.

## Future Educational Ratings

Educational long-term analytical ratings may be added later, including:

- `BUY`;
- `HOLD`;
- `SELL`;
- `WATCH`;
- `AVOID`.

These ratings must be clearly educational, not personal investment advice, and must never trigger broker orders automatically.

Do not add these ratings to the current v1 runtime unless a future task explicitly asks for them.

## Testing

Use Python 3.12 and the project `venv312` environment for verification.

Run:

```powershell
.\venv312\Scripts\python.exe -m unittest discover -q
```

Existing unittest tests should remain green unless a task explicitly changes covered behavior.

## Documentation Rule

Update `README.md` and/or `PROJECT_INSTRUCTIONS.md` whenever product behavior, safety policy, architecture, runtime scope, or setup changes.

Documentation should keep the project framed as a local sandbox-first long-term investor assistant and research terminal.
