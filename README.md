# Tbot v1 - Local Long-Term Investor Assistant

Tbot v1 is a local, sandbox-first assistant for a private long-term investor. It uses Telegram as the primary UI, FastAPI as a local backend and web terminal, SQLite for local storage, and the T-Invest API for portfolio, instrument, dividend, and manual order operations.

This project is not an investment adviser and does not make financial recommendations. Production trading is treated as dangerous and remains blocked unless `APP_MODE="prod"`, a production token for the active user, and `ALLOW_PROD_TRADING="true"` are explicitly configured.

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

## Architecture

```mermaid
graph TD
    TG[Telegram Bot<br/>pyTelegramBotAPI] --> H[Handlers<br/>app/client/handlers/]
    WEB[Web Terminal<br/>FastAPI + Jinja2] --> R[Web Routes<br/>app/backend/web/routes.py]
    H --> S[Service Layer<br/>app/services/]
    R --> S
    S --> B[Broker Integration<br/>app/integrations/tinvest.py]
    S --> DB[(SQLite per-user<br/>data/users/)]
    S --> RS[Research Adapters<br/>app/research/]
    B --> API[T-Invest API<br/>sandbox / prod]

    subgraph Safety
        MODE[ModeService<br/>sandbox / prod]
        ORDER[OrderService<br/>preview → confirm → execute]
        POLICY[TradingPolicyService<br/>limits + flags]
    end

    S --> MODE
    S --> ORDER
    S --> POLICY
```

Key runtime flows:

- Trading: Telegram -> Handler -> OrderService -> preview → confirm → TInvestBroker.
- Web: Browser -> FastAPI Route -> WebRequestServices -> Service -> DB/Broker.
- Multi-user: chat_id -> UserContextResolver -> UserContext -> per-user SessionFactory.

## Install

Use Python 3.12 if available. The recommended investor v1 install uses only
the active runtime dependency set:

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements-base.txt
```

Default compatibility aliases also install only the active v1 runtime
dependencies and do not include optional legacy packages:

```powershell
python -m pip install -r requirements.txt
python -m pip install -r requirements-v1.txt
```

Optional legacy analytics, charting, signal, ML, and GPT dependencies are not
part of the active investor v1 runtime. Install them only when explicitly
working with quarantined legacy modules:

```powershell
python -m pip install -r requirements-optional.txt
```

Development tooling:

```powershell
python -m pip install -r requirements-dev.txt
```

The legacy T-Invest SDK packages used here are quarantined on PyPI, so `requirements-base.txt` pins them through direct PyPI wheel URLs. Revisit those pins before production use.

## Configure `.env` And Users

Copy the example and fill only local secrets in `.env`:

```powershell
Copy-Item .env.example .env
```

Copy the user config example and fill per-user local secrets in `users.json`:

```powershell
Copy-Item users.example.json users.json
```

Required app-level values for sandbox v1:

```env
BOT_TOKEN = "your_telegram_bot_token"
USERS_CONFIG_PATH = "users.json"
DEFAULT_WEB_USER_ID = "default"
APP_MODE = "sandbox"
ALLOW_PROD_TRADING = "false"
ENABLE_BACKGROUND_SCHEDULERS = "false"
ENABLE_INVESTOR_REMINDERS = "false"
INVESTOR_REMINDER_TIME = "09:00"
API_BASE_URL = "http://localhost:8000"
```

Each `users.json` user has its own `telegram_chat_id`, `sandbox_token`,
production `token`, `broker_fee`, and per-user SQLite `db_path`.
`users.json` is ignored by git and must not contain shareable secrets.

`CHAT_ID`, `SANDBOX_TOKEN`, `TOKEN`, and `BROKER_FEE` in `.env` remain a
temporary legacy fallback when `users.json` is not configured. New multi-user
setup should use `users.json`.

`INVEST_MODE="sandbox"` may remain as a legacy alias, but `APP_MODE` is the primary mode variable. A production token is only required for production mode.

Production trading requires all of these values:

```env
APP_MODE = "prod"
ALLOW_PROD_TRADING = "true"
```

The active user in `users.json` must also have a production `token` value.

## Launch In Sandbox

```powershell
python app/run.py
```

Startup path:

1. Validate required environment variables and configured users.
2. Initialize SQLite. With `users.json`, each enabled user gets their own configured DB file.
3. Start FastAPI at `http://localhost:8000`.
4. Configure disabled-by-default schedulers/reminders.
5. Start Telegram polling.

