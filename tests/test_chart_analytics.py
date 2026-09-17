import ast
from datetime import datetime, timedelta
from pathlib import Path
import unittest

from app.charts.analytics import ENTRY_LABEL, EXIT_LABEL, ChartAnalyticsService
from app.charts.schemas import PriceCandle


def candle(day: int, close: float) -> PriceCandle:
    candle_time = datetime(2026, 5, 1, 10, 0) + timedelta(days=day - 1)
    return PriceCandle(
        time=candle_time,
        open=close,
        high=close,
        low=close,
        close=close,
        volume=None,
    )


def candle_with_volume(day: int, close: float, volume: int) -> PriceCandle:
    candle_time = candle_time_for(day)
    return PriceCandle(
        time=candle_time,
        open=close - 1,
        high=close + 2,
        low=close - 2,
        close=close,
        volume=volume,
    )


def candle_time(day: int) -> datetime:
    return candle_time_for(day)


def candle_time_for(day: int) -> datetime:
    return datetime(2026, 5, 1, 10, 0) + timedelta(days=day - 1)


class ChartAnalyticsServiceTests(unittest.TestCase):
    def setUp(self):
        self.service = ChartAnalyticsService()

    def test_min_marker_and_post_min_max_marker_use_earliest_matches(self):
        analytics = self.service.calculate(
            [
                candle(1, 12.0),
                candle(2, 8.0),
                candle(3, 8.0),
                candle(4, 15.0),
                candle(5, 15.0),
                candle(6, 11.0),
            ]
        )

        self.assertIsNotNone(analytics.entry_marker)
        self.assertEqual(analytics.entry_marker.label, ENTRY_LABEL)
        self.assertEqual(analytics.entry_marker.time, candle_time(2))
        self.assertEqual(analytics.entry_marker.close, 8.0)

        self.assertIsNotNone(analytics.exit_marker)
        self.assertEqual(analytics.exit_marker.label, EXIT_LABEL)
        self.assertEqual(analytics.exit_marker.time, candle_time(4))
        self.assertEqual(analytics.exit_marker.close, 15.0)
        self.assertAlmostEqual(analytics.hindsight_return_pct, 87.5)

    def test_no_exit_when_minimum_is_last_candle(self):
        analytics = self.service.calculate([candle(1, 12.0), candle(2, 10.0), candle(3, 7.0)])

        self.assertIsNotNone(analytics.entry_marker)
        self.assertEqual(analytics.entry_marker.time, candle_time(3))
        self.assertIsNone(analytics.exit_marker)
        self.assertIsNone(analytics.hindsight_return_pct)

    def test_max_drawdown_uses_prior_peak_and_later_trough_closes(self):
        analytics = self.service.calculate(
            [candle(1, 100.0), candle(2, 120.0), candle(3, 90.0), candle(4, 95.0)]
        )

        self.assertIsNotNone(analytics.max_drawdown)
        self.assertEqual(analytics.max_drawdown.peak_time, candle_time(2))
        self.assertEqual(analytics.max_drawdown.trough_time, candle_time(3))
        self.assertAlmostEqual(analytics.max_drawdown.drawdown_pct, -25.0)

    def test_empty_and_one_candle_series_return_partial_annotations(self):
        empty = self.service.calculate([])
        self.assertIsNone(empty.entry_marker)
        self.assertIsNone(empty.exit_marker)
        self.assertIsNone(empty.max_drawdown)
        self.assertIsNone(empty.range_position)
        self.assertEqual(empty.sma20.points, [])
        self.assertEqual(empty.sma50.points, [])

        single = self.service.calculate([candle(1, 10.0)])
        self.assertIsNotNone(single.entry_marker)
        self.assertIsNone(single.exit_marker)
        self.assertIsNone(single.max_drawdown)
        self.assertIsNotNone(single.range_position)
        self.assertEqual(single.range_position.vs_range_high_pct, 0.0)
        self.assertEqual(single.range_position.vs_range_low_pct, 0.0)

    def test_sma_uses_only_current_and_prior_candles(self):
        analytics = self.service.calculate([candle(day, float(day)) for day in range(1, 56)])

        self.assertEqual(len(analytics.sma20.points), 36)
        self.assertEqual(analytics.sma20.points[0].time, candle_time(20))
        self.assertAlmostEqual(analytics.sma20.points[0].value, 10.5)
        self.assertEqual(analytics.sma20.points[1].time, candle_time(21))
        self.assertAlmostEqual(analytics.sma20.points[1].value, 11.5)

        self.assertEqual(len(analytics.sma50.points), 6)
        self.assertEqual(analytics.sma50.points[0].time, candle_time(50))
        self.assertAlmostEqual(analytics.sma50.points[0].value, 25.5)

    def test_extended_indicators_use_only_current_and_prior_candles(self):
        analytics = self.service.calculate([candle(day, float(day)) for day in range(1, 61)])

        self.assertAlmostEqual(analytics.range_return_pct, 5900.0)
        self.assertAlmostEqual(analytics.latest_change_pct, (60.0 - 59.0) / 59.0 * 100)
        self.assertIsNotNone(analytics.periodic_volatility_pct)
        self.assertIsNotNone(analytics.annualized_volatility_pct)

        self.assertEqual(analytics.ema12.points[0].time, candle_time(12))
        self.assertAlmostEqual(analytics.ema12.points[0].value, 6.5)
        self.assertEqual(analytics.ema26.points[0].time, candle_time(26))
        self.assertAlmostEqual(analytics.ema26.points[0].value, 13.5)

        self.assertEqual(analytics.rsi14.points[0].time, candle_time(15))
        self.assertAlmostEqual(analytics.rsi14.points[0].value, 100.0)
        self.assertEqual(analytics.bollinger20.points[0].time, candle_time(20))
        self.assertAlmostEqual(analytics.bollinger20.points[0].middle, 10.5)
        self.assertTrue(analytics.bollinger20.points[0].upper > analytics.bollinger20.points[0].middle)
        self.assertTrue(analytics.macd.points)

    def test_volume_stats_and_atr_are_reported_when_data_exists(self):
        analytics = self.service.calculate(
            [
                candle_with_volume(day, 100.0 + day, volume=day * 100)
                for day in range(1, 21)
            ]
        )

        self.assertEqual(analytics.volume_stats.latest_volume, 2000)
        self.assertAlmostEqual(analytics.volume_stats.average_volume, 1050.0)
        self.assertAlmostEqual(analytics.volume_stats.latest_vs_average_pct, (2000 - 1050.0) / 1050.0 * 100)
        self.assertEqual(analytics.atr14.points[0].time, candle_time(14))
        self.assertGreater(analytics.atr14.points[0].value, 0)

    def test_calculation_sorts_candles_by_time_before_analytics(self):
        analytics = self.service.calculate([candle(3, 14.0), candle(1, 10.0), candle(2, 12.0)])

        self.assertEqual(analytics.entry_marker.time, candle_time(1))
        self.assertEqual(analytics.exit_marker.time, candle_time(3))

    def test_chart_analytics_imports_no_order_signal_or_rating_modules(self):
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
        forbidden_names = {
            "OrderService",
            "place_order",
            "post_order",
            "preview",
            "execute",
            "BUY",
            "SELL",
            "HOLD",
            "WATCH",
            "AVOID",
        }
        service_path = Path(__file__).resolve().parents[1] / "app" / "charts" / "analytics.py"
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
        self.assertEqual({"preview", "execute", "place_order", "post_order"}.intersection(attribute_names), set())


if __name__ == "__main__":
    unittest.main()
