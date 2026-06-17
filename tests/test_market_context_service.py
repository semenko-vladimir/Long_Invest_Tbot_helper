import ast
from datetime import date, datetime
from pathlib import Path
import unittest

from app.data_sources.schemas import DATA_SOURCE_MOEX_ISS, DELAY_STATUS_DELAYED_PUBLIC_ISS
from app.integrations.moex_iss import MOEXDailyCandle, MOEXDailyCandlesResult, MOEXDataGap
from app.research.market_context import MarketContextService, MOEXMarketContextAdapter


def moex_index_candle(ticker="IMOEX", day=1, close=100.0, fetched_at=None):
    fetched_at = fetched_at or datetime(2026, 5, 23, 12, 0)
    return MOEXDailyCandle(
        ticker=ticker,
        begin=datetime(2026, 5, day, 0, 0),
        end=datetime(2026, 5, day, 23, 59, 59),
        trade_date=date(2026, 5, day),
        open=close - 1,
        high=close + 1,
        low=close - 2,
        close=close,
        fetched_at=fetched_at,
    )


class FakeMarketContextClient:
    def __init__(self, results=None, errors=None):
        self.results = dict(results or {})
        self.errors = dict(errors or {})
        self.calls = []

    def get_index_daily_candles_result(self, ticker, from_date=None, till_date=None):
        self.calls.append((ticker, from_date, till_date))
        if ticker in self.errors:
            raise self.errors[ticker]
        return self.results[ticker]


class MarketContextServiceTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 5, 23, 12, 0)

    def test_context_includes_latest_close_change_and_freshness(self):
        fetched_at = datetime(2026, 5, 23, 11, 0)
        client = FakeMarketContextClient(
            {
                "IMOEX": MOEXDailyCandlesResult(
                    ticker="IMOEX",
                    fetched_at=fetched_at,
                    candles=[
                        moex_index_candle("IMOEX", day=1, close=100.0, fetched_at=fetched_at),
                        moex_index_candle("IMOEX", day=22, close=110.0, fetched_at=fetched_at),
                    ],
                )
            }
        )
        service = MarketContextService(
            client=client,
            index_tickers=("IMOEX",),
            period_days=31,
            now_provider=lambda: self.now,
        )

        result = service.get_context()

        self.assertEqual(client.calls, [("IMOEX", date(2026, 4, 22), date(2026, 5, 23))])
        self.assertEqual(result.errors, [])
        self.assertEqual(result.data_gaps, [])
        self.assertEqual(result.payload["source"], DATA_SOURCE_MOEX_ISS)
        self.assertEqual(result.payload["as_of_date"], "2026-05-22")
        self.assertEqual(result.payload["delay_status"], DELAY_STATUS_DELAYED_PUBLIC_ISS)
        index = result.payload["indexes"][0]
        self.assertEqual(index["ticker"], "IMOEX")
        self.assertEqual(index["latest_close"], 110.0)
        self.assertAlmostEqual(index["recent_change_pct"], 10.0)
        self.assertEqual(index["as_of_date"], "2026-05-22")
        self.assertEqual(index["fetched_at"], fetched_at)

    def test_context_preserves_partial_failures_as_data_gaps_and_errors(self):
        fetched_at = datetime(2026, 5, 23, 11, 0)
        client = FakeMarketContextClient(
            results={
                "IMOEX": MOEXDailyCandlesResult(
                    ticker="IMOEX",
                    fetched_at=fetched_at,
                    candles=[moex_index_candle("IMOEX", day=22, close=110.0, fetched_at=fetched_at)],
                    data_gaps=[MOEXDataGap("price_history", "Only one candle was available.", "low")],
                )
            },
            errors={"RTSI": RuntimeError("source unavailable")},
        )
        service = MarketContextService(
            client=client,
            index_tickers=("IMOEX", "RTSI"),
            now_provider=lambda: self.now,
        )

        result = service.get_context()

        self.assertEqual(len(result.payload["indexes"]), 2)
        self.assertTrue(any(gap.category == "market_context" for gap in result.data_gaps))
        self.assertTrue(any(gap.category == "price_history" for gap in result.data_gaps))
        self.assertTrue(any("source unavailable" in error for error in result.errors))
        self.assertTrue(result.payload["data_gaps"])
        self.assertTrue(result.payload["errors"])
        self.assertEqual(result.payload["indexes"][1]["ticker"], "RTSI")
        self.assertIsNone(result.payload["indexes"][1]["latest_close"])

    def test_adapter_returns_market_context_without_rating_or_order_methods(self):
        fetched_at = datetime(2026, 5, 23, 11, 0)
        client = FakeMarketContextClient(
            {
                "IMOEX": MOEXDailyCandlesResult(
                    ticker="IMOEX",
                    fetched_at=fetched_at,
                    candles=[
                        moex_index_candle("IMOEX", day=1, close=100.0, fetched_at=fetched_at),
                        moex_index_candle("IMOEX", day=22, close=105.0, fetched_at=fetched_at),
                    ],
                )
            }
        )
        service = MarketContextService(
            client=client,
            index_tickers=("IMOEX",),
            now_provider=lambda: self.now,
        )
        adapter = MOEXMarketContextAdapter(service=service, now_provider=lambda: self.now)

        result = adapter.fetch("sber")

        self.assertEqual(result.source_name, DATA_SOURCE_MOEX_ISS)
        self.assertEqual(result.errors, [])
        self.assertEqual(result.data["ticker"], "SBER")
        self.assertIn("market_context", result.data)
        self.assertNotIn("educational_rating", result.data)
        self.assertIn("No broker token is used", result.freshness.notes)
        self.assertEqual(result.freshness.delay_status, DELAY_STATUS_DELAYED_PUBLIC_ISS)
        forbidden_methods = {"place_order", "post_order", "preview", "execute", "buy", "sell", "execute_order"}
        self.assertEqual(forbidden_methods.intersection(dir(adapter)), set())

    def test_market_context_module_imports_no_order_signal_or_rating_modules(self):
        forbidden_prefixes = (
            "app.services.orders",
            "app.client.orders",
            "app.client.handlers.orders",
            "app.client.handlers.signals",
            "app.client.signals",
            "app.client.strategy",
            "app.client.api.signals_client",
            "app.client.api.strategy_client",
            "app.integrations.tinvest",
            "keras",
            "tensorflow",
            "g4f",
        )
        forbidden_names = {"OrderService", "manual_order_handler", "place_order", "post_order"}
        module_path = Path(__file__).resolve().parents[1] / "app" / "research" / "market_context.py"
        tree = ast.parse(module_path.read_text(encoding="utf-8"))

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
