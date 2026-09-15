# Local Telegram setup

Tbot v1 runs as a local Telegram polling process. The former FastAPI/web-terminal process is no longer part of the runtime.

1. Create or activate a Python 3.12 virtual environment.
2. Install dependencies:

   ```powershell
   .\venv312\Scripts\python.exe -m pip install -r requirements-v1.txt
   ```

3. Copy `.env.example` to `.env` and set `BOT_TOKEN`, `SANDBOX_TOKEN`, `CHAT_ID`, and `BROKER_FEE`.
4. Keep `APP_MODE="sandbox"` and `ALLOW_PROD_TRADING="false"` for local development.
5. Start the bot:

   ```powershell
   .\venv312\Scripts\python.exe app\run.py
   ```

The bot supports Telegram portfolio, positions, watchlist, dividends, charts, settings, and manual order preview/confirmation. No automatic market monitoring or auto-trading is implemented.

Run tests with:

```powershell
.\venv312\Scripts\python.exe -m unittest discover -q
```

Do not commit `.env`, `users.json`, tokens, local databases, caches, virtual environments, or `../Tbot_terminal_archive/`.
