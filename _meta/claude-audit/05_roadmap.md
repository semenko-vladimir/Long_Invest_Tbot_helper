# Stabilization & Safety Roadmap

Audit date: 2026-05-14

This roadmap covers **stabilization, cleanup, and safety hardening** —
not new features. The feature roadmap (P0–P6) is already in `ROADMAP.md`.
This document is a complement to it, focused on what must be solid before
feature work continues safely.

Cross-reference: `ROADMAP.md` (existing feature roadmap), `P1_CLOSURE_AUDIT.md`.

---

## Stage 0 — Stabilization

**Goal:** Fix two correctness bugs that block safe P2 implementation.

**Tasks:**
1. Fix `PlanConfirmationService` deadlock: `_execute` callback must not run
   while `self._lock` is held when it contains broker I/O.
   Pattern: capture the callback, release the lock, then call the callback.
2. Fix `investor_reminders.py` multi-user: replace `require_env("CHAT_ID")` with
   `UserContextResolver().enabled_users()` and send to all enabled users.

**Allowed files:**
- `app/services/plan_confirmation.py`
- `app/client/config/investor_reminders.py`
- Tests in `tests/` for the above (add or update only)

**Forbidden files:**
- `app/services/orders.py`
- `app/integrations/tinvest.py`
- `app/services/plan_runner.py`
- `alembic/versions/*`
- `.env`, `users.json`, `database.db*`

**Acceptance criteria:**
- `python -m unittest discover -q` passes.
- `PlanConfirmationService.confirm()` does not hold `_lock` while calling `on_confirm()`.
- `configure_investor_reminders()` iterates all enabled users via `UserContextResolver`.
- New/updated tests cover both fixes.

**Tests:**
- Add `tests/test_plan_confirmation_service.py` — token issuance, confirm, skip, expire, double-consume.
- Update or add reminder test covering multi-user iteration.

**Rollback plan:**
- `git revert` the two commits independently (one per fix).

**Do not do:**
- Touch `OrderService`, `TInvestBroker`, APScheduler wiring.
- Change any `.env` variable names or behavior.
- Implement P2-T1 (APScheduler wiring for PlanRunner). Stage 0 is a prerequisite, not P2.

---

## Stage 1 — Legacy isolation

**Goal:** Make legacy signal/graphics/strategy modules un-importable from the active v1 runtime without deleting them.

**Tasks:**
1. Create `_legacy/` directory at project root.
2. Move `app/client/signals/` to `_legacy/signals/`.
3. Move `app/client/graphics/` to `_legacy/graphics/`.
4. Read `app/client/strategy/` and `app/client/orders/` contents; move to `_legacy/` if confirmed legacy.
5. Decouple `schedulers_config.py` import of `app.client.store.store` (make it lazy or remove).
6. Verify: `grep -r "from app.client.signals" app/` returns empty.
7. Verify: `grep -r "from app.client.graphics" app/` returns empty.
8. Add `_legacy/README.md` explaining that files there are excluded from v1 runtime.

**Allowed files:**
- Entire `_legacy/` directory (new, created by this stage).
- `app/client/config/schedulers_config.py` (only to remove the `store` import).
- `_legacy/README.md` (new).

