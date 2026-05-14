# Prompt 007 — First Safe Refactor: Decouple legacy store import

SAFE_FOR_UNATTENDED_RUN: NO — OWNER_REVIEW_REQUIRED
CHANGES_TO_CODE: YES — one production file
OWNER_REVIEW_REQUIRED: YES

Owner must review: git diff of `app/client/config/schedulers_config.py` before committing.
Reason: this touches a startup file. Even a small change can break the startup path.

---

## Role

You are qwen3-coder:30b acting as a local coding agent.
You may edit ONE production source file to fix a specific import issue.
All existing tests must pass after your change.

---

## Project context

Tbot v1 / Investor v1:
- Sandbox-first, manual-first investment terminal.
- `app/client/config/schedulers_config.py` currently imports at module level:
  `from app.client.store.store import market_scheduler`
- This means the legacy `store.py` module is imported at startup even when
  `ENABLE_BACKGROUND_SCHEDULERS=false`, which is the default for v1.
- The goal is to make this import lazy (inside the function that uses it),
  so the legacy store is not loaded during normal v1 startup.

---

## Task

In `app/client/config/schedulers_config.py`:
1. Remove the top-level `from app.client.store.store import market_scheduler` import.
2. Move that import inside `configure_market_scheduler()`, where `market_scheduler` is actually used.
3. Declare `market_scheduler = None` at module level (to replace the imported reference used by the shutdown check).

The change must:
- Not change any function signatures.
- Not change the behavior of `configure_schedulers()` when `background_schedulers_enabled()` returns False.
- Not change the behavior of `configure_market_scheduler()` when it runs.
- Pass all existing tests.

---

## Before you start: understand the current code

Read `app/client/config/schedulers_config.py` completely.
Note: `configure_market_scheduler()` uses `market_scheduler` as a global variable
(it checks `if market_scheduler: market_scheduler.shutdown()` and assigns a new one).
Your refactor must preserve this global variable pattern — just stop importing it from `store.py`.

---

## Allowed files (may edit)

- `app/client/config/schedulers_config.py` (ONE file only)

## Read-only files (inspect before editing)

- `app/client/config/schedulers_config.py` (read completely first)
- `app/client/store/store.py` (understand what `market_scheduler` is)
- `tests/test_schedulers_config.py` (if exists — read to understand test coverage)

## Forbidden files — do NOT touch

- `app/client/store/store.py` (do not modify — just stop importing from it at module level)
- `app/services/orders.py`
- `app/integrations/tinvest.py`
- `app/services/plan_runner.py`
- `app/run.py` (do not touch)
- `.env`, `users.json`, `database.db*`
- `alembic/versions/**`
- `tests/**` (do not edit existing tests)

---

## Required workflow

```
1. git status --short
   → If working tree is not clean, STOP.

2. Read app/client/config/schedulers_config.py completely.

3. Read app/client/store/store.py to understand what market_scheduler is.

4. Write a 3-line plan of your change.

5. Make the minimal edit to schedulers_config.py.

6. Run: .\venv312\Scripts\python.exe -m unittest discover -q
   → All tests must pass.
   → If tests fail, investigate once.
   → If still failing after one fix attempt, revert and STOP.

7. Run: git diff app/client/config/schedulers_config.py
   → Review the diff. If it is larger than 10 lines or touches unexpected code, STOP.

8. Run: python app/run.py --help 2>&1 || python -c "import app.client.config.schedulers_config; print('import ok')"
   → Verify the module still imports without error.

9. Write summary to _meta/claude-audit/qwen-run-log.md.
```

---

## Stop conditions

Stop immediately if:
- git status is not clean at the start.
- Tests fail after one fix attempt — revert `schedulers_config.py` (`git checkout app/client/config/schedulers_config.py`).
- git diff shows more than 15 lines changed.
- git diff shows any file other than `schedulers_config.py`.
- The module fails to import after your change.
- You realize the change requires modifying more than one file.

---

## Rollback

```bash
git checkout app/client/config/schedulers_config.py
```

Verify with:
```bash
.\venv312\Scripts\python.exe -m unittest discover -q
```

---

## Final report format

Append to `_meta/claude-audit/qwen-run-log.md`:

```markdown
## Task 007 — Decouple store import in schedulers_config.py

Date: [today]
Status: COMPLETE / FAILED / REVERTED

Changed files:
- app/client/config/schedulers_config.py

Commands run:
- git status --short
- .\venv312\Scripts\python.exe -m unittest discover -q
- git diff app/client/config/schedulers_config.py
- python -c "import app.client.config.schedulers_config; print('import ok')"

Tests result: PASS / FAIL

Diff summary:
[Paste the actual diff here — it should be < 15 lines]

Risks:
[Any concern about the change]

Rollback plan:
- git checkout app/client/config/schedulers_config.py
- Verify: .\venv312\Scripts\python.exe -m unittest discover -q

Checklist:
- [ ] Only schedulers_config.py in diff
- [ ] Tests pass
- [ ] Module imports cleanly
- [ ] No behavior change in configure_schedulers() when disabled
- [ ] Log entry written
- [ ] OWNER: review diff before committing
```
