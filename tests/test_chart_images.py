import ast
from datetime import datetime
from pathlib import Path
import unittest

from app.charts.images import ChartImageService
from app.charts.schemas import (
    ChartAnalytics,
    ChartDataGap,
    ChartHistory,
    PositionValueChart,
    PositionValuePoint,
    PriceCandle,
)


PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


class FakeHistoryService:
    def __init__(self, history):
        self.history = history
        self.calls = []

    def get_history(self, ticker, range_name):
        self.calls.append((ticker, range_name))
        return self.history


class FakeAnalyticsService:
    def __init__(self, analytics=None, should_raise=False):
        self.analytics = analytics or ChartAnalytics()
        self.should_raise = should_raise
        self.calls = []

    def calculate(self, candles):
        self.calls.append(list(candles))
        if self.should_raise:
            raise AssertionError("analytics should not be calculated")
        return self.analytics


class FakePositionValueService:
    def __init__(self, result):
        self.result = result
        self.calls = []

    def get_position_value(self, ticker, range_name):
        self.calls.append((ticker, range_name))
        return self.result


def candle(day=1, close=101.0, volume=1000):
    return PriceCandle(
        time=datetime(2026, 5, day, 12, 0),
        open=100.0,
        high=102.0,
        low=99.0,
        close=close,
        volume=volume,
    )


def history(**kwargs):
    values = {
        "ticker": "SBER",
        "figi": "FIGI-SBER",
        "range": "month",
        "candles": [candle(1), candle(2, close=102.0)],
        "generated_at": datetime(2026, 5, 21, 12, 0),
        "source": "fake-source",
        "fetched_at": datetime(2026, 5, 21, 11, 59),
        "data_gaps": [],
        "errors": [],
        "disclaimer": (
            "Educational chart only. Hindsight-only analytics. Not a trading signal. "
            "Not investment advice. No broker orders were created."
        ),
    }
    values.update(kwargs)
    return ChartHistory(**values)


def position_value(**kwargs):
    values = {
        "ticker": "SBER",
        "figi": "FIGI-SBER",
        "range": "month",
        "quantity": 2.0,
        "value_series": [
            PositionValuePoint(datetime(2026, 5, 1, 12, 0), close_price=100.0, value=200.0),
            PositionValuePoint(datetime(2026, 5, 2, 12, 0), close_price=110.0, value=220.0),
        ],
        "generated_at": datetime(2026, 5, 21, 12, 0),
        "source": "fake-position-value",
        "fetched_at": datetime(2026, 5, 21, 11, 58),
        "data_gaps": [],
        "errors": [],
    }
    values.update(kwargs)
    return PositionValueChart(**values)


