# Prompt 005 — First Safe Test Task: PlanConfirmationService

SAFE_FOR_UNATTENDED_RUN: NO — OWNER_REVIEW_REQUIRED before running
CHANGES_TO_CODE: tests/ only (new test file)
CHANGES_TO_PRODUCTION_LOGIC: NONE

Owner must review: the test file before it is committed, and the test results.
Reason: even a test-only change can reveal assumptions about locking behavior
that the owner should confirm before they are encoded in the test suite.

---

## Role

You are qwen3-coder:30b acting as a local coding agent.
You may create ONE new test file.
You may NOT modify any production source code.

---

## Project context

Tbot v1 / Investor v1:
- Sandbox-first, manual-first investment terminal.
- `PlanConfirmationService` in `app/services/plan_confirmation.py` manages pending
  Telegram button confirmations for auto-investment plans.
- It uses a threading.Lock to protect the `_pending` dict.
- Test pattern in this project: `unittest`, fake/stub objects, no real broker, no real DB.
- Test command: `.\venv312\Scripts\python.exe -m unittest discover -q`

---

## Task

Create `tests/test_plan_confirmation_service.py` with unit tests for `PlanConfirmationService`.

Tests to write (use simple unittest.TestCase):

1. `test_issue_token_returns_unique_tokens` — issue two tokens, verify they are different.
2. `test_confirm_valid_token_calls_on_confirm` — issue a token, call confirm(), verify on_confirm was called.
3. `test_confirm_returns_true_for_valid_token` — confirm() returns True for a fresh token.
4. `test_confirm_returns_false_for_unknown_token` — confirm("nonexistent") returns False.
5. `test_double_confirm_returns_false` — confirm() returns False on second call for same token.
6. `test_skip_valid_token_calls_on_skip` — skip() calls on_skip with a reason string.
7. `test_skip_after_confirm_returns_false` — after confirm(), skip() returns False (token consumed).
8. `test_expire_old_calls_on_skip_with_timeout` — manually set expires_at to the past,
   call expire_old(), verify on_skip was called with "timeout".
9. `test_expired_token_confirm_returns_false` — set expires_at to the past, confirm() returns False.

Do NOT write tests that:
- Start a real background scheduler.
- Make network calls.
- Touch the database.
- Test thread safety (too complex for this task).

---

## Allowed files (may create/edit)

- `tests/test_plan_confirmation_service.py` (NEW — create only)

## Read-only files (inspect but do NOT modify)

- `app/services/plan_confirmation.py` (understand the API before writing tests)
- `tests/test_plan_runner.py` (for style reference — follow the same fake/stub pattern)
- `tests/test_order_service.py` (for style reference)

## Forbidden files — do NOT touch

- `app/services/plan_confirmation.py` (read only)
- `app/services/plan_runner.py`
- `app/services/orders.py`
- `app/integrations/tinvest.py`
- `.env`, `users.json`, `database.db*`
- `alembic/versions/**`
- Any existing test files (do not edit, only read for reference)

---

## Required workflow

```
1. git status --short
   → If working tree is not clean, STOP.

2. Read app/services/plan_confirmation.py carefully.

3. Read tests/test_plan_runner.py for style reference.

4. Write a 3-line plan:
   - What class/methods you are testing.
   - What fake objects you need.
   - Any edge cases.

5. Create tests/test_plan_confirmation_service.py.

6. Run: .\venv312\Scripts\python.exe -m unittest discover -q
   → All tests must pass.
   → If your new tests fail, investigate once.
   → If still failing after one fix, STOP. Write failure report. Do NOT delete the test file.

7. Run: git diff --stat
   → Only tests/test_plan_confirmation_service.py should appear.
   → If any other file appears, STOP. Run git checkout on unexpected files.

8. Write summary to _meta/claude-audit/qwen-run-log.md.
```

---

## Stop conditions

Stop immediately if:
- git status is not clean at the start.
- Tests fail after one fix attempt.
- Any file other than the new test file is in git diff.
- You find a need to modify `plan_confirmation.py` to make tests pass.
  (If the API does not match expectations, stop and write a report instead.)
- A test requires mocking the threading.Lock (too complex — simplify the test instead).

---

## Final report format

Append to `_meta/claude-audit/qwen-run-log.md`:

```markdown
## Task 005 — PlanConfirmationService Tests

Date: [today]
Status: COMPLETE / FAILED / STOPPED

Created files:
- tests/test_plan_confirmation_service.py (N tests)

Commands run:
- git status --short
- .\venv312\Scripts\python.exe -m unittest discover -q
- git diff --stat

Tests result: N tests, 0 failures, 0 errors / FAILED (reason)

Risks:
[Any concerns about the test coverage or assumptions made]

Rollback plan:
- git rm tests/test_plan_confirmation_service.py
- git checkout .

Checklist:
- [ ] 9 test cases written
- [ ] All tests pass
- [ ] Only the new test file in git diff
- [ ] No production code modified
- [ ] Log entry written
```
