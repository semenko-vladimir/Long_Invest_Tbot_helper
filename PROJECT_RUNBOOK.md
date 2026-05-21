# Tbot Project Runbook

Этот документ - практический справочник по запуску проекта и пониманию его функций.
Основной путь запуска для этого репозитория: Windows + PowerShell + Python 3.12.

## 1. Что это за проект

Tbot v1 - локальный помощник долгосрочного инвестора для одного владельца.
Он объединяет:

- Telegram-бота для портфеля, watchlist, дивидендов, research и ручных заявок;
- локальный FastAPI backend;
- web-терминал на FastAPI/Jinja2;
- SQLite-базу для локальных данных;
- интеграцию с T-Invest API в sandbox/prod режимах.

Проект не является инвестиционным советником и не должен восприниматься как источник персональных рекомендаций. Runtime v1 не должен превращаться в signal bot или auto-trading bot.

Ключевое правило торговли: брокерская заявка проходит через `preview -> confirmation -> execute`. Production-торговля дополнительно заблокирована, пока явно не настроены `APP_MODE="prod"`, production token и `ALLOW_PROD_TRADING="true"`.

## 2. Основные возможности

Telegram:

- `/start` и меню инвестора;
- просмотр портфеля;
- ручные `buy` / `sell` по тикеру и количеству лотов;
- watchlist;
- дивиденды по инструментам из watchlist;
- локальная статистика ручных операций;
- read-only research по тикеру;
- Telegram-подтверждения для инвестиционных планов и anti-greedy политики.

Web:

- `Portfolio`;
- `Buy`;
- `Sell`;
- `Dividends`;
- `Watchlist`;
- `Research`;
- `Plans`;
- `Stats` / order history;
- `Settings`.

Automation scope:

- инвестиционные планы могут подготовить предложение покупки, но заявка отправляется только после Telegram-подтверждения;
- daily buy condition может подготовить покупку только если текущая цена не выше `вчерашняя дневная OHLC-средняя * 0.995` при пороге `0.5`;
- anti-greedy policy может предложить продажу позиции, если доходность выше порога, по умолчанию `20%`;
- перед подтвержденным исполнением планов и anti-greedy сделок условие и order preview проверяются заново.

## 3. Первичная установка

Из корня репозитория:

```powershell
cd C:\Users\vladimir\Desktop\Investment\Tbot
```

Создать окружение Python 3.12:

```powershell
py -3.12 -m venv venv
.\venv\Scripts\Activate.ps1
```

