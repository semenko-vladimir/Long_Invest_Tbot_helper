import calendar
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Callable, Optional

from app.backend.models.trading import InvestmentPlan
from app.services.orders import OrderPreviewRequest, OrderPreviewResult, OrderService
from app.services.trading_policy import (
    AutoExecutionRequest,
    PolicyCheckResult,
    TradingPolicyService,
    TradingPolicyStatus,
)
from app.services.user_database import SessionFactory, get_default_session_factory


SUPPORTED_SCHEDULES = {"daily", "weekly", "monthly"}
SUPPORTED_OPERATIONS = {"buy", "sell"}
SUPPORTED_PRICE_RULES = {"any", "current_market", "max_price", "pct_from_avg"}
SUPPORTED_ORDER_TYPES = {"limit"}
SUPPORTED_CONFIRMATION_MODES = {"telegram_confirm", "auto"}

SCHEDULE_LABELS = {
    "daily": "Daily",
    "weekly": "Weekly",
    "monthly": "Monthly",
}

PRICE_RULE_LABELS = {
    "any": "Any price",
    "current_market": "Current market price",
    "max_price": "Fixed price limit",
    "pct_from_avg": "% from moving average",
}

ORDER_TYPE_LABELS = {
    "limit": "Limit",
}


class InvestmentPlanServiceError(ValueError):
    pass


@dataclass(frozen=True)
class PlanDefinition:
    ticker: str
    lots: int
    schedule: str
    time: str
    price_rule: str = "current_market"
    order_type: str = "limit"
    confirmation_required: bool = True
    operation: str = "buy"
    price_limit: Optional[float] = None
    pct_threshold: Optional[float] = None
    avg_period_days: Optional[int] = None
    confirmation_mode: str = "telegram_confirm"


@dataclass(frozen=True)
class InvestmentPlanView:
    id: int
    ticker: str
    lots: int
    schedule: str
    schedule_label: str
    time: str
    price_rule: str
    price_rule_label: str
    order_type: str
    order_type_label: str
    confirmation_required: bool
    confirmation_label: str
    next_run_at: str
    next_run_display: str
    operation: str = "buy"
    price_limit: Optional[float] = None
    pct_threshold: Optional[float] = None
    avg_period_days: Optional[int] = None
    confirmation_mode: str = "telegram_confirm"
    price_condition_display: str = "Текущая рыночная"


@dataclass(frozen=True)
class InvestmentPlanListView:
    plans: list[InvestmentPlanView]
    empty: bool
    notice: Optional[str] = None
    error: Optional[str] = None


@dataclass(frozen=True)
class ProposedPrice:
    value: float
    display: str
    rule_label: str


@dataclass(frozen=True)
class InvestmentPlanProposal:
    plan: InvestmentPlanView
    proposed_lots: int
    proposed_limit_price: float
    proposed_limit_price_display: str
    preview: OrderPreviewResult
    generated_at: str
    execution_note: str


class NextRunCalculator:
    def calculate(
        self,
        *,
        schedule: str,
        time_text: str,
        created_at: Optional[datetime] = None,
        now: Optional[datetime] = None,
    ) -> datetime:
        now = now or datetime.now()
        created_at = created_at or now
        hour, minute = self._parse_time(time_text)

        if schedule == "daily":
            candidate = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
            return candidate if candidate > now else candidate + timedelta(days=1)

        if schedule == "weekly":
            days_ahead = (created_at.weekday() - now.weekday()) % 7
            candidate = (now + timedelta(days=days_ahead)).replace(
                hour=hour,
                minute=minute,
                second=0,
                microsecond=0,
            )
            return candidate if candidate > now else candidate + timedelta(days=7)

        if schedule == "monthly":
            candidate = self._monthly_candidate(now.year, now.month, created_at.day, hour, minute)
            if candidate > now:
                return candidate
            next_year, next_month = self._next_month(now.year, now.month)
            return self._monthly_candidate(next_year, next_month, created_at.day, hour, minute)

        raise InvestmentPlanServiceError("Unsupported plan schedule.")

    def _parse_time(self, time_text: str) -> tuple[int, int]:
        parts = str(time_text or "").split(":", 1)
        if len(parts) != 2:
            raise InvestmentPlanServiceError("Plan time must use HH:MM format.")

        try:
            hour = int(parts[0])
            minute = int(parts[1])
        except ValueError as exc:
            raise InvestmentPlanServiceError("Plan time must use HH:MM format.") from exc

        if not (0 <= hour <= 23 and 0 <= minute <= 59):
            raise InvestmentPlanServiceError("Plan time must use HH:MM format.")

        return hour, minute

    def _monthly_candidate(self, year: int, month: int, day: int, hour: int, minute: int) -> datetime:
        last_day = calendar.monthrange(year, month)[1]
        return datetime(year, month, min(day, last_day), hour, minute)

    def _next_month(self, year: int, month: int) -> tuple[int, int]:
        if month == 12:
            return year + 1, 1
        return year, month + 1


