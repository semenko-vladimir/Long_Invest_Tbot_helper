# Add / Remove / Isolate / Defer Recommendations

Audit date: 2026-05-14

---

## Add

These additions would make the project stronger as an educational investor terminal
without compromising the sandbox-first, manual-first philosophy.

### Fix PlanConfirmationService deadlock before P2-T1
- **Priority: Critical / Before anything else in P2.**
- `_execute` callback in PlanRunner is called while `PlanConfirmationService._lock` is held.
- Broker calls inside the callback may block for seconds or time out.
- Fix: release the lock before calling the callback, or use a thread pool for the callback.
- **This is a correctness bug, not a feature.**

### Fix investor_reminders.py multi-user support
- Replace `require_env("CHAT_ID")` with `UserContextResolver().enabled_users()` and
  send reminders to each enabled user's `telegram_chat_id`.
- Low risk; existing reminder text stays unchanged.

### WatchlistService tests (P0-T3, partially done)
- ROADMAP lists WatchlistService tests as planned in P0-T3. Add them.
- Pattern: same fake/stub approach as existing `test_order_service.py`.

### PlanConfirmationService tests
- No test file found for `plan_confirmation.py`.
- Test: token issuance, confirm, skip, timeout/expiry, double-consume prevention.

### `_meta/` or `docs/` folder for historical markdown
- Move `MIGRATION_AUDIT.md`, `P1_CLOSURE_AUDIT.md`, `AUTO_SCHEDULE_TASKS.md`,
  `INVESTOR_MODE.md`, `RESEARCH_TERMINAL_FOUNDATION.md` out of project root.
- Reduces cognitive load for new developers and automated agents.

### ARCHITECTURE.md
- A brief document describing the service dependency graph (who calls what).
- Especially useful for explaining how PlanRunner → PlanConfirmationService → OrderService → TInvestBroker chains together.
- Single page, diagram optional.

### Portfolio snapshot storage (P4-T1 from ROADMAP)
- Daily portfolio value snapshot in SQLite.
- This makes the "long-term investment terminal" story concrete and differentiates from "it's just a Telegram bot."

### Local fundamentals data expansion
- `app/research/data/local_fundamentals.json` is intentionally sparse.
- Adding real company profiles (name, sector, P/E, dividend yield, market cap) for 10–20 MOEX tickers would make the research feature actually useful for portfolio analysis.
- No code changes needed — data-only work.

---

## Remove

These should be removed because they actively undermine the project's focus.

### `venv/` (old environment directory)
- `venv312/` is the verified test environment per `PROJECT_INSTRUCTIONS.md`.
- `venv/` creates confusion for agents and developers.
- Action: delete `venv/`, add `.gitignore` entry if not already present.

### Top-level markdown sprawl (consolidate, not delete)
- `AUTO_SCHEDULE_TASKS.md` — task-tracking in a root file is antipattern. Move to `_meta/`.
- `MIGRATION_AUDIT.md` — historical; move to `_meta/`.
- `P1_CLOSURE_AUDIT.md` — historical; move to `_meta/`.
- Keep at root: `README.md`, `PROJECT_INSTRUCTIONS.md`, `ROADMAP.md`, `V1_SCOPE.md`.

---

## Isolate (do not delete, do not wire)

These modules should stay in the repository for reversibility but must not be importable
from active runtime code.

### `app/client/signals/` (8 files)
Specific files to isolate:
- `gpt_signal.py` — GPT integration, directly contradicts v1.
- `lstm_signal.py` — LSTM, directly contradicts v1.
- `ema_signal.py`, `macd_signal.py`, `rsi_signal.py`, `sma_signal.py`, `bollinger_signal.py`, `alligator_signal.py` — technical indicators, v1 explicitly excludes runtime signals.

Isolation approach: move to `_legacy/signals/` with a `README.md` explaining they are
excluded from v1. Do NOT delete — they represent implemented work with potential future use.

### `app/client/graphics/` (6 files)
- `alligator_graph.py`, `bollinger_graph.py`, `ema_graph.py`, `macd_graph.py`, `rsi_graph.py`, `sma_graph.py`, `statistics_graph.py`.
- Not wired into v1 runtime. Move to `_legacy/graphics/`.

### `app/client/strategy/`
- Directory listed, contents not inspected in this audit.
- Owner: read contents before isolating. If purely legacy strategy automation, move to `_legacy/strategy/`.

### `app/client/store/store.py`
- Imported by `schedulers_config.py` (`from app.client.store.store import market_scheduler`).
- This import runs at startup regardless of scheduler flags.
- Decouple the import first (move `market_scheduler` to `schedulers_config.py` itself or make it lazy),
  then isolate `store.py` to `_legacy/`.

---

## Defer

These are interesting but not ready or not needed in v1.

### Price alerts engine (P6-T1)
- Useful for long-term investors. Depends on stable broker price API access.
- Not needed until P4 (analytics) is working.

### Dividend calendar and notifications (P4-T3, P6-T2)
- Good UX for long-term investors, but requires reliable dividend date data.
- Defer until dividend data quality is validated.

### Portfolio value chart (P4-T2)
- Needs portfolio snapshots first (P4-T1).
- No point building the chart without the data layer.

### Local LLM research adapter (Qwen/Qwen3-235B)
- Documented in `PROJECT_INSTRUCTIONS.md` as a future direction.
- Correct to defer: no structured output validation, no hallucination safety, no LLM infra yet.
- Do NOT wire to order execution under any circumstances.

### Educational ratings (BUY/HOLD/SELL/WATCH/AVOID)
- Described as future feature in `PROJECT_INSTRUCTIONS.md`.
- Defer: need data quality validation first. Ratings without reliable data are misleading.

### Web terminal authentication
- Currently localhost-only, no auth. Acceptable for local use.
- Defer until there's a concrete need (e.g., remote access).

### Keyboard shortcuts (P3-T2)
- Nice UX improvement. Defer until responsive layout (P3-T1) is done first.

---

## Never in v1

These must not be implemented regardless of requests or pressure.

- **Automatic order placement without Telegram confirmation** — PlanRunner must always issue a confirmation request. Never `confirmation_required=False` by default.
- **Hidden trading signals** — no RSI/MACD/GPT output routed to order creation.
- **Production orders without all three gates** — `APP_MODE=prod` + production token + `ALLOW_PROD_TRADING=true` must all be present simultaneously.
- **LLM output triggering broker orders** — any future LLM feature must have explicit human confirmation before any order is placed.
- **Alembic migration changes during unattended overnight agent runs** — schema changes require owner review.
- **Mass refactoring of app/services/orders.py or app/integrations/tinvest.py by automated agents** — these are the core safety files.
- **Complex ML models (LSTM, Transformer-based) trained on broker data** — no training infrastructure, no validation protocol, no safe fallback.
- **Enabling `ENABLE_STRATEGY_SCHEDULER`** — explicitly stubbed to no-op in `schedulers_config.py`. Must stay that way.
