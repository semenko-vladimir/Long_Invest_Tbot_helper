# AGENT TASKS — Tbot Architectural Fixes

Этот файл содержит пронумерованные задачи для AI-агента.
Каждая задача самодостаточна: содержит контекст, файлы, что менять, и критерии проверки.

Формат вызова агента:
> В файле `AGENT_TASKS.md` прочитай задачу `БЛОК-1-ЧАСТЬ-1` и выполни её полностью.

---

## БЛОК-1-ЧАСТЬ-1 — Привязать FastAPI к 127.0.0.1

### Контекст
Приложение — локальный инвестиционный ассистент (Tbot).
FastAPI сервер сейчас привязан к `host="0.0.0.0"`, что открывает все API-эндпоинты
(включая историю ордеров и торговые операции) для всех устройств в локальной сети.
Веб-интерфейс не имеет аутентификации, поэтому это — уязвимость безопасности.

### Задача
Изменить привязку FastAPI сервера с `0.0.0.0` на конфигурируемый хост,
безопасный по умолчанию (`127.0.0.1`).

### Файлы для изменения

**1. `app/run.py` строка 90:**
```python
# БЫЛО:
uvicorn.run(fastapi_app, host="0.0.0.0", port=8000)

# СТАЛО:
api_host = os.getenv("API_HOST", "127.0.0.1")
api_port = int(os.getenv("API_PORT", "8000"))
uvicorn.run(fastapi_app, host=api_host, port=api_port)
```

**2. `app/backend/main_api.py` строка 54 (блок `if __name__ == "__main__"`):**
```python
# БЫЛО:
uvicorn.run(app, host="0.0.0.0", port=8000)

# СТАЛО:
api_host = os.getenv("API_HOST", "127.0.0.1")
api_port = int(os.getenv("API_PORT", "8000"))
uvicorn.run(app, host=api_host, port=api_port)
```

**3. `.env.example` — добавить новые переменные после строки `API_BASE_URL`:**
```
# Хост FastAPI сервера. По умолчанию 127.0.0.1 (только локальный доступ).
# Измените на 0.0.0.0 только если нужен доступ из локальной сети И вы понимаете риски.
API_HOST = "127.0.0.1"
# Порт FastAPI сервера.
API_PORT = "8000"
```

**4. `app/client/config/__init__.py` — добавить `API_HOST` и `API_PORT` в `validate_startup_config()`
если там есть список разрешённых переменных.**
Если функции `validate_startup_config()` нет — пропустить этот шаг.

### Что НЕ менять
- Не трогать `API_BASE_URL` — он используется клиентом для исходящих запросов, не для привязки сервера
- Не менять логи — строка `logger.info("API сервер запущен на http://localhost:8000")` может остаться как есть

### Проверка выполнения
- [ ] В `app/run.py` нет строки `host="0.0.0.0"` — вместо неё `host=api_host`
- [ ] В `app/backend/main_api.py` нет строки `host="0.0.0.0"`
- [ ] В `.env.example` добавлены `API_HOST` и `API_PORT` с комментариями
- [ ] `os` уже импортирован в `app/run.py` (строка 2) — дополнительный импорт не нужен

---

## БЛОК-1-ЧАСТЬ-2 — Исправить CORS-конфигурацию

### Контекст
В `app/backend/main_api.py` CORS настроен с `allow_origins=["*"]` и `allow_credentials=True` одновременно.
По спецификации Fetch API (и RFC 7235) это сочетание некорректно: браузеры блокируют такие ответы.
Комбинация даёт ложное ощущение настроенной безопасности.
Для локального сервера достаточно явного списка разрешённых origins.

### Файл для изменения

**`app/backend/main_api.py` строки 25-31:**
```python
# БЫЛО:
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# СТАЛО:
_allowed_origins = [
    "http://127.0.0.1:8000",
    "http://localhost:8000",
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["Content-Type", "Authorization"],
)
```

### Проверка выполнения
- [ ] Нет `allow_origins=["*"]` в `main_api.py`
- [ ] Нет `allow_credentials=True` в `main_api.py`
- [ ] Список origins содержит явные localhost-адреса
- [ ] Методы и заголовки явно перечислены (не `["*"]`)

---

## БЛОК-1-ЧАСТЬ-3 — Удалить дублирующийся файл `app/backend/api/main.py`

