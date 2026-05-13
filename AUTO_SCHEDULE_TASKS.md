# AUTO SCHEDULE TASKS — Автоматические инвестиционные планы

## Описание функции

Пользователь задаёт план: купить/продать N лотов тикера X каждый день (или еженедельно/ежемесячно)
в заданное время. Перед исполнением бот присылает уведомление в Telegram с кнопками
✅ Исполнить / ❌ Пропустить. Можно задать условие по цене: любая цена, не выше X (для покупки),
не ниже X (для продажи), или не выше/ниже N% от скользящей средней за M дней.
В выходные и праздники — перенос на следующий торговый день.

---

## Архитектура (справочно, агент читает перед каждым блоком)

```
InvestmentPlan (БД)
    ↓
AutoSchedulerService (APScheduler, ежедневные задачи)
    ↓
PriceConditionService (проверка цены)
    ↓ условие выполнено
TelegramConfirmationService (InlineKeyboard, 30 мин TTL)
    ↓ пользователь нажал ✅
OrderService.execute() (существующий, безопасный)
    ↓
InvestmentPlanExecution (лог исполнения)
```

**Ключевые файлы проекта (прочитай перед работой):**
- `app/backend/models/trading.py` — ORM-модели (InvestmentPlan, InvestmentPlanExecution)
- `app/services/investment_plans.py` — InvestmentPlanService (CRUD + proposals)
- `app/services/orders.py` — OrderService (preview/confirm/execute)
- `app/services/mode.py` — ModeService (sandbox/prod)
- `app/integrations/tinvest.py` — TInvestBroker (get_price, place_order)
- `app/client/config/schedulers_config.py` — существующий планировщик (legacy)
- `app/run.py` — точка запуска (там нужно подключить новый scheduler)
- `app/backend/web/routes.py` — web-маршруты
- `app/backend/web/templates/pages/plans.html` — шаблон планов
- `alembic/versions/` — директория для новой миграции

---

## Актуальный backlog

| # | Блок | Активные зависимости | Сложность |
|---|------|----------------------|-----------|
| 1 | АВТО-БЛОК-3: TelegramConfirmationService | — | 5/10 |
| 2 | АВТО-БЛОК-4: AutoSchedulerService | АВТО-БЛОК-3 | 6/10 |
| 3 | АВТО-БЛОК-5: Подключение APScheduler в run.py | АВТО-БЛОК-4 | 2/10 |
| 4 | АВТО-БЛОК-6: Web UI обновление | — | 4/10 |
| 5 | АВТО-БЛОК-7: Telegram команды управления | АВТО-БЛОК-4 | 4/10 |
| 6 | АВТО-БЛОК-8: Config + safety gates | АВТО-БЛОК-4 | 2/10 |
| 7 | АВТО-БЛОК-9: Тесты | все предыдущие активные блоки | 5/10 |

---
## АВТО-БЛОК-3 — TelegramConfirmationService

### Контекст
Когда условие по цене выполнено, бот отправляет в Telegram сообщение с inline-кнопками.
Пользователь нажимает ✅ Исполнить или ❌ Пропустить. Если ответа нет 30 минут — автопропуск.
Архитектурно похоже на `OrderService._preview_tokens`: храним pending-подтверждения в памяти.

### Задача

**Создать `app/services/plan_confirmation.py`:**

