# Minimal Long-Term-Investor Migration Audit

## Critical path to run locally

- Primary local entrypoint: `python app/run.py`.
- `app/run.py` loads `.env`, verifies `BOT_TOKEN`, `CHAT_ID`, `SANDBOX_TOKEN`, `BROKER_FEE`, and only requires `TOKEN` when `INVEST_MODE` resolves to production.
- Telegram bot instance is created in `app/client/bot/bot.py` via `telebot.TeleBot(BOT_TOKEN)`.
- Database initialization runs twice in the normal path:
  - `app/client/config/db_config.py` calls `Base.metadata.create_all(bind=engine)`.
  - `app/backend/main_api.py` also calls `create_all_tables()` on FastAPI startup.
- SQLite storage is configured in `app/backend/models/database.py` as `sqlite:///./database.db`.
- FastAPI app used by local startup is `app/backend/main_api.py`; `app/run.py` imports it as `fastapi_app` and starts it in a daemon thread on `0.0.0.0:8000`.
- API router currently mounted by `app/backend/api/__init__.py`: `config`, `trading`, `instruments`.
- Telegram polling starts last via `bot.polling()`.
- Docker entrypoint is `python /app/run.py` from `Dockerfile`; `docker-compose.yml` supplies `.env` and mounts `./app:/app`.
- Secondary FastAPI app exists in `app/backend/api/main.py`, but it is not used by `app/run.py`.

## Must keep for investor v1

- Sandbox-first configuration in `app/client/config/__init__.py`: `INVEST_MODE`, `ALLOW_PROD_TRADING`, `ENABLE_BACKGROUND_SCHEDULERS`, active token selection.
- Main startup in `app/run.py`: token verification, DB init, FastAPI thread startup, Telegram polling, reduced v1 menu.
- Telegram v1 flows:
  - `app/client/handlers/portfolio/portfolio_handler.py` for portfolio display.
  - `app/client/handlers/orders/manual_order_handler.py` for manual buy/sell by ticker and lot count.
  - `app/client/handlers/instruments/` for local watched instruments.
  - `app/client/handlers/dividends/dividends_handler.py` for dividend lookup.
  - `app/client/handlers/bot/sandbox_info.py` for sandbox portfolio and sandbox balance top-up.
- T-Invest helper layer in `app/client/utils/methods.py` and money/date helpers in `app/client/utils/helpers.py`.
- Local API clients needed by Telegram handlers: `app/client/api/base_client.py`, `app/client/api/instruments_client.py`, `app/client/api/trading_client.py`.
- Backend v1 API:
  - `app/backend/api/endpoints/instruments.py`.
  - `app/backend/api/endpoints/trading.py`.
  - `app/backend/api/endpoints/config.py`, while sandbox-trigger strategy coupling remains unresolved.
- Persistence for v1:
  - `Instrument` and `Order` in `app/backend/models/trading.py`.
  - `Base`, `engine`, `SessionLocal`, `get_db` in `app/backend/models/database.py`.

## Can disable in v1

- Signals:
  - `app/client/signals/`.
  - `app/client/handlers/signals/`.
  - `app/client/api/signals_client.py`.
  - `app/backend/api/endpoints/signals.py`.
  - `app/backend/models/signals.py`.
  - `app/backend/schemas/signals.py`.
- Strategies and auto-trading:
  - `app/client/strategy/strategy_run.py`.
  - `app/client/handlers/bot/strategy_set.py`.
  - `app/client/handlers/bot/strategy_remove.py`.
  - `app/client/api/strategy_client.py`.
  - `app/backend/api/endpoints/strategy.py`.
  - `app/backend/models/strategy.py`.
  - `app/backend/schemas/strategy.py`.
- ML/AI:
  - `app/client/signals/lstm_signal.py`.
  - `app/client/signals/gpt_signal.py`.
  - GPT/LSTM branches inside `app/client/strategy/strategy_run.py`.
- Charts and analytics:
  - `app/client/graphics/`.
  - `app/client/handlers/mls/`.
  - `app/client/handlers/statistics/`.
  - `app/client/handlers/market/`.
  - `app/client/handlers/notifications/`.
- Old knowledge-base topics about signals, ML, market notifications, and trading robot strategy setup.
- Heavy optional dependencies not needed for v1:
  - `tensorflow`, `tensorflow-intel`, `tensorboard*`, `keras`.
  - `scikit-learn`, `scipy`.
  - `g4f`.
  - `matplotlib`, `seaborn`, `mplfinance`.
  - `ta`, `pandas-datareader`.
- Keep for now until utility functions are simplified:
  - `pandas`, because `app/client/utils/methods.py` and `app/client/utils/helpers.py` still use `DataFrame`.
  - `APScheduler`, unless scheduler code is fully removed instead of feature-gated.

## Risky places

- `app/client/handlers/dividends/dividends_handler.py` still reads `TOKEN` directly and ignores sandbox-first active token selection.
- `app/backend/models/__init__.py` still imports and registers signal and strategy tables even though active API routers no longer expose them.
- `app/client/handlers/knowledge_base/knowledge_base_handler.py` still links to disabled topics: notifications, market state, trading robot, Middle/Long signals, signal settings.
- `app/client/orders/orders.py` still contains signal/auto-trading-oriented behavior and messages. It can place real orders when called with `sandbox_method=False`.
- `app/client/handlers/orders/manual_order_handler.py` posts orders and then records them through `TradingApiClient`, so manual order success depends on the localhost FastAPI thread being reachable.
- `app/client/api/base_client.py` hardcodes `http://localhost:8000`; Docker or non-default ports will break Telegram handlers unless the base URL becomes configurable.
- `app/backend/api/endpoints/config.py` exposes `sandbox-trigger` through `StrategySettings`, keeping config coupled to disabled strategy storage.
- `app/client/utils/methods.py` mixes v1 portfolio/order helpers with historical candle, market-change, and analytics helpers, so importing one module can keep optional dependencies such as `pandas` in the v1 runtime.
- `Dockerfile` still installs a dependency set derived from the full `requirements.txt`, so v1 Docker builds remain heavier than needed.

## Suggested first wave of edits

- Keep the current sandbox-first app menu in `app/run.py`.
- Switch `dividends_handler` to `get_active_invest_token()` so dividend lookup follows `INVEST_MODE`.
- Prune `knowledge_base_handler` to investor-v1 topics only: portfolio, instruments, dividends, sandbox/manual orders.
- Keep signal and strategy routers out of the active API router; leave the files in place for reversible migration.
- Decide whether `app/backend/models/__init__.py` should stop importing signal/strategy models now or keep them documented as dormant tables for backward compatibility.
- Isolate old `app/client/orders/orders.py` from v1 manual trading, or rename/document it as legacy strategy-order flow to avoid accidental reuse.
- Make `BaseApiClient` base URL configurable via env, with `http://localhost:8000` as default.
- Split dependencies into a minimal v1 runtime set and optional analytics/ML extras, without deleting the full dependency list until the v1 runtime is validated.
- Keep `.env.example` placeholder-only and sandbox-first.

## Smoke-test commands

```powershell
python -m compileall app
```

```powershell
python -c "from app.client.config import get_invest_mode; print(get_invest_mode())"
```

```powershell
python -m pip show fastapi pyTelegramBotAPI tinkoff-investments SQLAlchemy python-dotenv requests uvicorn
```

```powershell
python app/run.py
```

```powershell
curl http://localhost:8000/
```

```powershell
curl http://localhost:8000/api/instruments/
```