### Контекст
В проекте существуют два файла, оба создающие экземпляр `app = FastAPI(...)`:
- `app/backend/main_api.py` — **реальный** entry point, используется в `app/run.py`
- `app/backend/api/main.py` — **дублирующий**, нигде не подключён, создаёт "голый" FastAPI без middleware

Дублирующий файл опасен: тест или скрипт, импортирующий его случайно, получит FastAPI
без CORS, без аутентификации, без web-роутеров — невидимый второй сервер.

### Шаги выполнения

**1. Убедиться что `app/backend/api/main.py` нигде не импортируется:**
Выполнить поиск по всему проекту: `from app.backend.api.main import` и `import app.backend.api.main`.
Если импорты найдены — перенаправить их на `app/backend/main_api.py`.

**2. Проверить `app/backend/api/__init__.py`:**
Убедиться что он импортирует роутеры из `endpoints/`, а не из `main.py`.

**3. Удалить файл `app/backend/api/main.py`.**

### Проверка выполнения
- [ ] Файл `app/backend/api/main.py` удалён
- [ ] Поиск по проекту на `from app.backend.api.main` возвращает 0 результатов
- [ ] `app/run.py` по-прежнему импортирует из `app.backend.main_api` (не из api.main)
- [ ] Проект запускается без ошибок импорта

---

## БЛОК-1-ЧАСТЬ-4 — Нормализовать зависимости tinkoff SDK

### Контекст
В `requirements-base.txt` строки 16-17 содержат пины через прямые PyPI-URL:
```
tinkoff @ https://files.pythonhosted.org/packages/...
tinkoff-investments @ https://files.pythonhosted.org/packages/...
```
Проблемы:
1. `pip-audit` и `safety` не видят эти пакеты — CVE-сканирование слепо к ним
2. Если PyPI удалит/переместит файл — сборка падает без предупреждения
3. Хэши прописаны в URL, но не в `--hash=sha256:` формате pip

### Шаги выполнения

**1. Прочитать текущие URL в `requirements-base.txt`:**
Зафиксировать точные версии: `tinkoff==0.1.1` и `tinkoff-investments==0.2.0b105`.

**2. Проверить доступность через обычный pip:**
Запустить: `pip index versions tinkoff` и `pip index versions tinkoff-investments`.
Если версии недоступны через PyPI index — оставить URL-пины, но добавить `--hash` для integrity check.

**3. Если версии доступны нормально — заменить URL-пины на обычные:**
```
# БЫЛО:
tinkoff @ https://files.pythonhosted.org/...
tinkoff-investments @ https://files.pythonhosted.org/...

# СТАЛО:
tinkoff==0.1.1
tinkoff-investments==0.2.0b105
```

**4. Если версии НЕ доступны через нормальный pip index — добавить комментарий и hash:**
```
# Quarantined on PyPI: install via URL below. Verify hash before production use.
tinkoff @ https://files.pythonhosted.org/...  # sha256: 971ec61e...
tinkoff-investments @ https://files.pythonhosted.org/...  # sha256: 5ddbd0e0...
```

**5. Добавить в `requirements-dev.txt` (если его нет — создать):**
```
pip-audit>=2.7.0
```

### Проверка выполнения
- [ ] `requirements-base.txt` содержит версии tinkoff либо в нормальном формате, либо с явными hash-комментариями
- [ ] Добавлен комментарий что пакеты квалифицированы и требуют ревью перед production
- [ ] `pip-audit` добавлен в dev-зависимости

---

## БЛОК-2-ЧАСТЬ-1 — Добавить Alembic для миграций БД

### Контекст
Приложение использует `SQLAlchemy create_all()` при старте (`app/backend/main_api.py`).
Это означает: у существующих пользователей новые поля/таблицы не создаются — только у новых.
При обновлении приложения данные молча расходятся со схемой.
Приложение поддерживает per-user базы данных (каждый пользователь имеет свой `db_path`).

### Шаги выполнения

**1. Установить Alembic:**
Добавить `alembic>=1.13.0` в `requirements-base.txt`.

**2. Инициализировать Alembic в корне проекта:**
```
alembic init alembic
```

**3. Настроить `alembic/env.py`:**
- Импортировать все модели из `app/backend/models/`
- Установить `target_metadata = Base.metadata`
- Настроить `get_url()` читающий из env-переменной или аргумента командной строки

