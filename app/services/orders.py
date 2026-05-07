import secrets
import time
from dataclasses import dataclass
from threading import Lock
from typing import Callable, Optional

from app.client.config import get_active_invest_token
from app.integrations.tinvest import TInvestBroker
from app.services.mode import ModeContext, ModeService
from app.services.portfolio import money


CONFIRM_TOKEN_TTL_SECONDS = 10 * 60


class OrderServiceError(ValueError):
    pass


class OrderValidationError(OrderServiceError):
    pass


class OrderExecutionBlocked(OrderServiceError):
    pass


@dataclass(frozen=True)
class OrderPreviewRequest:
    operation: str
    ticker: str
    lots: int
    order_type: str = "limit"


@dataclass(frozen=True)
class OrderPreviewResult:
    operation: str
    operation_label: str
    ticker: str
    lots: int
    instrument_name: str
    figi: str
    estimated_price: float
    estimated_value: float
    estimated_price_display: str
    estimated_value_display: str
    order_type: str
    mode: ModeContext
    trading_enabled: bool
    can_execute: bool
    requires_ticker_confirmation: bool
    warnings: list[str]
    confirm_token: str


@dataclass(frozen=True)
class OrderConfirmCommand:
    operation: str
    ticker: str
    lots: int
    confirm_token: str
    ticker_confirmation: Optional[str] = None
    order_type: str = "limit"


@dataclass(frozen=True)
class OrderExecutionResult:
    operation: str
    operation_label: str
    ticker: str
    lots: int
    order_id: str
    executed_price_display: str
    total_value_display: str
    mode: ModeContext
    message: str


@dataclass
class _PreviewToken:
    operation: str
    ticker: str
    lots: int
    expires_at: float
    consumed: bool = False


