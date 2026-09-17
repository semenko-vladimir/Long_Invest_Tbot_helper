# Local Telegram setup

Tbot v1 runs as a local Telegram polling process. The former FastAPI/web-terminal process is no longer part of the runtime.

1. Create or activate a Python 3.12 virtual environment.
2. Install dependencies:

   ```powershell
   .\venv312\Scripts\python.exe -m pip install -r requirements-v1.txt
   ```

3. Copy `.env.example` to `.env` and set `BOT_TOKEN`.
4. Copy `users.example.json` to `users.json` and replace the Telegram chat ID and sandbox token placeholders. Keep the default user enabled and adjust `broker_fee` only if needed.
5. Keep `APP_MODE="sandbox"` and `ALLOW_PROD_TRADING="false"` for local development.
6. Keep `SSL_TBANK_VERIFY="True"` in `.env`. With Python SDK 1.49.2+, this selects the SDK-bundled T-Bank/Ministry certificate for TLS verification. Never set it to disable verification, and do not use `verify=False`.
7. Start the bot:

   ```powershell
   .\venv312\Scripts\python.exe app\run.py
   ```

The bot supports Telegram portfolio, positions, watchlist, dividends, charts, settings, and manual order preview/confirmation. No automatic market monitoring or auto-trading is implemented.

The active broker dependency is `t-tech-investments` from the official T-Bank Python package index declared in `requirements-base.txt`. Sandbox remains the default and uses `sandbox-invest-public-api.tbank.ru:443`; production requires the existing explicit mode and safety configuration.

Run tests with:

```powershell
.\venv312\Scripts\python.exe -m unittest discover -q
```

Do not commit `.env`, `users.json`, tokens, local databases, caches, virtual environments, or `../Tbot_terminal_archive/`.

Legacy fallback: if `users.json` is absent and `USERS_CONFIG_PATH` is unset, the bot can use `SANDBOX_TOKEN`, `TOKEN`, `CHAT_ID`, and `BROKER_FEE` from `.env`.
