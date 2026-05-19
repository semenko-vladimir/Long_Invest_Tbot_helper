# Tbot v1 Project Instructions

These instructions define the durable project rules for future Codex work in Tbot v1.

## Product Framing

Tbot v1 is a local, sandbox-first assistant for one unique private long-term investor. It is a Telegram bot and FastAPI web terminal backed by SQLite and the T-Invest API.

The product direction is a calm local research terminal for long-term investing. It is not an auto-trading bot, signal bot, scalping tool, or investment adviser.

The broader product idea includes read-only visibility into current trading strategies from both the local web terminal and the Telegram bot. Strategy visibility means showing configured strategy names, status, watched instruments, rules, and recent checks. Local strategy proposal checks may also be enabled explicitly, but they may only send Telegram confirmation prompts and must not submit broker orders without explicit user confirmation and a fresh pre-execution check.

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
- investment plans, anti-greedy sell proposals, explicitly enabled local strategy proposal prompts, and reminders for manual review;
- read-only web visibility into local strategy folders and recent strategy history;
- local settings and mode visibility;
- read-only ticker research in the web terminal and Telegram.

Manual orders and explicitly confirmed plan/anti-greedy/strategy proposal prompts are the only active broker order paths.

The default dependency set for v1 is `requirements-base.txt`. The
`requirements.txt` and `requirements-v1.txt` files are compatibility aliases to
that active runtime set. Legacy analytics, charting, signal, ML, and GPT
dependencies belong only in `requirements-optional.txt` and must remain
explicitly opt-in.

## Safety Rules

- Keep the app sandbox-first by default.
- Keep manual orders manual.
- Do not add broad auto-trading. The only allowed autonomous broker-order path is the explicitly gated
  `auto_execute` strategy milestone, which is disabled by default, sandbox-only by default, and must use
  `OrderService` plus `TradingPolicyService`.
- Do not add runtime trading signals to the current v1 runtime.
- Scheduled investment plans may check price conditions and send Telegram confirmation prompts, but broker orders must still require explicit confirmation and a fresh condition check immediately before execution.
- Anti-greedy policy may detect positions above the configured profit threshold and send Telegram sell confirmation prompts, but broker orders must still require explicit confirmation and a fresh position/preview check immediately before execution.
- Local confirmation-required strategy checks may run only behind `ENABLE_BACKGROUND_SCHEDULERS=true` and `ENABLE_STRATEGY_PROPOSALS=true`; they may send Telegram confirmation prompts, but broker orders must still require explicit confirmation, a fresh preview, and a strategy recheck when configured.
- Local no-confirmation strategy checks may run only behind `ENABLE_BACKGROUND_SCHEDULERS=true` and `ENABLE_STRATEGY_OBSERVATIONS=true`; they are observation-only and must not create broker-order proposals or submit broker orders.
- Local auto-execute strategy checks may run only behind `ENABLE_BACKGROUND_SCHEDULERS=true`,
  `ENABLE_STRATEGY_AUTO_EXECUTION=true`, and `ALLOW_STRATEGY_AUTO_EXECUTION=true`; they load only from
  `STRATEGY_AUTO_EXECUTION_DIR`, are always sandbox-only, must pass strategy/global RUB limits, must use
  durable dedupe and SQLite-backed daily budget reservation, and must submit only through `OrderService`.
- No-confirmation strategy behavior remains read-only/observation-only.
- Do not create broker orders from analysis, ratings, signals, reminders, plans, or LLM output.
- Production trading must remain blocked unless all are explicitly configured:
  - `APP_MODE="prod"`;
  - production token for the active user;
  - `ALLOW_PROD_TRADING="true"`.
- Do not weaken safety guards in `ModeService`, `OrderService`, `TInvestBroker`, manual order handlers, or broker integration helpers.
- Keep server-rendered web form POST routes protected by CSRF tokens.
- Do not mount or enable legacy signal or strategy routers unless a future task explicitly reactivates them with a new safety design.
- Keep legacy local-write API endpoints (`/api/trading/*` POST/DELETE, `/api/instruments/*` POST/DELETE) disabled by default. They do not place broker orders, but predate CSRF and require an explicit opt-in via `ENABLE_LEGACY_LOCAL_WRITE_API="true"`.
- Treat user strategy directories (`STRATEGY_CONFIRMATION_REQUIRED_DIR`, `STRATEGY_NO_CONFIRMATION_DIR`, `STRATEGY_AUTO_EXECUTION_DIR`) as executable code paths: they must be owner-write-only on the local machine, and must contain only locally reviewed code.
- Local LLM / research / rating output (educational BUY/HOLD/SELL/WATCH/AVOID labels are allowed only as non-advisory educational analysis) must never call `OrderService.preview()` or `OrderService.execute()` directly and must never create broker orders.

## Legacy Status

Signal, strategy, ML, GPT, LSTM, chart, market-notification, and old trading-bot modules are legacy/non-runtime for investor v1.

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
