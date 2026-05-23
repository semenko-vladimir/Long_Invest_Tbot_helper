import ast
from datetime import date, datetime
from pathlib import Path
import unittest

from app.charts.adapters import FallbackChartDataAdapter
from app.charts.moex_iss_candles_adapter import MOEXISSCandlesAdapter
from app.charts.schemas import ChartAdapterResult, ChartDataGap, PriceCandle
from app.charts.services import ChartHistoryService, normalize_chart_mode, normalize_chart_range
from app.integrations.moex_iss import MOEXDailyCandle, MOEXDailyCandlesResult, MOEXDataGap


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


class FakeMOEXDailyCandlesClient:
    def __init__(self, result=None, error=None):
        self.result = result
        self.error = error
        self.calls = []

    def get_daily_candles_result(self, ticker, from_date=None, till_date=None):
        self.calls.append((ticker, from_date, till_date))
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


def moex_candle(day=1, close=101.0, fetched_at=None):
    fetched_at = fetched_at or datetime(2026, 5, 21, 12, 0)
    return MOEXDailyCandle(
        ticker="SBER",
        begin=datetime(2026, 5, day, 0, 0),
        end=datetime(2026, 5, day, 23, 59, 59),
        trade_date=date(2026, 5, day),
        open=100.0,
        high=102.0,
        low=99.0,
        close=close,
        volume=1000,
        value=close * 1000,
        fetched_at=fetched_at,
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
                fetched_at=self.now,
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
        self.assertEqual(history.fetched_at, self.now)
        self.assertEqual(history.source, "fake-chart-source")
        self.assertEqual(history.source_name, "fake-chart-source")
        self.assertEqual(history.errors, [])
        self.assertEqual(history.data_gaps, [])
        self.assertEqual(adapter.calls, [("SBER", "six_months")])
        self.assertIn("Hindsight-only analytics", history.disclaimer)
        self.assertIn("Not a trading signal", history.disclaimer)
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

    def test_fallback_adapter_keeps_tinvest_success_path(self):
        primary = FakeChartAdapter(
            ChartAdapterResult(
                source_name="t-invest-candles",
                ticker="SBER",
                figi="FIGI-SBER",
                fetched_at=self.now,
                candles=[candle(1), candle(2, close=102.0)],
            )
        )
        fallback = FakeChartAdapter(
            ChartAdapterResult(
                source_name="MOEX ISS",
                ticker="SBER",
                candles=[candle(3, close=103.0)],
            )
        )
        service = ChartHistoryService(
            adapter=FallbackChartDataAdapter(primary=primary, fallback=fallback),
            now_provider=lambda: self.now,
        )

        history = service.get_history("SBER", "month")

        self.assertEqual(primary.calls, [("SBER", "month")])
        self.assertEqual(fallback.calls, [])
        self.assertEqual(history.source, "t-invest-candles")
        self.assertEqual(history.figi, "FIGI-SBER")
        self.assertEqual(len(history.candles), 2)
        self.assertEqual(history.errors, [])

    def test_fallback_adapter_uses_moex_when_tinvest_unavailable(self):
        moex_fetched_at = datetime(2026, 5, 21, 13, 0)
        primary = FakeChartAdapter(
            ChartAdapterResult(
                source_name="t-invest-candles",
                ticker="SBER",
                data_gaps=[ChartDataGap("authentication", "T-Invest token is unavailable.", "high")],
                errors=["No T-Invest token is configured."],
            )
        )
        fallback = FakeChartAdapter(
            ChartAdapterResult(
                source_name="MOEX ISS",
                ticker="SBER",
                fetched_at=moex_fetched_at,
                candles=[candle(1), candle(2, close=102.0)],
            )
        )
        service = ChartHistoryService(
            adapter=FallbackChartDataAdapter(primary=primary, fallback=fallback),
            now_provider=lambda: self.now,
        )

        history = service.get_history("sber", "month")

        self.assertEqual(primary.calls, [("SBER", "month")])
        self.assertEqual(fallback.calls, [("SBER", "month")])
        self.assertEqual(history.source, "MOEX ISS")
        self.assertEqual(history.fetched_at, moex_fetched_at)
        self.assertEqual(len(history.candles), 2)
        self.assertEqual(history.errors, [])
        self.assertTrue(any(gap.category == "source_fallback" for gap in history.data_gaps))

    def test_fallback_adapter_returns_explicit_error_when_both_sources_unavailable(self):
        primary = FakeChartAdapter(
            ChartAdapterResult(
                source_name="t-invest-candles",
                ticker="SBER",
                data_gaps=[ChartDataGap("price_history", "T-Invest candles unavailable.", "medium")],
                errors=["T-Invest candle lookup failed."],
            )
        )
        fallback = FakeChartAdapter(
            ChartAdapterResult(
                source_name="MOEX ISS",
                ticker="SBER",
                data_gaps=[ChartDataGap("price_history", "MOEX ISS returned no daily candles.", "low")],
                errors=["MOEX ISS candle lookup failed."],
            )
        )
        service = ChartHistoryService(
            adapter=FallbackChartDataAdapter(primary=primary, fallback=fallback),
            now_provider=lambda: self.now,
        )

        history = service.get_history("SBER", "month")

        self.assertEqual(history.candles, [])
        self.assertEqual(history.source, "t-invest-candles + MOEX ISS")
        self.assertTrue(any("T-Invest candle lookup failed" in error for error in history.errors))
        self.assertTrue(any("MOEX ISS candle lookup failed" in error for error in history.errors))
        self.assertTrue(any(gap.category == "price_history" for gap in history.data_gaps))

    def test_moex_iss_chart_adapter_maps_daily_candles(self):
        fetched_at = datetime(2026, 5, 21, 13, 0)
        client = FakeMOEXDailyCandlesClient(
            MOEXDailyCandlesResult(
                ticker="SBER",
                fetched_at=fetched_at,
                candles=[moex_candle(20, close=250.5, fetched_at=fetched_at)],
                data_gaps=[MOEXDataGap("sample", "Sample gap.", "low")],
            )
        )
        adapter = MOEXISSCandlesAdapter(client=client, now_provider=lambda: self.now)

        result = adapter.fetch_candles(" sber ", "day")

        self.assertEqual(client.calls, [("SBER", date(2026, 5, 20), date(2026, 5, 21))])
        self.assertEqual(result.source_name, "MOEX ISS")
        self.assertEqual(result.ticker, "SBER")
        self.assertEqual(result.fetched_at, fetched_at)
        self.assertEqual(result.errors, [])
        self.assertEqual(len(result.candles), 1)
        self.assertIsInstance(result.candles[0], PriceCandle)
        self.assertEqual(result.candles[0].close, 250.5)
        self.assertTrue(any(gap.category == "sample" for gap in result.data_gaps))
        self.assertTrue(any(gap.category == "granularity" for gap in result.data_gaps))

    def test_range_normalization(self):
        self.assertEqual(normalize_chart_range("day"), "day")
        self.assertEqual(normalize_chart_range("six-month"), "six_months")
        self.assertEqual(normalize_chart_range("1y"), "year")
        self.assertEqual(normalize_chart_range("max"), "all")
        self.assertIsNone(normalize_chart_range("bad"))

    def test_chart_mode_normalization(self):
        self.assertEqual(normalize_chart_mode("price"), "price")
        self.assertEqual(normalize_chart_mode("position-value"), "position_value")
        self.assertEqual(normalize_chart_mode("current_position_value"), "position_value")
        self.assertIsNone(normalize_chart_mode("bad"))

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
        imported_modules = set()
        imported_names = set()
        attribute_names = set()
        charts_dir = Path(__file__).resolve().parents[1] / "app" / "charts"
        service_paths = [
            charts_dir / "services.py",
            charts_dir / "adapters.py",
            charts_dir / "moex_iss_candles_adapter.py",
        ]
        for service_path in service_paths:
            tree = ast.parse(service_path.read_text(encoding="utf-8"))
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