**4. Создать начальную миграцию (текущая схема как baseline):**
```
alembic revision --autogenerate -m "initial_schema"
```

**5. Добавить хелпер `app/services/user_database.py` — функцию `run_migrations_for_user(user)`:**
```python
def run_migrations_for_user(db_path: str) -> None:
    """Запустить alembic upgrade head для конкретной пользовательской БД."""
    from alembic.config import Config
    from alembic import command
    alembic_cfg = Config("alembic.ini")
    alembic_cfg.set_main_option("sqlalchemy.url", f"sqlite:///{db_path}")
    command.upgrade(alembic_cfg, "head")
```

**6. Вызвать `run_migrations_for_user()` в `configure_runtime_databases()` вместо `create_all_tables()`
или дополнительно к нему (для безопасности оставить `create_all` как fallback на первый запуск).**

### Проверка выполнения
- [ ] `alembic/` директория создана с `env.py`, `versions/`
- [ ] Начальная миграция существует в `alembic/versions/`
- [ ] `run_migrations_for_user()` добавлена в `app/services/user_database.py`
- [ ] `alembic upgrade head` выполняется без ошибок на тестовой БД

---

## БЛОК-2-ЧАСТЬ-2 — Мигрировать на FastAPI lifespan

### Контекст
`@app.on_event("startup")` в `app/backend/main_api.py` — deprecated начиная с FastAPI 0.93.
В следующем major-релизе будет удалён. Нужно мигрировать на `lifespan` context manager.

### Файл для изменения

**`app/backend/main_api.py`:**

```python
# ДОБАВИТЬ импорт:
from contextlib import asynccontextmanager

# ЗАМЕНИТЬ:
# @app.on_event("startup")
# def startup_event():
#     create_all_tables()

# НА:
@asynccontextmanager
async def lifespan(app: FastAPI):
    create_all_tables()
    yield

# И изменить создание app:
# БЫЛО:
# app = FastAPI(title="...", ...)

# СТАЛО:
app = FastAPI(
    title="Long-Term Investor Assistant API",
    description="Sandbox-first API for portfolio, instruments, and manual orders",
    version="1.0.0",
    lifespan=lifespan,
)
```

### Проверка выполнения
- [ ] Нет `@app.on_event` в `main_api.py`
- [ ] `lifespan` функция определена с `@asynccontextmanager`
- [ ] `app = FastAPI(lifespan=lifespan, ...)` — lifespan передан в конструктор
- [ ] `from contextlib import asynccontextmanager` добавлен в импорты

---

## БЛОК-2-ЧАСТЬ-3 — Удалить мёртвый код

### Контекст
В проекте существуют модули, которые **не подключены** к runtime:
- Не импортируются в `app/run.py`
- Не регистрированы в API-роутерах
- Не используются ни одним активным handler'ом

Мёртвый код вводит в заблуждение при навигации и поддержке.

### Шаги выполнения

**1. Подтвердить что следующие handler-папки нигде не импортируются в активном коде:**
- `app/client/handlers/signals/`
- `app/client/handlers/mls/`
- `app/client/handlers/notifications/`
- `app/client/handlers/knowledge_base/`
- `app/client/handlers/market/`

Выполнить поиск: `from app.client.handlers.signals`, `from app.client.handlers.mls` и т.д.
Если импорты найдены в активных файлах (не в самих удаляемых папках) — НЕ удалять, зафиксировать находку.

**2. Подтвердить что следующие backend-модели не используются активными сервисами:**
- `app/backend/models/signals.py`
- `app/backend/models/strategy.py`
- `app/backend/models/research.py` (если отличается от `app/research/`)
- `app/backend/schemas/signals.py`
- `app/backend/schemas/strategy.py`
- `app/backend/api/endpoints/signals.py` (если существует)
- `app/backend/api/endpoints/strategy.py` (если существует)

**3. Удалить все подтверждённые мёртвые модули.**

**4. Убедиться что `app/backend/models/__init__.py` не импортирует удалённые модели.**

**5. Если удалённые модели создавали таблицы в БД — добавить Alembic-миграцию
`drop_legacy_tables` которая удаляет их (только если БЛОК-2-ЧАСТЬ-1 уже выполнен).**

