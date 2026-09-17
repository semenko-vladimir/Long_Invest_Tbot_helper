# Tbot v1

Tbot v1 is a Telegram-first local investment assistant for one long-term investor. It is sandbox-first, stores local state in SQLite, reads portfolio and market data through the T-Invest/MOEX integrations, and keeps broker operations manual.

The portfolio foundation supports any number of investment accounts under a broker connection. Telegram opens with an aggregate total and a separate broker-named summary for every enabled account, then allows drill-down into one account. Account identity always uses the broker's stable account ID; account list order and account names are never used as identity.

The active runtime includes Telegram views and workflows for portfolio, positions, watchlist, dividends, charts, settings, and manual buy/sell order preview and confirmation. Telegram charts are read-only; chart data and reminders never create orders.

The previous research/web-terminal direction has been archived locally in `../Tbot_terminal_archive/` and is not part of the active runtime. FastAPI, its web UI, research API, research snapshots, and terminal assets were removed because no active Telegram path requires them.

## Direction and safety

The intended future direction is automatic market and event monitoring with Telegram notifications. Monitoring, news/fundamental analysis, LLM analysis, ratings, and alert rules are not implemented by this cleanup.

No automatic trading is allowed. `APP_MODE`, `ALLOW_PROD_TRADING`, `ModeService`, `OrderService`, `TInvestBroker`, and manual preview/confirmation safeguards remain in force. Signals, reminders, analysis, and future monitoring events must never call broker order methods.

Production portfolio viewing is supported with `APP_MODE="prod"` and `ALLOW_PROD_TRADING="false"`. In that configuration the Telegram menu is read-only and does not show Buy/Sell actions; the service-level execution block remains authoritative.

## Account architecture

Persistent ownership follows `User -> BrokerConnection -> InvestmentAccount -> StrategyProfile`. Each account also owns its portfolio and position snapshots. The current per-user SQLite database supplies the `User` boundary; a secret-free broker connection can own N accounts and the account schema is provider-neutral so another broker adapter can be added later.

T-Invest tokens remain in `.env` or `users.json` and are never copied into SQLite. Broker connections store only provider/key/display metadata. A strategy profile can hold a different free-form thesis, settings payload, and future analysis-profile key for each account. Future notifications and local-LLM/research work must accept an explicit investment-account context; the same ticker may therefore be treated differently under different account strategies. Deterministic calculations remain Python service logic, not prompt-only logic. See [the multi-account foundation note](docs/multi_account_foundation.md).

## Local setup

Use Python 3.12 and install the base requirements:

```powershell
.\venv312\Scripts\python.exe -m pip install -r requirements-v1.txt
.\venv312\Scripts\python.exe -m unittest discover -q
```

Tbot uses the current `t-tech-investments==1.51.0` Python SDK from the official T-Bank package index declared in `requirements-base.txt`. Keep `SSL_TBANK_VERIFY="True"` in `.env`; Python SDK 1.49.2+ then uses its bundled T-Bank/Ministry certificate for TLS verification. SSL verification must never be disabled. The SDK client targets the official sandbox endpoint while `APP_MODE="sandbox"` is active and the official production endpoint only for explicit prod mode.

Copy `.env.example` to `.env`, copy `users.example.json` to `users.json`, and replace its placeholders. Configure `BOT_TOKEN` in `.env`; the copied `users.json` is the preferred source for the Telegram chat ID, sandbox token, optional production token, broker fee, database path, and default user. Keep `APP_MODE="sandbox"`, `ALLOW_PROD_TRADING="false"`, and automatic execution flags disabled. Never commit `.env`, `users.json`, tokens, or local databases. If `users.json` is absent and `USERS_CONFIG_PATH` is unset, the legacy `.env` values `SANDBOX_TOKEN`, `TOKEN`, `CHAT_ID`, and `BROKER_FEE` remain supported as a fallback.

Start the Telegram runtime with:

```powershell
.\venv312\Scripts\python.exe app\run.py
```

The archive is outside the Git repository and must not be staged or committed with Tbot.
