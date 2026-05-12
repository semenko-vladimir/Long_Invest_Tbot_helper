import unittest
from types import SimpleNamespace
from unittest import mock

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.backend.main_api import app
from app.backend.models.database import Base
from app.backend.models.trading import Instrument
from app.services.mode import ModeContext
from app.services.portfolio import PortfolioView
from app.services.settings_view import SettingsView
from app.services.statistics import StatisticsService
from app.services.trading_policy import TradingPolicyStatus
from app.services.watchlist import WatchlistService


class FakeBroker:
    def resolve_unique_instrument(self, _token, ticker):
        return SimpleNamespace(ticker=ticker.upper(), figi=f"FIGI-{ticker.upper()}")


class WebRouteTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(bind=self.engine)
        self.session_factory = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)
        self.client = TestClient(app)

    def tearDown(self):
        Base.metadata.drop_all(bind=self.engine)
        self.engine.dispose()

    def mode(self):
        return ModeContext(
            mode="sandbox",
            is_sandbox=True,
            prod_trading_allowed=False,
            trading_available=True,
            banner_title="Mode: sandbox",
            banner_message="Sandbox mode.",
        )

    def plan_policy(self):
        mode = self.mode()
        return TradingPolicyStatus(
            plans_enabled=True,
            auto_investing_allowed=False,
            max_order_rub=0.0,
            max_order_rub_display="0.00 RUB",
            max_daily_invest_rub=0.0,
            max_daily_invest_rub_display="0.00 RUB",
            daily_used_rub=0.0,
            daily_used_rub_display="0.00 RUB",
            daily_remaining_rub=0.0,
            daily_remaining_rub_display="0.00 RUB",
            mode=mode,
            automation_mode_allowed=True,
            summary="Manual proposals only.",
            blocked_reasons=[],
        )

    def services(self):
        mode = self.mode()
        watchlist_service = WatchlistService(
            broker=FakeBroker(),
            session_factory=self.session_factory,
            token_provider=lambda: "sandbox-token",
        )
        return SimpleNamespace(
            user=SimpleNamespace(display_name="Test User", user_id="test", db_path=":memory:"),
            mode_service=SimpleNamespace(current=lambda: mode),
            portfolio_service=SimpleNamespace(
                get_portfolio_view=lambda: PortfolioView(
                    mode=mode,
                    total_value=0.0,
                    total_value_display="0.00 RUB",
                    positions=[],
                    empty=True,
                )
            ),
            watchlist_service=watchlist_service,
            statistics_service=StatisticsService(session_factory=self.session_factory),
            settings_view_service=SimpleNamespace(
                current=lambda: SettingsView(
                    mode=mode,
                    active_mode="sandbox",
                    active_mode_meaning="Sandbox mode.",
                    sandbox_token_configured=True,
                    token_configured=False,
                    allow_prod_trading=False,
                    background_schedulers_enabled=False,
                    investment_plans_enabled=True,
                    api_base_url="http://localhost:8000",
                    investor_reminders_enabled=False,
                    investor_reminder_time="09:00",
                )
            ),
            investment_plan_service=SimpleNamespace(policy_status=self.plan_policy),
        )

    def test_health_endpoint(self):
        response = self.client.get("/api/health")

        self.assertEqual(response.status_code, 200)

    def test_portfolio_page_loads(self):
        with mock.patch("app.backend.web.routes.get_web_services", return_value=self.services()):
            response = self.client.get("/portfolio")

        self.assertEqual(response.status_code, 200)
        self.assertIn("text/html", response.headers["content-type"])

    def test_watchlist_page_loads(self):
        with mock.patch("app.backend.web.routes.get_web_services", return_value=self.services()):
            response = self.client.get("/watchlist")

        self.assertEqual(response.status_code, 200)
        self.assertIn("text/html", response.headers["content-type"])

    def test_stats_page_loads(self):
        with mock.patch("app.backend.web.routes.get_web_services", return_value=self.services()):
            response = self.client.get("/stats")

        self.assertEqual(response.status_code, 200)
        self.assertIn("text/html", response.headers["content-type"])

    def test_settings_page_loads(self):
        with mock.patch("app.backend.web.routes.get_web_services", return_value=self.services()):
            response = self.client.get("/settings")

        self.assertEqual(response.status_code, 200)
        self.assertIn("text/html", response.headers["content-type"])

    def test_unknown_route_returns_404(self):
        response = self.client.get("/nonexistent-page")

        self.assertEqual(response.status_code, 404)

    def test_watchlist_add_form_submission(self):
        services = self.services()
        with mock.patch("app.backend.web.routes.get_web_services", return_value=services):
            response = self.client.post("/watchlist/add", data={"ticker": "sber"})

        self.assertEqual(response.status_code, 200)
        self.assertIn("SBER was added to the watchlist.", response.text)

        db = self.session_factory()
        try:
            instrument = db.query(Instrument).filter(Instrument.ticker == "SBER").first()
            self.assertIsNotNone(instrument)
            self.assertEqual(instrument.figi, "FIGI-SBER")
        finally:
            db.close()


if __name__ == "__main__":
    unittest.main()
