# Project Roadmap — Investment Bot

## Project Vision

A **semi-automatic personal investment assistant** for multiple users.

- Primary interface: **local web terminal** (FastAPI, `localhost:8000`)
- Secondary interface: **Telegram bot** — quick commands, notifications, confirmations
- Broker: T-Invest (Tinkoff) API, sandbox-first
- All real orders require explicit confirmation (manual or scheduled-plan flow)
- No autonomous trading, no ML signals — investor stays in control

---

## Agent Behavior Rules

These rules apply to every AI agent working on this project:

1. **Read before writing.** Always read the relevant files before making changes.
2. **Ask when unsure.** If a requirement is ambiguous, a design decision has multiple valid options, or the scope is unclear — ask the user immediately. Do not guess and do not implement a placeholder.
3. **Use AGENT_BEHAVIOR.md as the architecture constitution.** If a task conflicts with it, surface the conflict and ask.
4. **Respect V1_SCOPE.md.** Do not re-introduce disabled features (signals, LSTM, GPT, auto-strategies) unless the roadmap phase explicitly enables them.
5. **One phase at a time.** Do not start the next phase until the current one is reviewed and approved.
6. **Safety first.** Any change that touches order execution, token handling, or trading-mode logic requires extra review. Mention it explicitly.
7. **No dead scaffolding.** Do not create placeholder files, empty services, or TODO stubs unless the prompt explicitly asks for a skeleton.
8. **Verify the startup path.** After any structural change, confirm that `python app/run.py` still works correctly.
9. **Shared service layer.** Business logic belongs in `app/services/`. Telegram handlers and web routes must stay thin.
10. **If you find a bug or risky issue while working on a different task** — report it to the user before fixing it, so they can decide priority.

---

## How to Use This Document

Each phase contains a **ready-to-paste prompt**. Copy the prompt block and send it to the agent.
The agent will read the relevant files, plan the work, and implement.
After each phase, review the result before moving to the next prompt.

Phases must be executed **in order** — each one builds on the previous.

---

## Current State (after V1)

Already implemented:
- `app/services/`: ModeService, PortfolioService, OrderService (preview→confirm flow), WatchlistService, DividendsService, InvestmentPlanService, TradingPolicyService, StatisticsService
- `app/integrations/tinvest.py`: TInvestBroker adapter
- `app/backend/web/routes.py`: Portfolio, Buy, Sell, Dividends, Watchlist, Plans, Stats, Settings pages
- `app/backend/web/templates/`: base.html, all pages, partials (nav, mode_banner, order_feedback, order_form)
- `app/client/handlers/`: Telegram handlers for all V1 flows
- DB models: Order, Instrument, InvestmentPlan, InvestmentPlanExecution
- Tests: started (test_investment_plans.py, test_mode_service.py, test_portfolio_service.py)

---

## Phase 0 — V1 Completion

**Goal:** Close all remaining V1 gaps before adding new features.

---

### P0-T1: Settings page — real system status

```
TASK_MODE=implement
PLAN_MODE=OFF

Read app/backend/web/routes.py and app/backend/web/templates/pages/settings.html.
The settings page currently only shows plan_policy. Expand it to show real system state:

1. Active mode (sandbox / prod) and what it means
2. Broker token status: SANDBOX_TOKEN configured yes/no, TOKEN configured yes/no (show only whether set, never the value)
3. ALLOW_PROD_TRADING value
4. ENABLE_BACKGROUND_SCHEDULERS value
5. ENABLE_INVESTMENT_PLANS value
6. API_BASE_URL in use
7. ENABLE_INVESTOR_REMINDERS and INVESTOR_REMINDER_TIME

Add a SettingsView dataclass in app/services/settings_view.py.
Read values from app/client/config/__init__.py functions — do not re-read env directly in the route.
The page must be read-only. No forms for changing values (changes require .env restart).
Add a note: "To change settings, edit .env and restart the app."

If you are unsure which config functions to call, ask before implementing.
```

---

### P0-T2: Order history page (web terminal)