### Проверка выполнения
- [ ] Удалённые папки/файлы отсутствуют в файловой системе
- [ ] `app/backend/models/__init__.py` не ссылается на удалённые модели
- [ ] `python -m py_compile app/run.py` выполняется без ошибок
- [ ] `python -m unittest discover -q` проходит без ошибок

---

## БЛОК-3-ЧАСТЬ-1 — Веб-портал: страница инвестиционных планов

### Контекст
Сервис `InvestmentPlanService` в `app/services/investment_plans.py` полностью реализован:
- `list_plans()` — список планов
- `create_plan()` — создание
- `delete_plan()` — удаление
- `generate_order_proposal()` — предложение ордера

Но web-интерфейса для него нет: нет маршрута в `app/backend/web/routes.py`,
нет Jinja2-шаблона. Функция написана, но недоступна через UI.

### Шаги выполнения

**1. Прочитать `app/backend/web/routes.py` и `app/backend/web/context.py`
для понимания паттерна существующих маршрутов.**

**2. Прочитать существующий шаблон (например `app/backend/web/templates/portfolio.html`)
для понимания стиля и структуры.**

**3. Добавить маршруты в `app/backend/web/routes.py`:**
- `GET /plans` — список планов
- `POST /plans/create` — форма создания плана
- `POST /plans/{plan_id}/delete` — удаление плана
- `GET /plans/{plan_id}/proposal` — просмотр предложения ордера

**4. Создать шаблон `app/backend/web/templates/plans.html`:**
- Список существующих планов (ticker, schedule, lots, next_run_display)
- Форма создания: ticker, lots, schedule (daily/weekly/monthly), time (HH:MM)
- Кнопка "Удалить" для каждого плана
- Кнопка "Просмотр предложения" — открывает страницу proposal

**5. Создать шаблон `app/backend/web/templates/plan_proposal.html`:**
- Детали плана
- Предложенная цена и количество
- Кнопка "Перейти к подтверждению" (ссылка на `/buy` с pre-filled параметрами)
- Нота: "This proposal is not an order."

**6. Убедиться что `WebRequestServices` (в `app/backend/web/context.py`)
содержит `investment_plan_service`. Если нет — добавить.**

### Проверка выполнения
- [ ] `GET /plans` возвращает HTML без ошибок (пустой список — нормально)
- [ ] Форма создания плана отправляет POST и создаёт запись в БД
- [ ] Удаление плана работает
- [ ] Страница proposal показывает предложение без авто-исполнения
- [ ] В шаблоне явно написано что это proposal, не ордер

---

## БЛОК-4-ЧАСТЬ-1 — SQLite WAL mode и connection timeout

### Контекст
Приложение использует SQLite с тремя одновременными источниками записи:
Telegram bot (main thread), FastAPI (daemon thread), и опциональный планировщик.
При concurrent writes SQLite выдаёт `database is locked`.
WAL (Write-Ahead Logging) режим существенно снижает блокировки.

### Файл для изменения

**`app/services/user_database.py` — функция создания engine (или `app/client/config/db_config.py`):**

Найти место где создаётся `create_engine(...)` для SQLite и добавить:

```python
engine = create_engine(
    db_url,
    connect_args={
        "check_same_thread": False,
        "timeout": 10,           # ждать до 10 секунд при блокировке
    },
    pool_pre_ping=True,
)

# Включить WAL mode при первом подключении
with engine.connect() as conn:
    conn.execute(text("PRAGMA journal_mode=WAL"))
    conn.execute(text("PRAGMA synchronous=NORMAL"))
    conn.commit()
```

Добавить импорт: `from sqlalchemy import text`

### Проверка выполнения
- [ ] `check_same_thread=False` установлен для всех SQLite engine
- [ ] `timeout=10` установлен в connect_args
- [ ] PRAGMA WAL применяется при создании engine
- [ ] `pool_pre_ping=True` установлен
- [ ] Тесты проходят без `database is locked`

---

## БЛОК-5-ЧАСТЬ-1 — Интеграционные тесты web-маршрутов

### Контекст
Сервисный слой покрыт unit-тестами, но web-маршруты (`app/backend/web/routes.py`)
не тестируются. Рендеринг шаблонов, 404/500 поведение, form submission — не проверены.
Регрессии в HTML-маршрутах не обнаружатся существующими тестами.

