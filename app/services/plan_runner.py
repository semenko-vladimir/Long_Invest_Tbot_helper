import logging
from dataclasses import dataclass
from datetime import date
from typing import Callable

from app.services.auto_scheduler import is_trading_day
from app.services.investment_plans import InvestmentPlanService, InvestmentPlanView
from app.services.orders import OrderConfirmCommand, OrderPreviewRequest, OrderService
from app.services.plan_confirmation import PlanConfirmationService
from app.services.price_conditions import PriceConditionService
from app.services.user_database import SessionFactory

logger = logging.getLogger(__name__)


@dataclass
class PlanRunResult:
    plan_id: int
    ticker: str
    status: str   # "sent_for_confirmation" | "skipped" | "executed" | "error"
    reason: str


class PlanRunner:
    """
    Executes one auto-investment plan: checks trading day, current price,
    price condition, then sends a Telegram confirmation request or logs a skip.
    Does not place orders directly — delegates to OrderService via on_confirm callback.
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
        notify_fn: Callable,
        send_confirmation_fn: Callable,
    ) -> None:
        self.plan_service = plan_service
        self.price_condition_service = price_condition_service
        self.confirmation_service = confirmation_service
        self.order_service = order_service
        self.session_factory = session_factory
        self.chat_id = telegram_chat_id
        self.notify = notify_fn
        self.send_confirmation = send_confirmation_fn

    def run(self, plan_id: int) -> PlanRunResult:
        """Entry point — called from APScheduler."""
        if not is_trading_day(date.today()):
            return self._skip(plan_id, "market_closed", "Сегодня не торговый день.")

        try:
            plan = self.plan_service._get_plan_view(plan_id)
        except Exception as exc:
            return PlanRunResult(plan_id=plan_id, ticker="?", status="error", reason=str(exc))

        try:
            preview = self.order_service.preview(
                OrderPreviewRequest(operation=plan.operation, ticker=plan.ticker, lots=plan.lots)
            )
            current_price = preview.estimated_price
        except Exception as exc:
            return self._skip(plan_id, "error", f"Ошибка получения цены: {exc}", ticker=plan.ticker)

        condition = self.price_condition_service.check(plan=plan, current_price=current_price)
        if not condition.allowed:
            self.notify(
                self.chat_id,
                f"⏭ *Авто-план пропущен*: {plan.ticker}\n{condition.reason}",
            )
            return self._skip(plan_id, "price_condition", condition.reason, ticker=plan.ticker)

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
            plan_id=plan_id,
            ticker=plan.ticker,
            status="sent_for_confirmation",
            reason="Ожидание подтверждения в Telegram.",
        )

    def _execute(self, plan_id: int, plan: InvestmentPlanView, preview) -> None:
        """Called from on_confirm callback when user presses ✅."""
        try:
            result = self.order_service.execute(
                OrderConfirmCommand(
                    operation=plan.operation,
                    ticker=plan.ticker,
                    lots=plan.lots,
                    confirm_token=preview.confirm_token,
                )
            )
            self._record_execution(plan_id, plan.ticker, result.order_id, preview.estimated_value)
            self.notify(
                self.chat_id,
                f"✅ *Авто-план исполнен*: {plan.ticker}\n"
                f"Ордер: {result.order_id}\nСумма: ~{preview.estimated_value:.2f}₽",
            )
        except Exception as exc:
            self.notify(self.chat_id, f"❌ *Ошибка исполнения плана* {plan.ticker}: {exc}")

    def _skip(
        self, plan_id: int, reason_code: str, reason: str, *, ticker: str = "?"
    ) -> PlanRunResult:
        self._record_skip(plan_id, ticker, reason_code)
        return PlanRunResult(plan_id=plan_id, ticker=ticker, status="skipped", reason=reason)

    def _record_execution(
        self, plan_id: int, ticker: str, order_id: str, amount_rub: float
    ) -> None:
        from app.backend.models.trading import InvestmentPlanExecution

        db = self.session_factory()
        try:
            db.add(
                InvestmentPlanExecution(
                    plan_id=plan_id,
                    order_id=order_id,
                    ticker=ticker,
                    amount_rub=amount_rub,
                    status="executed",
                    execution_mode="auto",
                    skipped_reason=None,
                )
            )
            db.commit()
        finally:
            db.close()

    def _record_skip(self, plan_id: int, ticker: str, reason_code: str) -> None:
        from app.backend.models.trading import InvestmentPlanExecution

        db = self.session_factory()
        try:
            db.add(
                InvestmentPlanExecution(
                    plan_id=plan_id,
                    order_id=None,
                    ticker=ticker,
                    amount_rub=0.0,
                    status="skipped",
                    execution_mode="auto",
                    skipped_reason=reason_code,
                )
            )
            db.commit()
        finally:
            db.close()