**Forbidden files:**
- `app/services/**`
- `app/integrations/**`
- `alembic/**`
- `tests/**` (only add tests, don't change existing)
- `.env`, `users.json`

**Acceptance criteria:**
- `python -m unittest discover -q` passes.
- No `import` in `app/` references `app.client.signals.*` or `app.client.graphics.*`.
- `app/run.py` startup completes without importing legacy signal modules.

**Rollback plan:**
- `git revert` the move commits. Files are moved, not deleted; recovery is clean.

**Do not do:**
- Delete any legacy files (move only).
- Change signal logic or reimport them elsewhere.
- Touch trading execution code.

---

## Stage 2 — Test gaps

**Goal:** Fill the most critical test gaps identified in the audit.

**Tasks (in order of priority):**
1. `tests/test_plan_confirmation_service.py` — if not created in Stage 0, create here.
2. `tests/test_watchlist_service.py` — ROADMAP P0-T3 gap (WatchlistService add/remove/duplicate/error cases).
3. `tests/test_investor_reminders.py` — test multi-user iteration, bad env fallback, scheduler not started when disabled.
4. Review existing tests for `test_p1_user_context_wiring.py` — ensure it covers the multi-user reminder path after Stage 0 fix.

**Allowed files:**
- All files in `tests/` (add new test files only; do not edit app source for these tests).
- `app/services/watchlist.py` (read-only; if WatchlistService API doesn't match expected, report and stop).

**Forbidden files:**
- All `app/services/` except read-only inspection.
- `app/integrations/**`
- `alembic/**`
- `.env`, `users.json`, `database.db*`

**Acceptance criteria:**
- All tests pass.
- Coverage for PlanConfirmationService, WatchlistService, and investor reminders is added.
- No regressions in existing test suite.

**Rollback plan:**
- Test files are new additions. `git rm` the new files if they break the suite unexpectedly.

**Do not do:**
- Modify `app/services/orders.py` or `app/integrations/tinvest.py` to make tests easier.
- Write integration tests that require a live broker or Telegram connection.
- Add mocks that misrepresent production behavior (especially for order execution).

---

## Stage 3 — Analytics core

**Goal:** Portfolio snapshot storage (P4-T1 from ROADMAP) — the data layer for future charts.

**Tasks:**
1. Add `PortfolioSnapshot` DB model in `app/backend/models/analytics.py`.
2. Add `SnapshotService` in `app/services/snapshot.py` (`take_snapshot()`, `list_snapshots()`).
3. Wire `take_snapshot()` to a daily APScheduler job (configurable time, default 18:00 Moscow).
4. Add `GET /api/snapshots/portfolio` route returning JSON list of `{date, value}`.
5. Guard: if portfolio data unavailable (broker error), skip silently and log warning.

**This is from ROADMAP.md P4-T1. Follow the full task specification there.**

**Acceptance criteria:**
- `python -m unittest discover -q` passes.
- Snapshot is created without real broker (stub-based test).
- Alembic migration added for `PortfolioSnapshot` table (Alembic only for this change).

**Do not do:**
- Build charts (P4-T2) in this stage.
- Wire to auto-investing execution.
- Change existing portfolio service behavior.

---

## Stage 4 — UX polish

**Goal:** Responsive web terminal layout (P3-T1 from ROADMAP).

**Tasks:**
- Follow ROADMAP.md P3-T1 specification exactly.
- HTML and CSS only. No Python file changes.

**Note:** This is the safest stage for an automated agent because it has zero risk
of affecting trading behavior. However, it's also the hardest to verify automatically
(requires visual browser check).

---

## Stage 5 — Documentation consolidation

**Goal:** Reduce root-level markdown sprawl and add ARCHITECTURE.md.

**Tasks:**
1. Move `MIGRATION_AUDIT.md`, `P1_CLOSURE_AUDIT.md`, `AUTO_SCHEDULE_TASKS.md` to `_meta/history/`.
2. Consider moving `INVESTOR_MODE.md` and `RESEARCH_TERMINAL_FOUNDATION.md` to `docs/`.
3. Add `ARCHITECTURE.md` with service dependency graph (text diagram, no external tools).
4. Update `README.md` to point to the new file locations.

**Allowed files:**
- New files in `_meta/history/` and `docs/`.
- `README.md` (only to update cross-references).

**Forbidden files:**
- `PROJECT_INSTRUCTIONS.md` (do not change without owner review).
- Any source code files.

**Acceptance criteria:**
- `python -m unittest discover -q` passes (no broken imports from moved files).
- `README.md` links are all valid.
- Root directory has ≤ 5 markdown files.