### Шаги выполнения

**1. Прочитать существующие тесты в `tests/` для понимания стиля и fixtures.**

**2. Создать `tests/test_web_routes.py` с использованием FastAPI `TestClient`:**

```python
from fastapi.testclient import TestClient
from app.backend.main_api import app

client = TestClient(app)

def test_health_endpoint():
    response = client.get("/api/health")
    assert response.status_code == 200

def test_portfolio_page_loads():
    response = client.get("/portfolio")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]

def test_watchlist_page_loads():
    response = client.get("/watchlist")
    assert response.status_code == 200

def test_stats_page_loads():
    response = client.get("/stats")
    assert response.status_code == 200

def test_settings_page_loads():
    response = client.get("/settings")
    assert response.status_code == 200

def test_unknown_route_returns_404():
    response = client.get("/nonexistent-page")
    assert response.status_code == 404
```

**3. Добавить тест на form submission (добавление инструмента в watchlist):**
- POST `/watchlist/add` с валидным ticker
- Проверить redirect или успешный ответ

**4. Добавить fixture для тестовой БД в памяти (`:memory:`) чтобы тесты не писали в реальную БД.**

### Проверка выполнения
- [ ] `tests/test_web_routes.py` создан
- [ ] Все тесты из файла проходят `python -m unittest tests/test_web_routes.py`
- [ ] Тесты используют in-memory SQLite, не реальную БД
- [ ] Покрыты: GET главных страниц, 404, хотя бы один POST

---

## БЛОК-5-ЧАСТЬ-2 — Архитектурная диаграмма в README

### Контекст
README.md описывает установку, но не даёт понимания архитектуры.
Новый разработчик не видит: как слои связаны, куда добавлять новую функцию,
где проходит граница sandbox/prod.

### Шаги выполнения

**1. Прочитать текущий `README.md`.**

**2. Добавить секцию `## Architecture` с Mermaid-диаграммой:**

```markdown
## Architecture

\`\`\`mermaid
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
\`\`\`
```

**3. Добавить текстовое описание ключевых потоков:**
- Поток торговли: Telegram → Handler → OrderService → preview → confirm → TInvestBroker
- Поток web: Browser → FastAPI Route → WebRequestServices → Service → DB/Broker
- Поток multi-user: chat_id → UserContextResolver → UserContext → per-user SessionFactory

**4. Вставить диаграмму в начало README после кратного описания проекта,
перед разделом установки.**

### Проверка выполнения
- [ ] Секция `## Architecture` добавлена в `README.md`
- [ ] Mermaid-диаграмма корректно описывает все три слоя
- [ ] Описан safety-поток (preview → confirm → execute)
- [ ] README рендерится корректно на GitHub (проверить синтаксис mermaid)

---

## Порядок выполнения (рекомендуемый)

| Приоритет | Задача | Зависимости | Статус |
|-----------|--------|-------------|--------|
| P0 | БЛОК-1-ЧАСТЬ-1 (host 127.0.0.1) | нет | ✅ Выполнено |
| P0 | БЛОК-1-ЧАСТЬ-2 (CORS fix) | нет | ✅ Выполнено |
| P0 | БЛОК-1-ЧАСТЬ-3 (удалить дубль) | нет | ✅ Выполнено |
| P1 | БЛОК-1-ЧАСТЬ-4 (tinkoff deps) | нет | ✅ Выполнено |
| P1 | БЛОК-2-ЧАСТЬ-2 (lifespan) | нет | ✅ Выполнено |
| P1 | БЛОК-4-ЧАСТЬ-1 (SQLite WAL) | нет | ✅ Выполнено (в рамках Alembic) |
| P1 | БЛОК-5-ЧАСТЬ-2 (диаграмма) | нет | — |
| P2 | БЛОК-2-ЧАСТЬ-1 (Alembic) | нет | ✅ Выполнено |
| P2 | БЛОК-2-ЧАСТЬ-3 (мёртвый код) | БЛОК-2-ЧАСТЬ-1 | ✅ Выполнено |
| P2 | БЛОК-3-ЧАСТЬ-1 (web /plans) | нет | — |
| P2 | БЛОК-5-ЧАСТЬ-1 (web тесты) | БЛОК-3-ЧАСТЬ-1 если нужно | — |
