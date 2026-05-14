# Repository Cleanup Audit

Date: 2026-05-14

## Scope and Method

This audit covered tracked project files plus visible local artifacts. Cleanup scope was limited to git-tracked repository files so rollback remains reversible with `git restore`.

Commands/methods used:

- `git status --short` before changes: only untracked `.runtime/`.
- `git ls-files` and `rg --files -uuu -g '!.git' -g '!venv*'` for file inventory.
- AST import inspection over all tracked Python files to build internal import edges and runtime/test reachability.
- `rg` reference searches for `_meta`, Qwen/Aider audit artifacts, legacy signal/strategy/ML/GPT/LSTM/chart paths, app startup, FastAPI, Telegram handlers, SQLite models, T-Invest, order safety, and research services.
- Baseline tests before deletion: `.\venv312\Scripts\python.exe -m unittest discover -q`.

Baseline result:

- PASS, 205 tests.
- Existing warnings only: Pydantic v2 config warning plus dependency/deprecation warnings from the current stack.

Post-cleanup result:

- PASS, 205 tests with `.\venv312\Scripts\python.exe -m unittest discover -q`.
- Existing warnings only: Pydantic v2 config warning plus dependency/deprecation warnings from the current stack.

## Active Runtime Entrypoints

| Entrypoint | Role | Keep reason |
| --- | --- | --- |
| `app/run.py` | Main local startup: validates config/tokens, configures SQLite, starts FastAPI thread, configures schedulers/reminders, starts Telegram polling. | KEEP_RUNTIME |
| `app/backend/main_api.py` | FastAPI app factory/module: lifespan creates DB tables, mounts `/api`, web routes, and static assets. | KEEP_RUNTIME |
| `app/client/bot/bot.py` | Telegram bot instance. | KEEP_RUNTIME |
| `app/backend/api/__init__.py` | Mounted API router for trading DB CRUD, instruments, and research. | KEEP_RUNTIME |
| `app/backend/web/routes.py` | Web terminal routes for portfolio, buy/sell preview/confirm, dividends, watchlist, plans, stats, orders, settings. | KEEP_RUNTIME |
| `alembic/env.py` and `alembic/versions/*` | SQLite schema/migration path. | KEEP_CONFIG_OR_SCHEMA |

## Runtime Dependency Map

AST reachability from `app.run` and `app.backend.main_api` found 60 runtime Python modules. The active runtime graph is:

- Startup/config: `app/run.py`, `app/client/config/*`, `app/services/user_context.py`, `app/services/user_database.py`.
- Telegram UI: `app/client/bot/bot.py`, `app/client/handlers/bot/*`, `dividends/*`, `help/*`, `instruments/*`, `menu/*`, `orders/manual_order_handler.py`, `portfolio/*`, `research/*`, `statistics/*`, `utils/message_utils.py`.
- FastAPI/web: `app/backend/main_api.py`, `app/backend/api/*`, `app/backend/web/context.py`, `app/backend/web/routes.py`, templates under `app/backend/web/templates/`, static CSS/JS under `app/backend/web/static/`.
- Services: `dividends.py`, `investment_plans.py`, `mode.py`, `order_history.py`, `orders.py`, `portfolio.py`, `settings_view.py`, `statistics.py`, `trading_policy.py`, `watchlist.py`.
- Broker/read-only integration: `app/integrations/tinvest.py`, `app/client/utils/helpers.py`, `app/client/utils/methods.py`.
- Research terminal foundation: `app/research/adapters.py`, `local_fundamentals_adapter.py`, `schemas.py`, `services.py`, `snapshots.py`, `tinvest_adapter.py`, `app/research/data/local_fundamentals.json`.
- Persistence: `app/backend/models/database.py`, `research.py`, `trading.py`, Alembic migration files.

Runtime-adjacent modules not reached from app startup but intentionally kept:

- `app/services/auto_scheduler.py`, `plan_confirmation.py`, `plan_runner.py`, `price_conditions.py`.
- `app/client/handlers/plans/auto_confirm_handler.py`.

These are not mounted in the active default scheduler path, but they are tested and touch investment plans/order safety, so they are KEEP_TEST or REVIEW_UNCERTAIN_DO_NOT_DELETE.

## Test Dependency Map

