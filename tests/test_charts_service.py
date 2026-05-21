import ast
from datetime import datetime
from pathlib import Path
import unittest

from app.charts.schemas import ChartAdapterResult, ChartDataGap, PriceCandle
from app.charts.services import ChartHistoryService, normalize_chart_range


class FakeChartAdapter:
    source_name = "fake-chart-source"

    def __init__(self, result=None, error=None):
        self.result = result
        self.error = error
        self.calls = []

    def fetch_candles(self, ticker, range_name):
        self.calls.append((ticker, range_name))
        if self.error:
            raise self.error
        return self.result


def candle(day=1, close=101.0):
    return PriceCandle(
        time=datetime(2026, 5, day, 10, 0),
        open=100.0,
        high=102.0,
        low=99.0,
        close=close,
        volume=1000,
    )


class ChartHistoryServiceTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 5, 21, 12, 0)

    def test_returns_normalized_history_for_supported_range(self):
        adapter = FakeChartAdapter(
            ChartAdapterResult(
                source_name="fake-chart-source",
                ticker="SBER",
                figi="FIGI-SBER",
                candles=[candle(1), candle(2, close=102.0)],
            )
        )
        service = ChartHistoryService(adapter=adapter, now_provider=lambda: self.now)

        history = service.get_history(" sber ", "6m")

        self.assertEqual(history.ticker, "SBER")
        self.assertEqual(history.figi, "FIGI-SBER")
        self.assertEqual(history.range, "six_months")
        self.assertEqual(len(history.candles), 2)
        self.assertEqual(history.generated_at, self.now)
        self.assertEqual(history.source, "fake-chart-source")
        self.assertEqual(history.errors, [])
        self.assertEqual(history.data_gaps, [])
        self.assertEqual(adapter.calls, [("SBER", "six_months")])
        self.assertIn("must not trigger broker orders", history.disclaimer)

    def test_unsupported_range_returns_structured_error_without_adapter_call(self):
        adapter = FakeChartAdapter()
        service = ChartHistoryService(adapter=adapter, now_provider=lambda: self.now)

        history = service.get_history("SBER", "intraday_scalp")

        self.assertEqual(adapter.calls, [])
        self.assertEqual(history.ticker, "SBER")
        self.assertEqual(history.range, "intraday_scalp")
        self.assertEqual(history.candles, [])
        self.assertTrue(any("Unsupported chart range" in error for error in history.errors))
        self.assertTrue(any(gap.category == "range" for gap in history.data_gaps))

    def test_invalid_ticker_returns_structured_error_without_adapter_call(self):
        adapter = FakeChartAdapter()
        service = ChartHistoryService(adapter=adapter, now_provider=lambda: self.now)

        history = service.get_history("***", "month")

        self.assertEqual(adapter.calls, [])
        self.assertEqual(history.ticker, "")
        self.assertEqual(history.range, "month")
        self.assertTrue(any(gap.category == "ticker" for gap in history.data_gaps))
        self.assertTrue(history.errors)

    def test_no_candles_adds_explicit_gap(self):
        adapter = FakeChartAdapter(
            ChartAdapterResult(
                source_name="fake-chart-source",
                ticker="SBER",
                figi="FIGI-SBER",
                candles=[],
            )
        )
        service = ChartHistoryService(adapter=adapter, now_provider=lambda: self.now)

        history = service.get_history("SBER", "month")

        self.assertEqual(history.errors, [])
        self.assertTrue(any(gap.category == "price_history" for gap in history.data_gaps))

    def test_adapter_failure_returns_structured_error(self):
        adapter = FakeChartAdapter(error=RuntimeError("source unavailable"))
        service = ChartHistoryService(adapter=adapter, now_provider=lambda: self.now)

        history = service.get_history("SBER", "month")

        self.assertEqual(history.candles, [])
        self.assertTrue(any("adapter failed" in error for error in history.errors))
        self.assertTrue(any(gap.category == "adapter" for gap in history.data_gaps))

    def test_preserves_adapter_data_gaps_and_errors(self):
        adapter = FakeChartAdapter(
            ChartAdapterResult(
                source_name="fake-chart-source",
                ticker="SBER",
                figi=None,
                data_gaps=[ChartDataGap("instrument_identity", "FIGI unavailable.", "high")],
                errors=["Instrument identity lookup failed."],
            )
        )
        service = ChartHistoryService(adapter=adapter, now_provider=lambda: self.now)

        history = service.get_history("SBER", "week")

        self.assertTrue(any(gap.category == "instrument_identity" for gap in history.data_gaps))
        self.assertTrue(any(gap.category == "price_history" for gap in history.data_gaps))
        self.assertEqual(history.errors, ["Instrument identity lookup failed."])

    def test_range_normalization(self):
        self.assertEqual(normalize_chart_range("day"), "day")
        self.assertEqual(normalize_chart_range("six-month"), "six_months")
        self.assertEqual(normalize_chart_range("1y"), "year")
        self.assertEqual(normalize_chart_range("max"), "all")
        self.assertIsNone(normalize_chart_range("bad"))

    def test_chart_services_import_no_order_signal_or_plotting_modules(self):
        forbidden_prefixes = (
            "app.services.orders",
            "app.client.handlers.orders",
            "app.client.handlers.signals",
            "app.client.signals",
            "app.client.strategy",
            "matplotlib",
            "plotly",
            "seaborn",
            "keras",
            "tensorflow",
        )
        forbidden_names = {"OrderService", "place_order", "post_order", "BUY", "SELL", "HOLD", "WATCH", "AVOID"}
        service_path = Path(__file__).resolve().parents[1] / "app" / "charts" / "services.py"
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
