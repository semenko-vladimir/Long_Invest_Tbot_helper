# Project Audit — Tbot v1 / Investor v1

Audit date: 2026-05-14
Auditor: Claude Sonnet 4.6 (senior architect mode)
Scope: read-only analysis. No source code was modified.

---

## Coverage note

Files inspected directly: `README.md`, `PROJECT_INSTRUCTIONS.md`, `V1_SCOPE.md`,
`ROADMAP.md`, `AGENT_BEHAVIOR.md`, `P1_CLOSURE_AUDIT.md`, `requirements-base.txt`,
`requirements-optional.txt`, `app/run.py`, `app/backend/main_api.py`,
`app/services/orders.py`, `app/services/mode.py`, `app/services/trading_policy.py`,
`app/services/plan_runner.py`, `app/services/plan_confirmation.py`,
`app/services/price_conditions.py`, `app/services/auto_scheduler.py`,
`app/services/user_context.py`, `app/client/config/schedulers_config.py`,
`app/client/config/investor_reminders.py`.

**Files NOT read directly** (directory-level listing only):
`app/client/handlers/**`, `app/backend/web/routes.py`, `app/backend/web/templates/**`,
`alembic/versions/*`, `app/client/config/__init__.py` (partial grep only),
`app/integrations/tinvest.py`, `app/research/**`, individual test files.
Conclusions about these areas are based on directory listings, grep results,
and cross-references in documentation. Mark them as unverified if critical.

---

## 1. What the project already does

- Telegram bot with manual buy/sell (preview → confirm → execute flow).
- FastAPI web terminal: Portfolio, Buy, Sell, Dividends, Watchlist, Plans, Stats, Settings, Research.
- SQLite persistence per user (separate DB file per user, per-user session factory).
- Multi-user config via `users.json` (P1 complete per closure audit).
- ModeService: sandbox / prod / prod-read-only modes.
- OrderService: validates, previews, issues confirm token (10 min TTL), executes only on confirmed token.
- TradingPolicyService: limits (MAX_ORDER_RUB, MAX_DAILY_INVEST_RUB), auto-invest gate.
- InvestmentPlans with price conditions (max_price, pct_from_avg, any).
- PlanRunner: implements auto-plan execution flow (check trading day → preview → price condition → send Telegram confirmation → execute on ✅).
- PlanConfirmationService: manages pending Telegram button confirmations.
- Read-only ticker research: local fundamentals JSON + T-Invest adapter + snapshots.
- Optional investor reminder (daily Telegram text, no order execution).
- Safety-gated startup: validates env, checks users.json, creates per-user DBs.

---

## 2. What is done well

**Safety architecture is solid for the core manual flow.** The validate→preview→confirm→execute chain with token TTL (10 min) and consume-once semantics is a proper safety gate. Production trading requires three independent flags: `APP_MODE=prod` + production token + `ALLOW_PROD_TRADING=true`. This is intentional and well-implemented.

**Service layer separation is real.** Business logic is in `app/services/`, not in handlers or routes. Services use injected dependencies (broker, mode_service, session_factory), making them testable without live infrastructure.

**Multi-user foundation (P1) is clean.** `UserContext`, `UserContextResolver`, per-user SQLite files, and Telegram `chat_id` gating are all well-designed. Unknown Telegram chats are rejected before any user workflow proceeds.

**Documentation for the intended v1 scope is comprehensive.** README, PROJECT_INSTRUCTIONS, V1_SCOPE, ROADMAP, and AGENT_BEHAVIOR collectively define what the project does and does not do clearly enough for an external agent to work safely.

**Test count is respectable** (21 test files). Coverage of safety-critical paths (OrderService, ModeService, PlanRunner, PriceConditions) appears intentional.

**`configure_schedulers()` is properly gated.** The function checks `background_schedulers_enabled()` (defaults `false`) and returns immediately if disabled. `configure_strategy_scheduler()` is an explicit no-op. Legacy market notification jobs are stubbed out inside `setup_market_jobs`.

---

## 3. What is done poorly

**`configure_investor_reminders()` uses legacy `CHAT_ID` from `.env`**, not the multi-user `UserContext`. This contradicts the P1 multi-user architecture: if multiple users are configured, the reminder sends only to the single env-level `CHAT_ID`. This is a silent inconsistency, not a safety issue, but it's a design regression against the P1 work.