| Test area | App dependencies |
| --- | --- |
| `test_web_routes.py`, `test_order_history.py` | FastAPI app, web routes, portfolio/settings/statistics/watchlist services, order history. |
| `test_telegram_manual_order_handler.py` | Telegram manual order handler, `OrderService`, `ModeService`, preview/confirm safety. |
| `test_order_service.py`, `test_mode_service.py` | Order preview/execute safety, production guard behavior, mode config. |
| `test_trading_policy.py`, `test_investment_plans.py`, `test_plan_runner.py`, `test_price_conditions.py` | Investment plan policy, runner, price conditions, order execution guard boundaries. |
| `test_research_*`, `test_local_fundamentals_adapter.py`, `test_tinvest_research_adapter.py`, `test_telegram_research_handler.py` | Research schemas, read-only adapters, snapshots, API, Telegram research formatting, no legacy signal/LLM imports. |
| `test_user_database.py`, `test_users_config.py`, `test_p1_user_context_wiring.py` | Per-user config, SQLite routing, migration helpers, context boundaries. |
| `test_dependency_files.py`, `test_schedulers_config.py`, `test_investor_reminders.py` | Dependency isolation, scheduler no-op safety, reminders without signals/trade advice. |

No tests depend on `_meta/` or `scripts/run_qwen_prompts_aider.ps1`.

## File Classification

| Path or group | Classification | Evidence |
| --- | --- | --- |
| `app/run.py` | KEEP_RUNTIME | Main startup entrypoint. |
| `app/backend/main_api.py`, `app/backend/api/**`, `app/backend/web/**` | KEEP_RUNTIME | Mounted FastAPI API/web routes and assets. |
| `app/client/bot/**`, `app/client/handlers/**`, `app/client/utils/**`, `app/client/log/logger.py` | KEEP_RUNTIME | Telegram runtime and shared helper path. |
| `app/client/config/**` | KEEP_RUNTIME | Startup, mode, user, scheduler, reminder config. |
| `app/services/mode.py`, `orders.py`, `trading_policy.py` | KEEP_RUNTIME | Safety-critical mode/order/policy guards. |
| `app/services/portfolio.py`, `watchlist.py`, `dividends.py`, `statistics.py`, `order_history.py`, `settings_view.py`, `investment_plans.py`, `user_context.py`, `user_database.py` | KEEP_RUNTIME | Active Telegram/web/API service layer. |
| `app/integrations/tinvest.py` | KEEP_RUNTIME | T-Invest broker adapter, manual-order placement boundary. |
| `app/research/**` | KEEP_FUTURE_RESEARCH_FOUNDATION | Active read-only research terminal foundation and tests. |
| `app/backend/models/**`, `alembic.ini`, `alembic/**` | KEEP_CONFIG_OR_SCHEMA | SQLite models and migrations; required by runtime/tests. |
| `tests/**` | KEEP_TEST | Full unittest suite and safety regression coverage. |
| `requirements*.txt`, `.env.example`, `users.example.json`, `Dockerfile`, `docker-compose.yml`, `scripts/bootstrap.ps1` | KEEP_CONFIG_OR_SCHEMA | Install, runtime config examples, Docker/bootstrap paths; dependency tests cover these files. |
| `README.md`, `PROJECT_INSTRUCTIONS.md`, `RESEARCH_TERMINAL_FOUNDATION.md`, `V1_SCOPE.md`, `INVESTOR_MODE.md`, `README_LOCAL_SETUP.md`, `AGENT_BEHAVIOR.md`, `AUTO_SCHEDULE_TASKS.md`, `ROADMAP.md` | KEEP_DOCS_OR_PROJECT_RULES | Product scope, safety rules, setup, roadmap, and owner-facing planning docs. |
| `docs/token-optimization-architecture.md` | REVIEW_UNCERTAIN_DO_NOT_DELETE | Contains stale legacy references, but may be useful future LLM/context-budget architecture. Kept because future LLM/adapters are explicitly in scope only behind safe boundaries. |
| `requirements-optional.txt` | REVIEW_UNCERTAIN_DO_NOT_DELETE | Legacy optional dependency list, but tests assert it stays isolated from default installs. |
| `_meta/claude-audit/**` | DELETE_SAFE_UNUSED | Tracked agent audit/Qwen prompt artifacts only; no runtime/test imports; stale findings contradict current repo state; not required by startup, tests, safety, config, packaging, or research foundation. |
| `_meta/claude-work/**` | DELETE_SAFE_UNUSED | Tracked Claude work logs/plans only; no runtime/test imports; own plan marked new `_meta` files as deleteable with no impact. |
| `scripts/run_qwen_prompts_aider.ps1` | DELETE_SAFE_UNUSED | Dedicated runner for deleted `_meta/claude-audit/qwen-prompts`; not used by runtime, tests, bootstrap, Docker, packaging, or research terminal. |
| `.runtime/` | Local artifact, not committed | Runtime log directory observed as untracked. Added to `.gitignore`; not deleted because it is outside tracked cleanup scope. |