```python
import secrets
import threading
import time
from dataclasses import dataclass, field
from typing import Callable, Optional

CONFIRM_TTL_SECONDS = 30 * 60  # 30 минут


@dataclass
class _PendingConfirmation:
    plan_id: int
    ticker: str
    operation: str
    lots: int
    current_price: float
    price_condition_reason: str
    expires_at: float
    on_confirm: Callable       # вызывается при нажатии ✅
    on_skip: Callable          # вызывается при нажатии ❌ или таймауте
    consumed: bool = False


class PlanConfirmationService:
    """
    Управляет pending-подтверждениями авто-планов через Telegram.
    Не делает HTTP-запросов — только хранит состояние и вызывает коллбэки.
    """

    def __init__(self):
        self._pending: dict[str, _PendingConfirmation] = {}
        self._lock = threading.Lock()

    def issue_token(
        self,
        *,
        plan_id: int,
        ticker: str,
        operation: str,
        lots: int,
        current_price: float,
        price_condition_reason: str,
        on_confirm: Callable,
        on_skip: Callable,
    ) -> str:
        """Создаёт токен подтверждения, возвращает его для формирования callback_data."""
        with self._lock:
            self._cleanup()
            token = secrets.token_urlsafe(16)
            self._pending[token] = _PendingConfirmation(
                plan_id=plan_id,
                ticker=ticker,
                operation=operation,
                lots=lots,
                current_price=current_price,
                price_condition_reason=price_condition_reason,
                expires_at=time.time() + CONFIRM_TTL_SECONDS,
                on_confirm=on_confirm,
                on_skip=on_skip,
            )
            return token

    def confirm(self, token: str) -> bool:
        """Вызывается при нажатии ✅. Возвращает True если токен был валиден."""
        with self._lock:
            pending = self._pending.get(token)
            if pending is None or pending.consumed or pending.expires_at < time.time():
                return False
            pending.consumed = True
            pending.on_confirm()
            return True

    def skip(self, token: str, reason: str = "user_declined") -> bool:
        """Вызывается при нажатии ❌ или таймауте."""
        with self._lock:
            pending = self._pending.get(token)
            if pending is None or pending.consumed:
                return False
            pending.consumed = True
            pending.on_skip(reason)
            return True

    def expire_old(self):
        """Вызывать периодически из планировщика для автоматического истечения."""
        with self._lock:
            now = time.time()
            for token, pending in list(self._pending.items()):
                if not pending.consumed and pending.expires_at < now:
                    pending.consumed = True
                    pending.on_skip("timeout")
            self._cleanup()

    def _cleanup(self):
        self._pending = {
            t: p for t, p in self._pending.items()
            if not p.consumed and p.expires_at >= time.time()
        }
```

**Создать `app/client/handlers/plans/auto_confirm_handler.py`:**

```python
from app.client.bot.bot import bot
from app.services.plan_confirmation import PlanConfirmationService
from telebot import types

# Глобальный экземпляр (инициализируется в run.py)
plan_confirmation_service: PlanConfirmationService = None


def send_plan_confirmation_message(
    chat_id: int,
    *,
    token: str,
    ticker: str,
    operation: str,
    lots: int,
    current_price: float,
    price_reason: str,
):
    """Отправляет Telegram-сообщение с inline-кнопками ✅/❌."""
    op_label = "ПОКУПКА" if operation == "buy" else "ПРОДАЖА"
    text = (
        f"📋 *Авто-план готов к исполнению*\n\n"
        f"*{op_label}* {ticker} — {lots} лот(ов)\n"
        f"Цена: ~{current_price:.2f} ₽\n"
        f"Условие: {price_reason}\n\n"
        f"⏳ Подтверди в течение 30 минут."
    )

    keyboard = types.InlineKeyboardMarkup()
    keyboard.add(
        types.InlineKeyboardButton("✅ Исполнить", callback_data=f"plan_confirm:{token}"),
        types.InlineKeyboardButton("❌ Пропустить", callback_data=f"plan_skip:{token}"),
    )
    bot.send_message(chat_id, text, reply_markup=keyboard, parse_mode="Markdown")


@bot.callback_query_handler(func=lambda call: call.data.startswith("plan_confirm:"))
def handle_plan_confirm(call):
    token = call.data.split(":", 1)[1]
    if plan_confirmation_service and plan_confirmation_service.confirm(token):
        bot.answer_callback_query(call.id, "✅ Ордер отправлен!")
        bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id, reply_markup=None)
    else:
        bot.answer_callback_query(call.id, "⚠️ Запрос устарел или уже обработан.")


@bot.callback_query_handler(func=lambda call: call.data.startswith("plan_skip:"))
def handle_plan_skip(call):
    token = call.data.split(":", 1)[1]
    if plan_confirmation_service and plan_confirmation_service.skip(token, "user_declined"):
        bot.answer_callback_query(call.id, "❌ Пропущено.")
        bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id, reply_markup=None)
    else:
        bot.answer_callback_query(call.id, "⚠️ Запрос устарел или уже обработан.")
```

