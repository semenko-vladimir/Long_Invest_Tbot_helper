import logging
import secrets
import threading
import time
from dataclasses import dataclass
from typing import Callable, Optional, Protocol

from app.services.orders import (
    OrderConfirmCommand,
    OrderExecutionBlocked,
    OrderPreviewRequest,
    OrderPreviewResult,
    OrderServiceError,
)
from app.services.strategy_models import (
    STRATEGY_TYPE_CONFIRMATION_REQUIRED,
    STRATEGY_STATUS_BLOCKED,
    STRATEGY_STATUS_EXECUTED,
    STRATEGY_STATUS_EXPIRED,
    STRATEGY_STATUS_FAILED,
    STRATEGY_STATUS_SKIPPED,
    StrategyProposal,
)


STRATEGY_CONFIRM_TTL_SECONDS = 30 * 60
logger = logging.getLogger(__name__)
_MISSING_HISTORY_ID = object()


class StrategyOrderService(Protocol):
    def preview(self, request: OrderPreviewRequest) -> OrderPreviewResult:
        ...

    def execute(self, command: OrderConfirmCommand):
        ...


@dataclass(frozen=True)
class StrategyRecheckResult:
    allowed: bool
    reason: str = ""

    @classmethod
    def from_value(cls, value: "StrategyRecheckResult | bool") -> "StrategyRecheckResult":
        if isinstance(value, StrategyRecheckResult):
            return value
        return cls(allowed=bool(value), reason="" if value else "Strategy recheck failed.")


StrategyRecheckFn = Callable[[StrategyProposal, OrderPreviewResult], StrategyRecheckResult | bool]
StrategyOutcomeRecorder = Callable[["StrategyConfirmationResult"], None]


@dataclass(frozen=True)
class StrategyConfirmationResult:
    status: str
    message: str
    strategy_id: str = ""
    strategy_name: str = ""
    strategy_type: str = STRATEGY_TYPE_CONFIRMATION_REQUIRED
    ticker: str = ""
    operation: str = ""
    lots: int = 0
    order_id: Optional[str] = None
    estimated_value_rub: Optional[float] = None
    history_id: Optional[int] = None


@dataclass
class _PendingStrategyConfirmation:
    chat_id: int
    strategy_id: str
    strategy_name: str
    proposal: StrategyProposal
    expires_at: float
    strategy_type: str = STRATEGY_TYPE_CONFIRMATION_REQUIRED
    recheck_fn: Optional[StrategyRecheckFn] = None
    history_id: Optional[int] = None
    outcome_recorder: Optional[StrategyOutcomeRecorder] = None
    consumed: bool = False


