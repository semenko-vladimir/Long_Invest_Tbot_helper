import ast
from datetime import datetime, timezone
import os
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from app.data_sources.schemas import (
    DATA_SOURCE_MOEX_ISS,
    DATA_SOURCE_T_INVEST_THEN_MOEX_ISS_FALLBACK,
    DELAY_STATUS_DELAYED_PUBLIC_ISS,
)

os.environ["BOT_TOKEN"] = "123456:TEST"

from app.client.handlers.charts import chart_handler


PNG_BYTES = b"\x89PNG\r\n\x1a\nfake-chart"


class FakeMessage:
    def __init__(self, text: str, chat_id: int = 42):
        self.text = text
        self.chat = SimpleNamespace(id=chat_id)


class FakeChartImageService:
    def __init__(self, result):
        self.result = result
        self.calls = []

    def render_png(self, ticker, range_name, include_analytics=True, mode="price"):
        self.calls.append((ticker, range_name, include_analytics, mode))
        return self.result


def chart_result(**overrides):
    values = {
        "ok": True,
        "png_bytes": PNG_BYTES,
        "content_type": "image/png",
        "errors": [],
        "data_gaps": [],
    }
    values.update(overrides)
    return SimpleNamespace(**values)


class TelegramChartHandlerTests(unittest.TestCase):
    def test_parser_accepts_all_supported_ranges(self):
        for range_name in chart_handler.CHART_RANGE_ORDER:
            with self.subTest(range_name=range_name):
                command = chart_handler.parse_chart_command(f"/chart sber {range_name}")
                self.assertIsNotNone(command)
                self.assertEqual(command.ticker, "SBER")
                self.assertEqual(command.range_name, range_name)
                self.assertTrue(command.include_analytics)

    def test_parser_accepts_plain_and_no_analytics_forms(self):
        plain = chart_handler.parse_chart_command("/chart sber month plain")
        no_analytics = chart_handler.parse_chart_command("/chart sber month no_analytics")

        self.assertIsNotNone(plain)
        self.assertEqual(plain.ticker, "SBER")
        self.assertEqual(plain.range_name, "month")
        self.assertFalse(plain.include_analytics)
        self.assertIsNotNone(no_analytics)
        self.assertEqual(no_analytics.ticker, "SBER")
        self.assertEqual(no_analytics.range_name, "month")
        self.assertFalse(no_analytics.include_analytics)

    def test_moex_parser_accepts_supported_ranges_and_plain_forms(self):
        command = chart_handler.parse_moex_chart_command("/moex_chart sber month")
        plain = chart_handler.parse_moex_chart_command("/moex_chart sber month plain")
        no_analytics = chart_handler.parse_moex_chart_command("/moex_chart sber month no_analytics")

        self.assertIsNotNone(command)
        self.assertEqual(command.ticker, "SBER")
        self.assertEqual(command.range_name, "month")
        self.assertTrue(command.include_analytics)
        self.assertIsNotNone(plain)
        self.assertFalse(plain.include_analytics)
        self.assertIsNotNone(no_analytics)
        self.assertFalse(no_analytics.include_analytics)

    def test_parser_rejects_missing_or_unsupported_arguments(self):
        invalid_inputs = [
            None,
            "",
            "/chart",
            "/chart SBER",
            "/chart SBER intraday",
            "/chart SBER month analytics",
            "/chart *** month",
            "/research SBER",
        ]

        for text in invalid_inputs:
            with self.subTest(text=text):
                self.assertIsNone(chart_handler.parse_chart_command(text))

    def test_moex_parser_rejects_missing_or_unsupported_arguments(self):
        invalid_inputs = [
            None,
            "",
            "/moex_chart",
            "/moex_chart SBER",
            "/moex_chart SBER intraday",
            "/moex_chart SBER month analytics",
            "/moex_chart *** month",
            "/chart SBER month",
        ]

        for text in invalid_inputs:
            with self.subTest(text=text):
                self.assertIsNone(chart_handler.parse_moex_chart_command(text))

    def test_position_chart_parser_accepts_ticker_and_supported_range(self):
        command = chart_handler.parse_position_chart_command("/position_chart sber month")

        self.assertIsNotNone(command)
        self.assertEqual(command.ticker, "SBER")
        self.assertEqual(command.range_name, "month")

    def test_position_chart_parser_rejects_missing_or_unsupported_arguments(self):
        invalid_inputs = [
            None,
            "",
            "/position_chart",
            "/position_chart SBER",
            "/position_chart SBER intraday",
            "/position_chart SBER month plain",
            "/position_chart *** month",
            "/chart SBER month",
        ]

        for text in invalid_inputs:
            with self.subTest(text=text):
                self.assertIsNone(chart_handler.parse_position_chart_command(text))

    def test_invalid_command_sends_usage_without_loading_services(self):
        with patch.object(chart_handler, "get_telegram_services_or_notify") as get_services:
            with patch.object(chart_handler.bot, "send_message", return_value=SimpleNamespace(message_id=100)) as send:
                chart_handler.chart_command_handler(FakeMessage("/chart SBER"))

        get_services.assert_not_called()
        text = send.call_args.kwargs["text"]
        self.assertIn("/chart SBER month", text)
        self.assertIn("/chart SBER month plain", text)
        self.assertIn("/chart SBER month no_analytics", text)
        self.assertIn("Supported ranges", text)
        self.assertIn("Hindsight-only analytics", text)
        self.assertIn("Not a trading signal", text)
        self.assertIn("Not investment advice", text)
        self.assertIn("No broker orders were created", text)

    def test_invalid_moex_chart_command_sends_usage_without_loading_services(self):
        with patch.object(chart_handler, "get_telegram_services_or_notify") as get_services:
            with patch.object(chart_handler.bot, "send_message", return_value=SimpleNamespace(message_id=100)) as send:
                chart_handler.moex_chart_command_handler(FakeMessage("/moex_chart SBER"))

        get_services.assert_not_called()
        text = send.call_args.kwargs["text"]
        self.assertIn("/moex_chart SBER month", text)
        self.assertIn("/moex_chart SBER month plain", text)
        self.assertIn("delayed public MOEX ISS data", text)
        self.assertIn("No broker orders were created", text)

    def test_successful_command_sends_png_with_safe_caption(self):
        fake_service = FakeChartImageService(chart_result())
        services = SimpleNamespace(chart_image_service=fake_service)

        with patch.object(chart_handler, "get_telegram_services_or_notify", return_value=services):
            with patch.object(chart_handler.bot, "send_photo", return_value=SimpleNamespace(message_id=101)) as send_photo:
                with patch.object(chart_handler.bot, "send_message") as send_message:
                    chart_handler.chart_command_handler(FakeMessage("/chart sber month"))

        self.assertEqual(fake_service.calls, [("SBER", "month", True, "price")])
        send_message.assert_not_called()
        self.assertEqual(send_photo.call_args.kwargs["chat_id"], 42)
        self.assertEqual(send_photo.call_args.kwargs["photo"], PNG_BYTES)
        self.assertEqual(send_photo.call_args.kwargs["caption"], chart_handler.CHART_CAPTION)
        self.assertIn("Hindsight-only analytics", send_photo.call_args.kwargs["caption"])
        self.assertIn("Not a trading signal", send_photo.call_args.kwargs["caption"])

    def test_successful_command_caption_includes_moex_source_metadata(self):
        fake_service = FakeChartImageService(
            chart_result(
                history=SimpleNamespace(
                    source=DATA_SOURCE_MOEX_ISS,
                    fetched_at=datetime(2026, 5, 21, 13, 0, tzinfo=timezone.utc),
                    as_of_date="2026-05-20",
                    delay_status=DELAY_STATUS_DELAYED_PUBLIC_ISS,
                )
            )
        )
        services = SimpleNamespace(chart_image_service=fake_service)

        with patch.object(chart_handler, "get_telegram_services_or_notify", return_value=services):
            with patch.object(chart_handler.bot, "send_photo", return_value=SimpleNamespace(message_id=101)) as send_photo:
                with patch.object(chart_handler.bot, "send_message"):
                    chart_handler.chart_command_handler(FakeMessage("/chart sber month"))

        caption = send_photo.call_args.kwargs["caption"]
        self.assertIn(f"Source: {DATA_SOURCE_MOEX_ISS}", caption)
        self.assertNotIn(DATA_SOURCE_T_INVEST_THEN_MOEX_ISS_FALLBACK, caption)
        self.assertIn("As of: 2026-05-20", caption)
        self.assertIn("Fetched: 2026-05-21 13:00 UTC", caption)
        self.assertIn("Freshness: latest_available", caption)
        self.assertIn("Delay: moex_delayed", caption)
        self.assertIn("Candles: 0", caption)
        self.assertIn("No broker orders were created", caption)

    def test_successful_moex_chart_command_uses_moex_service_and_caption(self):
        regular_service = FakeChartImageService(chart_result())
        moex_service = FakeChartImageService(
            chart_result(
                source_name=DATA_SOURCE_MOEX_ISS,
                fetched_at=datetime(2026, 5, 21, 13, 0, tzinfo=timezone.utc),
                as_of_date="2026-05-20",
                delay_status=DELAY_STATUS_DELAYED_PUBLIC_ISS,
            )
        )
        services = SimpleNamespace(
            chart_image_service=regular_service,
            moex_chart_image_service=moex_service,
        )

        with patch.object(chart_handler, "get_telegram_services_or_notify", return_value=services):
            with patch.object(chart_handler.bot, "send_photo", return_value=SimpleNamespace(message_id=101)) as send_photo:
                with patch.object(chart_handler.bot, "send_message") as send_message:
                    chart_handler.moex_chart_command_handler(FakeMessage("/moex_chart sber month"))

        self.assertEqual(regular_service.calls, [])
        self.assertEqual(moex_service.calls, [("SBER", "month", True, "price")])
        send_message.assert_not_called()
        caption = send_photo.call_args.kwargs["caption"]
        self.assertIn("Read-only MOEX ISS chart", caption)
        self.assertIn("delayed public MOEX ISS data", caption)
        self.assertIn(f"Source: {DATA_SOURCE_MOEX_ISS}", caption)
        self.assertNotIn(DATA_SOURCE_T_INVEST_THEN_MOEX_ISS_FALLBACK, caption)
        self.assertIn("As of: 2026-05-20", caption)
        self.assertIn("Freshness: latest_available", caption)
        self.assertIn("Delay: moex_delayed", caption)
        self.assertIn("Candles: 0", caption)
        self.assertIn("No broker orders were created", caption)

    def test_plain_command_sends_png_without_analytics(self):
        fake_service = FakeChartImageService(chart_result())
        services = SimpleNamespace(chart_image_service=fake_service)

        with patch.object(chart_handler, "get_telegram_services_or_notify", return_value=services):
            with patch.object(chart_handler.bot, "send_photo", return_value=SimpleNamespace(message_id=101)):
                with patch.object(chart_handler.bot, "send_message"):
                    chart_handler.chart_command_handler(FakeMessage("/chart sber month plain"))

        self.assertEqual(fake_service.calls, [("SBER", "month", False, "price")])

    def test_moex_plain_command_sends_png_without_analytics(self):
        regular_service = FakeChartImageService(chart_result())
        moex_service = FakeChartImageService(chart_result(source_name=DATA_SOURCE_MOEX_ISS))
        services = SimpleNamespace(
            chart_image_service=regular_service,
            moex_chart_image_service=moex_service,
        )

        with patch.object(chart_handler, "get_telegram_services_or_notify", return_value=services):
            with patch.object(chart_handler.bot, "send_photo", return_value=SimpleNamespace(message_id=101)):
                with patch.object(chart_handler.bot, "send_message"):
                    chart_handler.moex_chart_command_handler(FakeMessage("/moex_chart sber month plain"))

        self.assertEqual(regular_service.calls, [])
        self.assertEqual(moex_service.calls, [("SBER", "month", False, "price")])

    def test_successful_position_chart_command_sends_png_with_safe_caption(self):
        fake_service = FakeChartImageService(chart_result())
        services = SimpleNamespace(chart_image_service=fake_service)

        with patch.object(chart_handler, "get_telegram_services_or_notify", return_value=services):
            with patch.object(chart_handler.bot, "send_photo", return_value=SimpleNamespace(message_id=101)) as send_photo:
                with patch.object(chart_handler.bot, "send_message") as send_message:
                    chart_handler.position_chart_command_handler(FakeMessage("/position_chart sber month"))

        self.assertEqual(fake_service.calls, [("SBER", "month", False, "position_value")])
        send_message.assert_not_called()
        self.assertEqual(send_photo.call_args.kwargs["chat_id"], 42)
        self.assertEqual(send_photo.call_args.kwargs["photo"], PNG_BYTES)
        caption = send_photo.call_args.kwargs["caption"]
        self.assertIn("current position quantity valued at historical close prices", caption)
        self.assertIn("not historical holdings", caption)
        self.assertIn("no broker orders were created", caption)

    def test_successful_position_chart_caption_includes_moex_fallback_source(self):
        fake_service = FakeChartImageService(
            chart_result(
                source_name=DATA_SOURCE_MOEX_ISS,
                fetched_at=datetime(2026, 5, 21, 13, 0, tzinfo=timezone.utc),
                as_of_date="2026-05-20",
                delay_status=DELAY_STATUS_DELAYED_PUBLIC_ISS,
            )
        )
        services = SimpleNamespace(chart_image_service=fake_service)

        with patch.object(chart_handler, "get_telegram_services_or_notify", return_value=services):
            with patch.object(chart_handler.bot, "send_photo", return_value=SimpleNamespace(message_id=101)) as send_photo:
                with patch.object(chart_handler.bot, "send_message"):
                    chart_handler.position_chart_command_handler(FakeMessage("/position_chart sber month"))

        caption = send_photo.call_args.kwargs["caption"]
        self.assertIn(f"Source: {DATA_SOURCE_MOEX_ISS}", caption)
        self.assertNotIn(DATA_SOURCE_T_INVEST_THEN_MOEX_ISS_FALLBACK, caption)
        self.assertIn("As of: 2026-05-20", caption)
        self.assertIn("current position quantity valued at historical close prices", caption)

    def test_position_chart_non_portfolio_ticker_sends_clear_message(self):
        fake_service = FakeChartImageService(
            chart_result(
                ok=False,
                png_bytes=None,
                errors=[
                    "Ticker SBER is not in the current portfolio; current quantity value chart requires an open position."
                ],
            )
        )
        services = SimpleNamespace(chart_image_service=fake_service)

        with patch.object(chart_handler, "get_telegram_services_or_notify", return_value=services):
            with patch.object(chart_handler.bot, "send_message", return_value=SimpleNamespace(message_id=102)) as send:
                chart_handler.position_chart_command_handler(FakeMessage("/position_chart sber month"))

        text = send.call_args.kwargs["text"]
        self.assertIn("Current quantity value chart could not be generated", text)
        self.assertIn("not in the current portfolio", text)
        self.assertIn("current position quantity valued at historical close prices", text)

    def test_invalid_position_chart_command_sends_usage_without_loading_services(self):
        with patch.object(chart_handler, "get_telegram_services_or_notify") as get_services:
            with patch.object(chart_handler.bot, "send_message", return_value=SimpleNamespace(message_id=100)) as send:
                chart_handler.position_chart_command_handler(FakeMessage("/position_chart SBER"))

        get_services.assert_not_called()
        text = send.call_args.kwargs["text"]
        self.assertIn("/position_chart SBER month", text)
        self.assertIn("Supported ranges", text)
        self.assertIn("current position quantity valued at historical close prices", text)

    def test_invalid_analytics_argument_sends_usage_without_loading_services(self):
        with patch.object(chart_handler, "get_telegram_services_or_notify") as get_services:
            with patch.object(chart_handler.bot, "send_message", return_value=SimpleNamespace(message_id=100)) as send:
                chart_handler.chart_command_handler(FakeMessage("/chart SBER month overlays"))

        get_services.assert_not_called()
        self.assertIn("Read-only chart usage", send.call_args.kwargs["text"])

    def test_handler_error_sends_safe_text(self):
        fake_service = FakeChartImageService(
            chart_result(ok=False, png_bytes=None, errors=["No candles are available for chart rendering."])
        )
        services = SimpleNamespace(chart_image_service=fake_service)

        with patch.object(chart_handler, "get_telegram_services_or_notify", return_value=services):
            with patch.object(chart_handler.bot, "send_message", return_value=SimpleNamespace(message_id=102)) as send:
                chart_handler.chart_command_handler(FakeMessage("/chart sber month"))

        text = send.call_args.kwargs["text"]
        self.assertIn("No candles are available", text)
        self.assertIn("Read-only chart could not be generated", text)
        self.assertIn("No broker orders were created", text)

    def test_moex_handler_error_sends_safe_text(self):
        fake_service = FakeChartImageService(
            chart_result(ok=False, png_bytes=None, errors=["MOEX ISS returned no daily candles."])
        )
        services = SimpleNamespace(moex_chart_image_service=fake_service)

        with patch.object(chart_handler, "get_telegram_services_or_notify", return_value=services):
            with patch.object(chart_handler.bot, "send_message", return_value=SimpleNamespace(message_id=102)) as send:
                chart_handler.moex_chart_command_handler(FakeMessage("/moex_chart sber month"))

        text = send.call_args.kwargs["text"]
        self.assertIn("MOEX ISS returned no daily candles", text)
        self.assertIn("MOEX ISS chart could not be generated", text)
        self.assertIn("No broker orders were created", text)

    def test_telegram_chart_handler_imports_no_order_signal_or_rating_modules(self):
        forbidden_prefixes = (
            "app.services.orders",
            "app.client.orders",
            "app.client.handlers.orders",
            "app.client.handlers.signals",
            "app.client.handlers.mls",
            "app.client.signals",
            "app.client.strategy",
            "app.client.api.signals_client",
            "app.client.api.strategy_client",
            "keras",
            "tensorflow",
            "g4f",
        )
        forbidden_names = {
            "OrderService",
            "manual_order_handler",
            "place_order",
            "post_order",
            "BUY",
            "SELL",
            "HOLD",
            "WATCH",
            "AVOID",
        }
        handler_path = (
            Path(__file__).resolve().parents[1]
            / "app"
            / "client"
            / "handlers"
            / "charts"
            / "chart_handler.py"
        )
        tree = ast.parse(handler_path.read_text(encoding="utf-8"))

        imported_modules = set()
        imported_names = set()
        attribute_names = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported_modules.update(alias.name for alias in node.names)
                imported_names.update(alias.asname or alias.name.split(".")[-1] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported_modules.add(node.module)
                imported_names.update(alias.asname or alias.name for alias in node.names)
            elif isinstance(node, ast.Attribute):
                attribute_names.add(node.attr)

        forbidden_imports = sorted(
            module
            for module in imported_modules
            if any(module == prefix or module.startswith(f"{prefix}.") for prefix in forbidden_prefixes)
        )

        self.assertEqual(forbidden_imports, [])
        self.assertEqual(forbidden_names.intersection(imported_names), set())
        self.assertEqual({"place_order", "post_order"}.intersection(attribute_names), set())


if __name__ == "__main__":
    unittest.main()