```
TASK_MODE=implement
PLAN_MODE=OFF

Read app/backend/models/trading.py (Order model) and app/backend/web/routes.py.

Add a GET /orders route and orders.html page to the web terminal.
Show the stored Order records from the database in a table:
- order_id (truncated to 12 chars + "...")
- ticker
- operation_type (Buy / Sell badge)
- bm_value (formatted as money)
- Empty state when no orders exist

Do NOT add Order to NAV_ITEMS (it is a sub-page, not top nav).
Instead, add a "View order history" link on the Stats page (stats.html).

Create an OrderHistoryService in app/services/order_history.py that:
- Returns an OrderHistoryView dataclass with a list of OrderRowView items
- Queries the DB directly (not via HTTP client)

If the Order model fields are insufficient for a useful table, ask the user before adding columns.
```

---

### P0-T3: Test coverage for OrderService and WatchlistService

```
TASK_MODE=implement
PLAN_MODE=OFF

Read app/services/orders.py, app/services/watchlist.py, and the existing test files in tests/.

Write unit tests using unittest and fake/stub objects (no real broker, no real DB, no HTTP).

For OrderService, cover:
- preview blocked when no token
- preview raises OrderValidationError for invalid ticker format
- preview raises OrderValidationError for lots < 1
- execute raises OrderExecutionBlocked when trading_available=False
- execute raises OrderExecutionBlocked when confirm_token is missing or expired
- execute raises OrderExecutionBlocked in prod mode when ticker_confirmation does not match
- execute raises OrderExecutionBlocked when confirm_token was already consumed

For WatchlistService, cover:
- add_ticker saves to DB and returns updated list
- add_ticker raises WatchlistServiceError for empty ticker
- add_ticker raises WatchlistServiceError for duplicate ticker
- remove_ticker removes from DB
- remove_ticker raises WatchlistServiceError for unknown ticker

Use the same fake pattern as existing tests (FakeBroker, FakeModeService).
Do not add integration tests or tests that require a real database in this task.

If app/services/watchlist.py does not exist yet or has different structure than expected, read it first and report before writing tests.
```

---

## Phase 1 — Multi-User Foundation

**Goal:** Support multiple independent users, each with their own broker tokens, Telegram chat ID, and isolated data.

**Architecture decision to confirm with user before starting:**
- Users are configured in `.env` as a list or via a separate `users.json` / DB table?
- Web terminal: protected by a shared password, per-user login, or IP-only access?

---

### P1-T0: Design session (ask user before coding)

```
TASK_MODE=plan
PLAN_MODE=ON

Read app/client/config/__init__.py, app/backend/models/database.py, and app/backend/models/trading.py.

The project needs to support multiple users. Each user has:
- Their own Telegram chat_id
- Their own T-Invest tokens (sandbox + prod)
- Their own broker fee
- Isolated Order, InvestmentPlan, and Watchlist data in the DB

Before writing any code, produce a plan covering:

1. How users are stored: options are (a) .env with USER_1_*, USER_2_* prefixes,
   (b) a JSON config file, (c) a Users DB table. Evaluate each. Do not choose — present to the user.

2. How Telegram routing works: each incoming message must be matched to a user by chat_id.
   What happens with unknown chat_ids.

3. How the web terminal identifies the current user: options are (a) shared password, 
   (b) per-user token in URL or cookie, (c) no auth (local-only assumption).

4. DB isolation: Option A — add user_id FK to Order, Instrument, InvestmentPlan tables (migration needed).
   Option B — separate DB files per user. Evaluate.

5. Affected files and migration risk.

Present the plan. Do not write any code. Ask the user to choose between options before Phase 1 implementation begins.
```

---

### P1-T1: Users config and user context

Status: Done.

Implemented local `users.json` configuration, `UserContext`, Telegram chat ID
resolution, default local web user resolution, startup validation, and legacy
`.env` fallback.

---

### P1-T2: Per-user DB session factory and service wiring

Status: Done.

Implemented per-user SQLite session factories and wired DB-backed services to
accept injected session factories instead of direct global `SessionLocal()` use.

---

### P1-T3: Thread UserContext through Telegram handlers and web routes

Status: Done.

Active Telegram data handlers resolve the current user by Telegram chat ID.
Web routes resolve the local default web user and build services for that user.

---

### P1-T4: Closure audit

Status: Done.

Result: P1 is closed for the active v1 runtime. Active Telegram flows, web
routes, and mounted user-data API endpoints now use user-context service/DB
wiring. Quarantined legacy handlers remain outside active runtime and must not
be reactivated without a separate user-context design.

