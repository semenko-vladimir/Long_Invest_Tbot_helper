import ast
from dataclasses import dataclass
import os
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch


os.environ["BOT_TOKEN"] = "123456:TEST"

from app.client.handlers.orders import manual_order_handler
from app.services.mode import ModeContext
from app.services.orders import (
    OrderExecutionBlocked,
    OrderExecutionResult,
    OrderPreviewResult,
    OrderServiceError,
)


class FakeMessage:
    def __init__(self, text: str, chat_id: int = 42):
        self.text = text
        self.chat = SimpleNamespace(id=chat_id)


class FakeOrderService:
    def __init__(
        self,
        *,
        preview_token="preview-token",
        preview_error=None,
        execute_error=None,
        preview_mode="sandbox",
        preview_can_execute=True,
        preview_requires_ticker_confirmation=False,
    ):
        self.preview_token = preview_token
        self.preview_error = preview_error
        self.execute_error = execute_error
        self.preview_mode = preview_mode
        self.preview_can_execute = preview_can_execute
        self.preview_requires_ticker_confirmation = preview_requires_ticker_confirmation
        self.preview_calls = []
        self.execute_calls = []
        self.cancel_calls = []

    def preview(self, request):
        self.preview_calls.append(request)
        if self.preview_error:
            raise self.preview_error
        return OrderPreviewResult(
            operation=request.operation,
            operation_label=request.operation.title(),
            ticker=request.ticker.upper(),
            lots=request.lots,
            instrument_name="Sber",
            figi="FIGI-SBER",
            estimated_price=101.0,
            estimated_value=1_010.0,
            estimated_price_display="101.00 RUB",
            estimated_value_display="1 010.00 RUB",
            order_type=request.order_type,
            mode=ModeContext(
                mode=self.preview_mode,
                is_sandbox=self.preview_mode == "sandbox",
                prod_trading_allowed=self.preview_mode == "prod" and self.preview_can_execute,
                trading_available=self.preview_can_execute,
                banner_title=f"Mode: {self.preview_mode}",
                banner_message="Test mode",
            ),
            trading_enabled=self.preview_can_execute,
            can_execute=self.preview_can_execute,
            requires_ticker_confirmation=self.preview_requires_ticker_confirmation,
            warnings=["Production trading is disabled."]
            if self.preview_mode == "prod" and not self.preview_can_execute
            else [],
            confirm_token=self.preview_token,
        )

    def execute(self, command):
        self.execute_calls.append(command)
        if self.execute_error:
            raise self.execute_error
        return OrderExecutionResult(
            operation=command.operation,
            operation_label=command.operation.title(),
            ticker=command.ticker,
            lots=command.lots,
            order_id="order-1",
            executed_price_display="101.00 RUB",
            total_value_display="1 010.00 RUB",
            mode=ModeContext(
                mode="sandbox",
                is_sandbox=True,
                prod_trading_allowed=False,
                trading_available=True,
                banner_title="Mode: sandbox",
                banner_message="Test mode",
            ),
            message="Order submitted successfully.",
        )

    def cancel_preview(self, confirm_token):
        self.cancel_calls.append(confirm_token)
        return True