### Проверка выполнения
- [ ] `app/services/plan_confirmation.py` создан
- [ ] `PlanConfirmationService` хранит pending под threading.Lock
- [ ] TTL 30 минут, токен на `secrets.token_urlsafe(16)`
- [ ] `expire_old()` вызывает on_skip("timeout") для истёкших
- [ ] `app/client/handlers/plans/auto_confirm_handler.py` создан
- [ ] Callback-handlers зарегистрированы на `plan_confirm:*` и `plan_skip:*`
- [ ] `python -m unittest discover -q` проходит

---

## АВТО-БЛОК-4 — AutoSchedulerService

### Контекст
Основной оркестратор: читает активные планы, определяет следующий запуск, проверяет
торговый день, получает цену, вызывает PriceConditionService, отправляет подтверждение
или логирует пропуск. Не вызывает `OrderService` напрямую — только готовит и делегирует.

### Задача

**Создать `app/services/auto_scheduler.py`:**

```python
from datetime import datetime, date
import logging

logger = logging.getLogger(__name__)

# Известные нерабочие дни Московской биржи (дополнять ежегодно)
# Формат: set of (month, day) — применяется к любому году
MOEX_HOLIDAY_MMDD: set[tuple[int, int]] = {
    (1, 1), (1, 2), (1, 3), (1, 4), (1, 5), (1, 6), (1, 7), (1, 8),  # Новый год
    (2, 23),   # День защитника
    (3, 8),    # 8 марта
    (5, 1),    # Праздник труда
    (5, 9),    # День Победы
    (6, 12),   # День России
    (11, 4),   # День народного единства
    (12, 31),  # Новый год (сокращённый)
}


def is_trading_day(dt: date) -> bool:
    """Возвращает True если день является торговым на Московской бирже."""
    if dt.weekday() >= 5:  # суббота=5, воскресенье=6
        return False
    if (dt.month, dt.day) in MOEX_HOLIDAY_MMDD:
        return False
    return True


def next_trading_day(dt: date) -> date:
    """Возвращает ближайший следующий торговый день (включая текущий)."""
    from datetime import timedelta
    candidate = dt
    while not is_trading_day(candidate):
        candidate += timedelta(days=1)
    return candidate
```

**Создать `app/services/plan_runner.py` — исполнитель одного плана:**

