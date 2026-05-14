# Idea Alignment — Tbot v1 / Investor v1

Audit date: 2026-05-14

Grading: ✅ Aligned | ⚠️ Partially aligned | ❌ Not aligned | ❓ Not verified

---

| Область | Сейчас в проекте | Соответствует идее? | Что исправить |
|---|---|---|---|
| **Telegram UI** | Команды buy/sell, меню, preview→confirm flow, research, stats, watchlist, dividends | ✅ | `/start` handler в `run.py` — вынести в отдельный модуль |
| **Web UI** | FastAPI + Jinja2, страницы Portfolio/Buy/Sell/Dividends/Watchlist/Plans/Stats/Settings/Research, server-rendered | ✅ | Нет keyboard shortcuts (запланировано P3-T2). Нет auth (принято для v1) |
| **FastAPI / backend** | Thin router → service layer, API + web routers разделены, CORS ограничен localhost | ✅ | `main_api.py` создаёт таблицы через `create_all_tables()` в lifespan — приемлемо для v1, но стоит отделить DB init от app init |
| **SQLite / ORM** | SQLAlchemy 2.x, per-user SQLite files, Alembic для миграций, injected session factory | ✅ | Два venv (`venv/`, `venv312/`) создают путаницу при DB migrations. Нет `test_watchlist_service.py` |
| **T-Invest integration** | `TInvestBroker` адаптер, sandbox/prod токены, quarantined SDK через прямые PyPI URL | ⚠️ | SDK пины не прошли security review. Зависимость от quarantined пакетов — задокументировано, но не решено |
| **Portfolio service** | Читает позиции, форматирует, injected broker + session | ✅ | Не проверено: покрытие тестами для edge cases (пустой портфель, broker ошибка) |
| **Watchlist** | CRUD через сервис, хранение в SQLite | ✅ | По информации из ROADMAP P0-T3 — тесты для WatchlistService не дописаны |
| **Dividends** | Dividend info по watchlist тикерам через broker | ✅ | Нет dividend calendar (запланировано P4-T3). Нет кэширования — каждый запрос бьёт API |
| **Manual orders** | Preview → confirm → execute, TTL 10 мин, consume-once token, prod требует тикер-подтверждение | ✅ Лучшее в проекте | Нечего исправлять в текущей реализации |
| **Investment plans** | CRUD планов, price conditions (max_price, pct_from_avg, any), PlanRunner реализован | ⚠️ | P2-T1 (APScheduler wiring) не реализован → PlanRunner существует, но не запускается автоматически. Дедлок-риск в PlanConfirmationService (медленный I/O внутри lock) |
| **Analytics** | StatisticsService (базовая статистика ручных сделок), OrderHistory страница | ⚠️ | Нет portfolio snapshots (P4-T1), нет charts (P4-T2). Analytics — самая слабая часть v1 |
| **Signals** | RSI/MACD/EMA/SMA/Bollinger/Alligator сигнальные файлы присутствуют в `app/client/signals/` | ⚠️ | Не подключены к runtime — это хорошо. Но они importable и засоряют проект. Нужна изоляция в `_legacy/` |
| **ML/GPT/LSTM legacy** | `gpt_signal.py`, `lstm_signal.py` в `app/client/signals/` | ❌ | Прямо противоречит идее v1. Требуют изоляции или удаления. Самый высокий приоритет cleanup |
| **Tests** | 21 тестовый файл, покрытие OrderService/ModeService/PlanRunner/PriceConditions/Research/UserContext | ⚠️ | Нет WatchlistService тестов (P0-T3 не завершён). Нет тестов для PlanConfirmationService lock behavior. Нет интеграционного теста полного auto-plan flow |
| **Safety gates** | ModeService, OrderService token TTL, TradingPolicyService (MAX_ORDER/MAX_DAILY), ALLOW_PROD_TRADING, ALLOW_AUTO_INVESTING | ✅ | Дедлок в PlanConfirmationService._lock при slow I/O callback — должен быть исправлен до P2-T1 |
| **Documentation** | README + PROJECT_INSTRUCTIONS + V1_SCOPE + ROADMAP + AGENT_BEHAVIOR — полные и последовательные | ⚠️ | 11 markdown файлов в корне. `INVESTOR_MODE.md`, `RESEARCH_TERMINAL_FOUNDATION.md`, `AUTO_SCHEDULE_TASKS.md`, `MIGRATION_AUDIT.md` — не ясно, актуальны ли они. Нет ARCHITECTURE.md |
| **Config** | `.env` + `users.json`, startup validation, feature flags через env vars | ⚠️ | `investor_reminders.py` использует legacy `CHAT_ID` из `.env` вместо `UserContextResolver`. Противоречит multi-user P1 архитектуре |
| **Deployment / local run** | `python app/run.py` — единственный entrypoint. Docker-compose есть. README_LOCAL_SETUP.md есть | ✅ | Docker-compose не проверен на актуальность. Два venv (`venv/` и `venv312/`) без чёткой документации |
| **User experience** | Telegram: inline кнопки + текстовые команды. Web: функциональный минималистичный UI | ⚠️ | P3 (responsive layout, sidebar, keyboard shortcuts) запланирован, но не реализован. Web UI без auth приемлем только для localhost-only |

---

## Summary

**Сильные стороны**: manual order flow, safety gates, multi-user foundation, service layer separation.

**Слабые стороны**: analytics (не реализованы), legacy signal files (присутствуют), инвестор reminder bypasses multi-user, PlanConfirmationService deadlock risk.

**Критические несоответствия идее v1**:
1. `gpt_signal.py` и `lstm_signal.py` — прямо запрещены идеей v1, но importable.
2. `investor_reminders.py` — использует legacy CHAT_ID, игнорируя multi-user.
3. PlanConfirmationService callback под lock с broker I/O — P2 нельзя запускать без этого fix.
