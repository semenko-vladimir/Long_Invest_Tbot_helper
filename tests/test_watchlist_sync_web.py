import re
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
from app.services.portfolio import PortfolioPosition, PortfolioView
from app.services.watchlist import WatchlistService


class WatchlistSyncWebTests(unittest.TestCase):
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

    def services(self):
        mode = self.mode()
        return SimpleNamespace(
            user=SimpleNamespace(display_name="Test User", user_id="test", db_path=":memory:"),
            mode_service=SimpleNamespace(current=lambda: mode),
            watchlist_service=WatchlistService(
                session_factory=self.session_factory,
                token_provider=lambda: "sandbox-token",
            ),
            portfolio_service=SimpleNamespace(
                get_portfolio_view=lambda: PortfolioView(
                    mode=mode,
                    total_value=0.0,
                    total_value_display="0.00 RUB",
                    positions=[
                        PortfolioPosition(
                            ticker="SBER",
                            name="SBER",
                            quantity=1.0,
                            quantity_display="1.00",
                            average_price=0.0,
                            average_price_display="0.00 RUB",
                            current_price=0.0,
                            current_price_display="0.00 RUB",
                            pnl=0.0,
                            return_percent=None,
                            currency="RUB",
                            pnl_class="neutral",
                            pnl_display="0.00 RUB",
                            return_display="-",
                            figi="FIGI-SBER",
                        )
                    ],
                    empty=False,
                )
            ),
        )

    def csrf_token(self, response):
        match = re.search(r'name="csrf_token" value="([^"]+)"', response.text)
        self.assertIsNotNone(match)
        return match.group(1)

    def test_watchlist_page_exposes_portfolio_sync_button(self):
        with mock.patch("app.backend.auth.web_auth_enabled", return_value=False), mock.patch(
            "app.backend.web.routes.get_web_services",
            return_value=self.services(),
        ):
            response = self.client.get("/watchlist")

        self.assertEqual(response.status_code, 200)
        self.assertIn("Add portfolio tickers", response.text)
        self.assertIn('/watchlist/sync-portfolio', response.text)

    def test_watchlist_sync_route_adds_portfolio_tickers(self):
        services = self.services()
        with mock.patch("app.backend.auth.web_auth_enabled", return_value=False), mock.patch(
            "app.backend.web.routes.get_web_services",
            return_value=services,
        ):
            form_page = self.client.get("/watchlist")
            response = self.client.post(
                "/watchlist/sync-portfolio",
                data={"csrf_token": self.csrf_token(form_page)},
            )

        self.assertEqual(response.status_code, 200)
        self.assertIn("Portfolio sync: added 1", response.text)

        db = self.session_factory()
        try:
            instruments = db.query(Instrument).all()
            self.assertEqual(len(instruments), 1)
            self.assertEqual(instruments[0].ticker, "SBER")
            self.assertEqual(instruments[0].figi, "FIGI-SBER")
        finally:
            db.close()


if __name__ == "__main__":
    unittest.main()
