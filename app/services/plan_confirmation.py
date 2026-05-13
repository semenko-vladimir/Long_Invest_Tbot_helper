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
    on_confirm: Callable
    on_skip: Callable
    consumed: bool = False


class PlanConfirmationService:
    """
    Manages pending auto-plan confirmations via Telegram.
    Does not make HTTP requests — stores state and invokes callbacks only.

    NOTE: on_confirm and on_skip are called while holding self._lock.
    Callbacks must not re-enter PlanConfirmationService or perform slow I/O,
    or they will deadlock / serialize all confirmations behind them.
    """

    def __init__(self) -> None:
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
        """Creates a confirmation token and returns it for use as callback_data."""
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
        """Called on ✅ press. Returns True if the token was valid and not yet consumed."""
        with self._lock:
            pending = self._pending.get(token)
            if pending is None or pending.consumed or pending.expires_at < time.time():
                return False
            pending.consumed = True
            pending.on_confirm()
            return True

    def skip(self, token: str, reason: str = "user_declined") -> bool:
        """Called on ❌ press or timeout. Returns True if the token was valid and not yet consumed."""
        with self._lock:
            pending = self._pending.get(token)
            if pending is None or pending.consumed:
                return False
            pending.consumed = True
            pending.on_skip(reason)
            return True

    def expire_old(self) -> None:
        """Call periodically from a scheduler to auto-expire timed-out confirmations."""
        with self._lock:
            now = time.time()
            for token, pending in list(self._pending.items()):
                if not pending.consumed and pending.expires_at < now:
                    pending.consumed = True
                    pending.on_skip("timeout")
            self._cleanup()

    def _cleanup(self) -> None:
        self._pending = {
            t: p
            for t, p in self._pending.items()
            if not p.consumed and p.expires_at >= time.time()
        }
