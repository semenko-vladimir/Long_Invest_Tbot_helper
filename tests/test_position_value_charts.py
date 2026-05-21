import ast
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
import unittest

from app.charts.position_values import PositionValueChartService
from app.charts.schemas import ChartHistory, PriceCandle


def candle(day: int, close: float) -> PriceCandle:
    return PriceCandle(
        time=datetime(2026, 5, day, 12, 0),
        open=close - 1,
        high=close + 1,
        low=close - 2,
        close=close,
        volume=1000,
    )


def history(range_name: str = "month", candles=None, errors=None) -> ChartHistory:
    return ChartHistory(
        ticker="SBER",
        figi="FIGI-SBER",
        range=range_name,
        candles=list(candles if candles is not None else [candle(1, 100.0), candle(2, 110.0)]),
        generated_at=datetime(2026, 5, 21, 12, 0),
        source="fake-history",
        data_gaps=[],
        errors=list(errors or []),
    )


def position(ticker: str = "SBER", quantity=2.0):
    return SimpleNamespace(
        ticker=ticker,
        name=ticker,
        quantity=quantity,
        quantity_display=str(quantity),
        figi=f"FIGI-{ticker}",
    )


class FakePortfolioService:
    def __init__(self, *, positions=None, empty=False, error=None):
        self.view = SimpleNamespace(
            positions=list(positions or []),
            empty=empty,
            error=error,
        )

    def get_portfolio_view(self):
        return self.view


class FakeHistoryService:
    def __init__(self, histories=None):
        self.histories = histories or {"month": history("month")}
        self.calls = []

    def get_history(self, ticker, range_name):
        self.calls.append((ticker, range_name))
        return self.histories[range_name]


class PositionValueChartServiceTests(unittest.TestCase):
    def test_computes_current_quantity_times_close_price(self):
        history_service = FakeHistoryService()
        service = PositionValueChartService(
            portfolio_service=FakePortfolioService(positions=[position(quantity=3)]),
            history_service=history_service,
        )

        result = service.get_position_value("sber", "month")

        self.assertTrue(result.ok)
        self.assertEqual(result.quantity, 3.0)
        self.assertEqual([point.close_price for point in result.value_series], [100.0, 110.0])
        self.assertEqual([point.value for point in result.value_series], [300.0, 330.0])
        self.assertEqual(history_service.calls, [("SBER", "month")])
        self.assertIn("current position quantity valued at historical close prices", result.disclaimer)
        self.assertIn("not historical holdings", result.disclaimer)
        self.assertIn("no broker orders were created", result.disclaimer)

    def test_rejects_ticker_not_in_portfolio_without_history_lookup(self):
        history_service = FakeHistoryService()
        service = PositionValueChartService(
            portfolio_service=FakePortfolioService(positions=[position("GAZP", 5)]),
            history_service=history_service,
        )

        result = service.get_position_value("SBER", "month")

        self.assertFalse(result.ok)
        self.assertEqual(result.value_series, [])
        self.assertIn("not in the current portfolio", result.errors[0])
        self.assertEqual(history_service.calls, [])

    def test_rejects_zero_or_missing_quantity_without_history_lookup(self):
        for quantity in (0, None):
            with self.subTest(quantity=quantity):
                history_service = FakeHistoryService()
                service = PositionValueChartService(
                    portfolio_service=FakePortfolioService(positions=[position(quantity=quantity)]),
                    history_service=history_service,
                )

                result = service.get_position_value("SBER", "month")

                self.assertFalse(result.ok)
                self.assertIn("zero or missing current quantity", result.errors[0])
                self.assertEqual(history_service.calls, [])

    def test_returns_clear_no_candles_error(self):
        service = PositionValueChartService(
            portfolio_service=FakePortfolioService(positions=[position(quantity=2)]),
            history_service=FakeHistoryService({"month": history(candles=[])}),
        )

        result = service.get_position_value("SBER", "month")

        self.assertFalse(result.ok)
        self.assertEqual(result.value_series, [])
        self.assertTrue(any("No candles are available" in error for error in result.errors))
        self.assertTrue(any(gap.category == "price_history" for gap in result.data_gaps))

    def test_uses_selected_range_candles_only(self):
        history_service = FakeHistoryService(
            {
                "week": history("week", [candle(1, 10.0)]),
                "month": history("month", [candle(1, 100.0), candle(2, 120.0)]),
            }
        )
        service = PositionValueChartService(
            portfolio_service=FakePortfolioService(positions=[position(quantity=4)]),
            history_service=history_service,
        )

        result = service.get_position_value("SBER", "week")

        self.assertEqual(history_service.calls, [("SBER", "week")])
        self.assertEqual([point.value for point in result.value_series], [40.0])

    def test_position_value_service_imports_no_order_signal_or_rating_modules(self):
        forbidden_prefixes = (
            "app.services.orders",
            "app.client.handlers.orders",
            "app.client.handlers.signals",
            "app.client.signals",
            "app.client.strategy",
        )
        forbidden_names = {"OrderService", "place_order", "post_order", "BUY", "SELL", "HOLD", "WATCH", "AVOID"}
        service_path = Path(__file__).resolve().parents[1] / "app" / "charts" / "position_values.py"
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