**`PlanRunner._execute` is called under a held lock in `PlanConfirmationService`.**
The comment in `plan_confirmation.py` (lines 33–35) explicitly warns:
> "NOTE: on_confirm and on_skip are called while holding self._lock. Callbacks must not re-enter PlanConfirmationService or perform slow I/O, or they will deadlock."

`_execute` in PlanRunner calls `OrderService.execute()` which calls the T-Invest broker over the network. This is slow I/O inside a lock. The risk is a locked confirmation service unable to process any other Telegram button press while waiting for the broker. This is a real bug waiting to trigger.

**`PlanRunner` accesses `plan_service._get_plan_view` — a private method.**
`_get_plan_view` has a leading underscore, indicating it's not the intended public API. Calling it from an external class is a leaky abstraction.

**`app/client/signals/` contains 8 active Python files** (alligator, bollinger, ema, gpt, lstm, macd, rsi, sma) that are still importable. They are not wired into the v1 runtime, but:
- They import external dependencies (some optional) that may fail if requirements-optional.txt is not installed.
- They exist at import-time as findable modules — a future developer or agent could accidentally import them.
- `gpt_signal.py` and `lstm_signal.py` represent the most dangerous legacy risk.

**Two Python environments exist**: `venv/` and `venv312/`. Tests use `venv312`. This creates ambiguity for automated agents. Documentation says to use `venv312` for tests, but `venv/` could be confused for the primary environment.

**`app/run.py` contains a mix of responsibilities**: startup orchestration, token verification, Telegram handler registration, and the `/start` handler are all in the same file. The `/start` handler definition inside `run.py` means business logic is embedded in the startup script.

---

## 4. Technical debt

| Area | Debt |
|------|------|
| `app/client/signals/` | 8 legacy signal files, importable, untested in v1 context |
| `app/client/graphics/` | 6 legacy chart files, untested |
| `app/client/strategy/` | legacy strategy directory (contents not read) |
| `app/client/store/store.py` | legacy store; referenced in `schedulers_config.py` (`from app.client.store.store import market_scheduler`) |
| `app/client/orders/` | unclear — may be legacy order handling separate from `app/services/orders.py` |
| Two venvs | `venv/` and `venv312/` — confusing, not documented which is authoritative |
| 11 root-level markdown files | Doc sprawl; readers unsure what is current vs historical |
| T-Invest SDK pinned via direct PyPI URLs | Quarantined packages, hash-pinned but not audited for security; noted in README but not addressed |
| `investor_reminders.py` uses legacy `CHAT_ID` | Bypasses multi-user architecture |
| `plan_runner.py` calls `_get_plan_view` | Private method access across module boundary |

---

## 5. What does not match the Tbot v1 idea

**`app/client/signals/gpt_signal.py` and `lstm_signal.py`** — The project description explicitly excludes GPT/LSTM integration from v1. These files remain importable. Even if not wired into active runtime, their presence makes the "no GPT/LSTM" claim require a footnote.

**`app/client/store/store.py` is imported in `schedulers_config.py`** via `from app.client.store.store import market_scheduler`. This means the legacy store module is imported at startup (when `schedulers_config` is imported by `run.py`), regardless of `ENABLE_BACKGROUND_SCHEDULERS`. This is an active import of a legacy module, not isolation.

**`configure_investor_reminders` uses hardcoded `CHAT_ID` env variable**, not the configured `UserContextResolver`. For a multi-user v1 system, this means reminders only go to whoever set `CHAT_ID` in `.env`, not to all enabled users.

---

## 6. Auto-trading risk analysis

**Current state: no automatic order placement is active.**

The critical path for auto-execution:
1. `run.py` calls `configure_schedulers()` → guarded by `background_schedulers_enabled()` (default `false`) → safe.
2. `configure_schedulers()` does NOT wire `PlanRunner`. PlanRunner has no APScheduler registration anywhere in `app/`. P2-T1 (the scheduler wiring task) is listed as "Pending" in ROADMAP.
3. `configure_investor_reminders()` only sends a text message — no order calls.

**Result: currently, no code path in `app/` triggers `PlanRunner.run()` automatically.** The auto-execution architecture is implemented but unactivated.