```python
from dataclasses import dataclass
from typing import Callable, Optional
import logging

from app.services.investment_plans import InvestmentPlanService
from app.services.price_conditions import PriceConditionService
from app.services.plan_confirmation import PlanConfirmationService
from app.services.orders import OrderService, OrderPreviewRequest, OrderConfirmCommand
from app.services.user_database import SessionFactory

logger = logging.getLogger(__name__)


@dataclass
class PlanRunResult:
    plan_id: int
    ticker: str
    status: str          # "sent_for_confirmation", "skipped", "executed", "error"
    reason: str


class PlanRunner:
    """
    Исполняет один план: проверяет цену, отправляет подтверждение или логирует пропуск.
    """

    def __init__(
        self,
        *,
        plan_service: InvestmentPlanService,
        price_condition_service: PriceConditionService,
        confirmation_service: PlanConfirmationService,
        order_service: OrderService,
        session_factory: SessionFactory,
        telegram_chat_id: int,
        notify_fn: Callable,       # функция отправки TG-сообщения об итогах
        send_confirmation_fn: Callable,  # функция из auto_confirm_handler
    ):
        self.plan_service = plan_service
        self.price_condition_service = price_condition_service
        self.confirmation_service = confirmation_service
        self.order_service = order_service
        self.session_factory = session_factory
        self.chat_id = telegram_chat_id
        self.notify = notify_fn
        self.send_confirmation = send_confirmation_fn

    def run(self, plan_id: int) -> PlanRunResult:
        """Точка входа — вызывается из APScheduler."""
        from datetime import date
        from app.services.auto_scheduler import next_trading_day

        today = date.today()
        from app.services.auto_scheduler import is_trading_day
        if not is_trading_day(today):
            return self._skip(plan_id, "market_closed", "Сегодня не торговый день.")

        try:
            plan = self.plan_service._get_plan_view(plan_id)
        except Exception as exc:
            return PlanRunResult(plan_id=plan_id, ticker="?", status="error", reason=str(exc))

        # Получить текущую цену
        try:
            preview = self.order_service.preview(
                OrderPreviewRequest(operation=plan.operation, ticker=plan.ticker, lots=plan.lots)
            )
            current_price = preview.estimated_price
        except Exception as exc:
            return self._skip(plan_id, "error", f"Ошибка получения цены: {exc}")

        # Проверить условие по цене
        condition = self.price_condition_service.check(plan=plan, current_price=current_price)
        if not condition.allowed:
            self.notify(
                self.chat_id,
                f"⏭ *Авто-план пропущен*: {plan.ticker}\n{condition.reason}",
            )
            return self._skip(plan_id, "price_condition", condition.reason)

        # Всё OK — запросить подтверждение
        token = self.confirmation_service.issue_token(
            plan_id=plan_id,
            ticker=plan.ticker,
            operation=plan.operation,
            lots=plan.lots,
            current_price=current_price,
            price_condition_reason=condition.reason,
            on_confirm=lambda: self._execute(plan_id, plan, preview),
            on_skip=lambda reason: self._record_skip(plan_id, plan.ticker, reason),
        )

        self.send_confirmation(
            self.chat_id,
            token=token,
            ticker=plan.ticker,
            operation=plan.operation,
            lots=plan.lots,
            current_price=current_price,
            price_reason=condition.reason,
        )

        return PlanRunResult(
            plan_id=plan_id, ticker=plan.ticker,
            status="sent_for_confirmation", reason="Ожидание подтверждения в Telegram.",
        )

    def _execute(self, plan_id: int, plan, preview):
        """Вызывается из on_confirm коллбэка."""
        try:
            result = self.order_service.execute(
                OrderConfirmCommand(
                    operation=plan.operation,
                    ticker=plan.ticker,
                    lots=plan.lots,
                    confirm_token=preview.confirm_token,
                )
            )
            self._record_execution(plan_id, plan.ticker, result)
            self.notify(
                self.chat_id,
                f"✅ *Авто-план исполнен*: {plan.ticker}\n"
                f"Ордер: {result.order_id}\nСумма: ~{result.estimated_value:.2f}₽",
            )
        except Exception as exc:
            self.notify(self.chat_id, f"❌ *Ошибка исполнения плана* {plan.ticker}: {exc}")

    def _skip(self, plan_id: int, reason_code: str, reason: str) -> PlanRunResult:
        self._record_skip(plan_id, "?", reason_code)
        return PlanRunResult(plan_id=plan_id, ticker="?", status="skipped", reason=reason)

    def _record_execution(self, plan_id: int, ticker: str, result):
        from app.backend.models.trading import InvestmentPlanExecution
        from datetime import datetime
        db = self.session_factory()
        try:
            db.add(InvestmentPlanExecution(
                plan_id=plan_id, order_id=result.order_id, ticker=ticker,
                amount_rub=result.estimated_value, status="executed",
                execution_mode="auto", skipped_reason=None,
            ))
            db.commit()
        finally:
            db.close()

    def _record_skip(self, plan_id: int, ticker: str, reason_code: str):
        from app.backend.models.trading import InvestmentPlanExecution
        from datetime import datetime
        db = self.session_factory()
        try:
            db.add(InvestmentPlanExecution(
                plan_id=plan_id, order_id=None, ticker=ticker,
                amount_rub=0.0, status="skipped",
                execution_mode="auto", skipped_reason=reason_code,
            ))
            db.commit()
        finally:
            db.close()
```

**Добавить вспомогательный метод в `InvestmentPlanService`:**

```python
def _get_plan_view(self, plan_id: int) -> InvestmentPlanView:
    """Возвращает InvestmentPlanView по id, бросает InvestmentPlanServiceError если не найден."""
    db = self.session_factory()
    try:
        plan = self._get_plan(db, plan_id)
        return self._to_view(plan)
    finally:
        db.close()
```