Если PowerShell блокирует activation script:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\venv\Scripts\Activate.ps1
```

Установить активные runtime-зависимости:

```powershell
python -m pip install --upgrade pip
python -m pip install -r requirements-base.txt
```

Альтернативно можно запустить bootstrap helper:

```powershell
.\scripts\bootstrap.ps1
```

Он создает `venv`, ставит `requirements-v1.txt` и копирует `.env.example` в `.env`, если `.env` еще нет.

## 4. Настройка `.env` и `users.json`

Создать локальные конфиги:

```powershell
Copy-Item .env.example .env
Copy-Item users.example.json users.json
```

Минимальные значения в `.env` для sandbox:

```env
BOT_TOKEN = "your_telegram_bot_token"
USERS_CONFIG_PATH = "users.json"
DEFAULT_WEB_USER_ID = "default"
APP_MODE = "sandbox"
INVEST_MODE = "sandbox"
ALLOW_PROD_TRADING = "false"
WEB_AUTH_ENABLED = "false"
WEB_AUTH_TOKEN = ""
ENABLE_BACKGROUND_SCHEDULERS = "false"
ENABLE_INVESTOR_REMINDERS = "false"
ENABLE_INVESTMENT_PLANS = "false"
ENABLE_ANTI_GREEDY_POLICY = "false"
API_BASE_URL = "http://localhost:8000"
API_HOST = "127.0.0.1"
API_PORT = "8000"
```

В `users.json` заполнить одного локального пользователя:

- `telegram_chat_id`;
- `sandbox_token`;
- `token` для production, можно оставить пустым в sandbox;
- `broker_fee`;
- `db_path`.

`users.json` и `.env` не должны попадать в git: там локальные секреты.

## 5. Web/API auth

Для чисто локального запуска на `API_HOST="127.0.0.1"` auth можно оставить выключенным:

```env
WEB_AUTH_ENABLED = "false"
WEB_AUTH_TOKEN = ""
```

Если `API_HOST="0.0.0.0"` или любой не-localhost host, startup должен падать без auth. Включить auth:

```powershell
.\venv\Scripts\python.exe -c "import secrets; print(secrets.token_urlsafe(32))"
```

Положить результат в `.env`:

```env
WEB_AUTH_ENABLED = "true"
WEB_AUTH_TOKEN = "generated_owner_token"
```

API-запрос с Bearer token:

```powershell
curl.exe -H "Authorization: Bearer generated_owner_token" http://localhost:8000/api/health
```

Для browser UI на этом шаге нет login form. Middleware принимает cookie `web_auth_token`; при включенном auth cookie можно поставить вручную в браузере для локального доступа:

```javascript
document.cookie = "web_auth_token=generated_owner_token; path=/; SameSite=Lax";
```

Значение токена не выводится в Settings, логах или ошибках.

## 6. Ежедневный запуск

Активировать окружение:

```powershell
cd C:\Users\vladimir\Desktop\Investment\Tbot
.\venv\Scripts\Activate.ps1
```

Запустить весь runtime: FastAPI, web terminal, schedulers и Telegram polling:

```powershell
python app/run.py
```

Если используется уже существующее окружение `venv312`:

```powershell
.\venv312\Scripts\python.exe app/run.py
```

Открыть web-терминал:

```text
http://localhost:8000/
```

Проверить API health:

```powershell
curl.exe http://localhost:8000/api/health
```

Проверить protected API при включенном auth:

```powershell
curl.exe -H "Authorization: Bearer generated_owner_token" http://localhost:8000/api/health
```

## 7. Web/API-only запуск для разработки

Если нужно поднять только FastAPI/web без Telegram polling и runtime schedulers:

```powershell
.\venv\Scripts\python.exe -m uvicorn app.backend.main_api:app --host 127.0.0.1 --port 8000 --reload
```

Или через `venv312`:

```powershell
.\venv312\Scripts\python.exe -m uvicorn app.backend.main_api:app --host 127.0.0.1 --port 8000 --reload
```

Этот режим удобен для web/API разработки, но он не заменяет полный startup path `python app/run.py` и должен использоваться только локально.

## 8. Telegram-команды

Старт:

```text
/start
/help
```

Ручная покупка:

```text
buy SBER 1
```

Ручная продажа:

```text
sell SBER 1
```

После `buy` или `sell` бот должен показать preview. Исполнение делается отдельной командой:

```text
confirm_order <preview_token>
```

В production при включенной торговле нужно дополнительно подтвердить тикер:

```text
confirm_order <preview_token> SBER
```

Отмена preview:

```text
cancel_order <preview_token>
```

Research:

```text
/research SBER
research SBER
```

Research является read-only: он не создает заявки, не дает торговые сигналы и не запускает стратегию.

## 9. Инвестиционные планы

Включить планировщики и plans:

```env
ENABLE_BACKGROUND_SCHEDULERS = "true"
ENABLE_INVESTMENT_PLANS = "true"
```

План создается через web page `Plans`. Для ежедневной покупки ниже вчерашней средней:

- `Schedule`: `Daily`;
- `Operation`: `Buy`;
- `Price rule`: `Yesterday average minus percent`;
- `Percent threshold`: `0.5`.

Логика условия:

```text
current_buy_price <= previous_daily_ohlc_average * 0.995
```

Scheduler отправляет Telegram-подтверждение. Брокерская заявка отправляется только после нажатия подтверждения, и перед этим цена/условие проверяются повторно.

## 10. Anti-greedy policy

Включить:

```env
ENABLE_BACKGROUND_SCHEDULERS = "true"
ENABLE_ANTI_GREEDY_POLICY = "true"
ANTI_GREEDY_PROFIT_PCT = "20"
ANTI_GREEDY_CHECK_TIME = "18:30"
```

Что делает policy:

- ежедневно проверяет портфель;
- находит позиции, где `return_percent > ANTI_GREEDY_PROFIT_PCT`;
- считает количество целых лотов для продажи;
- создает sell preview через `OrderService`;
- отправляет Telegram-подтверждение;
- после подтверждения заново проверяет позицию и делает fresh preview;
- только затем вызывает `OrderService.execute`.

Важно: это не скрытая автопродажа. Без Telegram-подтверждения broker order не отправляется.

## 11. Production-режим

Sandbox - режим по умолчанию:

```env
APP_MODE = "sandbox"
ALLOW_PROD_TRADING = "false"
```

Production-торговля требует всех условий:

```env
APP_MODE = "prod"
ALLOW_PROD_TRADING = "true"
```

Также в `users.json` должен быть production `token` активного пользователя.

Даже в production `OrderService` требует preview token, а подтверждение real order требует точный ticker.

## 12. Проверки и тесты

Запустить все тесты:

```powershell
.\venv312\Scripts\python.exe -m pytest -q
```

Если используется обычный `venv`:

```powershell
.\venv\Scripts\python.exe -m pytest -q
```

Проверить зависимости на известные уязвимости:

```powershell
.\venv312\Scripts\python.exe -m pip_audit -r requirements-base.txt -r requirements-dev.txt
.\venv312\Scripts\python.exe -m pip_audit -r requirements-optional.txt
```

Проверить health endpoint:

```powershell
curl.exe http://localhost:8000/api/health
```

## 13. Полезные файлы

- `app/run.py` - основной startup path.
- `app/backend/main_api.py` - FastAPI app, web router, `/api`.
- `app/backend/web/routes.py` - server-rendered web pages.
- `app/backend/auth.py` - owner-token auth middleware.
- `app/backend/web/csrf.py` - CSRF защита web forms.
- `app/client/config/__init__.py` - config helpers и startup validation.
- `app/client/config/schedulers_config.py` - investment plans и anti-greedy schedulers.
- `app/services/orders.py` - единый безопасный order flow.
- `app/services/investment_plans.py` - CRUD и preview логика планов.
- `app/services/plan_runner.py` - запуск планов с подтверждением.
- `app/services/anti_greedy.py` - anti-greedy sell proposal policy.
- `app/services/portfolio.py` - portfolio view и расчет `return_percent`.
- `README_LOCAL_SETUP.md` - короткая настройка Windows laptop.
- `PROJECT_INSTRUCTIONS.md` - durable safety rules для будущих изменений.

## 14. Частые проблемы

`BOT_TOKEN` missing:

Проверь `.env`, значение не должно быть placeholder.

Telegram chat is not authorized:

Проверь `telegram_chat_id` в `users.json`. Он должен совпадать с реальным chat id.

Нет sandbox token:

Заполни `sandbox_token` в `users.json` или legacy `SANDBOX_TOKEN` в `.env`.

Web/API не открывается:

Проверь, что запущен `python app/run.py`, порт `8000` свободен, а `API_HOST` равен `127.0.0.1`.

Startup падает при `API_HOST="0.0.0.0"`:

Включи `WEB_AUTH_ENABLED="true"` и задай `WEB_AUTH_TOKEN`.

План или anti-greedy ничего не отправляет:

Проверь:

- `ENABLE_BACKGROUND_SCHEDULERS="true"`;
- нужный feature flag включен;
- приложение перезапущено после изменения `.env`;
- сегодня торговый день;
- есть доступный Telegram chat;
- есть broker token;
- для anti-greedy позиция действительно выше порога и доступна минимум на один лот.

## 15. Короткая шпаргалка

```powershell
cd C:\Users\vladimir\Desktop\Investment\Tbot
.\venv\Scripts\Activate.ps1
python app/run.py
```

```powershell
curl.exe http://localhost:8000/api/health
```

```powershell
.\venv312\Scripts\python.exe -m pytest -q
```

```text
/start
buy SBER 1
sell SBER 1
research SBER
```
