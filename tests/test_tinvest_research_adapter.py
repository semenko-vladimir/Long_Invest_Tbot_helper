import ast
from dataclasses import dataclass
from datetime import datetime
import json
import os
from pathlib import Path
import unittest
from unittest import mock

from grpc import StatusCode
from tinkoff.invest import RequestError

from app.research.schemas import InstrumentIdentity, MarketSnapshot
from app.research.tinvest_adapter import TInvestDataAdapter


@dataclass(frozen=True)
class FakeInstrument:
    figi: str = "FIGI-SBER"
    ticker: str = "SBER"
    name: str = "Sber"


@dataclass(frozen=True)
class FakeDividend:
    dividend_net: str = "10.5"
    payment_date: str = "2026-07-01"
    declared_date: str = "2026-05-01"
    last_buy_date: str = "2026-06-20"
    record_date: str = "2026-06-23"
    yield_value: str = "5.2"


class FakeReadOnlyBroker:
    _DEFAULT_DIVIDEND = object()

    def __init__(self, *, price=101.5, dividend=_DEFAULT_DIVIDEND, identity_error=None, price_error=None):
        self.price = price
        self.dividend = FakeDividend() if dividend is self._DEFAULT_DIVIDEND else dividend
        self.identity_error = identity_error
        self.price_error = price_error
        self.calls = []

    def resolve_unique_instrument(self, token: str, ticker: str):
        self.calls.append(("resolve_unique_instrument", token, ticker))
        if self.identity_error:
            raise self.identity_error
        return FakeInstrument(ticker=ticker)

    def get_price(self, token: str, figi: str, operation: str) -> float:
        self.calls.append(("get_price", token, figi, operation))
        if self.price_error:
            raise self.price_error
        return self.price

    def get_dividend_info(self, token: str, figi: str, period_days: int):
        self.calls.append(("get_dividend_info", token, figi, period_days))
        return self.dividend

    def place_order(self, *args, **kwargs):
        raise AssertionError("Research adapter must not place orders.")