class ChartImageServiceTests(unittest.TestCase):
    def test_generates_png_bytes_for_fake_candles(self):
        fake_history = history()
        service = ChartImageService(FakeHistoryService(fake_history))

        result = service.render_png("SBER", "month")

        self.assertTrue(result.ok)
        self.assertEqual(result.mode, "price")
        self.assertEqual(result.errors, [])
        self.assertIsNotNone(result.png_bytes)
        self.assertTrue(result.png_bytes.startswith(PNG_SIGNATURE))
        self.assertGreater(len(result.png_bytes), 1000)
        self.assertEqual(result.content_type, "image/png")
        self.assertEqual(result.source_name, "fake-source")
        self.assertEqual(result.fetched_at, fake_history.fetched_at)

    def test_generates_png_bytes_for_price_mode_explicitly(self):
        fake_history = history()
        service = ChartImageService(FakeHistoryService(fake_history))

        result = service.render_png("SBER", "month", mode="price")

        self.assertTrue(result.ok)
        self.assertEqual(result.mode, "price")
        self.assertTrue(result.png_bytes.startswith(PNG_SIGNATURE))

    def test_analytics_enabled_calculates_overlay_and_still_generates_png(self):
        fake_history = history()
        fake_analytics = FakeAnalyticsService()
        service = ChartImageService(FakeHistoryService(fake_history), analytics_service=fake_analytics)

        result = service.render_png("SBER", "month")

        self.assertTrue(result.ok)
        self.assertTrue(result.png_bytes.startswith(PNG_SIGNATURE))
        self.assertEqual(fake_analytics.calls, [fake_history.candles])
        self.assertIs(result.analytics, fake_analytics.analytics)

    def test_analytics_disabled_does_not_request_overlays(self):
        fake_history = history()
        fake_analytics = FakeAnalyticsService(should_raise=True)
        service = ChartImageService(FakeHistoryService(fake_history), analytics_service=fake_analytics)

        result = service.render_png("SBER", "month", include_analytics=False)

        self.assertTrue(result.ok)
        self.assertTrue(result.png_bytes.startswith(PNG_SIGNATURE))
        self.assertEqual(fake_analytics.calls, [])
        self.assertIsNone(result.analytics)

    def test_position_value_mode_generates_png_without_analytics(self):
        fake_position_value = position_value()
        fake_position_service = FakePositionValueService(fake_position_value)
        fake_analytics = FakeAnalyticsService(should_raise=True)
        service = ChartImageService(
            FakeHistoryService(history()),
            analytics_service=fake_analytics,
            position_value_service=fake_position_service,
        )

        result = service.render_png("SBER", "month", include_analytics=True, mode="position_value")

        self.assertTrue(result.ok)
        self.assertEqual(result.mode, "position_value")
        self.assertTrue(result.png_bytes.startswith(PNG_SIGNATURE))
        self.assertEqual(fake_position_service.calls, [("SBER", "month")])
        self.assertEqual(fake_analytics.calls, [])
        self.assertIs(result.position_value, fake_position_value)
        self.assertEqual(result.source_name, "fake-position-value")
        self.assertEqual(result.fetched_at, fake_position_value.fetched_at)
        self.assertIn("current position quantity valued at historical close prices", result.position_value.disclaimer)
        self.assertIn("not historical holdings", result.position_value.disclaimer)

    def test_position_value_mode_returns_structured_error_without_png(self):
        fake_position_value = position_value(
            value_series=[],
            errors=["Ticker SBER is not in the current portfolio."],
        )
        service = ChartImageService(
            FakeHistoryService(history()),
            position_value_service=FakePositionValueService(fake_position_value),
        )

        result = service.render_png("SBER", "month", mode="position_value")

        self.assertFalse(result.ok)
        self.assertIsNone(result.png_bytes)
        self.assertEqual(result.mode, "position_value")
        self.assertIn("not in the current portfolio", result.errors[0])

    def test_no_candles_returns_error_and_gap_without_png(self):
        fake_history = history(
            candles=[],
            data_gaps=[ChartDataGap("price_history", "No candles were returned.", "low")],
        )
        service = ChartImageService(FakeHistoryService(fake_history))

        result = service.render_png("SBER", "month")

        self.assertFalse(result.ok)
        self.assertIsNone(result.png_bytes)
        self.assertTrue(any("No candles" in error for error in result.errors))
        self.assertTrue(any(gap.category == "price_history" for gap in result.data_gaps))

    def test_invalid_range_history_returns_error_without_png(self):
        fake_history = history(
            candles=[],
            range="bad",
            data_gaps=[ChartDataGap("range", "Unsupported chart range.", "high")],
            errors=["Unsupported chart range: bad."],
        )
        fake_service = FakeHistoryService(fake_history)
        service = ChartImageService(fake_service)

        result = service.render_png("SBER", "bad")

        self.assertEqual(fake_service.calls, [("SBER", "bad")])
        self.assertFalse(result.ok)
        self.assertIsNone(result.png_bytes)
        self.assertEqual(result.errors, ["Unsupported chart range: bad."])
        self.assertTrue(any(gap.category == "range" for gap in result.data_gaps))

    def test_chart_image_service_imports_no_order_signal_or_rating_modules(self):
        forbidden_prefixes = (
            "app.services.orders",
            "app.client.handlers.orders",
            "app.client.handlers.signals",
            "app.client.signals",
            "app.client.strategy",
            "mplfinance",
            "seaborn",
            "keras",
            "tensorflow",
        )
        forbidden_names = {"OrderService", "place_order", "post_order", "BUY", "SELL", "HOLD", "WATCH", "AVOID"}
        service_path = Path(__file__).resolve().parents[1] / "app" / "charts" / "images.py"
        tree = ast.parse(service_path.read_text(encoding="utf-8"))

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