class OrderService:
    def __init__(
        self,
        broker: Optional[TInvestBroker] = None,
        mode_service: Optional[ModeService] = None,
        token_provider: Optional[Callable[[], Optional[str]]] = None,
    ):
        self.broker = broker or TInvestBroker()
        self.mode_service = mode_service or ModeService()
        self.token_provider = token_provider or get_active_invest_token
        self._preview_tokens: dict[str, _PreviewToken] = {}
        self._preview_token_lock = Lock()

    def preview(self, request: OrderPreviewRequest) -> OrderPreviewResult:
        request = self._normalize_preview_request(request)
        mode = self.mode_service.current()
        token = self.token_provider()
        if not token:
            raise OrderValidationError("No broker token is configured for the current mode.")

        try:
            instrument = self.broker.resolve_unique_instrument(token, request.ticker)
            estimated_price = self.broker.get_price(token, instrument.figi, request.operation)
            lot_size = self.broker.get_lot_size(token, instrument.figi)
            if lot_size <= 0:
                raise OrderValidationError("Lot size is unavailable for this instrument.")

            if request.operation == "buy":
                if not self.broker.has_enough_cash(token, instrument.figi, request.lots, mode.is_sandbox):
                    raise OrderValidationError("There is not enough cash for this buy order.")
            else:
                available_quantity = self.broker.get_available_quantity(token, instrument.figi, mode.is_sandbox)
                requested_quantity = request.lots * lot_size
                if available_quantity <= 0:
                    raise OrderValidationError(f"{instrument.ticker} is not available in the active portfolio.")
                if available_quantity < requested_quantity:
                    raise OrderValidationError(
                        f"Not enough available quantity to sell: available {available_quantity:g}, needed {requested_quantity:g}."
                    )
        except OrderValidationError:
            raise
        except ValueError as exc:
            raise OrderValidationError(str(exc)) from exc
        except Exception as exc:
            raise OrderValidationError("Broker data is unavailable right now. Try again later.") from exc

        warnings = []
        if mode.mode == "prod" and not mode.trading_available:
            warnings.append("Production trading is disabled. Preview is allowed, but execution is blocked.")
        elif mode.mode == "prod":
            warnings.append("Production trading is enabled. Type the ticker exactly before confirming a real order.")

        estimated_value = estimated_price * lot_size * request.lots
        confirm_token = self._issue_preview_token(request)

        return OrderPreviewResult(
            operation=request.operation,
            operation_label=request.operation.title(),
            ticker=instrument.ticker,
            lots=request.lots,
            instrument_name=instrument.name,
            figi=instrument.figi,
            estimated_price=estimated_price,
            estimated_value=estimated_value,
            estimated_price_display=money(estimated_price),
            estimated_value_display=money(estimated_value),
            order_type=request.order_type,
            mode=mode,
            trading_enabled=mode.trading_available,
            can_execute=mode.trading_available,
            requires_ticker_confirmation=mode.mode == "prod" and mode.trading_available,
            warnings=warnings,
            confirm_token=confirm_token,
        )

    def execute(self, command: OrderConfirmCommand) -> OrderExecutionResult:
        command = self._normalize_confirm_command(command)
        self._consume_preview_token(command)

        mode = self.mode_service.current()
        if not mode.trading_available:
            raise OrderExecutionBlocked("Execution is blocked because production trading is disabled.")

        if mode.mode == "prod" and command.ticker_confirmation != command.ticker:
            raise OrderExecutionBlocked("Type the ticker exactly to confirm a production order.")

        preview = self.preview(
            OrderPreviewRequest(
                operation=command.operation,
                ticker=command.ticker,
                lots=command.lots,
                order_type=command.order_type,
            )
        )

        token = self.token_provider()
        if not token:
            raise OrderValidationError("No broker token is configured for the current mode.")

        try:
            broker_result = self.broker.place_order(
                token=token,
                figi=preview.figi,
                ticker=preview.ticker,
                lots=preview.lots,
                operation=preview.operation,
                sandbox=mode.is_sandbox,
            )
        except Exception as exc:
            raise OrderServiceError("Order execution failed. Check broker availability and try again.") from exc

        return OrderExecutionResult(
            operation=preview.operation,
            operation_label=preview.operation_label,
            ticker=preview.ticker,
            lots=preview.lots,
            order_id=broker_result.order_id,
            executed_price_display=money(broker_result.price),
            total_value_display=money(broker_result.total_value),
            mode=mode,
            message=broker_result.warning or "Order submitted successfully.",
        )

    def cancel_preview(self, confirm_token: str) -> bool:
        with self._preview_token_lock:
            self._cleanup_preview_tokens()
            token = str(confirm_token or "")
            return self._preview_tokens.pop(token, None) is not None

    def _normalize_preview_request(self, request: OrderPreviewRequest) -> OrderPreviewRequest:
        operation = str(request.operation or "").strip().lower()
        ticker = str(request.ticker or "").strip().upper()

        if operation not in {"buy", "sell"}:
            raise OrderValidationError("Unsupported order side.")
        if not ticker or not ticker.replace("-", "").isalnum():
            raise OrderValidationError("Enter a ticker using letters and numbers.")
        if request.lots < 1:
            raise OrderValidationError("Lots must be at least 1.")
        if request.order_type != "limit":
            raise OrderValidationError("Only limit orders are available in this version.")

        return OrderPreviewRequest(operation=operation, ticker=ticker, lots=request.lots, order_type=request.order_type)

    def _normalize_confirm_command(self, command: OrderConfirmCommand) -> OrderConfirmCommand:
        request = self._normalize_preview_request(
            OrderPreviewRequest(
                operation=command.operation,
                ticker=command.ticker,
                lots=command.lots,
                order_type=command.order_type,
            )
        )
        ticker_confirmation = None
        if command.ticker_confirmation is not None:
            ticker_confirmation = command.ticker_confirmation.strip().upper()

        return OrderConfirmCommand(
            operation=request.operation,
            ticker=request.ticker,
            lots=request.lots,
            confirm_token=str(command.confirm_token or ""),
            ticker_confirmation=ticker_confirmation,
            order_type=request.order_type,
        )

    def _issue_preview_token(self, request: OrderPreviewRequest) -> str:
        with self._preview_token_lock:
            self._cleanup_preview_tokens()
            token = secrets.token_urlsafe(24)
            self._preview_tokens[token] = _PreviewToken(
                operation=request.operation,
                ticker=request.ticker,
                lots=request.lots,
                expires_at=time.time() + CONFIRM_TOKEN_TTL_SECONDS,
            )
            return token

    def _consume_preview_token(self, command: OrderConfirmCommand) -> None:
        with self._preview_token_lock:
            self._cleanup_preview_tokens()
            preview_token = self._preview_tokens.get(command.confirm_token)
            if preview_token is None or preview_token.consumed:
                raise OrderExecutionBlocked("This preview has expired or was already used. Preview the order again.")
            if preview_token.expires_at < time.time():
                raise OrderExecutionBlocked("This preview has expired. Preview the order again.")
            if (
                preview_token.operation != command.operation
                or preview_token.ticker != command.ticker
                or preview_token.lots != command.lots
            ):
                raise OrderExecutionBlocked("The confirmation does not match the preview. Preview the order again.")

            preview_token.consumed = True

    def _cleanup_preview_tokens(self) -> None:
        now = time.time()
        for token, preview_token in list(self._preview_tokens.items()):
            if preview_token.expires_at < now or preview_token.consumed:
                del self._preview_tokens[token]
