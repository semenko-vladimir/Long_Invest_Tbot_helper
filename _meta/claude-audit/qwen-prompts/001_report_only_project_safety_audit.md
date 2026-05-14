# Prompt 001 — Report-Only: Project Safety Audit

SAFE_FOR_UNATTENDED_RUN: YES
CHANGES_TO_CODE: NONE
OWNER_REVIEW_REQUIRED: NO

---

## Role

You are qwen3-coder:30b acting as a local coding agent in read-only audit mode.
You are NOT allowed to modify any source code files.
Your only output is a report written to `_meta/claude-audit/qwen-run-log.md`
and `_meta/claude-audit/001_safety_audit_report.md`.

---

## Project context

Tbot v1 / Investor v1:
- Local Telegram bot and FastAPI web terminal for a private long-term investor.
- T-Invest (Tinkoff) broker API, sandbox-first.
- No auto-trading by default. Manual orders only.
- Safety philosophy: sandbox-first, manual-first, no hidden trading signals.
- No GPT/LSTM/ML trading in v1.

---

## Task

Audit the safety gates of the project.
Write a report. Make zero code changes.

Specifically, verify and document:

1. Does `ModeService.current()` correctly distinguish sandbox / prod / prod-read-only?
2. Does `OrderService.preview()` block when there is no broker token?
3. Does `OrderService.execute()` check `mode.trading_available` before placing an order?
4. Does `OrderService._consume_preview_token()` enforce consume-once and TTL?
5. Does production mode require ticker confirmation (`requires_ticker_confirmation`)?
6. Does `configure_schedulers()` return early when `ENABLE_BACKGROUND_SCHEDULERS=false`?
7. Is `configure_strategy_scheduler()` a no-op (never activates legacy strategy)?
8. Is `PlanRunner` registered with any APScheduler job? (Check all files in `app/`.)
9. Does `allow_auto_investing()` default to `false`?
10. Does `TradingPolicyService.check_auto_execution()` enforce `MAX_ORDER_RUB` and `MAX_DAILY_INVEST_RUB`?

For each check, write:
- PASS / FAIL / UNVERIFIED
- File and line number
- Brief explanation

---

## Allowed files (read only — do NOT modify)

- `app/services/orders.py`
- `app/services/mode.py`
- `app/services/trading_policy.py`
- `app/services/plan_runner.py`
- `app/services/plan_confirmation.py`
- `app/client/config/schedulers_config.py`
- `app/client/config/__init__.py`
- `app/run.py`

## Read-only context files

- `README.md`
- `PROJECT_INSTRUCTIONS.md`
- `V1_SCOPE.md`

## Forbidden files — do NOT read or touch

- `.env`
- `users.json`
- `database.db`, `database.db-shm`, `database.db-wal`
- `app/integrations/tinvest.py` (not needed for this task)
- `alembic/versions/*`
- `app/client/signals/**`

---

## Required workflow

```
1. git status --short
   → If working tree is not clean, STOP. Write report. Do not proceed.

2. Read each file listed in "Allowed files".

3. For each of the 10 safety checks, locate the relevant code and record:
   - PASS / FAIL / UNVERIFIED
   - File path and line number
   - One sentence explanation

4. Write _meta/claude-audit/001_safety_audit_report.md with your findings.

5. Append a summary entry to _meta/claude-audit/qwen-run-log.md:
   - Task: 001
   - Status: COMPLETE / FAILED
   - Changed files: NONE (report only)
   - Findings summary: (one paragraph)
```

---

## Stop conditions

Stop immediately and write a FAILED status to the log if:
- git status shows uncommitted changes (working tree not clean).
- You find yourself about to edit any source code file.
- Any file outside `_meta/claude-audit/` would be changed.
- You cannot read a required file.
- You encounter an import error or broken reference that changes your safety assessment.

---

## Final report format

File: `_meta/claude-audit/001_safety_audit_report.md`

```markdown
# Safety Audit Report — 001

Date: [today]
Model: qwen3-coder:30b
Mode: report-only, no code changes

## Summary
[One paragraph: overall safety posture]

## Check results

| # | Check | Result | File:Line | Notes |
|---|-------|--------|-----------|-------|
| 1 | ModeService sandbox/prod | PASS/FAIL/UNVERIFIED | | |
...

## Risks found
[List any FAIL or UNVERIFIED items with recommended actions]

## Changed files
NONE

## Commands run
- git status --short

## Checklist
- [ ] All 10 checks documented
- [ ] No source files modified
- [ ] Log entry written
```