---

## Phase 2 — Investment Plan Auto-Execution

**Goal:** Investment plans run automatically on their schedule. User is notified via Telegram and can confirm or skip. Plans marked `confirmation_required=False` execute without prompting.

**Depends on:** Phase 1 (multi-user user context)

---

### P2-T1: Scheduler integration

```
TASK_MODE=implement
PLAN_MODE=OFF

Read app/services/investment_plans.py, app/backend/models/trading.py (InvestmentPlan, InvestmentPlanExecution),
app/client/config/__init__.py (investment_plans_enabled, allow_auto_investing),
and app/client/config/schedulers_config.py.

Add a PlanScheduler class in app/services/plan_scheduler.py.
Use APScheduler (already in requirements) with an in-process scheduler.

Responsibilities:
- On startup, load all active InvestmentPlans from DB
- Schedule each plan using its next_run_at datetime
- On trigger: call InvestmentPlanService.generate_order_proposal_for_plan()
- If plan.confirmation_required=True: send Telegram notification with confirm/skip inline buttons
- If plan.confirmation_required=False and allow_auto_investing()=True: execute directly via OrderService
- After execution (success or skip): create an InvestmentPlanExecution record with status
- Reschedule the plan for its next run

Safety rules (enforce in service layer, not only in scheduler):
- ENABLE_INVESTMENT_PLANS must be True
- TradingPolicyService.check_auto_execution() must pass
- On any broker error: record status="failed", send Telegram alert, do not retry automatically

Wire PlanScheduler into app/run.py startup after configure_investor_reminders().

If APScheduler version in requirements does not support the pattern you need, ask before adding a new dependency.
```

---

### P2-T2: Execution history page

```
TASK_MODE=implement
PLAN_MODE=OFF

Read app/backend/models/trading.py (InvestmentPlanExecution),
app/services/investment_plans.py, and app/backend/web/routes.py.

Add GET /plans/{plan_id}/history route.
Show InvestmentPlanExecution records for the given plan_id in a table:
- created_at
- status badge (executed / skipped / failed)
- execution_mode (sandbox / prod)
- amount_rub (formatted as money)
- order_id (truncated, or "—" if null)

Add an ExecutionHistoryService in app/services/execution_history.py.
Add a link to execution history from the Plans page for each plan row.
Create app/backend/web/templates/pages/plan_history.html using existing template patterns.

If InvestmentPlanExecution is missing columns needed for a useful view, ask the user before adding them.
```

---

## Phase 3 — Web Terminal as Primary UI

**Goal:** The web terminal becomes fully self-sufficient. Improve UX, navigation, and visual design quality.

---

### P3-T1: Responsive layout and design polish

```
TASK_MODE=implement
PLAN_MODE=OFF

Read app/backend/web/templates/base.html and app/backend/web/static/css/.

The current layout is functional but minimal. Make the following improvements:

1. Responsive: the layout must work on tablet and desktop (min 768px). Mobile is not a priority.
2. Sidebar navigation instead of top nav bar — fixed left sidebar with page labels and icons (text icons, no external icon library).
3. Mode banner: make sandbox/prod mode visually prominent — color-coded header strip.
4. Table improvements: alternating row colors, better spacing.
5. Form improvements: consistent field sizing, focus states.
6. Button hierarchy: primary (blue/green), danger (red), secondary (grey).
7. CSS variables for all colors, spacing, and font sizes — make future restyling easy.

Do not introduce JavaScript frameworks. Vanilla JS only.
Do not change any Python files — HTML and CSS only.
After changes, list every template file you modified.

If the current CSS structure makes a refactor risky without reading all templates, read them first and report.
```

---

### P3-T2: Keyboard shortcuts and quick actions

```
TASK_MODE=implement
PLAN_MODE=OFF

Read app/backend/web/templates/base.html and the existing JS in app/backend/web/static/js/.

Add minimal keyboard shortcuts for power users:
- g p → go to /portfolio
- g b → go to /buy
- g s → go to /sell
- g d → go to /dividends
- g w → go to /watchlist
- ? → show shortcuts overlay

The shortcuts overlay is a simple modal listing the shortcuts.
Implement in a single new file: app/backend/web/static/js/shortcuts.js
Include it in base.html.

Do not add any dependencies. Pure JS only.
Do not intercept keys when focus is on a form input.
```

