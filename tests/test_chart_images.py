import ast
from datetime import datetime
from pathlib import Path
import unittest

from app.charts.images import ChartImageService
from app.charts.schemas import ChartDataGap, ChartHistory, PriceCandle


PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


class FakeHistoryService:
    def __init__(self, history):
        self.history = history
        self.calls = []

    def get_history(self, ticker, range_name):
        self.calls.append((ticker, range_name))
        return self.history


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
        "data_gaps": [],
        "errors": [],
        "disclaimer": "Educational chart only. Not investment advice.",
    }
    values.update(kwargs)
    return ChartHistory(**values)


class ChartImageServiceTests(unittest.TestCase):
    def test_generates_png_bytes_for_fake_candles(self):
        fake_history = history()
        service = ChartImageService(FakeHistoryService(fake_history))

        result = service.render_png("SBER", "month")

        self.assertTrue(result.ok)
        self.assertEqual(result.errors, [])
        self.assertIsNotNone(result.png_bytes)
        self.assertTrue(result.png_bytes.startswith(PNG_SIGNATURE))
        self.assertGreater(len(result.png_bytes), 1000)
        self.assertEqual(result.content_type, "image/png")

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
