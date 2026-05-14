# Prompt 004 — Report-Only: Tests Gap Analysis

SAFE_FOR_UNATTENDED_RUN: YES
CHANGES_TO_CODE: NONE
OWNER_REVIEW_REQUIRED: NO

---

## Role

You are qwen3-coder:30b acting as a local coding agent in read-only audit mode.
You are NOT allowed to write or modify any test or source files.
Your only output is a report.

---

## Project context

Tbot v1 / Investor v1:
- Sandbox-first, manual-first investment terminal.
- Test command: `.\venv312\Scripts\python.exe -m unittest discover -q`
- Test files are in `tests/`.
- The project uses `unittest` with fake/stub objects (FakeBroker, FakeModeService pattern).
- No real broker connections or live database in tests.

---

## Task

Analyze the current test suite and produce a gap report.
Make zero code changes.

Specifically:

1. List all existing test files in `tests/`.
2. For each test file, identify: which service/module it covers.
3. List all service modules in `app/services/`.
4. For each service module, check: is there a test file that covers it?
5. List gaps: services with no test coverage.
6. For the most critical services (orders.py, plan_runner.py, trading_policy.py,
   plan_confirmation.py, mode.py), check if the following scenarios are tested:
   - orders.py: no token → blocked; expired token → blocked; consumed token → blocked;
     prod mode without ticker confirmation → blocked; lot < 1 → validation error.
   - plan_runner.py: non-trading day → skipped; price condition fails → skipped;
     broker error on preview → skipped; successful flow → sent_for_confirmation.
   - trading_policy.py: MAX_ORDER_RUB exceeded → blocked; MAX_DAILY exceeded → blocked.
   - plan_confirmation.py: double-confirm → returns False; expired token → returns False.
7. Run the existing test suite and report results.
8. Identify any currently failing tests.

---

## Allowed files (read only — do NOT modify)

- All files in `tests/`
- All files in `app/services/`
- `app/client/config/__init__.py` (to understand config functions under test)

## Commands allowed

```bash
.\venv312\Scripts\python.exe -m unittest discover -q
.\venv312\Scripts\python.exe -m unittest discover -v 2>&1 | head -100
```

## Forbidden — do NOT touch

- `.env`, `users.json`, `database.db*`
- `app/integrations/**`
- `alembic/versions/**`
- Any writing to files other than `_meta/claude-audit/`

---

## Required workflow

```
1. git status --short
   → If working tree is not clean, STOP.

2. List tests/ directory.

3. List app/services/ directory.

4. Read each test file header (first 30 lines) to understand coverage.

5. Run: .\venv312\Scripts\python.exe -m unittest discover -q
   Record: number of tests, failures, errors.

6. For each critical service, verify coverage of specific scenarios.

7. Write _meta/claude-audit/004_tests_gap_report.md.

8. Append summary to _meta/claude-audit/qwen-run-log.md.
```

---

## Stop conditions

Stop immediately if:
- git status shows uncommitted changes at the start.
- Tests produce import errors that suggest broken dependencies.
- You find yourself about to write or edit any test or source file.

---

## Final report format

File: `_meta/claude-audit/004_tests_gap_report.md`

```markdown
# Tests Gap Report — 004

Date: [today]
Model: qwen3-coder:30b
Mode: report-only

## Test suite result
Total tests: N
Failures: N
Errors: N
Skipped: N

## Service coverage matrix

| Service module | Test file | Coverage verdict |
|----------------|-----------|-----------------|
| orders.py | test_order_service.py | covered / partial / missing |
| plan_confirmation.py | ? | |
| trading_policy.py | ? | |
...

## Critical scenario checks

| Service | Scenario | Tested? | Test file:line |
|---------|----------|---------|----------------|
| orders.py | no token → blocked | yes/no | |
...

## Gaps (priority order)
1. [Most critical missing test]
2. ...

## Currently failing tests
[List any failures with error message]

## Changed files
NONE

## Commands run
[List]

## Checklist
- [ ] All test files listed
- [ ] All service modules checked
- [ ] Critical scenarios verified
- [ ] Tests run and results recorded
- [ ] No files modified
- [ ] Log entry written
```