class TelegramManualOrderHandlerTests(unittest.TestCase):
    def setUp(self):
        manual_order_handler.telegram_order_previews.clear()

    def tearDown(self):
        manual_order_handler.telegram_order_previews.clear()

    def test_buy_command_creates_preview_and_does_not_execute(self):
        service = FakeOrderService(preview_token="buy-token")

        with patch.object(manual_order_handler, "order_service", service), \
            patch.object(manual_order_handler, "send_or_edit_message") as send_message:
            manual_order_handler.manual_trade_command_handler(FakeMessage("buy SBER 1"))

        self.assertEqual(len(service.preview_calls), 1)
        self.assertEqual(service.preview_calls[0].operation, "buy")
        self.assertEqual(service.preview_calls[0].ticker, "SBER")
        self.assertEqual(service.preview_calls[0].lots, 1)
        self.assertEqual(service.execute_calls, [])
        self.assertIn("buy-token", manual_order_handler.telegram_order_previews)
        text = send_message.call_args.args[1]
        self.assertIn("Order preview", text)
        self.assertIn("Side: `BUY`", text)
        self.assertIn("confirm_order buy-token", text)
        self.assertIn("No broker order has been sent yet.", text)

    def test_sell_command_creates_preview_and_does_not_execute(self):
        service = FakeOrderService(preview_token="sell-token")

        with patch.object(manual_order_handler, "order_service", service), \
            patch.object(manual_order_handler, "send_or_edit_message") as send_message:
            manual_order_handler.manual_trade_command_handler(FakeMessage("sell SBER 1"))

        self.assertEqual(len(service.preview_calls), 1)
        self.assertEqual(service.preview_calls[0].operation, "sell")
        self.assertEqual(service.execute_calls, [])
        self.assertIn("sell-token", manual_order_handler.telegram_order_previews)
        self.assertIn("Side: `SELL`", send_message.call_args.args[1])

    def test_confirmation_executes_only_through_order_service(self):
        service = FakeOrderService()
        manual_order_handler.telegram_order_previews["preview-token"] = manual_order_handler.TelegramOrderPreview(
            chat_id=42,
            operation="buy",
            ticker="SBER",
            lots=1,
            created_at=manual_order_handler.time.time(),
        )

        with patch.object(manual_order_handler, "order_service", service), \
            patch.object(manual_order_handler, "send_or_edit_message") as send_message:
            manual_order_handler.confirm_order_command_handler(FakeMessage("confirm_order preview-token"))

        self.assertEqual(len(service.execute_calls), 1)
        self.assertEqual(service.execute_calls[0].confirm_token, "preview-token")
        self.assertEqual(service.execute_calls[0].ticker, "SBER")
        self.assertNotIn("preview-token", manual_order_handler.telegram_order_previews)
        self.assertIn("Order submitted", send_message.call_args.args[1])

    def test_prod_confirmation_requires_ticker_and_blocked_prod_is_not_sent(self):
        blocked_service = FakeOrderService(
            preview_token="prod-token",
            preview_mode="prod",
            preview_can_execute=False,
            execute_error=OrderExecutionBlocked("Execution is blocked because production trading is disabled."),
        )

        with patch.object(manual_order_handler, "order_service", blocked_service), \
            patch.object(manual_order_handler, "send_or_edit_message") as send_message:
            manual_order_handler.preview_manual_order(42, "buy", "SBER", 1)
            preview_text = send_message.call_args.args[1]

        self.assertIn("Execution is blocked in the current mode.", preview_text)
        self.assertIn("prod-token", manual_order_handler.telegram_order_previews)

        with patch.object(manual_order_handler, "order_service", blocked_service), \
            patch.object(manual_order_handler, "send_or_edit_message") as send_message:
            manual_order_handler.confirm_order_command_handler(FakeMessage("confirm_order prod-token"))

        self.assertEqual(len(blocked_service.execute_calls), 1)
        self.assertIn("Order was not sent", send_message.call_args.args[1])
        self.assertIn("production trading is disabled", send_message.call_args.args[1])

    def test_invalid_direct_order_command_returns_error_and_no_preview(self):
        service = FakeOrderService()

        with patch.object(manual_order_handler, "order_service", service), \
            patch.object(manual_order_handler, "send_or_edit_message") as send_message:
            manual_order_handler.invalid_manual_trade_command_handler(FakeMessage("buy SBER 0"))

        self.assertEqual(service.preview_calls, [])
        self.assertEqual(service.execute_calls, [])
        self.assertIn("Invalid manual order format", send_message.call_args.args[1])

    def test_cancel_invalidates_preview_and_later_confirm_does_not_execute(self):
        service = FakeOrderService(preview_token="cancel-token")

        with patch.object(manual_order_handler, "order_service", service), \
            patch.object(manual_order_handler, "send_or_edit_message"):
            manual_order_handler.preview_manual_order(42, "buy", "SBER", 1)
            manual_order_handler.cancel_order_command_handler(FakeMessage("cancel_order cancel-token"))

        self.assertEqual(service.cancel_calls, ["cancel-token"])
        self.assertNotIn("cancel-token", manual_order_handler.telegram_order_previews)

        with patch.object(manual_order_handler, "order_service", service), \
            patch.object(manual_order_handler, "send_or_edit_message") as send_message:
            manual_order_handler.confirm_order_command_handler(FakeMessage("confirm_order cancel-token"))

        self.assertEqual(service.execute_calls, [])
        self.assertIn("not found or has expired", send_message.call_args.args[1])

    def test_manual_order_handler_has_no_direct_broker_order_placement(self):
        handler_path = (
            Path(__file__).resolve().parents[1]
            / "app"
            / "client"
            / "handlers"
            / "orders"
            / "manual_order_handler.py"
        )
        source = handler_path.read_text(encoding="utf-8")
        tree = ast.parse(source)

        imported_modules = set()
        imported_names = set()
        attribute_names = set()
        call_names = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported_modules.update(alias.name for alias in node.names)
                imported_names.update(alias.asname or alias.name.split(".")[-1] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported_modules.add(node.module)
                imported_names.update(alias.asname or alias.name for alias in node.names)
            elif isinstance(node, ast.Attribute):
                attribute_names.add(node.attr)
            elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                call_names.add(node.func.id)

        self.assertNotIn("tinkoff.invest", imported_modules)
        self.assertNotIn("TradingApiClient", imported_names)
        self.assertNotIn("Client", imported_names)
        self.assertNotIn("post_order", attribute_names)
        self.assertNotIn("post_sandbox_order", attribute_names)
        self.assertNotIn("place_manual_order", call_names)


if __name__ == "__main__":
    unittest.main()
