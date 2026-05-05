import ast
import json
from datetime import datetime
from pathlib import Path
import unittest

from fastapi import FastAPI
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

try:
    from fastapi.testclient import TestClient
except RuntimeError as exc:
    TestClient = None
    TESTCLIENT_IMPORT_ERROR = str(exc)
else:
    TESTCLIENT_IMPORT_ERROR = ""

from app.backend.api import api_router
from app.backend.api.endpoints.research import ResearchServices, get_research_services
from app.backend.models.database import Base, get_db
from app.research.schemas import (
    AdapterResult,
    DataGap,
    InstrumentIdentity,
    MarketSnapshot,
    ResearchReport,
    SourceFreshness,
)
from app.research.services import ResearchReportService, TickerResearchService
from app.research.snapshots import ResearchSnapshotService, snapshot_to_dict


class SnapshotAdapter:
    source_name = "snapshot-source"

    def fetch(self, ticker: str) -> AdapterResult:
        fetched_at = datetime(2026, 5, 5, 10, 0)
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
            freshness=SourceFreshness(source_name=self.source_name, fetched_at=fetched_at),
            gaps=[DataGap("financials", "Financial source is not configured.", "medium")],
            errors=["Optional data source unavailable."],
        )


class ResearchSnapshotServiceTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)
        Base.metadata.create_all(bind=self.engine)
        self.db = self.SessionLocal()

    def tearDown(self):
        self.db.close()
        Base.metadata.drop_all(bind=self.engine)
        self.engine.dispose()

    def build_report(self, ticker="SBER", source="unit-source", generated_at=None):
        generated_at = generated_at or datetime(2026, 5, 5, 10, 30)
        return ResearchReport(
            ticker=ticker,
            generated_at=generated_at,
            instrument_identity=InstrumentIdentity(
                ticker=ticker,
                figi=f"FIGI-{ticker}",
                name=f"{ticker} name",
                currency="RUB",
            ),
            sources=[source],
            freshness=[
                SourceFreshness(
                    source_name=source,
                    fetched_at=datetime(2026, 5, 5, 10, 0),
                    as_of_date="2026-05-05",
                )
            ],
            market_snapshot=MarketSnapshot(
                current_price=101.5,
                currency="RUB",
                captured_at=datetime(2026, 5, 5, 10, 0),
            ),
            company_profile={
                "public_note": "Stored local research data.",
                "api_token": "SHOULD_NOT_BE_STORED",
            },
            data_gaps=[DataGap("financials", "Financial source is not configured.", "medium")],
            errors=["Optional data source unavailable."],
        )

    def test_save_report_snapshot_stores_required_fields_and_report_json(self):
        service = ResearchSnapshotService(
            self.db,
            now_provider=lambda: datetime(2026, 5, 5, 11, 0),
        )

        snapshot = service.save_report(self.build_report())

        self.assertIsNotNone(snapshot.id)
        self.assertEqual(snapshot.ticker, "SBER")
        self.assertEqual(snapshot.generated_at, datetime(2026, 5, 5, 10, 30))
        self.assertEqual(json.loads(snapshot.source_names), ["unit-source"])
        self.assertEqual(snapshot.data_gap_count, 1)
        self.assertEqual(snapshot.error_count, 1)

        payload = snapshot_to_dict(snapshot)
        report_json = payload["report_json"]
        self.assertEqual(report_json["ticker"], "SBER")
        self.assertEqual(report_json["data_gaps"][0]["category"], "financials")
        self.assertEqual(report_json["errors"], ["Optional data source unavailable."])
        self.assertEqual(report_json["company_profile"]["public_note"], "Stored local research data.")
        self.assertNotIn("api_token", report_json["company_profile"])
        self.assertIn("not personal investment advice", report_json["disclaimer"])
        self.assertIsNone(report_json["educational_rating"])
        self.assertNotIn("token", json.dumps(payload).lower())
        self.assertNotIn("secret", json.dumps(payload).lower())
        self.assertNotIn("should_not_be_stored", json.dumps(payload).lower())

    def test_list_recent_supports_limit_and_ticker_filter(self):
        service = ResearchSnapshotService(self.db)
        sber = service.save_report(self.build_report("SBER", "source-a"))
        gazp = service.save_report(self.build_report("GAZP", "source-b"))

        recent = service.list_recent(limit=1)
        sber_only = service.list_recent(ticker=" sber ", limit=10)

        self.assertEqual(len(recent), 1)
        self.assertEqual(recent[0].id, gazp.id)
        self.assertEqual([snapshot.id for snapshot in sber_only], [sber.id])

    def test_get_snapshot_returns_one_snapshot_by_id(self):
        service = ResearchSnapshotService(self.db)
        snapshot = service.save_report(self.build_report())

        loaded = service.get_snapshot(snapshot.id)

        self.assertIsNotNone(loaded)
        self.assertEqual(loaded.id, snapshot.id)
        self.assertIsNone(service.get_snapshot(9999))

    def test_snapshot_service_imports_no_order_signal_or_llm_modules(self):
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
        paths = [
            Path(__file__).resolve().parents[1] / "app" / "research" / "snapshots.py",
            Path(__file__).resolve().parents[1] / "app" / "backend" / "models" / "research.py",
        ]

        imported_modules = set()
        imported_names = set()
        attribute_names = set()
        for path in paths:
            tree = ast.parse(path.read_text(encoding="utf-8"))
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


