from types import SimpleNamespace
import unittest
from unittest import mock

from app.integrations.tinvest import TInvestBroker
from app.services.price_conditions import PriceConditionResult, PriceConditionService


class FakeBroker:
    def __init__(self, prices=None, error=None):
        self.prices = prices if prices is not None else [100.0, 110.0, 120.0]
        self.error = error
        self.calls = []

    def get_closing_prices(self, token, ticker, days):
        self.calls.append((token, ticker, days))
        if self.error:
            raise self.error
        return self.prices


def plan(**kwargs):
    values = {
        "ticker": "SBER",
        "operation": "buy",
        "price_rule": "any",
        "price_limit": None,
        "pct_threshold": None,
        "avg_period_days": None,
    }
    values.update(kwargs)
    return SimpleNamespace(**values)


class PriceConditionServiceTests(unittest.TestCase):
    def service(self, broker=None):
        return PriceConditionService(token_provider=lambda: "token", broker=broker or FakeBroker())

    def test_result_shape(self):
        result = PriceConditionResult(allowed=True, reason="ok", current_price=10.0, limit_price=12.0)

        self.assertTrue(result.allowed)
        self.assertEqual(result.reason, "ok")
        self.assertEqual(result.current_price, 10.0)
        self.assertEqual(result.limit_price, 12.0)

    def test_any_rule_allows_without_broker_call(self):
        broker = FakeBroker()
        result = self.service(broker).check(plan=plan(price_rule="any"), current_price=999.0)

        self.assertTrue(result.allowed)
        self.assertEqual(result.current_price, 999.0)
        self.assertEqual(broker.calls, [])

    def test_current_market_rule_allows(self):
        result = self.service().check(plan=plan(price_rule="current_market"), current_price=101.0)

        self.assertTrue(result.allowed)

    def test_max_price_buy_allows_at_or_below_limit(self):
        result = self.service().check(
            plan=plan(price_rule="max_price", operation="buy", price_limit=310.0),
            current_price=309.5,
        )

        self.assertTrue(result.allowed)
        self.assertEqual(result.limit_price, 310.0)

    def test_max_price_buy_blocks_above_limit(self):
        result = self.service().check(
            plan=plan(price_rule="max_price", operation="buy", price_limit=310.0),
            current_price=311.0,
        )

        self.assertFalse(result.allowed)

    def test_max_price_sell_allows_at_or_above_limit(self):
        result = self.service().check(
            plan=plan(price_rule="max_price", operation="sell", price_limit=310.0),
            current_price=311.0,
        )

        self.assertTrue(result.allowed)

    def test_max_price_sell_blocks_below_limit(self):
        result = self.service().check(
            plan=plan(price_rule="max_price", operation="sell", price_limit=310.0),
            current_price=309.0,
        )

        self.assertFalse(result.allowed)

    def test_max_price_without_limit_blocks(self):
        result = self.service().check(
            plan=plan(price_rule="max_price", operation="buy", price_limit=None),
            current_price=100.0,
        )

        self.assertFalse(result.allowed)
        self.assertIn("price_limit", result.reason)

    def test_pct_from_avg_buy_uses_average_plus_threshold(self):
        broker = FakeBroker(prices=[100.0, 100.0, 100.0])
        result = self.service(broker).check(
            plan=plan(price_rule="pct_from_avg", operation="buy", pct_threshold=5.0, avg_period_days=30),
            current_price=104.0,
        )

        self.assertTrue(result.allowed)
        self.assertAlmostEqual(result.limit_price, 105.0)
        self.assertEqual(broker.calls, [("token", "SBER", 30)])

    def test_pct_from_avg_sell_uses_average_minus_threshold(self):
        result = self.service(FakeBroker(prices=[100.0, 100.0])).check(
            plan=plan(price_rule="pct_from_avg", operation="sell", pct_threshold=5.0, avg_period_days=30),
            current_price=96.0,
        )

        self.assertTrue(result.allowed)
        self.assertAlmostEqual(result.limit_price, 95.0)

    def test_pct_from_avg_blocks_when_average_unavailable(self):
        result = self.service(FakeBroker(prices=[])).check(
            plan=plan(price_rule="pct_from_avg", operation="buy", pct_threshold=5.0, avg_period_days=30),
            current_price=96.0,
        )

        self.assertFalse(result.allowed)
        self.assertIsNone(result.limit_price)


class TInvestBrokerClosingPricesTests(unittest.TestCase):
    def test_get_closing_prices_returns_positive_daily_closes(self):
        broker = TInvestBroker()
        broker.resolve_unique_instrument = mock.Mock(return_value=SimpleNamespace(figi="FIGI-SBER"))

        def money(units, nano=0):
            return SimpleNamespace(units=units, nano=nano)

        candles = [
            SimpleNamespace(close=money(100, 500_000_000)),
            SimpleNamespace(close=money(0, 0)),
            SimpleNamespace(close=money(101, 250_000_000)),
        ]

        class FakeMarketData:
            def get_candles(self, **kwargs):
                self.kwargs = kwargs
                return SimpleNamespace(candles=candles)

        class FakeClient:
            market_data = FakeMarketData()

            def __init__(self, token):
                self.token = token

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

        with mock.patch("app.integrations.tinvest.Client", FakeClient):
            prices = broker.get_closing_prices("token", "SBER", 30)

        self.assertEqual(prices, [100.5, 101.25])
        broker.resolve_unique_instrument.assert_called_once_with("token", "SBER")


if __name__ == "__main__":
    unittest.main()