### Проверка выполнения
- [ ] `app/services/auto_scheduler.py` создан с `is_trading_day()` и `next_trading_day()`
- [ ] `MOEX_HOLIDAY_MMDD` содержит основные российские праздники
- [ ] `app/services/plan_runner.py` создан с `PlanRunner`
- [ ] `PlanRunner.run()` проверяет торговый день → цену → условие → отправляет TG-подтверждение
- [ ] `_record_execution()` и `_record_skip()` пишут в `InvestmentPlanExecution`
- [ ] `InvestmentPlanService._get_plan_view()` добавлен
- [ ] `python -m unittest discover -q` проходит

---

## АВТО-БЛОК-5 — Подключение APScheduler в run.py

### Контекст
APScheduler уже является зависимостью (`requirements-base.txt`). Нужно:
1. Создать функцию `configure_auto_scheduler()` которая читает все активные планы и
   регистрирует для каждого cron-задачу.
2. Добавить периодическое истечение pending-подтверждений (каждые 5 минут).
3. Подключить в `app/run.py`.

### Задача

**Создать `app/client/config/auto_scheduler_config.py`:**

```python
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
import logging

logger = logging.getLogger(__name__)

_auto_scheduler: BackgroundScheduler | None = None


def configure_auto_scheduler(
    *,
    plan_runner,              # PlanRunner instance
    confirmation_service,     # PlanConfirmationService instance
    session_factory,
) -> BackgroundScheduler | None:
    """
    Читает все активные планы из БД и создаёт cron-задачу для каждого.
    Возвращает запущенный scheduler или None если ENABLE_INVESTMENT_PLANS=false.
    """
    from app.client.config import investment_plans_enabled
    if not investment_plans_enabled():
        logger.info("ENABLE_INVESTMENT_PLANS=false — авто-планировщик не запущен.")
        return None

    global _auto_scheduler
    _auto_scheduler = BackgroundScheduler(timezone="Europe/Moscow")

    # Истечение pending-подтверждений каждые 5 минут
    _auto_scheduler.add_job(
        confirmation_service.expire_old,
        trigger="interval",
        minutes=5,
        id="expire_confirmations",
    )

    # Задачи для каждого плана
    _reload_plan_jobs(_auto_scheduler, plan_runner, session_factory)

    _auto_scheduler.start()
    logger.info("Авто-планировщик запущен.")
    return _auto_scheduler


def _reload_plan_jobs(scheduler, plan_runner, session_factory):
    """Добавляет cron-задачи для всех активных планов."""
    from app.backend.models.trading import InvestmentPlan
    db = session_factory()
    try:
        plans = db.query(InvestmentPlan).all()
        for plan in plans:
            _add_plan_job(scheduler, plan_runner, plan)
        logger.info(f"Зарегистрировано задач: {len(plans)}")
    finally:
        db.close()


def _add_plan_job(scheduler, plan_runner, plan):
    """Регистрирует один план в планировщике."""
    hour, minute = plan.time.split(":")
    job_id = f"plan_{plan.id}"

    # Удалить старую задачу если есть
    if scheduler.get_job(job_id):
        scheduler.remove_job(job_id)

    if plan.schedule == "daily":
        trigger = CronTrigger(day_of_week="mon-fri", hour=int(hour), minute=int(minute), timezone="Europe/Moscow")
    elif plan.schedule == "weekly":
        trigger = CronTrigger(day_of_week=plan.created_at.weekday() if plan.created_at else 0,
                              hour=int(hour), minute=int(minute), timezone="Europe/Moscow")
    elif plan.schedule == "monthly":
        day = plan.created_at.day if plan.created_at else 1
        trigger = CronTrigger(day=day, hour=int(hour), minute=int(minute), timezone="Europe/Moscow")
    else:
        return

    scheduler.add_job(
        plan_runner.run,
        trigger=trigger,
        args=[plan.id],
        id=job_id,
        replace_existing=True,
        misfire_grace_time=3600,  # если пропущено — запустить в течение часа
    )
```

**Обновить `app/run.py` — добавить инициализацию авто-планировщика:**

В блоке `if __name__ == '__main__':` после `configure_schedulers()` добавить:

