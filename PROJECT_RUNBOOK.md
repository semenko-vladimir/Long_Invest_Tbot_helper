# Tbot v1 runbook

Tbot v1 is a local Telegram-first investor assistant. Start it from the repository root with:

```powershell
.\venv312\Scripts\python.exe app\run.py
```

Configure `.env` from `.env.example`. For safe local development use `APP_MODE="sandbox"`, a sandbox token, `ALLOW_PROD_TRADING="false"`, and disabled automatic execution flags.

Telegram provides portfolio, positions, watchlist, dividends, charts, settings, and manual order preview/confirmation. The old FastAPI/web terminal and research commands were archived and are not active.

Run tests with:

```powershell
.\venv312\Scripts\python.exe -m unittest discover -q
```

The future monitoring direction is market/event observation with Telegram notifications. It is not implemented yet. No signal, reminder, analysis, or monitoring event may create a broker order.
