import logging
import math
from dataclasses import dataclass, field
from typing import Callable, Optional

from app.client.config import get_active_invest_token
from app.integrations.tinvest import TInvestBroker
from app.services.orders import OrderConfirmCommand, OrderPreviewRequest, OrderService
from app.services.plan_confirmation import PlanConfirmationService
from app.services.portfolio import PortfolioPosition, PortfolioService, percent


logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class AntiGreedyCandidate:
    ticker: str
    return_percent: float
    average_price: float
    current_price: float
    quantity: float
    lot_size: int
    lots: int
    threshold_pct: float
    reason: str


@dataclass(frozen=True)
class AntiGreedyRunResult:
    status: str  # "sent_for_confirmation" | "skipped" | "error"
    candidates: int = 0
    sent_for_confirmation: int = 0
    errors: list[str] = field(default_factory=list)


class AntiGreedyPolicyService:
    """
    Finds positions whose gross return exceeds the anti-greedy threshold.

    This service does not place broker orders. It only prepares sell candidates;
    OrderService and Telegram confirmation remain responsible for execution.
    """

    def __init__(
        self,
        *,
        portfolio_service: Optional[PortfolioService] = None,
        broker: Optional[TInvestBroker] = None,
        token_provider: Optional[Callable[[], Optional[str]]] = None,
        threshold_pct: float = 20.0,
    ) -> None:
        self.portfolio_service = portfolio_service or PortfolioService()
        self.broker = broker or TInvestBroker()
        self.token_provider = token_provider or get_active_invest_token
        self.threshold_pct = threshold_pct

    def find_candidates(self) -> list[AntiGreedyCandidate]:
        token = self.token_provider()
        if not token:
            logger.warning("Anti-greedy policy skipped: broker token is not configured")
            return []

        view = self.portfolio_service.get_portfolio_view()
        if view.error:
            logger.warning("Anti-greedy policy skipped: %s", view.error)
            return []

        candidates = []
        for position in view.positions:
            candidate = self._candidate_from_position(token, position)
            if candidate is not None:
                candidates.append(candidate)
        return candidates

    def candidate_for_ticker(self, ticker: str) -> Optional[AntiGreedyCandidate]:
        normalized = str(ticker or "").strip().upper()
        for candidate in self.find_candidates():
            if candidate.ticker.upper() == normalized:
                return candidate
        return None

    def _candidate_from_position(
        self, token: str, position: PortfolioPosition
    ) -> Optional[AntiGreedyCandidate]:
        if position.return_percent is None or position.return_percent <= self.threshold_pct:
            return None

        ticker = str(position.ticker or "").strip().upper()
        if not ticker or ticker == "-":
            return None

        try:
            instrument = self.broker.resolve_unique_instrument(token, ticker)
            lot_size = int(self.broker.get_lot_size(token, instrument.figi))
        except Exception as exc:
            logger.warning("Anti-greedy policy skipped %s: lot size is unavailable: %s", ticker, exc)
            return None

        if lot_size <= 0:
            logger.warning("Anti-greedy policy skipped %s: invalid lot size %s", ticker, lot_size)
            return None

        lots = math.floor(float(position.quantity) / lot_size)
        if lots < 1:
            logger.info(
                "Anti-greedy policy skipped %s: quantity %s is below one lot of %s",
                ticker,
                position.quantity,
                lot_size,
            )
            return None

        return AntiGreedyCandidate(
            ticker=ticker,
            return_percent=position.return_percent,
            average_price=position.average_price,
            current_price=position.current_price,
            quantity=position.quantity,
            lot_size=lot_size,
            lots=lots,
            threshold_pct=self.threshold_pct,
            reason=(
                f"Профит {percent(position.return_percent)} выше "
                f"anti-greedy порога {self.threshold_pct:.2f}%."
            ),
        )