## Deleted Files

Evidence for every deleted file:

- No Python imports because files are Markdown or a standalone PowerShell runner.
- No test dependencies found.
- Not part of `app/run.py`, FastAPI startup, Telegram handler imports, SQLite migrations/models, T-Invest adapter, `ModeService`, `OrderService`, manual order handlers, or broker helpers.
- Not part of `RESEARCH_TERMINAL_FOUNDATION.md` or active `app/research/**`.
- Exact reference search outside the deleted area found only stale README/ROADMAP mentions, which were removed.
- The PowerShell runner only served the deleted `_meta/claude-audit/qwen-prompts` workflow.

Deleted:

- `_meta/claude-audit/01_project_audit.md`
- `_meta/claude-audit/02_idea_alignment.md`
- `_meta/claude-audit/03_add_remove_recommendations.md`
- `_meta/claude-audit/04_questions_for_owner.md`
- `_meta/claude-audit/05_roadmap.md`
- `_meta/claude-audit/AIDER_AUTO_RUN.md`
- `_meta/claude-audit/MIGRATION_AUDIT.md`
- `_meta/claude-audit/P1_CLOSURE_AUDIT.md`
- `_meta/claude-audit/QWEN_AGENT_RUN_ORDER.md`
- `_meta/claude-audit/README.md`
- `_meta/claude-audit/qwen-prompts/000_overnight_coding_agent_supervisor.md`
- `_meta/claude-audit/qwen-prompts/001_report_only_project_safety_audit.md`
- `_meta/claude-audit/qwen-prompts/002_report_only_legacy_inventory.md`
- `_meta/claude-audit/qwen-prompts/003_docs_update_project_boundaries.md`
- `_meta/claude-audit/qwen-prompts/004_tests_gap_report.md`
- `_meta/claude-audit/qwen-prompts/005_first_safe_test_task.md`
- `_meta/claude-audit/qwen-prompts/006_first_safe_docs_task.md`
- `_meta/claude-audit/qwen-prompts/007_first_safe_refactor_task.md`
- `_meta/claude-audit/qwen-prompts/008_next_recommended_task.md`
- `_meta/claude-audit/qwen-prompts/009_wire_check_report.md`
- `_meta/claude-work/final_report.md`
- `_meta/claude-work/implementation_plan.md`
- `_meta/claude-work/legacy_inventory.md`
- `_meta/claude-work/questions_for_owner.md`
- `_meta/claude-work/work_log.md`
- `scripts/run_qwen_prompts_aider.ps1`

## Kept As Uncertain Or Safety-Critical

- `app/services/auto_scheduler.py`, `plan_confirmation.py`, `plan_runner.py`, `price_conditions.py`, and `app/client/handlers/plans/auto_confirm_handler.py`: not startup-reachable in default v1, but tested and related to plan/order safety, so not deleted.
- `app/backend/api/endpoints/trading.py`, `app/backend/schemas/trading.py`, and legacy DB tables (`Margin`, `Buy`, `Order`): mounted or used by statistics/order history/API tests.
- All tests, migrations, schemas, config examples, and dependency files.
- `docs/token-optimization-architecture.md`: stale references found, but kept as uncertain future LLM architecture material rather than deleting a possible planning artifact.
- `AUTO_SCHEDULE_TASKS.md` and `ROADMAP.md`: planning docs for future work; not runtime, but project direction.

## Documentation Changes

- `README.md`: removed stale migration-audit reference, clarified legacy optional dependency status, added this cleanup report.
- `ROADMAP.md`: removed stale `P1_CLOSURE_AUDIT.md` artifact pointer while preserving the P1 closure result.
- `.gitignore`: added `.runtime/` so local runtime logs do not stay as untracked commit candidates.

## Rollback Plan

Review cleanup diff:

```powershell
git diff --name-status
```

Restore a specific deleted file:

```powershell
git restore -- _meta/claude-audit/README.md
git restore -- scripts/run_qwen_prompts_aider.ps1
```

Restore all cleanup changes:

```powershell
git restore .
git restore --staged .
```

If tests or startup checks fail, restore only the relevant deleted path first; otherwise restore the whole cleanup diff.