---

## Phase 4 — Analytics and Charts

**Goal:** Visual portfolio analytics in the web terminal. No real-time data — snapshot-based.

---

### P4-T1: Portfolio snapshot storage

```
TASK_MODE=implement
PLAN_MODE=OFF

Read app/backend/models/database.py, app/services/portfolio.py, and app/run.py.

Add a PortfolioSnapshot DB model in app/backend/models/analytics.py:
- id, captured_at (DateTime), user_id (if multi-user is done), total_value_rub (Float),
  position_count (Integer), snapshot_json (Text — serialized list of positions)

Add a SnapshotService in app/services/snapshot.py:
- take_snapshot() — calls PortfolioService, stores result to DB
- list_snapshots(limit=90) — returns last N snapshots ordered by date

Wire take_snapshot() into a daily APScheduler job in app/run.py.
Default time: 18:00 Moscow time. Configurable via SNAPSHOT_TIME env var.

Do not build charts yet — that is P4-T2.
Do not add any new Python dependencies.

If portfolio data is unavailable (broker error), skip the snapshot silently and log a warning.
```

---

### P4-T2: Portfolio value chart (web terminal)

```
TASK_MODE=implement
PLAN_MODE=OFF

Read app/services/snapshot.py (from P4-T1), app/backend/web/routes.py,
and app/backend/web/templates/pages/portfolio.html.

Add a portfolio value chart to the Portfolio page.
Use Chart.js (load from CDN in base.html, or download to static — ask user which they prefer).

The chart shows total_value_rub over time from portfolio snapshots.
If fewer than 2 snapshots exist, show "Not enough data yet — check back after the first snapshot."

Add GET /api/snapshots/portfolio route that returns JSON:
[{"date": "2025-01-15", "value": 152340.00}, ...]

Render the chart client-side via JS fetch to /api/snapshots/portfolio.

Do not add server-side chart rendering (matplotlib/seaborn). Client-side only.
Do not modify PortfolioService — use SnapshotService only for historical data.

Ask the user whether to load Chart.js from CDN or bundle it locally before implementing.
```

---

### P4-T3: Dividend calendar

```
TASK_MODE=implement
PLAN_MODE=OFF

Read app/services/dividends.py and app/backend/web/templates/pages/dividends.html.

Add a dividend calendar view to the Dividends page.
The calendar shows upcoming dividend dates for watchlist instruments in a simple table grouped by month.
It must work with existing DividendsService — no new broker calls.

Add a DividendCalendarView dataclass in app/services/dividends.py.
Render in dividends.html below the existing dividend list.

If DividendsService does not return enough date information for a calendar, read it first,
report what is missing, and ask the user how to proceed before implementing.
```

---

## Phase 5 — Fundamental Research

**Goal:** Per-ticker research cards with company fundamentals, stored locally.

---

### P5-T1: Research service and web page

```
TASK_MODE=implement
PLAN_MODE=OFF

Read app/client/handlers/research/research_handler.py (check if it exists and what it does),
app/integrations/tinvest.py, and app/backend/web/routes.py.

Add a ResearchService in app/services/research.py that:
- Calls TInvestBroker to fetch instrument fundamentals for a given ticker
- Returns a ResearchView dataclass with: ticker, name, figi, instrument_type,
  sector (if available), currency, lot_size, and any fundamental fields the API provides

Add GET /research?ticker=SBER route and research.html page.
The page has a ticker input form. On submit, show the research card.
If the instrument is not found, show a clear error.

Do not add a knowledge base or notes feature yet — that is P5-T2.

Read TInvestBroker first. If the T-Invest SDK does not expose fundamental data
(P/E, EPS, etc.), report what IS available and ask the user what to show before building the page.
```

---

### P5-T2: Per-ticker notes (local knowledge base)

