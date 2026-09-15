# Tbot v1

Tbot v1 is a Telegram-first local investment assistant for one long-term investor. It is sandbox-first, stores local state in SQLite, reads portfolio and market data through the T-Invest/MOEX integrations, and keeps broker operations manual.

The active runtime includes Telegram views and workflows for portfolio, positions, watchlist, dividends, charts, settings, and manual buy/sell order preview and confirmation. Telegram charts are read-only; chart data and reminders never create orders.

The previous research/web-terminal direction has been archived locally in `../Tbot_terminal_archive/` and is not part of the active runtime. FastAPI, its web UI, research API, research snapshots, and terminal assets were removed because no active Telegram path requires them.

## Direction and safety

The intended future direction is automatic market and event monitoring with Telegram notifications. Monitoring, news/fundamental analysis, LLM analysis, ratings, and alert rules are not implemented by this cleanup.

No automatic trading is allowed. `APP_MODE`, `ALLOW_PROD_TRADING`, `ModeService`, `OrderService`, `TInvestBroker`, and manual preview/confirmation safeguards remain in force. Signals, reminders, analysis, and future monitoring events must never call broker order methods.

## Local setup

Use Python 3.12 and install the base requirements:

```powershell
.\venv312\Scripts\python.exe -m pip install -r requirements-v1.txt
.\venv312\Scripts\python.exe -m unittest discover -q
```

Copy `.env.example` to `.env` and configure `BOT_TOKEN`, `SANDBOX_TOKEN`, `CHAT_ID`, and `BROKER_FEE`. Keep `APP_MODE="sandbox"`, `ALLOW_PROD_TRADING="false"`, and automatic execution flags disabled. Never commit `.env`, `users.json`, tokens, or local databases.

Start the Telegram runtime with:

```powershell
.\venv312\Scripts\python.exe app\run.py
```

The archive is outside the Git repository and must not be staged or committed with Tbot.