```python
# Авто-планировщик (Investment Plans)
from app.client.config.auto_scheduler_config import configure_auto_scheduler
from app.services.plan_runner import PlanRunner
from app.services.plan_confirmation import PlanConfirmationService
from app.client.handlers.plans.auto_confirm_handler import (
    send_plan_confirmation_message,
    plan_confirmation_service as _pcs_ref
)
import app.client.handlers.plans.auto_confirm_handler as _auto_confirm_module
from app.client.bot.bot import bot as _bot

# Инициализировать confirmation_service и привязать к handler
_confirmation_svc = PlanConfirmationService()
_auto_confirm_module.plan_confirmation_service = _confirmation_svc

# Создать PlanRunner для первого enabled-пользователя
# (для multi-user: итерировать по пользователям, создавать отдельный PlanRunner каждому)
default_user = user_context_resolver.default_web_user()
_telegram_services = ...  # получить TelegramServices для default_user

_plan_runner = PlanRunner(
    plan_service=_telegram_services.investment_plan_service,
    price_condition_service=_telegram_services.price_condition_service,
    confirmation_service=_confirmation_svc,
    order_service=_telegram_services.order_service,
    session_factory=_telegram_services.session_factory,
    telegram_chat_id=default_user.telegram_chat_id,
    notify_fn=lambda chat_id, text: _bot.send_message(chat_id, text, parse_mode="Markdown"),
    send_confirmation_fn=send_plan_confirmation_message,
)

configure_auto_scheduler(
    plan_runner=_plan_runner,
    confirmation_service=_confirmation_svc,
    session_factory=_telegram_services.session_factory,
)
```

**Добавить `investment_plans_enabled()` в `app/client/config/__init__.py`** если ещё нет:

```python
def investment_plans_enabled() -> bool:
    return os.getenv("ENABLE_INVESTMENT_PLANS", "false").strip().lower() == "true"
```

### Проверка выполнения
- [ ] `app/client/config/auto_scheduler_config.py` создан
- [ ] `configure_auto_scheduler()` запускает `BackgroundScheduler` в timezone Moscow
- [ ] `expire_old` задача добавлена (каждые 5 минут)
- [ ] `misfire_grace_time=3600` установлен для всех plan-задач
- [ ] `app/run.py` инициализирует PlanRunner и вызывает `configure_auto_scheduler()`
- [ ] `investment_plans_enabled()` существует в `app/client/config/__init__.py`
- [ ] При `ENABLE_INVESTMENT_PLANS=false` планировщик не запускается (проверить логи)

---

## АВТО-БЛОК-6 — Обновить Web UI (/plans)

### Контекст
Форма создания плана сейчас не имеет полей для `operation`, `price_limit`, `pct_threshold`,
`avg_period_days`, `confirmation_mode`. Шаблон нужно расширить.

### Задача

**1. Обновить `parse_plan_definition()` в `app/backend/web/routes.py`:**

```python
def parse_plan_definition(form: dict) -> PlanDefinition:
    return PlanDefinition(
        ticker=form.get("ticker", ""),
        operation=form.get("operation", "buy"),
        lots=parse_lots(form.get("lots", "1")),
        schedule=form.get("schedule", "monthly"),
        time=form.get("time", "09:00"),
        price_rule=form.get("price_rule", "any"),
        price_limit=float(form["price_limit"]) if form.get("price_limit") else None,
        pct_threshold=float(form["pct_threshold"]) if form.get("pct_threshold") else None,
        avg_period_days=int(form["avg_period_days"]) if form.get("avg_period_days") else None,
        order_type="limit",
        confirmation_mode=form.get("confirmation_mode", "telegram_confirm"),
        confirmation_required=True,
    )
```

**2. Обновить `PlanDefinition` dataclass в `app/services/investment_plans.py`:**

Добавить поля:
```python
operation: str = "buy"
price_limit: Optional[float] = None
pct_threshold: Optional[float] = None
avg_period_days: Optional[int] = None
confirmation_mode: str = "telegram_confirm"
```

**3. Обновить шаблон `app/backend/web/templates/pages/plans.html`:**

В форму создания плана добавить следующие секции:

**Секция "Операция":**
```html
<div class="field">
  <label>Операция</label>
  <select name="operation">
    <option value="buy">Купить</option>
    <option value="sell">Продать</option>
  </select>
</div>
```

