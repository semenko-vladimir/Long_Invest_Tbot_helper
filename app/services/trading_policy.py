from dataclasses import dataclass
from datetime import datetime, time, timezone
from typing import Optional

from app.backend.models.trading import InvestmentPlanExecution
from app.client.config import (
    allow_auto_investing,
    get_max_daily_invest_rub,
    get_max_order_rub,
    investment_plans_enabled,
)
from app.client.log.logger import setup_logger
from app.services.mode import ModeContext, ModeService
from app.services.portfolio import money
from app.services.user_database import SessionFactory, get_default_session_factory


AUTO_EXECUTION_ALLOWED_MODES = {"sandbox"}

logger = setup_logger(__name__)


class TradingPolicyError(ValueError):
    pass


@dataclass(frozen=True)
class TradingPolicyStatus:
    plans_enabled: bool
    auto_investing_allowed: bool
    max_order_rub: float
    max_order_rub_display: str
    max_daily_invest_rub: float
    max_daily_invest_rub_display: str
    daily_used_rub: float
    daily_used_rub_display: str
    daily_remaining_rub: float
    daily_remaining_rub_display: str
    mode: ModeContext
    automation_mode_allowed: bool
    summary: str
    blocked_reasons: list[str]


@dataclass(frozen=True)
class PolicyCheckResult:
    allowed: bool
    reasons: list[str]

    @property
    def message(self) -> str:
        return " ".join(self.reasons)


@dataclass(frozen=True)
class AutoExecutionRequest:
    plan_id: int
    ticker: str
    estimated_value: float
    confirmation_required: bool


class InvestmentPlanExecutionLedger:
    def __init__(self, *, session_factory: Optional[SessionFactory] = None):
        self.session_factory = session_factory or get_default_session_factory()

    def daily_total(self, *, now: Optional[datetime] = None) -> float:
        if now is None:
            now = datetime.now(timezone.utc).replace(tzinfo=None)
        elif now.tzinfo is not None and now.utcoffset() is not None:
            now = now.astimezone(timezone.utc).replace(tzinfo=None)

        start = datetime.combine(now.date(), time.min)
        end = datetime.combine(now.date(), time.max)

        db = self.session_factory()
        try:
            rows = (
                db.query(InvestmentPlanExecution)
                .filter(InvestmentPlanExecution.status == "executed")
                .filter(InvestmentPlanExecution.created_at >= start)
                .filter(InvestmentPlanExecution.created_at <= end)
                .all()
            )
            return sum(float(row.amount_rub or 0.0) for row in rows)
        finally:
            db.close()

    def record_blocked(self, *, request: AutoExecutionRequest, reason: str) -> None:
        db = self.session_factory()
        try:
            db.add(
                InvestmentPlanExecution(
                    plan_id=request.plan_id,
                    ticker=request.ticker,
                    amount_rub=request.estimated_value,
                    status="blocked",
                    execution_mode="auto",
                )
            )
            db.commit()
        except Exception:
            db.rollback()
        finally:
            db.close()

    def record_executed(self, *, request: AutoExecutionRequest, order_id: str) -> None:
        db = self.session_factory()
        try:
            db.add(
                InvestmentPlanExecution(
                    plan_id=request.plan_id,
                    order_id=order_id,
                    ticker=request.ticker,
                    amount_rub=request.estimated_value,
                    status="executed",
                    execution_mode="auto",
                )
            )
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()


