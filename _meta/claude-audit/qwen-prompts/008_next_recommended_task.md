# Prompt 008 — Next Recommended Task: WatchlistService Tests (P0-T3)

SAFE_FOR_UNATTENDED_RUN: NO — OWNER_REVIEW_REQUIRED
CHANGES_TO_CODE: tests/ only (new test file)
OWNER_REVIEW_REQUIRED: YES

Owner must review: confirm that WatchlistService API matches expectations
before this prompt is run. Prerequisite: run Prompt 004 (tests gap report) first.
If 004 shows that WatchlistService tests already exist and are adequate, skip this prompt.

---

## Role

You are qwen3-coder:30b acting as a local coding agent.
You may create ONE new test file.
You may NOT modify any production source code.

---

## Project context

Tbot v1 / Investor v1:
- The ROADMAP (P0-T3) planned WatchlistService unit tests that were not completed.
- `WatchlistService` in `app/services/watchlist.py` handles watchlist CRUD:
  add_ticker, remove_ticker, get_tickers, and error handling for duplicates and unknowns.
- Test pattern: `unittest`, fake/stub session factory, no real DB, no real broker.
- Test command: `.\venv312\Scripts\python.exe -m unittest discover -q`

---

## Prerequisite check

Before starting this task:
1. Read `_meta/claude-audit/004_tests_gap_report.md` (from Prompt 004).
2. If it says WatchlistService tests already exist and pass, STOP. Write "skipped — already covered" to the log.
3. If `app/services/watchlist.py` has a different API than described below, STOP and write a report.
   Do NOT adapt the tests to a different API without owner review.

---

## Task

Create `tests/test_watchlist_service.py` with unit tests for `WatchlistService`.

Expected WatchlistService API (verify against actual code before writing):
- `add_ticker(ticker: str) -> list[str]` — adds ticker, returns updated list
- `remove_ticker(ticker: str) -> list[str]` — removes ticker, returns updated list
- Raises `WatchlistServiceError` (or similar) for: empty ticker, duplicate add, unknown remove

Tests to write:

1. `test_add_ticker_returns_updated_list` — add a ticker, verify it appears in result.
2. `test_add_ticker_persists_in_db` — add a ticker, get_tickers() returns it.
3. `test_add_empty_ticker_raises_error` — `add_ticker("")` raises expected error.
4. `test_add_duplicate_ticker_raises_error` — add same ticker twice, second raises error.
5. `test_remove_ticker_removes_from_list` — add then remove, verify it is gone.
6. `test_remove_unknown_ticker_raises_error` — remove ticker not in watchlist raises error.
7. `test_get_tickers_returns_empty_on_fresh_db` — fresh fake DB returns empty list.

Use the same stub pattern as `tests/test_order_service.py`:
- Fake session factory / fake DB that stores data in memory.
- No real SQLAlchemy sessions (or use SQLite in-memory: `sqlite:///:memory:`).

---

## Allowed files (may create)

- `tests/test_watchlist_service.py` (NEW — create only)

## Read-only files (inspect before writing)

- `app/services/watchlist.py` (read completely — understand the real API)
- `tests/test_order_service.py` (style and fake pattern reference)
- `tests/test_investment_plans.py` (additional reference for DB faking)
- `_meta/claude-audit/004_tests_gap_report.md` (prerequisite)

## Forbidden files — do NOT touch

- `app/services/watchlist.py` (do not modify)
- Any existing test files
- `app/integrations/tinvest.py`
- `app/services/orders.py`
- `.env`, `users.json`, `database.db*`
- `alembic/versions/**`

---

## Required workflow

```
1. git status --short
   → If working tree is not clean, STOP.

2. Read _meta/claude-audit/004_tests_gap_report.md.
   → If WatchlistService is already covered, STOP and write "skipped" to log.

3. Read app/services/watchlist.py completely.
   → If the API is different from what this prompt describes, STOP and write a discrepancy report.

4. Read tests/test_order_service.py for style reference.

5. Write a 3-line plan.

6. Create tests/test_watchlist_service.py.

7. Run: .\venv312\Scripts\python.exe -m unittest discover -q
   → All tests must pass.
   → If your new tests fail, investigate once.
   → If still failing, STOP. Do NOT delete the test file. Write failure report.

8. Run: git diff --stat
   → Only tests/test_watchlist_service.py should appear.

9. Write summary to _meta/claude-audit/qwen-run-log.md.
```

---

## Stop conditions

- git status is not clean at the start.
- Prerequisite 004 report shows tests already exist.
- WatchlistService API differs from the description — stop and report, do not adapt.
- Tests fail after one fix attempt.
- Any file other than the new test file in git diff.
- You need to modify `watchlist.py` to make tests pass.

---

## Rollback

```bash
git rm tests/test_watchlist_service.py
.\venv312\Scripts\python.exe -m unittest discover -q
```

---

## Final report format

Append to `_meta/claude-audit/qwen-run-log.md`:

```markdown
## Task 008 — WatchlistService Tests

Date: [today]
Status: COMPLETE / SKIPPED / FAILED

Created files:
- tests/test_watchlist_service.py (N tests) — or SKIPPED

Commands run:
[list]

Tests result: N tests, 0 failures / FAILED

API discrepancies found:
[None / or list discrepancies]

Rollback plan:
- git rm tests/test_watchlist_service.py

Checklist:
- [ ] Prerequisite 004 checked
- [ ] WatchlistService API verified
- [ ] 7 test cases written
- [ ] All tests pass
- [ ] Only new test file in diff
- [ ] No production code modified
- [ ] OWNER: review before committing
```
