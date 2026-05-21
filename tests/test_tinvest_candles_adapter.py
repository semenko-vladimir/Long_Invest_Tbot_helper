from datetime import datetime, timezone
from types import SimpleNamespace
import unittest
from unittest import mock

from app.charts.schemas import PriceCandle
from app.charts.tinvest_candles_adapter import TInvestCandlesAdapter


class FakeInstrumentBroker:
    def __init__(self, *, error=None, figi="FIGI-SBER"):
        self.error = error
        self.figi = figi
        self.calls = []

    def resolve_unique_instrument(self, token, ticker):
        self.calls.append((token, ticker))
        if self.error:
            raise self.error
        return SimpleNamespace(ticker=ticker, figi=self.figi)


def money(units, nano=0):
    return SimpleNamespace(units=units, nano=nano)


class TInvestCandlesAdapterTests(unittest.TestCase):
    def build_adapter(self, broker=None, token_provider=lambda: "token"):
        return TInvestCandlesAdapter(
            broker=broker or FakeInstrumentBroker(),
            token_provider=token_provider,
            now_provider=lambda: datetime(2026, 5, 21, 12, 0, tzinfo=timezone.utc),
        )

    def test_missing_token_returns_structured_error_without_broker_call(self):
        broker = FakeInstrumentBroker()
        adapter = self.build_adapter(broker=broker, token_provider=lambda: None)

        result = adapter.fetch_candles("SBER", "month")

        self.assertEqual(result.ticker, "SBER")
        self.assertEqual(result.candles, [])
        self.assertEqual(broker.calls, [])
        self.assertTrue(any("No T-Invest token" in error for error in result.errors))
        self.assertTrue(any(gap.category == "authentication" for gap in result.data_gaps))

    def test_ticker_lookup_failure_returns_structured_error(self):
        broker = FakeInstrumentBroker(error=ValueError("ticker not found"))
        adapter = self.build_adapter(broker=broker)

        result = adapter.fetch_candles("SBER", "week")

        self.assertEqual(result.candles, [])
        self.assertTrue(any("Instrument identity lookup failed" in error for error in result.errors))
        self.assertTrue(any(gap.category == "instrument_identity" for gap in result.data_gaps))
        self.assertTrue(any(gap.category == "price_history" for gap in result.data_gaps))

    def test_empty_figi_returns_explicit_gap_without_candle_call(self):
        broker = FakeInstrumentBroker(figi="")
        adapter = self.build_adapter(broker=broker)

        result = adapter.fetch_candles("SBER", "week")

        self.assertEqual(result.candles, [])
        self.assertEqual(result.errors, [])
        self.assertTrue(any(gap.category == "instrument_identity" for gap in result.data_gaps))

    def test_maps_tinvest_candles_to_sorted_price_candles(self):
        broker = FakeInstrumentBroker()
        adapter = self.build_adapter(broker=broker)

        raw_candles = [
            SimpleNamespace(
                time=datetime(2026, 5, 20, 12, 0, tzinfo=timezone.utc),
                open=money(101),
                high=money(103),
                low=money(100),
                close=money(102, 250_000_000),
                volume=200,
            ),
            SimpleNamespace(
                time=datetime(2026, 5, 19, 12, 0, tzinfo=timezone.utc),
                open=money(100),
                high=money(101),
                low=money(99),
                close=money(100, 500_000_000),
                volume=100,
            ),
            SimpleNamespace(
                time=datetime(2026, 5, 18, 12, 0, tzinfo=timezone.utc),
                open=money(0),
                high=money(0),
                low=money(0),
                close=money(0),
                volume=0,
            ),
        ]

        class FakeMarketData:
            def get_candles(self, **kwargs):
                self.kwargs = kwargs
                return SimpleNamespace(candles=raw_candles)

        class FakeClient:
            market_data = FakeMarketData()

            def __init__(self, token):
                self.token = token

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

        with mock.patch("app.charts.tinvest_candles_adapter.Client", FakeClient):
            result = adapter.fetch_candles("SBER", "month")

        self.assertEqual(result.errors, [])
        self.assertEqual(result.figi, "FIGI-SBER")
        self.assertEqual(len(result.candles), 2)
        self.assertTrue(all(isinstance(item, PriceCandle) for item in result.candles))
        self.assertEqual([item.time.day for item in result.candles], [19, 20])
        self.assertEqual(result.candles[0].close, 100.5)
        self.assertEqual(result.candles[1].close, 102.25)
        self.assertEqual(FakeClient.market_data.kwargs["figi"], "FIGI-SBER")

    def test_candle_lookup_failure_redacts_token(self):
        secret = "sandbox-secret-token"
        adapter = self.build_adapter(token_provider=lambda: secret)

        class FakeMarketData:
            def get_candles(self, **kwargs):
                raise RuntimeError(f"request failed for {secret}")

        class FakeClient:
            market_data = FakeMarketData()

            def __init__(self, token):
                self.token = token

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

        with mock.patch("app.charts.tinvest_candles_adapter.Client", FakeClient):
            result = adapter.fetch_candles("SBER", "month")

        serialized = " ".join(result.errors)
        self.assertIn("[redacted]", serialized)
        self.assertNotIn(secret, serialized)
        self.assertTrue(any(gap.category == "price_history" for gap in result.data_gaps))


if __name__ == "__main__":
    unittest.main()