```
TASK_MODE=implement
PLAN_MODE=OFF

Read app/backend/models/database.py, app/services/research.py (P5-T1),
and app/backend/web/templates/pages/research.html.

Add a TickerNote DB model:
- id, ticker (String, indexed), body (Text), updated_at (DateTime)

Add a NotesService in app/services/notes.py:
- get_note(ticker) → TickerNoteView or None
- save_note(ticker, body) → TickerNoteView

Add a notes form to the research.html page (below the research card).
POST /research/notes saves the note. Reload the page after save.
Notes are plain text, no markdown rendering needed.

One note per ticker. Saving overwrites the previous note.
If the user wants per-section notes or richer structure, ask before adding complexity.
```

---

## Phase 6 — Notifications and Alerts

**Goal:** Telegram notifications for price thresholds, dividend payments, and portfolio milestones.

---

### P6-T1: Price alert engine

```
TASK_MODE=implement
PLAN_MODE=OFF

Read app/backend/models/database.py, app/integrations/tinvest.py,
app/client/bot/bot.py, and app/client/config/__init__.py.

Add a PriceAlert DB model:
- id, ticker, figi, threshold_price (Float), direction ("above" / "below"),
  active (Boolean), triggered_at (DateTime, nullable), created_at

Add an AlertService in app/services/alerts.py:
- create_alert(ticker, threshold, direction) → PriceAlertView
- list_alerts() → list[PriceAlertView]
- delete_alert(alert_id)
- check_alerts(token) — fetches current prices for all active alert tickers,
  marks triggered alerts, returns list of triggered ones

Add a scheduled job that calls check_alerts() every 5 minutes (configurable via ALERT_CHECK_INTERVAL_MINUTES).
On trigger: send a Telegram message and mark the alert as triggered (inactive).

Add GET /alerts and POST /alerts routes to the web terminal.
Add alerts.html page showing active and triggered alerts.
Add "Alerts" to NAV_ITEMS in routes.py.

If price fetching from TInvestBroker is rate-limited or too slow for many tickers,
report the constraint and ask how to handle it before implementing the scheduler job.
```

---

### P6-T2: Dividend payment notifications

```
TASK_MODE=implement
PLAN_MODE=OFF

Read app/services/dividends.py and app/client/config/investor_reminders.py.

Add a dividend payment notifier:
- A scheduled daily job that checks dividend payment_date for all watchlist instruments
- If any instrument has a payment_date within the next N days (configurable, default 7),
  send a Telegram notification: "SBER dividend of X RUB/share pays in 3 days (2025-06-01)"
- Do not send duplicate notifications for the same instrument+payment_date

Track sent notifications in a DividendNotification DB table:
- id, ticker, payment_date (String), notified_at (DateTime)

If DividendsService does not cache data and each call hits the broker API,
ask the user before adding a daily API call in a background job.
```

---

### P6-T3: Daily portfolio report

```
TASK_MODE=implement
PLAN_MODE=OFF

Read app/client/config/investor_reminders.py, app/services/portfolio.py,
app/services/statistics.py, and app/client/bot/bot.py.

Extend the investor reminder to send a richer daily report via Telegram:
- Total portfolio value
- Today's P&L (if snapshot from yesterday is available)
- Number of active investment plans
- Any alerts triggered today
- Link to web terminal: "Full details: http://localhost:8000"

Keep the existing reminder time config (INVESTOR_REMINDER_TIME).
Do not break the existing reminder — extend it.

If portfolio data is unavailable at reminder time (broker offline), send a short message:
"Daily reminder: portfolio data unavailable. Check the terminal."

Ask the user if they want the report in Russian or English before implementing message text.
```

---

## Appendix — Deferred Features (Not Yet Scheduled)

These features are deliberately excluded from the current roadmap. Do not implement them until explicitly added to a phase:

- Trading signals (RSI, MACD, EMA, etc.)
- ML / LSTM / GPT order generation
- Strategy auto-trading (signal-driven execution)
- Margin trading
- External data providers beyond T-Invest SDK
- Mobile app

---

## Roadmap Status

| Phase | Status |
|---|---|
| V1 Core | ✅ Done |
| P0 — V1 Completion | 🔄 In progress |
| P1 — Multi-User | ✅ Done |
| P2 — Plan Auto-Execution | ⏳ Pending P1 review |
| P3 — Web Terminal UI | ⏳ Pending P0 |
| P4 — Analytics & Charts | ⏳ Pending P3 |
| P5 — Research | ⏳ Pending P4 |
| P6 — Notifications | ⏳ Pending P2 |