**Секция "Условие по цене" (с динамической видимостью через JS):**
```html
<div class="field">
  <label>Условие по цене</label>
  <select name="price_rule" id="price_rule_select">
    <option value="any">Любая цена</option>
    <option value="max_price">Фиксированный лимит</option>
    <option value="pct_from_avg">% от скользящей средней</option>
  </select>
</div>

<!-- Показывать только при price_rule=max_price -->
<div id="price_limit_row" class="field" style="display:none">
  <label>Лимит цены (₽)</label>
  <input type="number" name="price_limit" step="0.01" min="0.01" placeholder="310.00">
</div>

<!-- Показывать только при price_rule=pct_from_avg -->
<div id="pct_row" class="field" style="display:none">
  <label>Порог (%)</label>
  <input type="number" name="pct_threshold" step="0.1" min="0.1" placeholder="5.0">
  <label>Период (дней)</label>
  <input type="number" name="avg_period_days" min="5" max="365" placeholder="30">
</div>
```

**JS для переключения:**
```html
<script>
document.getElementById('price_rule_select').addEventListener('change', function() {
  document.getElementById('price_limit_row').style.display =
    this.value === 'max_price' ? 'block' : 'none';
  document.getElementById('pct_row').style.display =
    this.value === 'pct_from_avg' ? 'block' : 'none';
});
</script>
```

**4. В списке планов показывать новые поля:**
- Операция (BUY/SELL бейдж)
- `price_condition_display`
- История последних 5 исполнений из `InvestmentPlanExecution`

**5. Обновить `plans_context()` в `routes.py` — добавить историю:**

```python
context["executions"] = services.investment_plan_service.list_recent_executions(limit=20)
```

Добавить `list_recent_executions()` в `InvestmentPlanService`.

### Проверка выполнения
- [ ] Форма содержит поля: operation, price_rule, price_limit, pct_threshold, avg_period_days
- [ ] JS динамически показывает/скрывает поля в зависимости от price_rule
- [ ] Список планов отображает operation и price_condition_display
- [ ] История исполнений отображается на странице
- [ ] `POST /plans/create` с новыми полями создаёт план без ошибок
- [ ] `python -m unittest discover -q` проходит

---

## АВТО-БЛОК-7 — Telegram команды управления планами

### Контекст
Пользователь должен уметь управлять авто-планами из Telegram без открытия браузера.
Минимальный набор: просмотр списка, добавление, удаление.

### Задача

**Создать `app/client/handlers/plans/plan_command_handler.py`:**

Зарегистрировать следующие команды:

**`/plans`** — список активных планов:
```
📋 Активные авто-планы:

1. SBER — ПОКУПКА 1 лот
   Расписание: ежедневно 09:00
   Условие: ≤ 310.00 ₽
   Подтверждение: Telegram

2. GAZP — ПОКУПКА 2 лота
   Расписание: ежемесячно 10:00
   Условие: Любая цена
```

**`/plan_add <TICKER> <buy|sell> <LOTS> <TIME> [max_price=X | pct=X days=Y]`**

Примеры:
- `/plan_add SBER buy 1 09:00` — купить 1 лот SBER каждый день в 09:00 по любой цене
- `/plan_add SBER buy 1 09:00 max_price=310` — не дороже 310₽
- `/plan_add SBER buy 1 09:00 pct=5 days=30` — не выше 5% от 30-дневной средней

Парсинг: разобрать аргументы через `shlex.split()` или простой split + keyword args.

**`/plan_remove <ID>`** — удалить план по ID.

**Зарегистрировать команды в `app/run.py`** после остальных handlers:
```python
from app.client.handlers.plans.plan_command_handler import register_plan_commands
register_plan_commands(bot, user_context_resolver)
```

### Проверка выполнения
- [ ] `/plans` возвращает список планов пользователя
- [ ] `/plan_add SBER buy 1 09:00` создаёт план без ошибок
- [ ] `/plan_add SBER buy 1 09:00 max_price=310` создаёт план с price_rule=max_price
- [ ] `/plan_remove 1` удаляет план #1
- [ ] Неизвестный ticker или неверные аргументы возвращают понятную ошибку
- [ ] Все команды доступны только авторизованным пользователям (через `UserContextResolver`)

