# Prompt 006 — First Safe Docs Task: Add ARCHITECTURE.md

SAFE_FOR_UNATTENDED_RUN: YES (docs-only, no source changes)
CHANGES_TO_CODE: NONE
OWNER_REVIEW_REQUIRED: NO (low risk — new file only, no edits to existing docs)

---

## Role

You are qwen3-coder:30b acting as a local coding agent.
You may create ONE new documentation file.
You may NOT modify any existing files (source, tests, or existing docs).

---

## Project context

Tbot v1 / Investor v1:
- Sandbox-first local investment terminal.
- Project has a service layer: `app/services/` contains the business logic.
- There is currently no document describing the service dependency graph.
- The project has 11 root-level markdown files and lacks an architectural overview.

---

## Task

Create `docs/ARCHITECTURE.md` describing the runtime service dependency graph
of the active v1 system.

The document must:
1. Describe the two entry points: Telegram bot (`app/run.py`) and web terminal (`app/backend/main_api.py`).
2. List the active services in `app/services/` and what each does (one sentence).
3. Show the order execution chain: Telegram handler → OrderService → preview token → confirm → TInvestBroker.
4. Show the multi-user resolution chain: Telegram message → UserContextResolver → UserContext → per-user SessionFactory → DB-backed service.
5. Describe the safety layers: ModeService, OrderService token TTL, TradingPolicyService, ALLOW_PROD_TRADING guard.
6. Note which modules are legacy/inactive (signals, graphics, strategy) and where they live.
7. Note that `PlanRunner` is implemented but not yet scheduled (P2-T1 pending).

Format: plain Markdown with text-based dependency notation (no Mermaid, no external tools required).
Length: 100–200 lines. Concise. No fluff.

---

## Preparation

Before writing, read these files to gather accurate information:

- `app/run.py`
- `app/backend/main_api.py`
- `app/services/orders.py` (first 50 lines)
- `app/services/mode.py`
- `app/services/user_context.py`
- `README.md` (for the existing Mermaid diagram — adapt it to text)
- `PROJECT_INSTRUCTIONS.md`

List of active services to document (read their `__init__` or class definition):
- `app/services/mode.py` → ModeService
- `app/services/orders.py` → OrderService
- `app/services/portfolio.py` → PortfolioService
- `app/services/watchlist.py` → WatchlistService
- `app/services/dividends.py` → DividendsService
- `app/services/investment_plans.py` → InvestmentPlanService
- `app/services/statistics.py` → StatisticsService
- `app/services/trading_policy.py` → TradingPolicyService
- `app/services/plan_runner.py` → PlanRunner (pending P2-T1)
- `app/services/plan_confirmation.py` → PlanConfirmationService
- `app/services/settings_view.py` → SettingsViewService
- `app/services/order_history.py` → OrderHistoryService
- `app/services/user_context.py` → UserContextResolver
- `app/services/user_database.py` → SessionFactory

---

## Allowed files (may create)

- `docs/ARCHITECTURE.md` (NEW — create only)

If `docs/` directory does not exist, create it.

## Read-only files

- All files listed in "Preparation" above.
- Any `app/services/*.py` file (read-only).

## Forbidden files — do NOT touch

- `.env`, `users.json`, `database.db*`
- `README.md` (do not edit — only read)
- `PROJECT_INSTRUCTIONS.md` (do not edit)
- `app/**` source files (do not edit)
- `tests/**`
- `alembic/**`
- Any existing file at project root

---

## Required workflow

```
1. git status --short
   → If working tree is not clean, STOP.

2. Read the preparation files listed above.

3. Write a 5-line outline of the document structure.

4. Create docs/ARCHITECTURE.md.

5. Run: git diff --stat
   → Only docs/ARCHITECTURE.md (new file) should appear.
   → If any other file changed, STOP.

6. Run: .\venv312\Scripts\python.exe -m unittest discover -q
   → All tests should still pass (docs-only change).
   → If tests fail, stop and report — do not try to fix source code.

7. Append summary to _meta/claude-audit/qwen-run-log.md.
```

---

## Stop conditions

- git status is not clean at the start.
- You find yourself editing any existing file.
- The document would need to make claims you cannot verify from the files you've read.
  (Write "unverified" or "not inspected" instead of guessing.)
- Tests fail (should not happen for docs-only change — stop and report if they do).

---

## Final report format

Append to `_meta/claude-audit/qwen-run-log.md`:

```markdown
## Task 006 — ARCHITECTURE.md

Date: [today]
Status: COMPLETE / SKIPPED / FAILED

Created files:
- docs/ARCHITECTURE.md (N lines)

Commands run:
- git status --short
- git diff --stat
- .\venv312\Scripts\python.exe -m unittest discover -q

Tests result: PASS

Notes:
[Anything you could not verify or had to mark as "unverified"]

Rollback plan:
- git rm docs/ARCHITECTURE.md
```