class AntiGreedyRunner:
    """
    Sends Telegram confirmation requests for anti-greedy sell candidates.

    The runner always rechecks the position and creates a fresh OrderService
    preview immediately before confirmed execution.
    """

    def __init__(
        self,
        *,
        policy_service: AntiGreedyPolicyService,
        confirmation_service: PlanConfirmationService,
        order_service: OrderService,
        telegram_chat_id: int,
        notify_fn: Callable,
        send_confirmation_fn: Callable,
    ) -> None:
        self.policy_service = policy_service
        self.confirmation_service = confirmation_service
        self.order_service = order_service
        self.chat_id = telegram_chat_id
        self.notify = notify_fn
        self.send_confirmation = send_confirmation_fn

    def run(self) -> AntiGreedyRunResult:
        try:
            candidates = self.policy_service.find_candidates()
        except Exception as exc:
            logger.exception("Anti-greedy policy failed")
            return AntiGreedyRunResult(status="error", errors=[str(exc)])

        sent = 0
        errors = []
        for candidate in candidates:
            try:
                preview = self.order_service.preview(
                    OrderPreviewRequest(operation="sell", ticker=candidate.ticker, lots=candidate.lots)
                )
            except Exception as exc:
                message = f"{candidate.ticker}: {exc}"
                errors.append(message)
                self.notify(self.chat_id, f"❌ *Anti-greedy не смог создать sell preview* {message}")
                continue

            token = self.confirmation_service.issue_token(
                plan_id=0,
                ticker=candidate.ticker,
                operation="sell",
                lots=candidate.lots,
                current_price=preview.estimated_price,
                price_condition_reason=candidate.reason,
                on_confirm=lambda candidate=candidate: self._execute(candidate),
                on_skip=lambda reason, candidate=candidate: self._notify_skip(candidate, reason),
                chat_id=self.chat_id,
            )

            self.send_confirmation(
                self.chat_id,
                token=token,
                ticker=candidate.ticker,
                operation="sell",
                lots=candidate.lots,
                current_price=preview.estimated_price,
                price_reason=candidate.reason,
            )
            sent += 1

        if sent:
            return AntiGreedyRunResult(
                status="sent_for_confirmation",
                candidates=len(candidates),
                sent_for_confirmation=sent,
                errors=errors,
            )
        if errors:
            return AntiGreedyRunResult(status="error", candidates=len(candidates), errors=errors)
        return AntiGreedyRunResult(status="skipped", candidates=0)

    def _execute(self, candidate: AntiGreedyCandidate) -> None:
        fresh_candidate = self.policy_service.candidate_for_ticker(candidate.ticker)
        if fresh_candidate is None:
            self.notify(
                self.chat_id,
                f"⏭ *Anti-greedy продажа пропущена*: {candidate.ticker}\n"
                "Позиция больше не выше порога прибыли.",
            )
            return

        try:
            fresh = self.order_service.preview(
                OrderPreviewRequest(
                    operation="sell",
                    ticker=fresh_candidate.ticker,
                    lots=fresh_candidate.lots,
                )
            )
        except Exception as exc:
            self.notify(self.chat_id, f"❌ *Ошибка повторного sell preview* {candidate.ticker}: {exc}")
            return

        try:
            result = self.order_service.execute(
                OrderConfirmCommand(
                    operation="sell",
                    ticker=fresh_candidate.ticker,
                    lots=fresh_candidate.lots,
                    confirm_token=fresh.confirm_token,
                )
            )
            self.notify(
                self.chat_id,
                f"✅ *Anti-greedy продажа отправлена*: {fresh_candidate.ticker}\n"
                f"Ордер: {result.order_id}\nСумма: ~{fresh.estimated_value:.2f}₽",
            )
        except Exception as exc:
            self.notify(self.chat_id, f"❌ *Ошибка anti-greedy продажи* {candidate.ticker}: {exc}")

    def _notify_skip(self, candidate: AntiGreedyCandidate, reason: str) -> None:
        self.notify(
            self.chat_id,
            f"⏭ *Anti-greedy продажа пропущена*: {candidate.ticker}\nПричина: {reason}",
        )
