# Tbot v1 project instructions

Tbot v1 is a Telegram-first local investment assistant for one private long-term investor. The runtime is sandbox-first, uses SQLite and T-Invest/MOEX integrations, and keeps broker operations manual.

The active interface is Telegram. Keep portfolio, positions, watchlist, dividends, read-only charts, settings, and manual buy/sell preview-confirmation workflows working. Do not reintroduce the archived web terminal or research HTTP surface without an explicit product decision.

The former research/web-terminal implementation is preserved outside the repository at `../Tbot_terminal_archive/`. It is not active runtime code. Future research and monitoring should be redesigned around Telegram notifications and should not restore the archived design unchanged.

Automatic market/event monitoring, news ingestion, LLM analysis, ratings, and alert rules are future work and are not implemented here.

## Multi-account boundary

- Portfolio ownership is `User -> BrokerConnection -> InvestmentAccount`.
- Broker credentials stay in `.env`/`users.json`; database broker rows are secret-free metadata only.
- Every account-specific portfolio read, snapshot, strategy, future notification, and future LLM/research request must carry an explicit investment-account context.
- Every production order execution must carry an explicit broker account ID; never select an order target from account list order.
- Never infer account identity from API list order or account display name.
- Aggregate portfolio views may sum account totals, but canonical positions and snapshots remain attributed to their source account.
- Strategy profiles are account-scoped and free-form. Do not introduce a global strategy or global LLM analysis profile.

## Safety invariants

- Keep `APP_MODE` sandbox-first and preserve production token handling.
- Use the current `t-tech-investments` Python SDK from the official T-Bank package index; keep `SSL_TBANK_VERIFY="True"` so TLS verification uses the SDK-bundled certificate.
- Use only the SDK's official `sandbox-invest-public-api.tbank.ru:443` and `invest-public-api.tbank.ru:443` endpoints; never disable SSL verification.
- Keep `ALLOW_PROD_TRADING` and all `ModeService`/`OrderService`/`TInvestBroker` guards intact.
- Broker orders require the existing explicit manual preview and confirmation flow.
- Never create an order from a chart, signal, reminder, analysis, research result, monitoring event, or LLM output.
- Do not add auto-trading or weaken production safety checks.
- Do not commit `.env`, `users.json`, tokens, databases, caches, virtual environments, or the external archive.

## Change boundaries

Prefer small changes that preserve Telegram/core behavior. Keep generic broker, database, portfolio, watchlist, dividend, order, and chart services when Telegram uses them. Remove terminal-only code rather than deleting shared services. Do not perform unrelated dependency upgrades or stack modernization.

Run the full suite from `Tbot` after runtime changes:

```powershell
.\venv312\Scripts\python.exe -m unittest discover -q
```
