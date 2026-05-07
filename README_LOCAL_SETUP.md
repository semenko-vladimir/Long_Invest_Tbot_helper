# Local Setup For Investor V1

This is the minimal laptop startup path for the sandbox-first investor assistant. It avoids the optional ML, signal, chart, and analytics dependencies from `requirements-optional.txt`.

Use Python 3.12 for the cleanest local path. Python 3.14 is not recommended for this repo right now because binary packages used by pandas/NumPy/grpc may not match the interpreter yet. The current T-Invest SDK packages used by this repo are quarantined on PyPI, so `requirements-base.txt` pins the same SDK versions through direct PyPI file URLs and should be revisited before production use.

## 1. Create a virtual environment

```powershell
py -V:Astral/CPython3.12.13 -m venv venv
.\venv\Scripts\Activate.ps1
```

If that launcher name is not available, use another local Python 3.12 executable instead of the first command above.

If PowerShell blocks activation, run:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\venv\Scripts\Activate.ps1
```

## 2. Install minimal dependencies

```powershell
python -m pip install --upgrade pip
python -m pip install -r requirements-base.txt
```

`requirements.txt` and `requirements-v1.txt` are compatibility aliases for the
same active investor v1 dependency set. They do not install optional legacy
packages.

Use the optional dependency set only if you explicitly need old signals, ML,
GPT, charts, or analytics. These packages are not part of the active investor
v1 runtime:

```powershell
python -m pip install -r requirements-optional.txt
```

## 3. Create `.env`

```powershell
Copy-Item .env.example .env
```

Fill these required values in `.env`:

```env
BOT_TOKEN = "your_telegram_bot_token"
SANDBOX_TOKEN = "your_sandbox_token"
CHAT_ID = "your_telegram_chat_id"
BROKER_FEE = 0.3
APP_MODE = "sandbox"
INVEST_MODE = "sandbox"
ALLOW_PROD_TRADING = "false"
ENABLE_BACKGROUND_SCHEDULERS = "false"
ENABLE_INVESTOR_REMINDERS = "false"
INVESTOR_REMINDER_TIME = "09:00"
API_BASE_URL = "http://localhost:8000"
```

`APP_MODE` is the canonical mode variable. `INVEST_MODE` is kept as a legacy alias for older local configs. `TOKEN` is only required when `APP_MODE="prod"`. Production trading is blocked unless `ALLOW_PROD_TRADING="true"` is set explicitly.

## 4. Launch locally

```powershell
python app/run.py
```

Expected startup path:

- SQLite creates `database.db` in the repo root.
- FastAPI starts on `http://localhost:8000`.
- Telegram polling starts.
- Background schedulers remain disabled unless explicitly enabled.

## 5. Verify

In another terminal:

```powershell
curl http://localhost:8000/
curl http://localhost:8000/api/instruments/
```

In Telegram:

```text
/start
buy SBER 1
Portfolio
sell SBER 1
```

Expected v1 menu:

- `Portfolio`
- `Buy`
- `Sell`
- `Dividends`
- `Watchlist`
- `Stats`
- `Reports`
- `Help`

Sandbox smoke-test scenario:

1. Fill `BOT_TOKEN`, `SANDBOX_TOKEN`, and `CHAT_ID`.
2. Keep `APP_MODE="sandbox"` and `ALLOW_PROD_TRADING="false"`.
3. Start the app with `python app/run.py`.
4. In Telegram, send `/start`.
5. Optionally top up sandbox balance through `Help` -> `Sandbox info`.
6. Send `buy SBER 1`, then verify the position with `Portfolio`.
7. Send `sell SBER 1` only after the sandbox position exists.

Use `/help` or `Help` in Telegram for the complete investor-mode command list. Optional daily check-in reminders are off by default; enable them with `ENABLE_INVESTOR_REMINDERS=true` and `INVESTOR_REMINDER_TIME=09:00`.

## Bootstrap Helper

You can run the local helper instead of the manual setup steps:

```powershell
.\scripts\bootstrap.ps1
```

The script creates `venv`, installs `requirements-v1.txt` (a compatibility alias for `requirements-base.txt`), and copies `.env.example` to `.env` only when `.env` does not already exist. It never installs optional legacy dependencies or overwrites local secrets.

## Common Blockers

- `BOT_TOKEN`, `SANDBOX_TOKEN`, and `CHAT_ID` must be real values, not placeholders.
- `TOKEN` can stay empty for sandbox mode.
- If `fastapi`, `telebot`, `tinkoff`, or `sqlalchemy` imports fail, install `requirements-base.txt` inside the active `venv`.
- If pip cannot resolve `tinkoff` or `tinkoff-investments`, check the quarantine note in `requirements-base.txt`; normal package-name installs are currently blocked by PyPI quarantine.
- If Telegram handlers cannot reach the API, check `API_BASE_URL` and confirm `http://localhost:8000/` responds.