class TradingPolicyService:
    def __init__(
        self,
        *,
        mode_service: Optional[ModeService] = None,
        ledger: Optional[InvestmentPlanExecutionLedger] = None,
        session_factory: Optional[SessionFactory] = None,
    ):
        self.mode_service = mode_service or ModeService()
        self.ledger = ledger or InvestmentPlanExecutionLedger(session_factory=session_factory)

    def current_status(self) -> TradingPolicyStatus:
        mode = self.mode_service.current()
        plans_enabled = investment_plans_enabled()
        auto_allowed = allow_auto_investing()
        config_errors = []
        max_order = self._read_limit(get_max_order_rub, "MAX_ORDER_RUB", config_errors)
        max_daily = self._read_limit(get_max_daily_invest_rub, "MAX_DAILY_INVEST_RUB", config_errors)
        daily_used = self.ledger.daily_total()
        daily_remaining = max(max_daily - daily_used, 0.0) if max_daily else 0.0
        automation_mode_allowed = mode.mode in AUTO_EXECUTION_ALLOWED_MODES
        blocked_reasons = self._status_blocked_reasons(
            plans_enabled=plans_enabled,
            auto_allowed=auto_allowed,
            max_order=max_order,
            max_daily=max_daily,
            mode=mode,
            automation_mode_allowed=automation_mode_allowed,
        )
        blocked_reasons.extend(config_errors)

        return TradingPolicyStatus(
            plans_enabled=plans_enabled,
            auto_investing_allowed=auto_allowed,
            max_order_rub=max_order,
            max_order_rub_display=self._limit_display(max_order),
            max_daily_invest_rub=max_daily,
            max_daily_invest_rub_display=self._limit_display(max_daily),
            daily_used_rub=daily_used,
            daily_used_rub_display=money(daily_used),
            daily_remaining_rub=daily_remaining,
            daily_remaining_rub_display=self._limit_display(daily_remaining) if max_daily else "Disabled",
            mode=mode,
            automation_mode_allowed=automation_mode_allowed,
            summary=self._summary(plans_enabled, auto_allowed, automation_mode_allowed),
            blocked_reasons=blocked_reasons,
        )

    def require_plans_enabled(self) -> None:
        if not investment_plans_enabled():
            self._log_block("plans_disabled", "Investment plans are disabled by ENABLE_INVESTMENT_PLANS.")
            raise TradingPolicyError("Investment plans are disabled. Set ENABLE_INVESTMENT_PLANS=true to use them.")

    def check_auto_execution(self, request: AutoExecutionRequest) -> PolicyCheckResult:
        status = self.current_status()
        reasons = list(status.blocked_reasons)

        if request.confirmation_required:
            reasons.append("This plan still requires manual confirmation.")
        if status.max_order_rub <= 0:
            reasons.append("MAX_ORDER_RUB must be set above 0 before auto-investing can run.")
        elif request.estimated_value > status.max_order_rub:
            reasons.append(
                f"Estimated order value {money(request.estimated_value)} exceeds MAX_ORDER_RUB {status.max_order_rub_display}."
            )
        if status.max_daily_invest_rub <= 0:
            reasons.append("MAX_DAILY_INVEST_RUB must be set above 0 before auto-investing can run.")
        elif status.daily_used_rub + request.estimated_value > status.max_daily_invest_rub:
            reasons.append(
                "Estimated order would exceed MAX_DAILY_INVEST_RUB "
                f"{status.max_daily_invest_rub_display}; already used {status.daily_used_rub_display} today."
            )

        result = PolicyCheckResult(allowed=len(reasons) == 0, reasons=reasons)
        if not result.allowed:
            reason = result.message
            self._log_block("auto_execution_blocked", reason, request=request)
            self.ledger.record_blocked(request=request, reason=reason)
        return result

    def _status_blocked_reasons(
        self,
        *,
        plans_enabled: bool,
        auto_allowed: bool,
        max_order: float,
        max_daily: float,
        mode: ModeContext,
        automation_mode_allowed: bool,
    ) -> list[str]:
        reasons = []
        if not plans_enabled:
            reasons.append("Investment plans are disabled.")
        if plans_enabled and not auto_allowed:
            reasons.append("Auto-investing is disabled; proposals require manual confirmation.")
        if auto_allowed and not automation_mode_allowed:
            reasons.append("Auto-investing is currently allowed only in sandbox mode.")
        if auto_allowed and not mode.trading_available:
            reasons.append("Trading is blocked by the current application mode.")
        if auto_allowed and max_order <= 0:
            reasons.append("MAX_ORDER_RUB is not configured.")
        if auto_allowed and max_daily <= 0:
            reasons.append("MAX_DAILY_INVEST_RUB is not configured.")
        return reasons

    def _summary(self, plans_enabled: bool, auto_allowed: bool, automation_mode_allowed: bool) -> str:
        if not plans_enabled:
            return "Investment plans are unavailable."
        if not auto_allowed:
            return "Plans are enabled in proposal/manual confirmation mode."
        if not automation_mode_allowed:
            return "Auto-investing is configured but blocked in this mode."
        return "Auto-investing is constrained by mode checks and RUB limits."

    def _limit_display(self, value: float) -> str:
        if value <= 0:
            return "Disabled"
        return money(value)

    def _read_limit(self, getter, name: str, errors: list[str]) -> float:
        try:
            return getter()
        except Exception as exc:
            message = f"{name} is invalid and is treated as disabled: {str(exc)}"
            errors.append(message)
            self._log_block("invalid_limit", message)
            return 0.0

    def _log_block(self, code: str, message: str, *, request: Optional[AutoExecutionRequest] = None) -> None:
        if request is None:
            logger.warning("Investment plan policy block: code=%s reason=%s", code, message)
            return
        logger.warning(
            "Investment plan policy block: code=%s plan_id=%s ticker=%s estimated_value=%s reason=%s",
            code,
            request.plan_id,
            request.ticker,
            request.estimated_value,
            message,
        )
