# Prompt 002 — Report-Only: Legacy Module Inventory

SAFE_FOR_UNATTENDED_RUN: YES
CHANGES_TO_CODE: NONE
OWNER_REVIEW_REQUIRED: NO

---

## Role

You are qwen3-coder:30b acting as a local coding agent in read-only audit mode.
You are NOT allowed to modify, move, or delete any source files.
Your only output is a report.

---

## Project context

Tbot v1 / Investor v1:
- Sandbox-first, manual-first investment assistant.
- v1 explicitly excludes: runtime signals (RSI/MACD/EMA/etc.), GPT, LSTM, strategy automation, chart generation from active runtime.
- Legacy modules may exist in the repository but must not be imported by active runtime code.

---

## Task

Build a complete inventory of legacy modules that are present in the repository
but should not be part of the active v1 runtime.
Make zero code changes.

For each legacy file or directory, document:
1. Full file path.
2. What the module does (one sentence from reading the file header or imports).
3. Is it currently imported by any active runtime file in `app/`? (grep to check)
4. Does it import external packages that are only in `requirements-optional.txt`?
5. Recommendation: keep / isolate to `_legacy/` / delete (with reason).

Focus areas:
- `app/client/signals/` (8 signal files)
- `app/client/graphics/` (6+ chart files)
- `app/client/strategy/`
- `app/client/store/store.py`
- `app/client/orders/` (if separate from `app/services/orders.py`)
- Any other directories/files that look like pre-v1 trading bot code.

---

## Allowed files (read only — do NOT modify)

- All files under `app/client/signals/`
- All files under `app/client/graphics/`
- All files under `app/client/strategy/` (if exists)
- `app/client/store/store.py` (if exists)
- `app/client/orders/` (if exists)
- `requirements-optional.txt`
- `requirements-base.txt`

## Read-only context

- `app/run.py` (check imports)
- `app/client/config/schedulers_config.py` (check imports)
- `app/backend/main_api.py` (check imports)

## Grep commands allowed

```bash
grep -r "from app.client.signals" app/ --include="*.py"
grep -r "from app.client.graphics" app/ --include="*.py"
grep -r "from app.client.strategy" app/ --include="*.py"
grep -r "from app.client.store" app/ --include="*.py"
grep -r "from app.client.orders" app/ --include="*.py"
```

## Forbidden — do NOT touch

- `.env`, `users.json`, `database.db*`
- `app/services/**` (read-only if needed for grep context)
- `app/integrations/**`
- `alembic/versions/**`
- Any file that is NOT in the "Allowed files" list above.

---

## Required workflow

```
1. git status --short
   → If working tree is not clean, STOP and write report.

2. List all files in app/client/signals/, app/client/graphics/, etc.

3. For each file: read the first 30 lines to identify its purpose.

4. Run grep commands to check if any active runtime file imports these modules.

5. Check requirements-optional.txt vs requirements-base.txt for each module's dependencies.

6. Write _meta/claude-audit/002_legacy_inventory_report.md.

7. Append summary to _meta/claude-audit/qwen-run-log.md.
```

---

## Stop conditions

Stop immediately if:
- git status shows uncommitted changes.
- You find yourself about to edit or move any file.
- Any file outside `_meta/claude-audit/` would be modified.

---

## Final report format

File: `_meta/claude-audit/002_legacy_inventory_report.md`

```markdown
# Legacy Module Inventory — 002

Date: [today]
Model: qwen3-coder:30b
Mode: report-only, no code changes

## Summary
[How many legacy files found, are any imported by active runtime?]

## Inventory

| File | Purpose | Imported by active runtime? | Optional deps? | Recommendation |
|------|---------|----------------------------|----------------|----------------|
| app/client/signals/gpt_signal.py | ... | yes/no (grep result) | yes/no | isolate/delete/keep |
...

## Active imports found (CRITICAL if any)
[List any case where active runtime imports a legacy module]

## Changed files
NONE

## Commands run
[List all commands]

## Checklist
- [ ] All signal files inventoried
- [ ] All graphics files inventoried
- [ ] strategy/ and store.py checked
- [ ] Active import check completed
- [ ] No files modified
- [ ] Log entry written
```
