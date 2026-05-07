from dataclasses import dataclass
import unittest

from app.services.mode import ModeContext
from app.services.orders import (
    OrderConfirmCommand,
    OrderExecutionBlocked,
    OrderPreviewRequest,
    OrderService,
    OrderValidationError,
)


class FakeModeService:
    def __init__(self, *, mode="sandbox", trading_available=True):
        self.mode = mode
        self.trading_available = trading_available

    def current(self):
        return ModeContext(
            mode=self.mode,
            is_sandbox=self.mode == "sandbox",
            prod_trading_allowed=self.mode == "prod" and self.trading_available,
            trading_available=self.trading_available,
            banner_title=f"Mode: {self.mode}",
            banner_message="Test mode",
        )


@dataclass(frozen=True)
class FakeInstrument:
    figi: str = "FIGI-SBER"
    ticker: str = "SBER"
    name: str = "Sber"


@dataclass(frozen=True)
class FakeOrderResult:
    order_id: str = "order-1"
    price: float = 101.0
    total_value: float = 1_010.0
    warning: str | None = None


class FakeBroker:
    def __init__(
        self,
        *,
        enough_cash=True,
        available_quantity=100.0,
        lot_size=10,
        price=101.0,
    ):
        self.enough_cash = enough_cash
        self.available_quantity = available_quantity
        self.lot_size = lot_size
        self.price = price
        self.placed_orders = []

    def resolve_unique_instrument(self, token, ticker):
        return FakeInstrument(ticker=ticker)

    def get_price(self, token, figi, operation):
        return self.price

    def get_lot_size(self, token, figi):
        return self.lot_size

    def has_enough_cash(self, token, figi, lots, sandbox):
        return self.enough_cash

    def get_available_quantity(self, token, figi, sandbox):
        return self.available_quantity

    def place_order(self, *, token, figi, ticker, lots, operation, sandbox):
        self.placed_orders.append(
            {
                "token": token,
                "figi": figi,
                "ticker": ticker,
                "lots": lots,
                "operation": operation,
                "sandbox": sandbox,
            }
        )
        return FakeOrderResult(total_value=self.price * self.lot_size * lots)


class OrderServiceTests(unittest.TestCase):
    def build_service(self, *, broker=None, mode="sandbox", trading_available=True, token="token"):
        broker = broker or FakeBroker()
        service = OrderService(
            broker=broker,
            mode_service=FakeModeService(mode=mode, trading_available=trading_available),
            token_provider=lambda: token,
        )
        return service, broker

    def test_preview_normalizes_ticker_and_builds_confirm_token(self):
        service, _ = self.build_service()

        preview = service.preview(OrderPreviewRequest(operation="BUY", ticker=" sber ", lots=2))

        self.assertEqual(preview.operation, "buy")
        self.assertEqual(preview.ticker, "SBER")
        self.assertEqual(preview.estimated_price, 101.0)
        self.assertEqual(preview.estimated_value, 2_020.0)
        self.assertTrue(preview.confirm_token)
        self.assertTrue(preview.can_execute)

    def test_preview_rejects_invalid_order_inputs(self):
        service, _ = self.build_service()

        invalid_requests = [
            OrderPreviewRequest(operation="hold", ticker="SBER", lots=1),
            OrderPreviewRequest(operation="buy", ticker="***", lots=1),
            OrderPreviewRequest(operation="buy", ticker="SBER", lots=0),
            OrderPreviewRequest(operation="buy", ticker="SBER", lots=1, order_type="market"),
        ]

        for request in invalid_requests:
            with self.subTest(request=request):
                with self.assertRaises(OrderValidationError):
                    service.preview(request)

    def test_preview_rejects_buy_without_cash(self):
        service, _ = self.build_service(broker=FakeBroker(enough_cash=False))

        with self.assertRaisesRegex(OrderValidationError, "not enough cash"):
            service.preview(OrderPreviewRequest(operation="buy", ticker="SBER", lots=1))

    def test_preview_rejects_sell_when_available_quantity_is_too_low(self):
        service, _ = self.build_service(broker=FakeBroker(available_quantity=15.0, lot_size=10))

        with self.assertRaisesRegex(OrderValidationError, "available 15, needed 20"):
            service.preview(OrderPreviewRequest(operation="sell", ticker="SBER", lots=2))

    def test_preview_allows_prod_read_only_but_marks_execution_blocked(self):
        service, _ = self.build_service(mode="prod", trading_available=False)

        preview = service.preview(OrderPreviewRequest(operation="buy", ticker="SBER", lots=1))

        self.assertFalse(preview.can_execute)
        self.assertIn("Production trading is disabled", preview.warnings[0])

    def test_execute_blocks_prod_read_only_without_placing_order(self):
        service, broker = self.build_service(mode="prod", trading_available=False)
        preview = service.preview(OrderPreviewRequest(operation="buy", ticker="SBER", lots=1))

        with self.assertRaisesRegex(OrderExecutionBlocked, "production trading is disabled"):
            service.execute(
                OrderConfirmCommand(
                    operation="buy",
                    ticker="SBER",
                    lots=1,
                    confirm_token=preview.confirm_token,
                )
            )

        self.assertEqual(broker.placed_orders, [])

    def test_execute_requires_ticker_confirmation_for_prod_orders(self):
        service, broker = self.build_service(mode="prod", trading_available=True)
        preview = service.preview(OrderPreviewRequest(operation="buy", ticker="SBER", lots=1))

        with self.assertRaisesRegex(OrderExecutionBlocked, "Type the ticker exactly"):
            service.execute(
                OrderConfirmCommand(
                    operation="buy",
                    ticker="SBER",
                    lots=1,
                    confirm_token=preview.confirm_token,
                    ticker_confirmation="VTBR",
                )
            )

        self.assertEqual(broker.placed_orders, [])

    def test_execute_places_prod_order_after_matching_confirmation(self):
        service, broker = self.build_service(mode="prod", trading_available=True)
        preview = service.preview(OrderPreviewRequest(operation="buy", ticker="SBER", lots=1))

        result = service.execute(
            OrderConfirmCommand(
                operation="buy",
                ticker="SBER",
                lots=1,
                confirm_token=preview.confirm_token,
                ticker_confirmation="sber",
            )
        )

        self.assertEqual(result.order_id, "order-1")
        self.assertEqual(len(broker.placed_orders), 1)
        self.assertFalse(broker.placed_orders[0]["sandbox"])

    def test_execute_rejects_confirmation_that_does_not_match_preview(self):
        service, broker = self.build_service()
        preview = service.preview(OrderPreviewRequest(operation="buy", ticker="SBER", lots=1))

        with self.assertRaisesRegex(OrderExecutionBlocked, "does not match the preview"):
            service.execute(
                OrderConfirmCommand(
                    operation="buy",
                    ticker="SBER",
                    lots=2,
                    confirm_token=preview.confirm_token,
                )
            )

        self.assertEqual(broker.placed_orders, [])

    def test_cancel_preview_invalidates_confirm_token(self):
        service, broker = self.build_service()
        preview = service.preview(OrderPreviewRequest(operation="buy", ticker="SBER", lots=1))

        self.assertTrue(service.cancel_preview(preview.confirm_token))
        self.assertFalse(service.cancel_preview(preview.confirm_token))

        with self.assertRaisesRegex(OrderExecutionBlocked, "expired or was already used"):
            service.execute(
                OrderConfirmCommand(
                    operation="buy",
                    ticker="SBER",
                    lots=1,
                    confirm_token=preview.confirm_token,
                )
            )

        self.assertEqual(broker.placed_orders, [])


if __name__ == "__main__":
    unittest.main()
