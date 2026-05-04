# Tbot v1 - Local Long-Term Investor Assistant

Tbot v1 is a local, sandbox-first assistant for a private long-term investor. It uses Telegram as the primary UI, FastAPI as a local backend and web terminal, SQLite for local storage, and the T-Invest API for portfolio, instrument, dividend, and manual order operations.

This project is not an investment adviser and does not make financial recommendations. Production trading is treated as dangerous and remains blocked unless `APP_MODE="prod"`, a production `TOKEN`, and `ALLOW_PROD_TRADING="true"` are explicitly configured.

## What It Does

- Shows portfolio and current positions.
- Supports manual buy and sell by ticker and lot count.
- Tracks a watchlist of tickers.
- Shows dividend-related information for watchlist instruments.
- Shows basic text statistics for stored manual trading records.
- Can prepare investment plan proposals and optional daily investor reminders without signals or trade advice.
- Provides a local FastAPI/web terminal for portfolio, watchlist, dividends, manual orders, plans, and settings.
- Runs in sandbox mode by default.

Investor v1 intentionally does not include runtime RSI/MACD/EMA/SMA signals, GPT/LSTM analysis, scalping flows, BUY/HOLD/SELL/WATCH/AVOID recommendations, or automatic broker order execution. Manual orders are the only active order path.

## Install

Use Python 3.12 if available.

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements-base.txt
```

Compatibility aliases:

```powershell
python -m pip install -r requirements-v1.txt
```

Optional legacy analytics, charting, signal, and ML dependencies are separated:

```powershell
python -m pip install -r requirements-optional.txt
```

Development tooling:

```powershell
python -m pip install -r requirements-dev.txt
```

The legacy T-Invest SDK packages used here are quarantined on PyPI, so `requirements-base.txt` pins them through direct PyPI wheel URLs. Revisit those pins before production use.

## Configure `.env`

Copy the example and fill only local secrets in `.env`:

```powershell
Copy-Item .env.example .env
```

Required for sandbox v1:

```env
BOT_TOKEN = "your_telegram_bot_token"
SANDBOX_TOKEN = "your_sandbox_token"
CHAT_ID = "your_telegram_chat_id"
BROKER_FEE = 0.3
APP_MODE = "sandbox"
ALLOW_PROD_TRADING = "false"
ENABLE_BACKGROUND_SCHEDULERS = "false"
ENABLE_INVESTOR_REMINDERS = "false"
INVESTOR_REMINDER_TIME = "09:00"
API_BASE_URL = "http://localhost:8000"
```

`INVEST_MODE="sandbox"` may remain as a legacy alias, but `APP_MODE` is the primary mode variable. `TOKEN` is only required for production mode.

Production trading requires all of these values:

```env
APP_MODE = "prod"
TOKEN = "your_prod_token"
ALLOW_PROD_TRADING = "true"
```

## Launch In Sandbox

```powershell
python app/run.py
```

Startup path:

1. Validate required environment variables.
2. Initialize SQLite in the repo root.
3. Start FastAPI at `http://localhost:8000`.
4. Configure disabled-by-default schedulers/reminders.
5. Start Telegram polling.

Smoke checks after startup:

```powershell
curl http://localhost:8000/
curl http://localhost:8000/api/instruments/
```

## Use Buy/Sell By Ticker

In Telegram:

```text
/start
/help
```

Menu:

- `Portfolio`
- `Buy`
- `Sell`
- `Dividends`
- `Watchlist`
- `Stats`
- `Reports`
- `Help`

Manual trading:

```text
buy SBER 1
sell SBER 1
```

You can also tap `Buy` or `Sell` and then enter:

```text
SBER 1
```

The bot resolves the ticker, blocks ambiguous/not-found tickers, checks sandbox account availability, checks cash before buy, checks available position quantity before sell, and logs every manual trade attempt without logging secrets.

Read-only ticker research:

```text
/research SBER
research SBER
```

The Telegram research command returns a compact educational summary with source names, instrument identity when available, market snapshot when available, data gaps, errors, and a non-advice disclaimer. It does not show runtime ratings or trading signals and does not create or prepare broker orders.

## Local Web Terminal

FastAPI also serves a local investor terminal at `http://localhost:8000/`. The web UI is intended for calm portfolio review and manual workflows:

- `Portfolio`
- `Buy`
- `Sell`
- `Dividends`
- `Watchlist`
- `Research`
- `Plans`
- `Settings`

Plan screens create recurring investment plan definitions and manual proposals. They do not create broker orders from analysis or trading signals.

Read-only ticker research is available at `http://localhost:8000/api/research`. Enter a ticker to call `GET /api/research/{ticker}` and display the partial research report JSON. The report includes sources, freshness metadata, `data_gaps`, `errors`, the educational disclaimer, and an empty or null `educational_rating`. This research entry does not create broker orders, does not provide trading signals, and does not recommend trades. Telegram also exposes the same read-only research flow through `/research SBER` or `research SBER`.

## Legacy Code Status

Older signal, strategy, ML, GPT/LSTM, chart, and market-notification modules remain in the repository as legacy code for migration safety and reversibility. They are not part of the active investor v1 menu or active API router, and this v1 runtime must not be treated as an auto-trading or signal bot.

## Known Limitations

- Full runtime validation requires real Telegram and T-Invest sandbox credentials.
- Manual order prices use the current order book and may fail when the book is empty or the market is unavailable.
- Manual order history stores limited metadata; some statistics are all-time rather than interval-filtered.
- Optional investor reminders require `APScheduler` from `requirements-base.txt` and are off by default.
- Legacy signal, strategy, ML, GPT/LSTM, chart, and market-notification modules remain in the repository for reversibility but are not part of the active investor v1 runtime.
- Pydantic v2 emits a warning for old `orm_mode` schema config; this is non-blocking.

## More Docs

- `README_LOCAL_SETUP.md` - Windows-first laptop setup.
- `INVESTOR_MODE.md` - investor-mode workflow.
- `V1_SCOPE.md` - v1 feature scope.
- `MIGRATION_AUDIT.md` - migration audit notes.
