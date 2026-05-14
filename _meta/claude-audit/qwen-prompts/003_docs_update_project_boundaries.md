# Prompt 003 — Docs Update: Project Boundaries

SAFE_FOR_UNATTENDED_RUN: YES
CHANGES_TO_CODE: NONE (documentation only)
OWNER_REVIEW_REQUIRED: NO (low risk — docs only, no source changes)

---

## Role

You are qwen3-coder:30b acting as a local coding agent.
You may edit ONE documentation file.
You may NOT modify any source code, tests, config, or database files.

---

## Project context

Tbot v1 / Investor v1:
- Sandbox-first, manual-first investment terminal.
- v1 scope is defined in `V1_SCOPE.md` and `PROJECT_INSTRUCTIONS.md`.
- There are several markdown files at the project root that overlap in coverage.

---

## Task

Add a brief "What is NOT in v1" section to `V1_SCOPE.md` that makes the
exclusions explicit and discoverable. The section should list:

1. No runtime trading signals (RSI, MACD, EMA, SMA, Bollinger, Alligator).
2. No GPT or LSTM integration.
3. No strategy automation (signal-driven execution).
4. No auto-trading without Telegram confirmation.
5. No educational ratings (BUY/HOLD/SELL/WATCH/AVOID) in current runtime.
6. No ML model training or inference in active runtime.
7. No chart generation from active runtime menus.

The section must NOT add new claims about future plans.
It should be concise: a bullet list, no more than 15 lines.
Match the existing writing style of `V1_SCOPE.md` (English, plain, concise).

If a "What Is Disabled" section already exists in `V1_SCOPE.md`,
extend it rather than creating a duplicate.

---

## Allowed files (may edit)

- `V1_SCOPE.md` (only this file)

## Read-only files (inspect before editing)

- `V1_SCOPE.md` (read carefully before any change)
- `README.md` (check for overlapping content to avoid duplication)
- `PROJECT_INSTRUCTIONS.md` (check for overlapping content)

## Forbidden files — do NOT touch

- `.env`, `users.json`, `database.db*`
- `app/**` (all source code)
- `tests/**`
- `alembic/**`
- `README.md` (read-only in this task)
- `PROJECT_INSTRUCTIONS.md` (read-only in this task)
- `ROADMAP.md`
- Any other file not listed under "Allowed files"

---

## Required workflow

```
1. git status --short
   → If working tree is not clean, STOP.

2. Read V1_SCOPE.md carefully.

3. Read README.md sections that cover scope to avoid duplication.

4. Write a short plan (3–5 bullet points) of what you will add/change.

5. Make the minimal edit to V1_SCOPE.md.

6. Run: git diff V1_SCOPE.md
   → If the diff touches more than the intended section, STOP and revert.

7. Run: python -m unittest discover -q
   → Tests should still pass (docs-only change should not affect tests).
   → If tests fail, STOP. Do not try to fix them. Write a failure report.

8. Write summary to _meta/claude-audit/qwen-run-log.md.
```

---

## Stop conditions

Stop immediately if:
- git status shows unexpected changes before you start.
- git diff shows changes to any file other than `V1_SCOPE.md`.
- Tests fail after your change (this should not happen for a docs edit,
  but if it does, there is a deeper problem — stop and report).
- You realize the section already exists and is adequate.
- You are unsure what to write — stop and write a question report instead.

---

## Final report format

Append to `_meta/claude-audit/qwen-run-log.md`:

```markdown
## Task 003 — Docs Update

Date: [today]
Status: COMPLETE / SKIPPED / FAILED

Changed files:
- V1_SCOPE.md (added "What Is NOT in v1" section, N lines)

Commands run:
- git status --short
- git diff V1_SCOPE.md
- .\venv312\Scripts\python.exe -m unittest discover -q

Tests result: PASS / FAIL

Notes:
[Any observations]

Rollback plan:
- git checkout V1_SCOPE.md
```