@unittest.skipIf(TestClient is None, TESTCLIENT_IMPORT_ERROR)
class ResearchSnapshotApiTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)
        Base.metadata.create_all(bind=self.engine)

    def tearDown(self):
        Base.metadata.drop_all(bind=self.engine)
        self.engine.dispose()

    def build_client(self):
        app = FastAPI()
        app.include_router(api_router, prefix="/api")
        now = datetime(2026, 5, 5, 10, 30)

        def override_get_db():
            db = self.SessionLocal()
            try:
                yield db
            finally:
                db.close()

        app.dependency_overrides[get_db] = override_get_db
        app.dependency_overrides[get_research_services] = lambda: ResearchServices(
            ticker_research=TickerResearchService([SnapshotAdapter()], now_provider=lambda: now),
            report_builder=ResearchReportService(now_provider=lambda: now),
        )
        return TestClient(app)

    def test_research_report_endpoint_saves_read_only_snapshot_without_changing_response(self):
        client = self.build_client()

        report_response = client.get("/api/research/sber")
        snapshots_response = client.get("/api/research/snapshots?ticker=SBER")

        self.assertEqual(report_response.status_code, 200)
        report_payload = report_response.json()
        self.assertEqual(report_payload["ticker"], "SBER")
        self.assertNotIn("snapshot", report_payload)

        self.assertEqual(snapshots_response.status_code, 200)
        snapshots = snapshots_response.json()
        self.assertEqual(len(snapshots), 1)
        self.assertEqual(snapshots[0]["ticker"], "SBER")
        self.assertEqual(snapshots[0]["source_names"], ["snapshot-source"])
        self.assertEqual(snapshots[0]["data_gap_count"], 2)
        self.assertEqual(snapshots[0]["error_count"], 1)
        self.assertIsNone(snapshots[0]["report_json"]["educational_rating"])
        self.assertIn("data_gaps", snapshots[0]["report_json"])
        self.assertIn("errors", snapshots[0]["report_json"])
        self.assertIn("disclaimer", snapshots[0]["report_json"])

    def test_snapshot_detail_endpoint_loads_one_snapshot_by_id(self):
        client = self.build_client()
        client.get("/api/research/sber")
        snapshots = client.get("/api/research/snapshots").json()

        detail_response = client.get(f"/api/research/snapshots/{snapshots[0]['id']}")
        missing_response = client.get("/api/research/snapshots/9999")

        self.assertEqual(detail_response.status_code, 200)
        self.assertEqual(detail_response.json()["id"], snapshots[0]["id"])
        self.assertEqual(missing_response.status_code, 404)


if __name__ == "__main__":
    unittest.main()
