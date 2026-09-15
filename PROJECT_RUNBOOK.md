# Tbot v1 runbook

Tbot v1 is a local Telegram-first investor assistant. Start it from the repository root with:

```powershell
.\venv312\Scripts\python.exe app\run.py
```

Configure `.env` from `.env.example` and copy `users.example.json` to ignored `users.json`. Put the Telegram chat ID, sandbox token, optional production token, broker fee, database path, and default user in `users.json`; keep `APP_MODE="sandbox"`, `ALLOW_PROD_TRADING="false"`, and automatic execution flags disabled. If `users.json` is absent and `USERS_CONFIG_PATH` is unset, the legacy `.env` user fields remain supported as a fallback.

Telegram provides portfolio, positions, watchlist, dividends, charts, settings, and manual order preview/confirmation. The old FastAPI/web terminal and research commands were archived and are not active.

Run tests with:

```powershell
.\venv312\Scripts\python.exe -m unittest discover -q
```

The future monitoring direction is market/event observation with Telegram notifications. It is not implemented yet. No signal, reminder, analysis, or monitoring event may create a broker order.
