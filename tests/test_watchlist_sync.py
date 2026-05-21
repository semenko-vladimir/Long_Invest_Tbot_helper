import unittest

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.backend.models.database import Base
from app.backend.models.trading import Instrument
from app.services.mode import ModeContext
from app.services.portfolio import PortfolioPosition, PortfolioView
from app.services.watchlist import WatchlistService


class FakePortfolioService:
    def __init__(self, view):
        self.view = view

    def get_portfolio_view(self):
        return self.view


def mode():
    return ModeContext(
        mode="sandbox",
        is_sandbox=True,
        prod_trading_allowed=False,
        trading_available=True,
        banner_title="Mode: sandbox",
        banner_message="Sandbox mode.",
    )


def position(ticker, figi):
    return PortfolioPosition(
        ticker=ticker,
        name=ticker,
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
        figi=figi,
    )


def portfolio_view(positions, error=None):
    return PortfolioView(
        mode=mode(),
        total_value=0.0,
        total_value_display="0.00 RUB",
        positions=positions,
        empty=len(positions) == 0,
        error=error,
    )


class WatchlistSyncTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(bind=self.engine)
        self.session_factory = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)
        self.service = WatchlistService(
            session_factory=self.session_factory,
            token_provider=lambda: "sandbox-token",
        )

    def tearDown(self):
        Base.metadata.drop_all(bind=self.engine)
        self.engine.dispose()

    def add_existing(self, ticker, figi):
        db = self.session_factory()
        try:
            db.add(Instrument(ticker=ticker, figi=figi))
            db.commit()
        finally:
            db.close()

    def tickers(self):
        db = self.session_factory()
        try:
            return [row.ticker for row in db.query(Instrument).order_by(Instrument.ticker.asc()).all()]
        finally:
            db.close()

    def test_sync_empty_portfolio_adds_nothing(self):
        result = self.service.sync_from_portfolio(FakePortfolioService(portfolio_view([])))

        self.assertEqual(result.added, 0)
        self.assertEqual(result.already_present, 0)
        self.assertEqual(result.skipped, 0)
        self.assertEqual(result.errors, 0)
        self.assertEqual(self.tickers(), [])

    def test_sync_all_tickers_already_present(self):
        self.add_existing("SBER", "FIGI-SBER")
        self.add_existing("GAZP", "FIGI-GAZP")

        result = self.service.sync_from_portfolio(
            FakePortfolioService(
                portfolio_view(
                    [
                        position("SBER", "FIGI-SBER"),
                        position("GAZP", "FIGI-GAZP"),
                    ]
                )
            )
        )

        self.assertEqual(result.added, 0)
        self.assertEqual(result.already_present, 2)
        self.assertEqual(result.skipped, 0)
        self.assertEqual(result.errors, 0)
        self.assertEqual(self.tickers(), ["GAZP", "SBER"])

    def test_sync_partial_additions(self):
        self.add_existing("SBER", "FIGI-SBER")

        result = self.service.sync_from_portfolio(
            FakePortfolioService(
                portfolio_view(
                    [
                        position("SBER", "FIGI-SBER"),
                        position("GAZP", "FIGI-GAZP"),
                        position("LKOH", "FIGI-LKOH"),
                    ]
                )
            )
        )

        self.assertEqual(result.added, 2)
        self.assertEqual(result.already_present, 1)
        self.assertEqual(result.skipped, 0)
        self.assertEqual(result.errors, 0)
        self.assertEqual(self.tickers(), ["GAZP", "LKOH", "SBER"])

    def test_sync_portfolio_unavailable_returns_error_without_writes(self):
        result = self.service.sync_from_portfolio(
            FakePortfolioService(portfolio_view([], error="Portfolio data is unavailable right now."))
        )

        self.assertEqual(result.added, 0)
        self.assertEqual(result.already_present, 0)
        self.assertEqual(result.skipped, 0)
        self.assertEqual(result.errors, 1)
        self.assertIn("Portfolio data is unavailable", result.error_messages[0])
        self.assertEqual(self.tickers(), [])

    def test_sync_is_idempotent_and_does_not_duplicate_rows(self):
        portfolio = FakePortfolioService(
            portfolio_view(
                [
                    position("SBER", "FIGI-SBER"),
                    position("SBER", "FIGI-SBER"),
                    position("GAZP", "FIGI-GAZP"),
                ]
            )
        )

        first = self.service.sync_from_portfolio(portfolio)
        second = self.service.sync_from_portfolio(portfolio)

        self.assertEqual(first.added, 2)
        self.assertEqual(second.added, 0)
        self.assertEqual(second.already_present, 2)
        self.assertEqual(self.tickers(), ["GAZP", "SBER"])


if __name__ == "__main__":
    unittest.main()