**Residual risk: P2-T1 implementation.**
When P2-T1 is implemented (wiring PlanRunner to APScheduler), the following guards must hold:
- `background_schedulers_enabled()` must gate the plan scheduler.
- `allow_auto_investing()` must be checked before scheduling.
- `TradingPolicyService.check_auto_execution()` must block execution if limits exceeded.
- The callback deadlock (slow I/O under lock in `PlanConfirmationService`) must be fixed first.
- Multi-user: each user's PlanRunner must use that user's broker token and session_factory.

**The deadlock in `PlanConfirmationService` is the most dangerous pre-condition for P2.**
If `_execute` is called while holding `self._lock` and the broker hangs or times out, the entire confirmation service freezes. This must be fixed before P2-T1 is implemented.

---

## 7. Legacy modules — keep / isolate / remove

| Module | Status | Recommendation |
|--------|--------|----------------|
| `app/client/signals/ema_signal.py` etc. (6 technical indicators) | Not wired, importable | Isolate: move to `_legacy/` or add `__init__.py` guard |
| `app/client/signals/gpt_signal.py` | Not wired, importable | Highest priority for removal or isolation |
| `app/client/signals/lstm_signal.py` | Not wired, importable | Highest priority for removal or isolation |
| `app/client/graphics/` (6 files) | Not wired, importable | Isolate |
| `app/client/strategy/` | Not wired (contents unread) | Review then isolate |
| `app/client/store/store.py` | Imported by schedulers_config | Do NOT isolate yet — decouple import first |
| `app/client/orders/` | Unclear (directory listed) | Read then decide |

---

## 8. Test gaps

**Directly observed gaps:**
- `app/services/watchlist.py` — ROADMAP P0-T3 planned watchlist tests, but `test_order_service.py` exists. No `test_watchlist_service.py` found in listing.
- `app/client/config/investor_reminders.py` — no test visible for reminder scheduling or legacy `CHAT_ID` usage.
- `app/services/plan_confirmation.py` — no dedicated test file found; lock/callback behavior untested.
- `app/client/signals/**` and `app/client/graphics/**` — legacy modules have no tests visible; this is a problem if they're ever reactivated.
- Integration path for PlanRunner → PlanConfirmationService → OrderService — no end-to-end test visible (only unit tests).
- `configure_investor_reminders()` fallback behavior (bad env, no CHAT_ID) — untested based on file listing.

**Verified coverage:**
`test_plan_runner.py`, `test_price_conditions.py`, `test_order_service.py`, `test_mode_service.py` suggest the critical trading path has unit test coverage. `test_p1_user_context_wiring.py` is a regression guard for multi-user architecture.

---

## 9. Documentation gaps

- `INVESTOR_MODE.md`, `RESEARCH_TERMINAL_FOUNDATION.md`, `AUTO_SCHEDULE_TASKS.md`, `MIGRATION_AUDIT.md` — unclear if these are current or historical. No "last updated" markers visible.
- `AUTO_SCHEDULE_TASKS.md` — filename suggests task tracking that should live in a task manager, not a root markdown file.
- No `CONTRIBUTING.md` or developer onboarding guide.
- No `ARCHITECTURE.md` or diagram explaining the service dependency graph.
- The deadlock risk in `PlanConfirmationService` is documented in the code comment but not surfaced in any design document.

---

## 10. Most valuable parts for portfolio

1. **OrderService** — the validate→preview→confirm→execute pattern with token TTL and consume-once is a textbook safe order flow. Clear, testable, no magic.
2. **Multi-user architecture (P1)** — `UserContext`, per-user SQLite, `UserContextResolver`, and P1 wiring guard tests demonstrate understanding of isolation concerns.
3. **TradingPolicyService** — per-day spend limits + mode checks + auto-investing gate shows understanding of risk management layers.
4. **Research module** (`app/research/`) — adapters, snapshots, local fundamentals JSON — shows a real data pipeline for an investment terminal.
5. **ModeService + AGENT_BEHAVIOR.md** — clear articulation of safety rules that an AI coding agent can follow is itself a portfolio differentiator.

---

## 11. What to simplify

- **Root-level markdown sprawl**: consolidate historical/audit docs into `_meta/` or `docs/`, keep only README, PROJECT_INSTRUCTIONS, and ROADMAP at root.
- **Two venvs**: remove `venv/`, document `venv312/` as the authoritative env.
- **`app/run.py`**: extract the `/start` handler and handler registration into a dedicated module; keep `run.py` as orchestration only.
- **Legacy signal directory**: move to `_legacy/` subdirectory with a README explaining they are not part of v1; this removes import risk without deletion.
