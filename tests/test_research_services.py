import ast
from datetime import datetime
import os
from pathlib import Path
import unittest
from unittest import mock

from grpc import StatusCode
from tinkoff.invest import RequestError

from app.research.local_fundamentals_adapter import LocalFundamentalsAdapter
from app.research.schemas import (
    AdapterResult,
    DataGap,
    InstrumentIdentity,
    MarketSnapshot,
    SourceFreshness,
)
from app.research.services import ResearchReportService, TickerResearchService
from app.research.tinvest_adapter import TInvestDataAdapter


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
                "dividends": {"yield_value": "5.2"},
                "risks": ["Dividend data may change."],
            },
            freshness=SourceFreshness(source_name=self.source_name, fetched_at=fetched_at),
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


class AuthFailingTInvestBroker:
    def resolve_unique_instrument(self, token: str, ticker: str):
        raise RequestError(
            StatusCode.UNAUTHENTICATED,
            "40003",
            {"message": "Authentication token is missing or invalid"},
        )

    def get_price(self, token: str, figi: str, operation: str) -> float:
        raise AssertionError("Market data should not be requested after auth failure.")

    def get_dividend_info(self, token: str, figi: str, period_days: int):
        raise AssertionError("Dividends should not be requested after auth failure.")


class ResearchServicesTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 5, 4, 12, 30)
        self.now_provider = lambda: self.now

    def test_successful_report_assembly_from_one_adapter(self):
        results = TickerResearchService(
            [SuccessfulAdapter()],
            now_provider=self.now_provider,
        ).collect(" sber ")
        report = ResearchReportService(now_provider=self.now_provider).build_report("sber", results)

        self.assertEqual(report.ticker, "SBER")
        self.assertEqual(report.sources, ["success"])
        self.assertEqual(report.instrument_identity.ticker, "SBER")
        self.assertEqual(report.market_snapshot.current_price, 101.5)
        self.assertEqual(report.dividends["yield_value"], "5.2")
        self.assertEqual(report.risks, ["Dividend data may change."])
        self.assertEqual(report.errors, [])
        self.assertEqual(report.data_gaps, [])

    def test_multiple_adapters_one_success_one_failure(self):
        results = TickerResearchService(
            [SuccessfulAdapter(), FailingAdapter()],
            now_provider=self.now_provider,
        ).collect("SBER")
        report = ResearchReportService(now_provider=self.now_provider).build_report("SBER", results)

        self.assertEqual(report.instrument_identity.figi, "FIGI-SBER")
        self.assertIn("success", report.sources)
        self.assertIn("failing", report.sources)
        self.assertTrue(any("failing adapter failed" in error for error in report.errors))
        self.assertTrue(any(gap.category == "adapter" for gap in report.data_gaps))
        self.assertTrue(any(gap.category == "source_errors" for gap in report.data_gaps))

    def test_partial_data_produces_explicit_gaps(self):
        results = TickerResearchService(
            [PartialAdapter()],
            now_provider=self.now_provider,
        ).collect("SBER")
        report = ResearchReportService(now_provider=self.now_provider).build_report("SBER", results)

        self.assertIsNone(report.instrument_identity)
        self.assertTrue(any(gap.category == "financials" for gap in report.data_gaps))

    def test_educational_rating_remains_none_and_disclaimer_is_present(self):
        results = TickerResearchService(
            [SuccessfulAdapter()],
            now_provider=self.now_provider,
        ).collect("SBER")
        report = ResearchReportService(now_provider=self.now_provider).build_report("SBER", results)

        self.assertIsNone(report.educational_rating)
        self.assertIn("not personal investment advice", report.disclaimer)
        self.assertIn("must not trigger broker orders", report.disclaimer)

    def test_invalid_ticker_returns_report_with_gap_and_error(self):
        results = TickerResearchService(
            [SuccessfulAdapter()],
            now_provider=self.now_provider,
        ).collect("***")
        report = ResearchReportService(now_provider=self.now_provider).build_report("***", results)

        self.assertEqual(report.ticker, "")
        self.assertTrue(any(gap.category == "ticker" for gap in report.data_gaps))
        self.assertTrue(report.errors)

    def test_local_fundamentals_survive_tinvest_auth_failure(self):
        tinvest_adapter = TInvestDataAdapter(
            broker=AuthFailingTInvestBroker(),
            now_provider=self.now_provider,
        )
        local_adapter = LocalFundamentalsAdapter(now_provider=self.now_provider)

        with mock.patch.dict(
            os.environ,
            {
                "APP_MODE": "sandbox",
                "SANDBOX_TOKEN": "sandbox-secret-token",
            },
            clear=True,
        ), mock.patch("app.client.config.load_dotenv"):
            results = TickerResearchService(
                [tinvest_adapter, local_adapter],
                now_provider=self.now_provider,
            ).collect("SBER")

        report = ResearchReportService(now_provider=self.now_provider).build_report("SBER", results)

        self.assertEqual(report.ticker, "SBER")
        self.assertEqual(report.company_profile["name"], "Sberbank of Russia PJSC")
        self.assertEqual(report.sector_industry["sector"], "Financials")
        self.assertIsNone(report.educational_rating)
        self.assertTrue(any("selected SANDBOX_TOKEN appears invalid" in error for error in report.errors))
        self.assertTrue(any(gap.category == "source_errors" for gap in report.data_gaps))
        self.assertNotIn("sandbox-secret-token", " ".join(report.errors))

    def test_services_expose_no_order_methods(self):
        forbidden_methods = {"place_order", "post_order", "buy", "sell", "execute_order"}

        self.assertEqual(forbidden_methods.intersection(dir(TickerResearchService([]))), set())
        self.assertEqual(forbidden_methods.intersection(dir(ResearchReportService())), set())

    def test_research_services_import_no_order_signal_or_llm_modules(self):
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
        service_path = Path(__file__).resolve().parents[1] / "app" / "research" / "services.py"
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
