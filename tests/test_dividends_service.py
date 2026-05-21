import unittest
from types import SimpleNamespace

from app.client.handlers.dividends.formatting import generate_dividends_report
from app.services.dividends import DividendItem, DividendsService, DividendsView
from app.services.mode import ModeContext
from app.services.watchlist import WatchlistItem, WatchlistView


class FakeModeService:
    def current(self):
        return ModeContext(
            mode="sandbox",
            is_sandbox=True,
            prod_trading_allowed=False,
            trading_available=True,
            banner_title="Mode: sandbox",
            banner_message="Sandbox mode.",
        )


class FakeWatchlistService:
    def __init__(self, items):
        self.items = items

    def list_items(self):
        return WatchlistView(items=self.items, empty=len(self.items) == 0)


class FakeBroker:
    def __init__(self, *, portfolio=None, dividend=None, portfolio_error=None):
        self.portfolio = portfolio or {"positions": []}
        self.dividend = dividend
        self.portfolio_error = portfolio_error
        self.portfolio_calls = []

    def get_portfolio(self, token, *, sandbox):
        self.portfolio_calls.append({"token": token, "sandbox": sandbox})
        if self.portfolio_error:
            raise self.portfolio_error
        return self.portfolio

    def get_instrument_name(self, token, figi):
        return f"Name {figi}"

    def get_dividend_info(self, token, figi, period_days):
        return self.dividend


def make_service(broker, items=None):
    return DividendsService(
        watchlist_service=FakeWatchlistService(
            items
            or [
                WatchlistItem(
                    id=1,
                    ticker="SBER",
                    figi="FIGI-SBER",
                    name="SBER",
                )
            ]
        ),
        broker=broker,
        mode_service=FakeModeService(),
        token_provider=lambda: "token",
    )


def make_dividend(value="12.5"):
    return SimpleNamespace(
        dividend_net=value,
        payment_date="2026-07-01",
        last_buy_date="2026-06-25",
        record_date="2026-06-27",
        yield_value="4.2",
    )


class DividendsServiceTests(unittest.TestCase):
    def test_calculates_expected_total_from_dividend_and_portfolio_quantity(self):
        broker = FakeBroker(
            portfolio={"positions": [{"ticker": "SBER", "quantity": "10"}]},
            dividend=make_dividend("12,5 RUB"),
        )
        service = make_service(broker)

        view = service.get_dividends_view(365)

        self.assertIsNone(view.portfolio_error)
        self.assertEqual(broker.portfolio_calls, [{"token": "token", "sandbox": True}])
        item = view.items[0]
        self.assertEqual(item.position_quantity, 10.0)
        self.assertEqual(item.position_quantity_display, "10.00")
        self.assertEqual(item.expected_dividend_per_share_display, "12.50 RUB")
        self.assertEqual(item.expected_total_dividend, 125.0)
        self.assertEqual(item.expected_total_dividend_display, "125.00 RUB")

    def test_watchlist_ticker_without_portfolio_position_gets_zero_total(self):
        broker = FakeBroker(
            portfolio={"positions": [{"ticker": "GAZP", "quantity": "3"}]},
            dividend=make_dividend("8"),
        )
        service = make_service(broker)

        view = service.get_dividends_view()

        item = view.items[0]
        self.assertEqual(item.position_quantity, 0.0)
        self.assertEqual(item.position_quantity_display, "0.00")
        self.assertEqual(item.expected_total_dividend, 0.0)
        self.assertEqual(item.expected_total_dividend_display, "0.00 RUB")

    def test_portfolio_unavailable_keeps_dividend_data_visible(self):
        broker = FakeBroker(
            dividend=make_dividend("9.75"),
            portfolio_error=RuntimeError("temporary outage"),
        )
        service = make_service(broker)

        view = service.get_dividends_view()

        self.assertIn("Portfolio data is unavailable", view.portfolio_error)
        item = view.items[0]
        self.assertTrue(item.has_data)
        self.assertEqual(item.position_quantity_display, "-")
        self.assertEqual(item.expected_dividend_per_share_display, "9.75 RUB")
        self.assertIsNone(item.expected_total_dividend)
        self.assertEqual(item.expected_total_dividend_display, "-")

    def test_telegram_report_includes_position_total_dividend(self):
        view = DividendsView(
            period_days=365,
            empty_watchlist=False,
            items=[
                DividendItem(
                    ticker="SBER",
                    name="Sber",
                    next_dividend_date="2026-07-01",
                    expected_dividend="12.50 RUB",
                    position_quantity=10.0,
                    position_quantity_display="10.00",
                    expected_dividend_per_share_display="12.50 RUB",
                    expected_total_dividend=125.0,
                    expected_total_dividend_display="125.00 RUB",
                    estimated_yield="4.2%",
                    last_buy_date="2026-06-25",
                    record_date="2026-06-27",
                    status="Dividend data available.",
                    has_data=True,
                )
            ],
        )

        report = generate_dividends_report(view)

        self.assertIn("Текущая позиция: `10.00`", report)
        self.assertIn("Дивиденд на акцию: `12.50 RUB`", report)
        self.assertIn("Оценка дивиденда по позиции: `125.00 RUB`", report)


if __name__ == "__main__":
    unittest.main()
