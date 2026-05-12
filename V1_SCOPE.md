# Investor V1 Scope

## What Remains

- Telegram bot as the main local user interface.
- Sandbox-first startup through `.env` with `INVEST_MODE="sandbox"`.
- Manual buy and sell by ticker and lot count through buttons or direct commands like `buy SBER 1`.
- Portfolio retrieval.
- Dividend lookup for configured instruments.
- Basic text statistics from stored trading records and manual orders.
- Watchlist storage and management.
- Optional simple investor reminders with no signals or trade advice.
- Local FastAPI backend with the v1 routers for config, trading, and instruments.
- SQLite persistence and existing configuration helpers.

## What Is Disabled

- Trading signal menus and signal settings.
- Middle/long signal menus.
- Strategy automation and signal-driven execution.
- GPT and LSTM integrations.
- ML/AI signal generation.
- Technical indicator flows used for signals.
- Chart-based statistics in the v1 runtime path.
- Signal and strategy API routers in the active FastAPI app.
- Background schedulers by default through `ENABLE_BACKGROUND_SCHEDULERS="false"`.

Legacy code for disabled features remains in the repository for now, but it is not wired into the v1 menu, active API router, or default scheduler startup path.

## What Is Postponed

- Production trading UX beyond the existing explicit `ALLOW_PROD_TRADING` guard.
- Full investor analytics and charting.
- Direct API replacement for the local FastAPI thread.
- Database cleanup or migrations that remove legacy signal and strategy tables.
- Replacing the legacy T-Invest SDK package pins with a production-ready dependency policy.
- Internationalized UI text across every legacy handler.