class StrategyConfirmationService:
    def __init__(
        self,
        *,
        ttl_seconds: int = STRATEGY_CONFIRM_TTL_SECONDS,
        outcome_recorder: Optional[StrategyOutcomeRecorder] = None,
    ) -> None:
        self.ttl_seconds = ttl_seconds
        self.outcome_recorder = outcome_recorder
        self._pending: dict[str, _PendingStrategyConfirmation] = {}
        self._lock = threading.Lock()

    def issue_token(
        self,
        *,
        chat_id: int,
        strategy_id: str,
        strategy_name: str,
        proposal: StrategyProposal,
        recheck_fn: Optional[StrategyRecheckFn] = None,
        history_id: Optional[int] = None,
        outcome_recorder: Optional[StrategyOutcomeRecorder] = None,
    ) -> str:
        ttl_seconds = proposal.expires_in_seconds or self.ttl_seconds
        with self._lock:
            self._record_expired_locked(time.time(), "Strategy confirmation expired.")
            self._cleanup_consumed_locked()
            token = secrets.token_urlsafe(16)
            self._pending[token] = _PendingStrategyConfirmation(
                chat_id=int(chat_id),
                strategy_id=str(strategy_id),
                strategy_name=str(strategy_name),
                proposal=proposal,
                expires_at=time.time() + ttl_seconds,
                strategy_type=STRATEGY_TYPE_CONFIRMATION_REQUIRED,
                recheck_fn=recheck_fn,
                history_id=history_id,
                outcome_recorder=outcome_recorder,
            )
            return token

    def confirm(
        self,
        *,
        chat_id: int,
        token: str,
        order_service: StrategyOrderService,
        ticker_confirmation: Optional[str] = None,
    ) -> StrategyConfirmationResult:
        pending = self._consume_for_chat(chat_id=chat_id, token=token)
        if isinstance(pending, StrategyConfirmationResult):
            return pending

        proposal = pending.proposal
        try:
            preview = order_service.preview(
                OrderPreviewRequest(
                    operation=proposal.operation,
                    ticker=proposal.ticker,
                    lots=proposal.lots,
                )
            )
        except Exception as exc:
            return self._terminal_result(
                pending,
                STRATEGY_STATUS_FAILED,
                f"Fresh preview failed: {exc}",
            )

        if pending.recheck_fn is not None:
            try:
                recheck = StrategyRecheckResult.from_value(pending.recheck_fn(proposal, preview))
            except Exception as exc:
                return self._terminal_result(
                    pending,
                    STRATEGY_STATUS_FAILED,
                    f"Strategy recheck failed: {exc}",
                    estimated_value_rub=preview.estimated_value,
                )
            if not recheck.allowed:
                message = recheck.reason or "Strategy condition is no longer valid."
                return self._terminal_result(
                    pending,
                    STRATEGY_STATUS_BLOCKED,
                    message,
                    estimated_value_rub=preview.estimated_value,
                )

        try:
            execution = order_service.execute(
                OrderConfirmCommand(
                    operation=proposal.operation,
                    ticker=proposal.ticker,
                    lots=proposal.lots,
                    confirm_token=preview.confirm_token,
                    ticker_confirmation=ticker_confirmation,
                )
            )
        except OrderExecutionBlocked as exc:
            return self._terminal_result(
                pending,
                STRATEGY_STATUS_BLOCKED,
                str(exc),
                estimated_value_rub=preview.estimated_value,
            )
        except OrderServiceError as exc:
            return self._terminal_result(
                pending,
                STRATEGY_STATUS_FAILED,
                str(exc),
                estimated_value_rub=preview.estimated_value,
            )
        except Exception as exc:
            return self._terminal_result(
                pending,
                STRATEGY_STATUS_FAILED,
                f"Order execution failed: {exc}",
                estimated_value_rub=preview.estimated_value,
            )

        return self._terminal_result(
            pending,
            STRATEGY_STATUS_EXECUTED,
            getattr(execution, "message", "Order submitted successfully."),
            order_id=getattr(execution, "order_id", None),
            estimated_value_rub=preview.estimated_value,
        )

    def skip(self, *, chat_id: int, token: str, reason: str = "user_declined") -> StrategyConfirmationResult:
        pending = self._consume_for_chat(chat_id=chat_id, token=token)
        if isinstance(pending, StrategyConfirmationResult):
            return pending
        return self._terminal_result(pending, STRATEGY_STATUS_SKIPPED, reason)

    def expire_old(self) -> int:
        with self._lock:
            expired_count = self._record_expired_locked(time.time(), "Strategy confirmation expired.")
            self._cleanup_consumed_locked()
            return expired_count

    def _consume_for_chat(
        self,
        *,
        chat_id: int,
        token: str,
    ) -> _PendingStrategyConfirmation | StrategyConfirmationResult:
        with self._lock:
            self._cleanup_consumed_locked()
            pending = self._pending.get(str(token or ""))
            if pending is None or pending.consumed:
                return StrategyConfirmationResult(
                    status=STRATEGY_STATUS_EXPIRED,
                    message="Strategy confirmation expired or was already handled.",
                )
            if pending.expires_at < time.time():
                pending.consumed = True
                result = self._result(
                    pending,
                    STRATEGY_STATUS_EXPIRED,
                    "Strategy confirmation expired or was already handled.",
                )
                self._record_result(result, pending)
                self._cleanup_consumed_locked()
                return result
            if pending.chat_id != int(chat_id):
                result = self._result(
                    pending,
                    STRATEGY_STATUS_BLOCKED,
                    "Strategy confirmation is not valid for this chat.",
                    history_id=None,
                )
                self._record_result(result, pending)
                return result

            pending.consumed = True
            return pending

    def _cleanup_consumed_locked(self) -> None:
        self._pending = {
            token: pending
            for token, pending in self._pending.items()
            if not pending.consumed
        }

    def _record_expired_locked(self, now: float, message: str) -> int:
        expired_count = 0
        for pending in self._pending.values():
            if not pending.consumed and pending.expires_at < now:
                pending.consumed = True
                self._record_result(
                    self._result(
                        pending,
                        STRATEGY_STATUS_EXPIRED,
                        message,
                    ),
                    pending,
                )
                expired_count += 1
        return expired_count

    def _terminal_result(
        self,
        pending: _PendingStrategyConfirmation,
        status: str,
        message: str,
        *,
        order_id: Optional[str] = None,
        estimated_value_rub: Optional[float] = None,
    ) -> StrategyConfirmationResult:
        result = self._result(
            pending,
            status,
            message,
            order_id=order_id,
            estimated_value_rub=estimated_value_rub,
        )
        self._record_result(result, pending)
        return result

    def _result(
        self,
        pending: _PendingStrategyConfirmation,
        status: str,
        message: str,
        *,
        order_id: Optional[str] = None,
        estimated_value_rub: Optional[float] = None,
        history_id: Optional[int] | object = _MISSING_HISTORY_ID,
    ) -> StrategyConfirmationResult:
        proposal = pending.proposal
        return StrategyConfirmationResult(
            status=status,
            message=message,
            strategy_id=pending.strategy_id,
            strategy_name=pending.strategy_name,
            strategy_type=pending.strategy_type,
            ticker=proposal.ticker,
            operation=proposal.operation,
            lots=proposal.lots,
            order_id=order_id,
            estimated_value_rub=estimated_value_rub,
            history_id=pending.history_id if history_id is _MISSING_HISTORY_ID else history_id,
        )

    def _record_result(
        self,
        result: StrategyConfirmationResult,
        pending: _PendingStrategyConfirmation,
    ) -> None:
        recorder = pending.outcome_recorder or self.outcome_recorder
        if recorder is not None:
            try:
                recorder(result)
            except Exception as exc:
                logger.warning("Strategy proposal confirmation history write failed: %s", exc)