---

## АВТО-БЛОК-8 — Config и safety gates

### Контекст
Новая функция требует явного включения через `.env`. По умолчанию всё выключено.
Нужно задокументировать переменные и добавить проверки при старте.

### Задача

**1. Обновить `.env.example` — добавить блок авто-планирования:**

```
# === АВТО-ИНВЕСТИЦИОННЫЕ ПЛАНЫ ===
# Включить инвестиционные планы (создание через web/telegram).
ENABLE_INVESTMENT_PLANS = "false"
# Разрешить автоматическое исполнение планов (планировщик APScheduler).
# Требует ENABLE_INVESTMENT_PLANS="true".
ENABLE_BACKGROUND_SCHEDULERS = "false"
# Разрешить автоматические ордера без дополнительного подтверждения.
# Если "false" — бот всегда запрашивает подтверждение в Telegram перед исполнением.
ALLOW_AUTO_INVESTING = "false"
# Максимальная сумма одного автоматического ордера в рублях. 0 = блокирует авто.
MAX_ORDER_RUB = "0"
# Максимальная сумма автоматических ордеров за один торговый день. 0 = блокирует авто.
MAX_DAILY_INVEST_RUB = "0"
```

**2. Добавить проверку в `validate_startup_config()` (`app/client/config/__init__.py`):**

```python
# Если планировщик включён без plans — предупредить
if background_schedulers_enabled() and not investment_plans_enabled():
    logger.warning("ENABLE_BACKGROUND_SCHEDULERS=true но ENABLE_INVESTMENT_PLANS=false — планировщик не запустится.")

# Если ALLOW_AUTO_INVESTING=true но MAX_ORDER_RUB=0 — предупредить что будет блокировка
if allow_auto_investing() and max_order_rub() == 0:
    logger.warning("ALLOW_AUTO_INVESTING=true но MAX_ORDER_RUB=0 — все авто-ордера будут заблокированы лимитом.")
```

**3. В `TradingPolicyService.check_auto_execution()` убедиться что:**
- При `MAX_ORDER_RUB=0` — блокирует и возвращает понятное сообщение
- При `ALLOW_AUTO_INVESTING=false` — разрешает только если пришло подтверждение из Telegram
  (то есть `confirmation_required=True` всегда эффективно при этом флаге)

### Проверка выполнения
- [ ] `.env.example` содержит все 5 переменных с комментариями
- [ ] `validate_startup_config()` логирует предупреждения при конфликтующих настройках
- [ ] При `MAX_ORDER_RUB=0` авто-ордер блокируется с понятной ошибкой
- [ ] Дефолтные значения (`ENABLE_INVESTMENT_PLANS=false`) не ломают существующие тесты

---

## АВТО-БЛОК-9 — Тесты

### Контекст
Оставшиеся сервисы требуют покрытия: логика торгового дня, подтверждения планов и базовый happy path для PlanRunner.

### Задача

**Создать `tests/test_auto_scheduler.py`:**

```python
# Тесты:
# 1. is_trading_day: понедельник → True
# 2. is_trading_day: суббота → False
# 3. is_trading_day: 1 января → False
# 4. next_trading_day: суббота → следующий понедельник
# 5. next_trading_day: 31 декабря (если воскресенье) → следующий рабочий день
```

**Создать `tests/test_plan_confirmation.py`:**

```python
# Тесты:
# 1. issue_token → confirm → on_confirm вызван, consumed=True
# 2. issue_token → skip → on_skip вызван
# 3. confirm дважды → второй раз возвращает False
# 4. expire_old → on_skip("timeout") вызван для истёкшего токена
# 5. confirm истёкшего токена → False
```

**Запустить все тесты:**
```
python -m unittest discover -q
```

### Проверка выполнения
- [ ] `tests/test_auto_scheduler.py` создан, все 5 тест-кейсов проходят
- [ ] `tests/test_plan_confirmation.py` создан, все 5 тест-кейсов проходят
- [ ] `python -m unittest discover -q` — все тесты зелёные, нет регрессий

