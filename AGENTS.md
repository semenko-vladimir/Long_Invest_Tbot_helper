# AI Agent Instructions for Tbot

These instructions are for coding agents working in this repository, including
local VS Code agents backed by `qwen3-coder:30b`.

## Read First

Before changing code, read:

1. `PROJECT_INSTRUCTIONS.md`
2. `AGENT_BEHAVIOR.md`
3. The specific files touched by the requested task
4. Relevant tests under `tests/`

If these instructions conflict, follow the stricter safety rule.

## Product Boundary

Tbot v1 is a local, sandbox-first assistant for one private long-term investor.
It combines a Telegram bot, FastAPI web terminal, SQLite, and T-Invest API.

The project is not an auto-trading bot, signal bot, scalping bot, or investment
adviser. Do not turn analysis, reminders, plans, ratings, or LLM output into
broker order execution.

## Trading Safety Rules

- Keep sandbox mode as the default working assumption.
- Never weaken safeguards in `ModeService`, `OrderService`,
  `TradingPolicyService`, Telegram order handlers, or `TInvestBroker`.
- Broker orders must keep the flow `preview -> confirmation -> execute`.
- No-confirmation strategies must remain observation-only unless a future safety
  policy explicitly allows strategy auto-execution.
- Production trading must remain blocked unless `APP_MODE="prod"`, a production
  token, and `ALLOW_PROD_TRADING="true"` are explicitly configured.
- Do not add automatic broker orders except the explicitly gated `auto_execute`
  strategy path, which must stay disabled by default, sandbox-only by default,
  deduped, limited, and routed only through `OrderService`.
- Do not add runtime trading signals or personal investment recommendations.
- Keep web form POST routes protected with CSRF tokens.
- Never print or commit secrets from `.env`, `users.json`, tokens, cookies, or
  database files.

## Architecture Rules

- Preserve the startup path: `python app/run.py`.
- Keep FastAPI and server-rendered Jinja2 templates for the web terminal.
- Prefer small changes in the existing service layer over broad rewrites.
- Keep routers and Telegram handlers thin.
- Put shared business logic in `app/services/`.
- Keep broker/raw external API responses out of templates.
- Keep domain logic out of Jinja templates.
- Preserve the single-owner local configuration model based on `users.json`,
  `UserContext`, and `DEFAULT_WEB_USER_ID`.
- Avoid new heavy dependencies unless the task explicitly requires them.

## How to Work

- Explain existing code before editing when the user asks for explanation.
- For implementation tasks, make the smallest coherent change that solves the
  request.
- Do not make large architecture changes unless explicitly requested.
- Do not clean up unrelated files while working on a task.
- If the working tree already has changes, preserve them and avoid reverting
  user work.
- Update docs only when behavior, setup, safety policy, or runtime scope changes.
- Prefer clear names and typed Python where useful.
- Add or update focused tests when behavior changes.

## Verification

Use Python 3.12. Preferred local verification:

```powershell
.\venv312\Scripts\python.exe -m unittest discover -q
```

For focused work, run the nearest relevant tests first, then the full suite when
the change affects shared behavior.

## Good Task Style

Good requests for this project are small and explicit:

- "Explain how `OrderService` confirms an order. Do not edit files."
- "Add validation for X in `app/services/...`; keep the existing flow."
- "Fix this test failure without changing public behavior."
- "Refactor this handler into a service method, but do not change architecture."

Avoid broad requests such as "rewrite the bot", "make it smarter", or "add AI
trading" without a dedicated design and safety plan.
