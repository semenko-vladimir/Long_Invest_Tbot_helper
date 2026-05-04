import ast
from datetime import datetime
from pathlib import Path
import unittest

from fastapi import FastAPI

try:
    from fastapi.testclient import TestClient
except RuntimeError as exc:
    TestClient = None
    TESTCLIENT_IMPORT_ERROR = str(exc)
else:
    TESTCLIENT_IMPORT_ERROR = ""

from app.backend.api import api_router
from app.backend.api.endpoints.research import ResearchServices, get_research_services
from app.research.schemas import (
    AdapterResult,
    DataGap,
    InstrumentIdentity,
    MarketSnapshot,
    SourceFreshness,
)
from app.research.services import ResearchReportService, TickerResearchService


class SuccessfulAdapter:
    source_name = "success"

    def fetch(self, ticker: str) -> AdapterResult:
        fetched_at = datetime(2026, 5, 4, 12, 0)
        return AdapterResult(
            source_name=self.source_name,
            data={
                "instrument_identity": InstrumentIdentity(
                    ticker=ticker,
                    figi="FIGI-SBER",
                    name="Sber",
                    currency="RUB",
                ),
                "market_snapshot": MarketSnapshot(
                    current_price=101.5,
                    currency="RUB",
                    captured_at=fetched_at,
                ),
            },
            freshness=SourceFreshness(
                source_name=self.source_name,
                fetched_at=fetched_at,
                as_of_date="2026-05-04",
            ),
        )


class PartialAdapter:
    source_name = "partial"

    def fetch(self, ticker: str) -> AdapterResult:
        return AdapterResult(
            source_name=self.source_name,
            data={"ticker": ticker},
            gaps=[DataGap("financials", "Financial source is not configured.", "medium")],
        )


class FailingAdapter:
    source_name = "failing"

    def fetch(self, ticker: str) -> AdapterResult:
        raise RuntimeError("source unavailable")


@unittest.skipIf(TestClient is None, TESTCLIENT_IMPORT_ERROR)
class ResearchApiTests(unittest.TestCase):
    def build_client(self, adapters):
        app = FastAPI()
        app.include_router(api_router, prefix="/api")
        now = datetime(2026, 5, 4, 12, 30)

        app.dependency_overrides[get_research_services] = lambda: ResearchServices(
            ticker_research=TickerResearchService(adapters, now_provider=lambda: now),
            report_builder=ResearchReportService(now_provider=lambda: now),
        )
        return TestClient(app)

    def test_get_research_endpoint_returns_report_for_successful_adapter(self):
        response = self.build_client([SuccessfulAdapter()]).get("/api/research/sber")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["ticker"], "SBER")
        self.assertEqual(payload["sources"], ["success"])
        self.assertEqual(payload["instrument_identity"]["figi"], "FIGI-SBER")
        self.assertEqual(payload["market_snapshot"]["current_price"], 101.5)
        self.assertEqual(payload["freshness"][0]["source_name"], "success")
        self.assertEqual(payload["data_gaps"], [])
        self.assertEqual(payload["errors"], [])

    def test_missing_partial_data_returns_explicit_data_gaps(self):
        response = self.build_client([PartialAdapter()]).get("/api/research/SBER")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertIsNone(payload["instrument_identity"])
        self.assertTrue(any(gap["category"] == "financials" for gap in payload["data_gaps"]))

    def test_adapter_error_is_reported_without_order_action(self):
        response = self.build_client([SuccessfulAdapter(), FailingAdapter()]).get("/api/research/SBER")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["instrument_identity"]["figi"], "FIGI-SBER")
        self.assertTrue(any("failing adapter failed" in error for error in payload["errors"]))
        self.assertTrue(any(gap["category"] == "source_errors" for gap in payload["data_gaps"]))

        post_response = self.build_client([SuccessfulAdapter()]).post("/api/research/SBER")
        self.assertEqual(post_response.status_code, 405)

    def test_educational_rating_is_null_and_disclaimer_is_present(self):
        response = self.build_client([SuccessfulAdapter()]).get("/api/research/SBER")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertIsNone(payload["educational_rating"])
        self.assertIn("not personal investment advice", payload["disclaimer"])
        self.assertIn("must not trigger broker orders", payload["disclaimer"])

    def test_research_api_imports_no_order_signal_or_llm_modules(self):
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
            "app.integrations.tinvest",
            "keras",
            "tensorflow",
            "g4f",
        )
        forbidden_names = {"OrderService", "manual_order_handler", "place_order", "post_order"}
        endpoint_path = Path(__file__).resolve().parents[1] / "app" / "backend" / "api" / "endpoints" / "research.py"
        tree = ast.parse(endpoint_path.read_text(encoding="utf-8"))

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