`ENABLE_STRATEGY_SCHEDULER` is intentionally ignored in investor v1; legacy strategy automation cannot be reactivated from `.env`.

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

These commands create an order preview only. To submit the order after reviewing the preview, send:

```text
confirm_order <preview_token>
```

In production mode, the confirmation command must also include the ticker shown in the preview:

```text
confirm_order <preview_token> SBER
```

To discard a preview, send `cancel_order <preview_token>`.

You can also tap `Buy` or `Sell` and then enter:

```text
SBER 1
```

The bot resolves the ticker, blocks ambiguous/not-found tickers, checks sandbox account availability, checks cash before buy, checks available position quantity before sell, and logs every manual trade attempt without logging secrets. No Telegram buy/sell command submits a broker order until the separate confirmation command is sent.

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
- `Order history` from the Stats page
- `Settings`

Plan screens create recurring investment plan definitions and manual proposals. They do not create broker orders from analysis or trading signals.

The `Settings` page is read-only. It shows the active mode, token configured
status without secret values, feature flags, API base URL, reminder time, and
investment-plan safety status. To change these values, edit `.env` and restart
the app.

Phase 1 uses no web authentication. The active local web user is selected by
`DEFAULT_WEB_USER_ID`; if it is unset, the first enabled user in `users.json`
is used. Web terminal routes and mounted user-data API endpoints build services
for that user and read/write the user's configured SQLite DB file.

Read-only ticker research is available at `http://localhost:8000/api/research`. Enter a ticker to call `GET /api/research/{ticker}` and display the partial research report JSON. The report includes sources, freshness metadata, local company profile fields when configured, `data_gaps`, `errors`, the educational disclaimer, and an empty or null `educational_rating`. This research entry does not create broker orders, does not provide trading signals, and does not recommend trades. Telegram also exposes the same read-only research flow through `/research SBER` or `research SBER`.

In sandbox mode, read-only T-Invest research selects `SANDBOX_TOKEN`; missing or invalid selected tokens are reported in `errors` without printing token values.

Local company/fundamental profile data is loaded from `app/research/data/local_fundamentals.json` through a read-only `LocalFundamentalsAdapter`. The file is optional and intentionally incomplete: missing tickers or fields are reported as `data_gaps`, not guessed. Do not store tokens, API keys, or other secrets in local research data.

Generated API reports are saved as local read-only snapshots when SQLite is available. Use `GET /api/research/snapshots` or `GET /api/research/snapshots?ticker=SBER` to review recent snapshots, and `GET /api/research/snapshots/{id}` to load one stored report.

## Legacy Code Status

Older signal, strategy, ML, GPT/LSTM, chart, and market-notification modules remain in the repository as legacy code for migration safety and reversibility. They are not part of the active investor v1 menu or active API router, and this v1 runtime must not be treated as an auto-trading or signal bot.

## Known Limitations

- Full runtime validation requires real Telegram and T-Invest sandbox credentials.
- Manual order prices use the current order book and may fail when the book is empty or the market is unavailable.
- Manual order history stores limited metadata; some statistics are all-time rather than interval-filtered.
- Phase 1 multi-user support is being introduced incrementally: `users.json`,
  user resolution, per-user service DB routing, and active Telegram/web/API
  request routing are in place. Quarantined legacy handlers still use their old
  storage paths until they are migrated or retired.
- Optional investor reminders require `APScheduler` from `requirements-base.txt` and are off by default.
- Legacy signal, strategy, ML, GPT/LSTM, chart, and market-notification modules remain in the repository for reversibility but are not part of the active investor v1 runtime.
- Pydantic v2 emits a warning for old `orm_mode` schema config; this is non-blocking.

## More Docs

- `README_LOCAL_SETUP.md` - Windows-first laptop setup.
- `INVESTOR_MODE.md` - investor-mode workflow.
- `V1_SCOPE.md` - v1 feature scope.
- `MIGRATION_AUDIT.md` - migration audit notes.
