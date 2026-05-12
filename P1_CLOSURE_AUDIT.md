# P1 Closure Audit - Multi-User Foundation

Date: 2026-05-11

## Architecture Decisions

- User storage: local `users.json`.
- Web identity: no auth in Phase 1; local default selected by `DEFAULT_WEB_USER_ID`, falling back to the first enabled user.
- DB isolation: separate SQLite DB file per user.

## Closure Result

P1 is closed for the active v1 runtime.

Implemented and verified:

- `UserContext` and `UserContextResolver` load enabled users, map Telegram `chat_id` to users, and select the default local web user.
- Startup database setup creates tables for each enabled user's configured `db_path`.
- DB-backed services accept injected `session_factory` and can be built per user.
- Active Telegram data flows resolve the user before broker or DB work:
  - portfolio;
  - watchlist add/list/remove/clear;
  - dividends;
  - manual buy/sell preview and confirmation;
  - statistics;
  - read-only research;
  - sandbox info and sandbox pay-in.
- Web terminal routes use the default web user's service container.
- Mounted user-data API endpoints use the default web user's DB:
  - `/api/trading/*`;
  - `/api/instruments/*`;
  - `/api/research/*`.
- Unknown Telegram chats are rejected before active user workflows proceed.
- Settings shows the active web user and DB path without exposing secrets.

## Verification

- `.\venv312\Scripts\python.exe -m unittest discover -q`
- Result: all tests passing.

Static regression checks were added in `tests/test_p1_user_context_wiring.py` to keep active Telegram handlers, web routes, and user-data API endpoints from drifting back to global token or legacy DB wiring.

## Non-Blocking Legacy Areas

These remain intentionally outside active P1 runtime:

- legacy signal, strategy, ML, market-notification, and old chart handlers;
- global config API storage for legacy scheduler config;
- historical `.env` fallback when `users.json` is not configured.

Future work that reactivates any legacy area must add an explicit user-context design first.

## P2 Handoff

P2 plan scheduling must iterate enabled users and build per-user `InvestmentPlanService`, `OrderService`, broker, and Telegram notification context. It must not use a process-global `SessionLocal()` or a process-global broker token.