class ProposedPriceCalculator:
    def calculate(self, *, plan: InvestmentPlanView, preview: OrderPreviewResult) -> ProposedPrice:
        if plan.price_rule not in SUPPORTED_PRICE_RULES:
            raise InvestmentPlanServiceError("Unsupported plan price rule.")

        return ProposedPrice(
            value=preview.estimated_price,
            display=preview.estimated_price_display,
            rule_label=plan.price_rule_label,
        )


class InvestmentPlanService:
    def __init__(
        self,
        *,
        order_service: Optional[OrderService] = None,
        next_run_calculator: Optional[NextRunCalculator] = None,
        price_calculator: Optional[ProposedPriceCalculator] = None,
        policy_service: Optional[TradingPolicyService] = None,
        now_provider: Optional[Callable[[], datetime]] = None,
        session_factory: Optional[SessionFactory] = None,
    ):
        self.session_factory = session_factory or get_default_session_factory()
        self.order_service = order_service or OrderService()
        self.next_run_calculator = next_run_calculator or NextRunCalculator()
        self.price_calculator = price_calculator or ProposedPriceCalculator()
        self.policy_service = policy_service or TradingPolicyService(session_factory=self.session_factory)
        self.now_provider = now_provider or datetime.now

    def policy_status(self) -> TradingPolicyStatus:
        return self.policy_service.current_status()

    def list_plans(self, *, notice: Optional[str] = None, error: Optional[str] = None) -> InvestmentPlanListView:
        db = self.session_factory()
        try:
            plans = db.query(InvestmentPlan).order_by(InvestmentPlan.ticker.asc(), InvestmentPlan.id.asc()).all()
            views = [self._to_view(plan) for plan in plans]
            return InvestmentPlanListView(plans=views, empty=len(views) == 0, notice=notice, error=error)
        except Exception:
            return InvestmentPlanListView(
                plans=[],
                empty=True,
                notice=notice,
                error=error or "Investment plans could not be loaded right now.",
            )
        finally:
            db.close()

    def create_plan(self, definition: PlanDefinition) -> InvestmentPlanView:
        self.policy_service.require_plans_enabled()
        definition = self._normalize_definition(definition)
        db = self.session_factory()
        try:
            plan = InvestmentPlan(
                ticker=definition.ticker,
                lots=definition.lots,
                schedule=definition.schedule,
                time=definition.time,
                price_rule=definition.price_rule,
                operation=definition.operation,
                price_limit=definition.price_limit,
                pct_threshold=definition.pct_threshold,
                avg_period_days=definition.avg_period_days,
                order_type=definition.order_type,
                confirmation_required=definition.confirmation_required,
                confirmation_mode=definition.confirmation_mode,
            )
            db.add(plan)
            db.commit()
            db.refresh(plan)
            return self._to_view(plan)
        except Exception as exc:
            db.rollback()
            raise InvestmentPlanServiceError("Investment plan could not be created right now.") from exc
        finally:
            db.close()

    def update_plan(self, plan_id: int, definition: PlanDefinition) -> InvestmentPlanView:
        self.policy_service.require_plans_enabled()
        definition = self._normalize_definition(definition)
        db = self.session_factory()
        try:
            plan = self._get_plan(db, plan_id)
            plan.ticker = definition.ticker
            plan.lots = definition.lots
            plan.schedule = definition.schedule
            plan.time = definition.time
            plan.price_rule = definition.price_rule
            plan.operation = definition.operation
            plan.price_limit = definition.price_limit
            plan.pct_threshold = definition.pct_threshold
            plan.avg_period_days = definition.avg_period_days
            plan.order_type = definition.order_type
            plan.confirmation_required = definition.confirmation_required
            plan.confirmation_mode = definition.confirmation_mode
            plan.updated_at = datetime.utcnow()
            db.commit()
            db.refresh(plan)
            return self._to_view(plan)
        except InvestmentPlanServiceError:
            db.rollback()
            raise
        except Exception as exc:
            db.rollback()
            raise InvestmentPlanServiceError("Investment plan could not be updated right now.") from exc
        finally:
            db.close()

    def delete_plan(self, plan_id: int) -> InvestmentPlanView:
        self.policy_service.require_plans_enabled()
        db = self.session_factory()
        try:
            plan = self._get_plan(db, plan_id)
            view = self._to_view(plan)
            db.delete(plan)
            db.commit()
            return view
        except InvestmentPlanServiceError:
            db.rollback()
            raise
        except Exception as exc:
            db.rollback()
            raise InvestmentPlanServiceError("Investment plan could not be deleted right now.") from exc
        finally:
            db.close()

    def generate_order_proposal(self, plan_id: int) -> InvestmentPlanProposal:
        self.policy_service.require_plans_enabled()
        db = self.session_factory()
        try:
            plan_model = self._get_plan(db, plan_id)
            plan = self._to_view(plan_model)
        finally:
            db.close()

        return self.generate_order_proposal_for_plan(plan)

    def generate_order_proposal_for_plan(self, plan: InvestmentPlanView) -> InvestmentPlanProposal:
        preview = self.order_service.preview(self.build_order_preview_request(plan))
        proposed_price = self.price_calculator.calculate(plan=plan, preview=preview)

        return InvestmentPlanProposal(
            plan=plan,
            proposed_lots=plan.lots,
            proposed_limit_price=proposed_price.value,
            proposed_limit_price_display=proposed_price.display,
            preview=preview,
            generated_at=self.now_provider().strftime("%Y-%m-%d %H:%M"),
            execution_note="This proposal is not an order. Continue to preview, then confirm before anything is sent.",
        )

    def check_auto_execution(self, proposal: InvestmentPlanProposal) -> PolicyCheckResult:
        return self.policy_service.check_auto_execution(
            AutoExecutionRequest(
                plan_id=proposal.plan.id,
                ticker=proposal.plan.ticker,
                estimated_value=proposal.preview.estimated_value,
                confirmation_required=proposal.plan.confirmation_required,
            )
        )

    def build_order_preview_request(self, plan: InvestmentPlanView) -> OrderPreviewRequest:
        return OrderPreviewRequest(
            operation=plan.operation,
            ticker=plan.ticker,
            lots=plan.lots,
            order_type=plan.order_type,
        )

    def _get_plan_view(self, plan_id: int) -> InvestmentPlanView:
        """Returns InvestmentPlanView by id; raises InvestmentPlanServiceError if not found."""
        db = self.session_factory()
        try:
            plan = self._get_plan(db, plan_id)
            return self._to_view(plan)
        finally:
            db.close()

    def _get_plan(self, db, plan_id: int) -> InvestmentPlan:
        try:
            plan_id = int(plan_id)
        except (TypeError, ValueError) as exc:
            raise InvestmentPlanServiceError("Investment plan was not found.") from exc

        plan = db.query(InvestmentPlan).filter(InvestmentPlan.id == plan_id).first()
        if plan is None:
            raise InvestmentPlanServiceError("Investment plan was not found.")
        return plan

    def _to_view(self, plan: InvestmentPlan) -> InvestmentPlanView:
        created_at = plan.created_at or datetime.utcnow()
        operation = str(getattr(plan, "operation", None) or "buy").strip().lower()
        operation = operation if operation in SUPPORTED_OPERATIONS else "buy"
        price_rule = str(plan.price_rule or "current_market").strip().lower()
        price_limit = getattr(plan, "price_limit", None)
        pct_threshold = getattr(plan, "pct_threshold", None)
        avg_period_days = getattr(plan, "avg_period_days", None)
        confirmation_mode = str(getattr(plan, "confirmation_mode", None) or "telegram_confirm").strip().lower()
        confirmation_mode = confirmation_mode if confirmation_mode in SUPPORTED_CONFIRMATION_MODES else "telegram_confirm"
        next_run = self.next_run_calculator.calculate(
            schedule=plan.schedule,
            time_text=plan.time,
            created_at=created_at,
        )

        return InvestmentPlanView(
            id=plan.id,
            ticker=plan.ticker,
            lots=plan.lots,
            schedule=plan.schedule,
            schedule_label=SCHEDULE_LABELS.get(plan.schedule, plan.schedule),
            time=plan.time,
            price_rule=price_rule,
            price_rule_label=PRICE_RULE_LABELS.get(price_rule, price_rule),
            order_type=plan.order_type,
            order_type_label=ORDER_TYPE_LABELS.get(plan.order_type, plan.order_type),
            confirmation_required=bool(plan.confirmation_required),
            confirmation_label="Required" if plan.confirmation_required else "Optional for future schedulers",
            next_run_at=next_run.isoformat(timespec="minutes"),
            next_run_display=next_run.strftime("%Y-%m-%d %H:%M"),
            operation=operation,
            price_limit=price_limit,
            pct_threshold=pct_threshold,
            avg_period_days=avg_period_days,
            confirmation_mode=confirmation_mode,
            price_condition_display=self._price_condition_display(
                price_rule=price_rule,
                operation=operation,
                price_limit=price_limit,
                pct_threshold=pct_threshold,
                avg_period_days=avg_period_days,
            ),
        )

    def _normalize_definition(self, definition: PlanDefinition) -> PlanDefinition:
        ticker = str(definition.ticker or "").strip().upper()
        schedule = str(definition.schedule or "").strip().lower()
        price_rule = str(definition.price_rule or "current_market").strip().lower()
        order_type = str(definition.order_type or "limit").strip().lower()
        operation = str(definition.operation or "buy").strip().lower()
        confirmation_mode = str(definition.confirmation_mode or "telegram_confirm").strip().lower()
        time_text = str(definition.time or "").strip()

        if not ticker or not ticker.replace("-", "").isalnum():
            raise InvestmentPlanServiceError("Enter a ticker using letters and numbers.")
        try:
            lots = int(definition.lots)
        except (TypeError, ValueError) as exc:
            raise InvestmentPlanServiceError("Lots must be a whole number.") from exc

        if lots < 1:
            raise InvestmentPlanServiceError("Lots must be at least 1.")
        if schedule not in SUPPORTED_SCHEDULES:
            raise InvestmentPlanServiceError("Choose a supported schedule.")
        if operation not in SUPPORTED_OPERATIONS:
            raise InvestmentPlanServiceError("Choose buy or sell for the plan operation.")
        if price_rule not in SUPPORTED_PRICE_RULES:
            raise InvestmentPlanServiceError("Choose a supported price rule.")
        if order_type not in SUPPORTED_ORDER_TYPES:
            raise InvestmentPlanServiceError("Only limit orders are available in this version.")
        if confirmation_mode not in SUPPORTED_CONFIRMATION_MODES:
            raise InvestmentPlanServiceError("Choose a supported confirmation mode.")

        price_limit = self._optional_float(definition.price_limit, "Price limit")
        pct_threshold = self._optional_float(definition.pct_threshold, "Percent threshold")
        avg_period_days = self._optional_int(definition.avg_period_days, "Average period")

        if price_rule == "max_price":
            if price_limit is None or price_limit <= 0:
                raise InvestmentPlanServiceError("Price limit must be greater than 0 for max_price.")
            pct_threshold = None
            avg_period_days = None
        elif price_rule == "pct_from_avg":
            if pct_threshold is None or pct_threshold <= 0:
                raise InvestmentPlanServiceError("Percent threshold must be greater than 0 for pct_from_avg.")
            if avg_period_days is None or avg_period_days < 5:
                raise InvestmentPlanServiceError("Average period must be at least 5 days for pct_from_avg.")
            price_limit = None
        else:
            price_limit = None
            pct_threshold = None
            avg_period_days = None

        hour, minute = self.next_run_calculator._parse_time(time_text)

        return PlanDefinition(
            ticker=ticker,
            lots=lots,
            schedule=schedule,
            time=f"{hour:02d}:{minute:02d}",
            price_rule=price_rule,
            order_type=order_type,
            confirmation_required=bool(definition.confirmation_required),
            operation=operation,
            price_limit=price_limit,
            pct_threshold=pct_threshold,
            avg_period_days=avg_period_days,
            confirmation_mode=confirmation_mode,
        )

    def _optional_float(self, value, field_label: str) -> Optional[float]:
        if value is None or value == "":
            return None
        try:
            return float(value)
        except (TypeError, ValueError) as exc:
            raise InvestmentPlanServiceError(f"{field_label} must be a number.") from exc

    def _optional_int(self, value, field_label: str) -> Optional[int]:
        if value is None or value == "":
            return None
        try:
            return int(value)
        except (TypeError, ValueError) as exc:
            raise InvestmentPlanServiceError(f"{field_label} must be a whole number.") from exc

    def _price_condition_display(
        self,
        *,
        price_rule: str,
        operation: str,
        price_limit: Optional[float],
        pct_threshold: Optional[float],
        avg_period_days: Optional[int],
    ) -> str:
        if price_rule == "any":
            return "Любая цена"
        if price_rule == "current_market":
            return "Текущая рыночная"
        if price_rule == "max_price":
            if price_limit is None:
                return "Лимит цены не задан"
            sign = "≤" if operation == "buy" else "≥"
            return f"{sign} {price_limit:.2f} ₽"
        if price_rule == "pct_from_avg":
            if pct_threshold is None or avg_period_days is None:
                return "Условие от средней не задано"
            return f"Не выше {pct_threshold}% от {avg_period_days}-дн. средней"
        return price_rule