class TInvestDataAdapterTests(unittest.TestCase):
    def build_adapter(self, broker):
        return TInvestDataAdapter(
            broker=broker,
            token_provider=lambda: "token",
            now_provider=lambda: datetime(2026, 5, 4, 12, 0),
        )

    def test_successful_ticker_identity_market_and_dividend_fetch(self):
        broker = FakeReadOnlyBroker()
        adapter = self.build_adapter(broker)

        result = adapter.fetch(" sber ")

        self.assertEqual(result.source_name, "t-invest")
        self.assertEqual(result.errors, [])
        self.assertEqual(result.gaps, [])
        self.assertIsInstance(result.data["instrument_identity"], InstrumentIdentity)
        self.assertEqual(result.data["instrument_identity"].ticker, "SBER")
        self.assertEqual(result.data["instrument_identity"].figi, "FIGI-SBER")
        self.assertIsInstance(result.data["market_snapshot"], MarketSnapshot)
        self.assertEqual(result.data["market_snapshot"].current_price, 101.5)
        self.assertEqual(result.data["dividends"]["yield_value"], "5.2")
        self.assertIsNotNone(result.freshness)
        self.assertEqual(result.freshness.source_name, "t-invest")
        self.assertNotIn(("place_order",), broker.calls)

    def test_partial_data_returns_explicit_gaps(self):
        broker = FakeReadOnlyBroker(price_error=RuntimeError("quote unavailable"), dividend=None)
        adapter = self.build_adapter(broker)

        result = adapter.fetch("SBER")

        self.assertIn("instrument_identity", result.data)
        self.assertNotIn("market_snapshot", result.data)
        self.assertNotIn("dividends", result.data)
        self.assertTrue(any(gap.category == "market_snapshot" for gap in result.gaps))
        self.assertTrue(any(gap.category == "dividends" for gap in result.gaps))
        self.assertTrue(any("Market snapshot lookup failed" in error for error in result.errors))

    def test_source_error_is_captured(self):
        broker = FakeReadOnlyBroker(identity_error=ValueError("ambiguous ticker"))
        adapter = self.build_adapter(broker)

        result = adapter.fetch("SBER")

        self.assertNotIn("instrument_identity", result.data)
        self.assertTrue(any("Instrument identity lookup failed" in error for error in result.errors))
        self.assertTrue(any(gap.category == "instrument_identity" for gap in result.gaps))
        self.assertTrue(any(gap.category == "market_snapshot" for gap in result.gaps))
        self.assertTrue(any(gap.category == "dividends" for gap in result.gaps))

    def test_sandbox_mode_selects_sandbox_token_without_token(self):
        broker = FakeReadOnlyBroker()
        adapter = TInvestDataAdapter(
            broker=broker,
            now_provider=lambda: datetime(2026, 5, 4, 12, 0),
        )

        with mock.patch.dict(
            os.environ,
            {
                "APP_MODE": "sandbox",
                "SANDBOX_TOKEN": "sandbox-token",
            },
            clear=True,
        ), mock.patch("app.client.config.load_dotenv"):
            result = adapter.fetch("SBER")

        self.assertEqual(result.errors, [])
        self.assertEqual(broker.calls[0], ("resolve_unique_instrument", "sandbox-token", "SBER"))
        self.assertTrue(all(call[1] == "sandbox-token" for call in broker.calls))
        self.assertIn("selected token variable: SANDBOX_TOKEN", result.freshness.notes)

    def test_prod_mode_selects_token_without_sandbox_fallback(self):
        broker = FakeReadOnlyBroker()
        adapter = TInvestDataAdapter(
            broker=broker,
            now_provider=lambda: datetime(2026, 5, 4, 12, 0),
        )

        with mock.patch.dict(
            os.environ,
            {
                "APP_MODE": "prod",
                "TOKEN": "prod-token",
                "SANDBOX_TOKEN": "sandbox-token",
            },
            clear=True,
        ), mock.patch("app.client.config.load_dotenv"):
            result = adapter.fetch("SBER")

        self.assertEqual(result.errors, [])
        self.assertEqual(broker.calls[0], ("resolve_unique_instrument", "prod-token", "SBER"))
        self.assertTrue(all(call[1] == "prod-token" for call in broker.calls))
        self.assertIn("selected token variable: TOKEN", result.freshness.notes)

    def test_prod_mode_does_not_fall_back_to_sandbox_token_when_token_missing(self):
        broker = FakeReadOnlyBroker()
        adapter = TInvestDataAdapter(
            broker=broker,
            now_provider=lambda: datetime(2026, 5, 4, 12, 0),
        )

        with mock.patch.dict(
            os.environ,
            {
                "APP_MODE": "prod",
                "SANDBOX_TOKEN": "sandbox-token",
            },
            clear=True,
        ), mock.patch("app.client.config.load_dotenv"):
            result = adapter.fetch("SBER")

        self.assertEqual(broker.calls, [])
        self.assertTrue(any("selected TOKEN" in error for error in result.errors))
        self.assertTrue(any(gap.category == "instrument_identity" for gap in result.gaps))
        self.assertIn("token is missing", result.freshness.notes)

    def test_missing_or_placeholder_selected_token_returns_structured_error(self):
        broker = FakeReadOnlyBroker()
        adapter = TInvestDataAdapter(
            broker=broker,
            now_provider=lambda: datetime(2026, 5, 4, 12, 0),
        )

        with mock.patch.dict(
            os.environ,
            {
                "APP_MODE": "sandbox",
                "SANDBOX_TOKEN": "your_sandbox_token",
            },
            clear=True,
        ), mock.patch("app.client.config.load_dotenv"):
            result = adapter.fetch("SBER")

        self.assertEqual(broker.calls, [])
        self.assertTrue(any("selected SANDBOX_TOKEN" in error for error in result.errors))
        self.assertTrue(any(gap.category == "instrument_identity" for gap in result.gaps))
        self.assertTrue(any(gap.category == "market_snapshot" for gap in result.gaps))
        self.assertTrue(any(gap.category == "dividends" for gap in result.gaps))
        serialized = json.dumps(
            {
                "errors": result.errors,
                "gaps": [gap.description for gap in result.gaps],
                "freshness": result.freshness.notes,
            }
        )
        self.assertNotIn("your_sandbox_token", serialized)

    def test_unauthenticated_error_is_sanitized_without_token_leak(self):
        secret_token = "sandbox-secret-token"
        broker = FakeReadOnlyBroker(
            identity_error=RequestError(
                StatusCode.UNAUTHENTICATED,
                "40003",
                {"message": "Authentication token is missing or invalid"},
            )
        )
        adapter = TInvestDataAdapter(
            broker=broker,
            now_provider=lambda: datetime(2026, 5, 4, 12, 0),
        )

        with mock.patch.dict(
            os.environ,
            {
                "APP_MODE": "sandbox",
                "SANDBOX_TOKEN": secret_token,
            },
            clear=True,
        ), mock.patch("app.client.config.load_dotenv"):
            result = adapter.fetch("SBER")

        self.assertTrue(any("selected SANDBOX_TOKEN appears invalid for sandbox mode" in error for error in result.errors))
        serialized = json.dumps(
            {
                "errors": result.errors,
                "gaps": [gap.description for gap in result.gaps],
                "freshness": result.freshness.notes,
            }
        )
        self.assertNotIn(secret_token, serialized)
        self.assertNotIn("StatusCode.UNAUTHENTICATED", serialized)
        self.assertNotIn("40003", serialized)

    def test_non_auth_broker_error_redacts_selected_token_value(self):
        secret_token = "sandbox-secret-token"
        broker = FakeReadOnlyBroker(identity_error=RuntimeError(f"failed for token {secret_token}"))
        adapter = TInvestDataAdapter(
            broker=broker,
            now_provider=lambda: datetime(2026, 5, 4, 12, 0),
        )

        with mock.patch.dict(
            os.environ,
            {
                "APP_MODE": "sandbox",
                "SANDBOX_TOKEN": secret_token,
            },
            clear=True,
        ), mock.patch("app.client.config.load_dotenv"):
            result = adapter.fetch("SBER")

        self.assertTrue(any("[redacted]" in error for error in result.errors))
        self.assertNotIn(secret_token, " ".join(result.errors))

    def test_adapter_produces_no_educational_rating(self):
        result = self.build_adapter(FakeReadOnlyBroker()).fetch("SBER")

        self.assertNotIn("educational_rating", result.data)

    def test_adapter_exposes_no_order_methods(self):
        adapter = self.build_adapter(FakeReadOnlyBroker())

        forbidden_methods = {"place_order", "post_order", "buy", "sell", "execute_order"}
        self.assertEqual(forbidden_methods.intersection(dir(adapter)), set())

    def test_tinvest_research_adapter_imports_no_order_signal_or_llm_modules(self):
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
        forbidden_names = {"OrderService", "manual_order_handler", "place_order", "post_order"}
        adapter_path = Path(__file__).resolve().parents[1] / "app" / "research" / "tinvest_adapter.py"
        tree = ast.parse(adapter_path.read_text(encoding="utf-8"))

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
