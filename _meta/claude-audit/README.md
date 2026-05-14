# Claude Audit — File Index

Generated: 2026-05-14
Auditor: Claude Sonnet 4.6

This directory contains the results of a senior architect audit of the Tbot v1 / Investor v1 project,
plus a safe unattended workflow for qwen3-coder:30b running as a local coding agent.

---

## Audit reports (read-only, no code changes)

| File | Contents | Who reads it | Safe for qwen overnight? |
|------|----------|-------------|--------------------------|
| `01_project_audit.md` | Full architectural audit: strengths, weaknesses, tech debt, safety gaps, legacy status | Owner, developer | Yes — read-only |
| `02_idea_alignment.md` | Table: each project area vs v1 idea — aligned/partial/not | Owner | Yes — read-only |
| `03_add_remove_recommendations.md` | What to add, remove, isolate, defer, never do in v1 | Owner, developer | Yes — read-only |
| `04_questions_for_owner.md` | 27 open questions for the project owner before next development cycle | Owner | Owner review required |
| `05_roadmap.md` | Stabilization roadmap (Stages 0–5) — complements the feature ROADMAP.md | Owner, developer | Yes — read-only |

---

## Agent run order

| File | Contents | Who reads it | Safe for qwen overnight? |
|------|----------|-------------|--------------------------|
| `QWEN_AGENT_RUN_ORDER.md` | How to run qwen3-coder:30b, in what order, with what commands. **Start here.** | Owner | Yes — qwen reads it first |

---

## Qwen prompts — ready for Roo Code / Cline / Aider / OpenCode

Each prompt is self-contained: it has role, context, task, allowed/forbidden files,
workflow, stop conditions, and final report format.

| File | Task | Safe overnight? | Changes code? |
|------|------|-----------------|---------------|
| `qwen-prompts/000_overnight_coding_agent_supervisor.md` | Main overnight supervisor. Tells qwen to run only safe prompts in order. | YES — give this to qwen at start | No source changes |
| `qwen-prompts/001_report_only_project_safety_audit.md` | Audit safety gates (ModeService, OrderService, scheduler gating). Report only. | YES | NONE |
| `qwen-prompts/002_report_only_legacy_inventory.md` | Inventory of legacy signal/graphics/strategy modules. Report only. | YES | NONE |
| `qwen-prompts/003_docs_update_project_boundaries.md` | Add "What is NOT in v1" section to `V1_SCOPE.md`. Docs-only. | YES | V1_SCOPE.md (docs) |
| `qwen-prompts/004_tests_gap_report.md` | Analyze test coverage gaps. Report only. Run existing tests. | YES | NONE |
| `qwen-prompts/005_first_safe_test_task.md` | Create `tests/test_plan_confirmation_service.py`. Tests only. | **NO — owner review** | tests/ only |
| `qwen-prompts/006_first_safe_docs_task.md` | Create `docs/ARCHITECTURE.md`. New file, docs only. | YES | docs/ (new) |
| `qwen-prompts/007_first_safe_refactor_task.md` | Decouple legacy store import in `schedulers_config.py`. 1 file. | **NO — owner review** | 1 production file |
| `qwen-prompts/008_next_recommended_task.md` | Create `tests/test_watchlist_service.py`. Tests only. | **NO — owner review** | tests/ only |

---

## Qwen output files (created by qwen during the run)

These files do not exist yet — qwen will create them:

| File | Created by | Contents |
|------|-----------|----------|
| `qwen-run-log.md` | qwen during run | Running log of all tasks, commands, results |
| `qwen-final-report.md` | qwen at end of session | Final summary, risks, recommendations |
| `001_safety_audit_report.md` | qwen task 001 | Safety gate audit results |
| `002_legacy_inventory_report.md` | qwen task 002 | Legacy module inventory |
| `004_tests_gap_report.md` | qwen task 004 | Test coverage gap analysis |

---

## Critical findings (top 3)

1. **`PlanConfirmationService` deadlock risk**: `on_confirm` callback is called while
   holding `self._lock`, and `_execute` inside the callback makes broker network calls.
   This can freeze the confirmation service if the broker is slow. Must be fixed before P2-T1.

2. **`gpt_signal.py` and `lstm_signal.py` are importable**: directly contradicts the v1 promise
   of "no GPT/LSTM." They are not wired into runtime, but they exist as importable modules.
   Isolation to `_legacy/` is the immediate mitigation.

3. **`investor_reminders.py` bypasses multi-user architecture**: uses legacy `CHAT_ID` from
   `.env` instead of `UserContextResolver`. Reminders go to only one user regardless of
   how many users are configured in `users.json`.

---

## Safe overnight workflow summary

```
Give qwen:
  _meta/claude-audit/qwen-prompts/000_overnight_coding_agent_supervisor.md

qwen will run:
  001 → 002 → 003 → 004 → 006 (in order, with git status checks between each)

Morning check:
  git status --short
  git diff --stat
  .\venv312\Scripts\python.exe -m unittest discover -q
  cat _meta/claude-audit/qwen-final-report.md
```
