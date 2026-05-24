import ast
import json
from datetime import datetime
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.backend.models.database import Base
from app.data_sources.schemas import DATA_SOURCE_LOCAL_FUNDAMENTALS, DELAY_STATUS_LOCAL_FILE
from app.research.local_fundamentals_adapter import LocalFundamentalsAdapter
from app.research.services import ResearchReportService, TickerResearchService
from app.research.snapshots import ResearchSnapshotService, snapshot_to_dict


class LocalFundamentalsAdapterTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 5, 6, 9, 0)
        self.tmp_dir = TemporaryDirectory()
        self.addCleanup(self.tmp_dir.cleanup)

    def test_adapter_returns_profile_and_sector_data_for_known_local_ticker(self):
        adapter = LocalFundamentalsAdapter(now_provider=lambda: self.now)

        result = adapter.fetch(" sber ")

        self.assertEqual(result.source_name, DATA_SOURCE_LOCAL_FUNDAMENTALS)
        self.assertEqual(result.errors, [])
        self.assertEqual(result.data["ticker"], "SBER")
        self.assertEqual(result.data["company_profile"]["name"], "Sberbank of Russia PJSC")
        self.assertEqual(result.data["sector_industry"]["sector"], "Financials")
        self.assertNotIn("educational_rating", result.data)
        self.assertIsNotNone(result.freshness)
        self.assertEqual(result.freshness.source_name, DATA_SOURCE_LOCAL_FUNDAMENTALS)
        self.assertEqual(result.freshness.as_of_date, "2026-05-05")
        self.assertEqual(result.freshness.delay_status, DELAY_STATUS_LOCAL_FILE)

    def test_unknown_ticker_returns_explicit_data_gaps_without_guessing(self):
        adapter = LocalFundamentalsAdapter(now_provider=lambda: self.now)

        result = adapter.fetch("UNKNOWN")

        self.assertEqual(result.errors, [])
        self.assertNotIn("company_profile", result.data)
        self.assertNotIn("sector_industry", result.data)
        self.assertNotIn("financials", result.data)
        self.assertTrue(any(gap.category == "company_profile" for gap in result.gaps))
        self.assertTrue(any(gap.category == "sector_industry" for gap in result.gaps))
        self.assertTrue(any(gap.category == "financials" for gap in result.gaps))

    def test_missing_local_data_file_returns_structured_error_and_gaps(self):
        missing_path = Path(self.tmp_dir.name) / "missing.json"
        adapter = LocalFundamentalsAdapter(data_path=missing_path, now_provider=lambda: self.now)

        result = adapter.fetch("SBER")

        self.assertTrue(any("data file is unavailable" in error for error in result.errors))
        self.assertTrue(any(gap.category == "local_fundamentals" for gap in result.gaps))
        self.assertTrue(any(gap.category == "company_profile" for gap in result.gaps))
        self.assertNotIn("company_profile", result.data)

    def test_malformed_local_data_file_returns_structured_error_and_gaps(self):
        malformed_path = Path(self.tmp_dir.name) / "malformed.json"
        malformed_path.write_text("{ bad json", encoding="utf-8")
        adapter = LocalFundamentalsAdapter(data_path=malformed_path, now_provider=lambda: self.now)

        result = adapter.fetch("SBER")

        self.assertTrue(any("malformed JSON" in error for error in result.errors))
        self.assertTrue(any(gap.category == "local_fundamentals" for gap in result.gaps))
        self.assertTrue(any(gap.category == "company_profile" for gap in result.gaps))
        self.assertNotIn("company_profile", result.data)

    def test_report_service_includes_local_profile_without_guessing_financials_or_rating(self):
        data_path = self._write_json(
            {
                "source": {"description": "Unit-test local profile source.", "as_of_date": "2026-05-01"},
                "tickers": {
                    "TEST": {
                        "company_profile": {"name": "Test Company", "country": "Nowhere"},
                        "sector_industry": {"sector": "Technology", "industry": "Software"},
                    }
                },
            }
        )
        adapter = LocalFundamentalsAdapter(data_path=data_path, now_provider=lambda: self.now)

        results = TickerResearchService([adapter], now_provider=lambda: self.now).collect("test")
        report = ResearchReportService(now_provider=lambda: self.now).build_report("test", results)

        self.assertEqual(report.sources, [DATA_SOURCE_LOCAL_FUNDAMENTALS])
        self.assertEqual(report.company_profile["name"], "Test Company")
        self.assertEqual(report.sector_industry["industry"], "Software")
        self.assertIsNone(report.financials)
        self.assertTrue(any(gap.category == "financials" for gap in report.data_gaps))
        self.assertEqual(report.errors, [])
        self.assertIsNone(report.educational_rating)

    def test_snapshot_with_local_adapter_data_does_not_store_secrets(self):
        data_path = self._write_json(
            {
                "tickers": {
                    "SAFE": {
                        "company_profile": {
                            "name": "Safe Profile",
                            "api_token": "SHOULD_NOT_BE_STORED",
                            "nested": {"secret_value": "SHOULD_NOT_BE_STORED", "public": "ok"},
                        },
                        "sector_industry": {"sector": "Utilities"},
                    }
                }
            }
        )
        adapter = LocalFundamentalsAdapter(data_path=data_path, now_provider=lambda: self.now)
        results = TickerResearchService([adapter], now_provider=lambda: self.now).collect("SAFE")
        report = ResearchReportService(now_provider=lambda: self.now).build_report("SAFE", results)

        engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
        Base.metadata.create_all(bind=engine)
        db = SessionLocal()
        try:
            snapshot = ResearchSnapshotService(db, now_provider=lambda: self.now).save_report(report)
            payload = snapshot_to_dict(snapshot)
        finally:
            db.close()
            Base.metadata.drop_all(bind=engine)
            engine.dispose()

        serialized = json.dumps(payload).lower()
        self.assertEqual(payload["report_json"]["company_profile"]["name"], "Safe Profile")
        self.assertEqual(payload["report_json"]["company_profile"]["nested"]["public"], "ok")
        self.assertNotIn("api_token", serialized)
        self.assertNotIn("secret_value", serialized)
        self.assertNotIn("should_not_be_stored", serialized)

    def test_adapter_exposes_and_imports_no_order_signal_or_llm_modules(self):
        adapter = LocalFundamentalsAdapter(now_provider=lambda: self.now)
        forbidden_methods = {"place_order", "post_order", "buy", "sell", "execute_order"}
        self.assertEqual(forbidden_methods.intersection(dir(adapter)), set())

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
        adapter_path = Path(__file__).resolve().parents[1] / "app" / "research" / "local_fundamentals_adapter.py"
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

    def _write_json(self, payload: dict) -> Path:
        data_path = Path(self.tmp_dir.name) / "local_fundamentals.json"
        data_path.write_text(json.dumps(payload), encoding="utf-8")
        return data_path


if __name__ == "__main__":
    unittest.main()
