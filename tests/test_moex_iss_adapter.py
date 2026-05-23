import ast
from datetime import date, datetime
import json
import os
from pathlib import Path
import unittest
from unittest import mock
from urllib.error import URLError

from app.integrations.moex_iss import (
    MOEXDailyCandlesResult,
    MOEXDataAdapter,
    MOEXISSClient,
    MOEXMarketData,
    MOEXSecurityMetadata,
    iss_table_to_rows,
)
from app.research.schemas import InstrumentIdentity, MarketSnapshot


class FakeHTTPResponse:
    def __init__(self, payload):
        if isinstance(payload, bytes):
            self.payload = payload
        elif isinstance(payload, str):
            self.payload = payload.encode("utf-8")
        else:
            self.payload = json.dumps(payload).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self):
        return self.payload


class FakeMOEXAdapterClient:
    def __init__(self, now):
        self.now = now
        self.calls = []

    def get_security_metadata(self, ticker):
        self.calls.append(("metadata", ticker))
        return MOEXSecurityMetadata(
            ticker=ticker,
            fetched_at=self.now,
            secid=ticker,
            name="Gazprom PJSC",
            short_name="GAZP",
            isin="RU0007661625",
            currency="RUB",
            lot_size=10,
        )

    def get_market_data(self, ticker):
        self.calls.append(("market", ticker))
        return MOEXMarketData(
            ticker=ticker,
            fetched_at=self.now,
            trade_date=date(2026, 5, 22),
            open=170.0,
            high=172.0,
            low=169.5,
            close=171.25,
            last=171.25,
            volume=1000,
            value=171250.0,
            currency="RUB",
        )


class MOEXISSClientTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 5, 23, 12, 0)

    def build_client(self):
        return MOEXISSClient(now_provider=lambda: self.now)

    def patch_urlopen(self, payloads):
        requests = []
        remaining_payloads = list(payloads)

        def fake_urlopen(request, timeout):
            requests.append((request, timeout))
            payload = remaining_payloads.pop(0)
            if isinstance(payload, BaseException):
                raise payload
            return FakeHTTPResponse(payload)

        return mock.patch("app.integrations.moex_iss.urlopen", side_effect=fake_urlopen), requests

    def test_successful_security_metadata_parse(self):
        payload = {
            "description": {
                "columns": ["name", "title", "value"],
                "data": [
                    ["SECID", "Ticker", "SBER"],
                    ["NAME", "Name", "Sberbank PJSC"],
                    ["ISIN", "ISIN", "RU0009029540"],
                    ["PRIMARY_BOARDID", "Primary board", "TQBR"],
                    ["FACEUNIT", "Currency", "SUR"],
                ],
            },
            "securities": {
                "columns": ["SECID", "SHORTNAME", "NAME", "ISIN", "PRIMARY_BOARDID", "TYPE", "GROUP"],
                "data": [["SBER", "Sber", "Sberbank PJSC", "RU0009029540", "TQBR", "common_share", "stock_shares"]],
            },
        }
        patcher, requests = self.patch_urlopen([payload])

        with patcher:
            result = self.build_client().get_security_metadata(" sber ")

        self.assertEqual(result.ticker, "SBER")
        self.assertEqual(result.source, "MOEX ISS")
        self.assertEqual(result.name, "Sberbank PJSC")
        self.assertEqual(result.short_name, "Sber")
        self.assertEqual(result.isin, "RU0009029540")
        self.assertEqual(result.board, "TQBR")
        self.assertEqual(result.currency, "RUB")
        self.assertEqual(result.errors, [])
        self.assertEqual(result.data_gaps, [])
        self.assertIn("/securities/SBER.json?", requests[0][0].full_url)
        self.assertEqual(requests[0][0].get_method(), "GET")
        self.assertIn("Tbot-v1", requests[0][0].get_header("User-agent"))
        self.assertEqual(requests[0][1], 5.0)

    def test_successful_market_data_parse(self):
        payload = {
            "securities": {
                "columns": ["SECID", "BOARDID", "FACEUNIT"],
                "data": [["GAZP", "TQBR", "SUR"]],
            },
            "marketdata": {
                "columns": [
                    "SECID",
                    "BOARDID",
                    "OPEN",
                    "HIGH",
                    "LOW",
                    "LAST",
                    "CLOSEPRICE",
                    "VOLTODAY",
                    "VALTODAY",
                    "SYSTIME",
                ],
                "data": [["GAZP", "TQBR", 170, 172.5, 169.5, 171.7, 171.25, 1000, 171250, "2026-05-22 18:45:00"]],
            },
        }
        patcher, _ = self.patch_urlopen([payload])

        with patcher:
            result = self.build_client().get_market_data("gazp")

        self.assertEqual(result.ticker, "GAZP")
        self.assertEqual(result.board, "TQBR")
        self.assertEqual(result.trade_date, date(2026, 5, 22))
        self.assertEqual(result.open, 170.0)
        self.assertEqual(result.high, 172.5)
        self.assertEqual(result.low, 169.5)
        self.assertEqual(result.close, 171.25)
        self.assertEqual(result.last, 171.7)
        self.assertEqual(result.volume, 1000)
        self.assertEqual(result.value, 171250.0)
        self.assertEqual(result.currency, "RUB")
        self.assertEqual(result.errors, [])

    def test_successful_candles_parse_with_pagination(self):
        first_page = {
            "candles": {
                "columns": ["begin", "end", "open", "high", "low", "close", "volume", "value"],
                "data": [["2026-05-20 00:00:00", "2026-05-20 23:59:59", 100, 103, 99, 102, 5000, 510000]],
            },
            "candles.cursor": {"columns": ["INDEX", "TOTAL", "PAGESIZE"], "data": [[0, 2, 1]]},
        }
        second_page = {
            "candles": {
                "columns": ["begin", "end", "open", "high", "low", "close", "volume", "value"],
                "data": [["2026-05-21 00:00:00", "2026-05-21 23:59:59", 102, 104, 101, 103, 4000, 412000]],
            },
            "candles.cursor": {"columns": ["INDEX", "TOTAL", "PAGESIZE"], "data": [[1, 2, 1]]},
        }
        patcher, requests = self.patch_urlopen([first_page, second_page])

        with patcher:
            result = self.build_client().get_daily_candles_result(
                "gazp",
                from_date=date(2026, 5, 1),
                till_date=date(2026, 5, 31),
            )

        self.assertIsInstance(result, MOEXDailyCandlesResult)
        self.assertEqual(result.ticker, "GAZP")
        self.assertEqual(result.errors, [])
        self.assertEqual(result.data_gaps, [])
        self.assertEqual(len(result.candles), 2)
        self.assertEqual(result.candles[0].trade_date, date(2026, 5, 20))
        self.assertEqual(result.candles[0].open, 100.0)
        self.assertEqual(result.candles[0].high, 103.0)
        self.assertEqual(result.candles[0].low, 99.0)
        self.assertEqual(result.candles[0].close, 102.0)
        self.assertEqual(result.candles[0].volume, 5000)
        self.assertEqual(result.candles[0].value, 510000.0)
        self.assertIn("/boards/TQBR/securities/GAZP.json/candles.json?", requests[0][0].full_url)
        self.assertIn("interval=24", requests[0][0].full_url)
        self.assertIn("from=2026-05-01", requests[0][0].full_url)
        self.assertIn("till=2026-05-31", requests[0][0].full_url)
        self.assertIn("start=0", requests[0][0].full_url)
        self.assertIn("start=1", requests[1][0].full_url)

    def test_get_daily_candles_returns_candle_list(self):
        payload = {
            "candles": {
                "columns": ["begin", "end", "open", "high", "low", "close"],
                "data": [["2026-05-20 00:00:00", "2026-05-20 23:59:59", 100, 103, 99, 102]],
            },
            "candles.cursor": {"columns": ["INDEX", "TOTAL", "PAGESIZE"], "data": [[0, 1, 100]]},
        }
        patcher, _ = self.patch_urlopen([payload])

        with patcher:
            candles = self.build_client().get_daily_candles("lkoh")

        self.assertEqual(len(candles), 1)
        self.assertEqual(candles[0].ticker, "LKOH")

    def test_empty_candles_response_returns_explicit_gap(self):
        payload = {
            "candles": {"columns": ["begin", "end", "open", "high", "low", "close"], "data": []},
            "candles.cursor": {"columns": ["INDEX", "TOTAL", "PAGESIZE"], "data": [[0, 0, 100]]},
        }
        patcher, _ = self.patch_urlopen([payload])

        with patcher:
            result = self.build_client().get_daily_candles_result("SBER")

        self.assertEqual(result.candles, [])
        self.assertEqual(result.errors, [])
        self.assertTrue(any(gap.category == "price_history" for gap in result.data_gaps))

    def test_http_failure_returns_sanitized_error_without_secret_leak(self):
        secret = "sandbox-secret-token"
        patcher, _ = self.patch_urlopen([URLError(f"request failed token={secret}")])

        with mock.patch.dict(os.environ, {"SANDBOX_TOKEN": secret}, clear=False), patcher:
            result = self.build_client().get_daily_candles_result("SBER")

        serialized = json.dumps(
            {
                "errors": result.errors,
                "gaps": [gap.description for gap in result.data_gaps],
            }
        )
        self.assertIn("[redacted]", serialized)
        self.assertNotIn(secret, serialized)
        self.assertTrue(any(gap.category == "price_history" for gap in result.data_gaps))

    def test_malformed_json_and_table_return_structured_errors(self):
        json_patcher, _ = self.patch_urlopen([b"{not valid json"])
        with json_patcher:
            metadata = self.build_client().get_security_metadata("SBER")

        self.assertTrue(metadata.errors)
        self.assertTrue(any(gap.category == "instrument_identity" for gap in metadata.data_gaps))

        table_payload = {"candles": {"columns": "bad", "data": []}}
        table_patcher, _ = self.patch_urlopen([table_payload])
        with table_patcher:
            candles = self.build_client().get_daily_candles_result("SBER")

        self.assertTrue(candles.errors)
        self.assertTrue(any(gap.category == "price_history" for gap in candles.data_gaps))

    def test_ticker_normalization_rejects_invalid_ticker_without_request(self):
        client = self.build_client()

        with mock.patch("app.integrations.moex_iss.urlopen") as mocked_urlopen:
            result = client.get_security_metadata("SBER!")

        self.assertEqual(result.ticker, "")
        self.assertEqual(result.errors, [])
        self.assertTrue(any(gap.category == "ticker" for gap in result.data_gaps))
        mocked_urlopen.assert_not_called()

    def test_iss_table_to_rows_accepts_short_rows(self):
        rows = iss_table_to_rows(
            {
                "sample": {
                    "columns": ["SECID", "OPEN", "CLOSE"],
                    "data": [["SBER", 100]],
                }
            },
            "sample",
        )

        self.assertEqual(rows, [{"secid": "SBER", "open": 100, "close": None}])


class MOEXDataAdapterTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 5, 23, 12, 0)

    def test_fetch_maps_moex_metadata_and_market_snapshot(self):
        client = FakeMOEXAdapterClient(self.now)
        adapter = MOEXDataAdapter(client=client, now_provider=lambda: self.now)

        result = adapter.fetch(" gazp ")

        self.assertEqual(result.source_name, "MOEX ISS")
        self.assertEqual(result.errors, [])
        self.assertEqual(result.gaps, [])
        self.assertEqual(client.calls, [("metadata", "GAZP"), ("market", "GAZP")])
        self.assertIsInstance(result.data["instrument_identity"], InstrumentIdentity)
        self.assertEqual(result.data["instrument_identity"].ticker, "GAZP")
        self.assertEqual(result.data["instrument_identity"].exchange, "MOEX")
        self.assertIsInstance(result.data["market_snapshot"], MarketSnapshot)
        self.assertEqual(result.data["market_snapshot"].current_price, 171.25)
        self.assertEqual(result.data["moex_metadata"]["source"], "MOEX ISS")
        self.assertEqual(result.data["moex_market_data"]["trade_date"], "2026-05-22")
        self.assertNotIn("educational_rating", result.data)
        self.assertIn("No broker token is used", result.freshness.notes)

    def test_adapter_exposes_no_order_methods(self):
        adapter = MOEXDataAdapter(client=FakeMOEXAdapterClient(self.now), now_provider=lambda: self.now)

        forbidden_methods = {"place_order", "post_order", "preview", "execute", "buy", "sell", "execute_order"}
        self.assertEqual(forbidden_methods.intersection(dir(adapter)), set())

    def test_moex_module_imports_no_order_signal_or_rating_modules(self):
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
        module_path = Path(__file__).resolve().parents[1] / "app" / "integrations" / "moex_iss.py"
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
