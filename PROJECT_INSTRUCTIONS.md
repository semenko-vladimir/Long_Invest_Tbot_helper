# Tbot v1 Project Instructions

These instructions define the durable project rules for future Codex work in Tbot v1.

## Product Framing

Tbot v1 is a local, sandbox-first assistant for a private long-term investor. It is a Telegram bot and FastAPI web terminal backed by SQLite and the T-Invest API.

The product direction is a calm local research terminal for long-term investing. It is not an auto-trading bot, signal bot, scalping tool, or investment adviser.

## Current V1 Runtime

The active v1 runtime is limited to:

- portfolio and current positions;
- watchlist management;
- dividend information for watched instruments;
- manual buy and sell orders by ticker and lot count;
- local manual order history and basic statistics;
- investment plans and reminders for manual review;
- local settings and mode visibility;
- read-only ticker research in the web terminal and Telegram.

Manual orders are the only active broker order path.

The default dependency set for v1 is `requirements-base.txt`. The
`requirements.txt` and `requirements-v1.txt` files are compatibility aliases to
that active runtime set. Legacy analytics, charting, signal, ML, and GPT
dependencies belong only in `requirements-optional.txt` and must remain
explicitly opt-in.

## Safety Rules

- Keep the app sandbox-first by default.
- Keep manual orders manual.
- Do not add auto-trading.
- Do not add runtime trading signals to the current v1 runtime.
- Do not create broker orders from analysis, ratings, signals, reminders, plans, or LLM output.
- Production trading must remain blocked unless all are explicitly configured:
  - `APP_MODE="prod"`;
  - production `TOKEN`;
  - `ALLOW_PROD_TRADING="true"`.
- Do not weaken safety guards in `ModeService`, `OrderService`, `TInvestBroker`, manual order handlers, or broker integration helpers.
- Do not mount or enable legacy signal or strategy routers unless a future task explicitly reactivates them with a new safety design.

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
