# Qwen Agent Run Order

This file defines the safe execution order for qwen3-coder:30b
running as a coding agent (Roo Code / Cline / Aider / OpenCode).

---

## 1. Which agent tool to use

Recommended tools (in order of preference for this project):

1. **Roo Code** (VS Code extension) — best for file-aware coding agent with Ollama.
2. **Cline** (VS Code extension) — solid file-read/write, terminal, good Ollama support.
3. **Aider** — terminal-based, mature, good for targeted file edits.
4. **OpenCode** — newer, check Ollama compatibility before using.

All tools must be configured with:
- Provider: **Ollama** (local)
- Model: **qwen3:coder-30b** or `qwen3-coder:30b` (exact name depends on your Ollama pull)
- Base URL: `http://localhost:11434` (default Ollama)

---

## 2. How to connect the model

### Ollama setup

```bash
# Verify model is available
ollama list

# If not pulled yet
ollama pull qwen3-coder:30b

# Check it runs
ollama run qwen3-coder:30b "say: ready"
```

### Context window settings

Start with a SMALL context to avoid OOM on 30B:

| Setting | Value |
|---------|-------|
| Context window | 4096 (start here) |
| Max tokens output | 2048 |
| Temperature | 0 (deterministic for code tasks) |

If 4096 is too small for a task, increase to 8192.
Do NOT give qwen the entire repository as context at once.
Feed it only the files listed in the specific prompt.

### Working directory

```powershell
cd C:\Users\vladimir\Desktop\Investment\Tbot
```

---

## 3. Execution order

Run prompts in this exact sequence. Do not skip ahead.

| Order | Prompt file | Type | Unattended? |
|-------|------------|------|-------------|
| 1 | `001_report_only_project_safety_audit.md` | report | YES |
| 2 | `002_report_only_legacy_inventory.md` | report | YES |
| 3 | `004_tests_gap_report.md` | report | YES |
| 4 | `003_docs_update_project_boundaries.md` | docs edit | YES (low risk) |
| 5 | `006_first_safe_docs_task.md` | new docs file | YES |
| 6 | **OWNER REVIEW POINT** | — | STOP |
| 7 | `005_first_safe_test_task.md` | new test file | NO — owner review |
| 8 | `007_first_safe_refactor_task.md` | 1-file refactor | NO — owner review |
| 9 | `008_next_recommended_task.md` | new test file | NO — owner review |

---

## 4. Prompts safe for unattended overnight run

```
SAFE_FOR_UNATTENDED_RUN:
  001 — safety audit report (read-only)
  002 — legacy inventory report (read-only)
  003 — V1_SCOPE.md docs update (docs-only)
  004 — tests gap report (read-only)
  006 — create docs/ARCHITECTURE.md (new file, docs-only)
```

Use `000_overnight_coding_agent_supervisor.md` to run these automatically.

---

## 5. Prompts that require owner review before running

```
OWNER_REVIEW_REQUIRED:
  005 — adds PlanConfirmationService tests (review test design and results)
  007 — edits schedulers_config.py (review git diff before committing)
  008 — adds WatchlistService tests (requires 004 report first; review API match)
```

Do not give these to qwen overnight without reviewing the audit outputs from 001–004 first.

---

## 6. Commands to run before starting

```powershell
# 1. Check Python environment
.\venv312\Scripts\python.exe --version

# 2. Check all tests pass before any agent work
.\venv312\Scripts\python.exe -m unittest discover -q

# 3. Check git is clean
git status --short

# 4. Record the starting state
git log --oneline -5

# 5. Optional: create a backup branch
git checkout -b before-qwen-run
git checkout main
```

If tests fail before qwen starts, fix them yourself first. Do not give qwen a broken suite.

---

## 7. Commands to run after each task

```powershell
# After each qwen task:
git status --short
git diff --stat
.\venv312\Scripts\python.exe -m unittest discover -q
```

Read `_meta/claude-audit/qwen-run-log.md` to check qwen's own summary.

---

## 8. When qwen must stop

qwen must stop (within a task or between tasks) if any of these occur:

- `git status --short` shows unexpected changed files.
- `git diff` includes changes to:
  - `.env`, `users.json`, `database.db*`
  - `alembic/versions/`
  - `app/services/orders.py`
  - `app/integrations/tinvest.py`
  - `app/services/plan_runner.py`
  - `app/services/trading_policy.py`
  - `app/services/mode.py`
  - `app/services/plan_confirmation.py`
- Tests fail after one fix attempt.
- A task's diff is larger than 30 lines (scope grew beyond safe).
- qwen cannot run tests (broken imports, missing venv312).
- Any task requires an owner decision.
- Any change would affect real trading behavior or safety gates.
- Memory/context problems cause incoherent output.

---

## 9. How to check the result in the morning

```powershell
# 1. Check what changed
git status --short
git diff --stat
git log --oneline -10

# 2. Run the test suite
.\venv312\Scripts\python.exe -m unittest discover -q

# 3. Read qwen's log
cat _meta/claude-audit/qwen-run-log.md

# 4. Read qwen's final report
cat _meta/claude-audit/qwen-final-report.md

# 5. Review any new files
# Expected new files after a safe overnight run:
#   _meta/claude-audit/001_safety_audit_report.md
#   _meta/claude-audit/002_legacy_inventory_report.md
#   _meta/claude-audit/004_tests_gap_report.md
#   V1_SCOPE.md (small addition)
#   docs/ARCHITECTURE.md (new)
#   _meta/claude-audit/qwen-run-log.md
#   _meta/claude-audit/qwen-final-report.md

# 6. If anything looks wrong
git checkout .    # revert uncommitted changes
# or
git revert HEAD   # revert last commit
```

---

## Absolute forbidden list (for any qwen task, at any time)

qwen must NEVER:

```
- Touch .env, .env.example, users.json
- Touch database.db, database.db-shm, database.db-wal
- Touch alembic/versions/*
- Touch app/services/orders.py
- Touch app/integrations/tinvest.py
- Touch app/services/plan_runner.py
- Touch app/services/plan_confirmation.py
- Touch app/services/trading_policy.py
- Touch app/services/mode.py
- Touch app/services/price_conditions.py
- Delete any file
- Enable ALLOW_AUTO_INVESTING=true
- Enable ENABLE_STRATEGY_SCHEDULER=true
- Enable ALLOW_PROD_TRADING=true
- Wire PlanRunner to an APScheduler job
- Add any code that places broker orders automatically without user confirmation
```

---

## Test command reference

```powershell
# Full test suite (use this)
.\venv312\Scripts\python.exe -m unittest discover -q

# Verbose (for debugging failures)
.\venv312\Scripts\python.exe -m unittest discover -v

# Single test file
.\venv312\Scripts\python.exe -m unittest tests.test_order_service -v
```
