import ast
from datetime import datetime
from pathlib import Path
import unittest

from app.research.adapters import DataSourceAdapter
from app.research.schemas import (
    AdapterResult,
    DataGap,
    InstrumentIdentity,
    MarketSnapshot,
    ResearchReport,
    SourceFreshness,
)


class DummyAdapter:
    source_name = "dummy"

    def fetch(self, ticker: str) -> AdapterResult:
        fetched_at = datetime(2026, 5, 4, 12, 0)
        return AdapterResult(
            source_name=self.source_name,
            data={"ticker": ticker.upper()},
            freshness=SourceFreshness(source_name=self.source_name, fetched_at=fetched_at),
        )


class ResearchFoundationTests(unittest.TestCase):
    def test_research_report_defaults_to_no_educational_rating(self):
        report = ResearchReport(ticker="SBER", generated_at=datetime(2026, 5, 4, 12, 0))

        self.assertIsNone(report.educational_rating)
        self.assertIn("not personal investment advice", report.disclaimer)
        self.assertIn("must not trigger broker orders", report.disclaimer)

    def test_data_gaps_are_explicit(self):
        gap = DataGap(category="financials", description="Financial statement source is not configured.", severity="high")
        report = ResearchReport(
            ticker="SBER",
            generated_at=datetime(2026, 5, 4, 12, 0),
            data_gaps=[gap],
        )

        self.assertEqual(report.data_gaps[0].category, "financials")
        self.assertEqual(report.data_gaps[0].severity, "high")

    def test_dummy_adapter_matches_read_only_interface_shape(self):
        adapter: DataSourceAdapter = DummyAdapter()

        result = adapter.fetch("sber")

        self.assertEqual(adapter.source_name, "dummy")
        self.assertEqual(result.source_name, "dummy")
        self.assertEqual(result.data["ticker"], "SBER")
        self.assertEqual(result.gaps, [])
        self.assertEqual(result.errors, [])
        self.assertIsNotNone(result.freshness)

    def test_schemas_allow_partial_missing_data(self):
        identity = InstrumentIdentity(ticker="SBER")
        snapshot = MarketSnapshot()
        report = ResearchReport(
            ticker="SBER",
            generated_at=datetime(2026, 5, 4, 12, 0),
            instrument_identity=identity,
            market_snapshot=snapshot,
            sources=["dummy"],
        )

        self.assertEqual(report.instrument_identity.ticker, "SBER")
        self.assertIsNone(report.instrument_identity.figi)
        self.assertIsNone(report.market_snapshot.current_price)
        self.assertIsNone(report.company_profile)
        self.assertEqual(report.sources, ["dummy"])

    def test_research_package_does_not_import_order_signal_or_llm_modules(self):
        forbidden_prefixes = (
            "app.services.orders",
            "app.client.orders",
            "app.integrations.tinvest",
            "app.client.signals",
            "app.client.strategy",
            "app.client.handlers.signals",
            "app.client.handlers.mls",
            "app.client.api.signals_client",
            "app.client.api.strategy_client",
            "keras",
            "tensorflow",
            "g4f",
        )

        research_dir = Path(__file__).resolve().parents[1] / "app" / "research"
        imported_modules = set()
        for path in research_dir.glob("*.py"):
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    imported_modules.update(alias.name for alias in node.names)
                elif isinstance(node, ast.ImportFrom) and node.module:
                    imported_modules.add(node.module)

        forbidden_imports = sorted(
            module
            for module in imported_modules
            if any(module == prefix or module.startswith(f"{prefix}.") for prefix in forbidden_prefixes)
        )
        self.assertEqual(forbidden_imports, [])


if __name__ == "__main__":
    unittest.main()
