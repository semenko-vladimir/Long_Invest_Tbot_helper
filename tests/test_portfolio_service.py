import unittest

from app.services.mode import ModeContext
from app.services.portfolio import PortfolioService


class FakeModeService:
    def __init__(self, *, mode="sandbox", trading_available=True):
        self.mode = mode
        self.trading_available = trading_available

    def current(self):
        return ModeContext(
            mode=self.mode,
            is_sandbox=self.mode == "sandbox",
            prod_trading_allowed=self.mode == "prod" and self.trading_available,
            trading_available=self.trading_available,
            banner_title=f"Mode: {self.mode}",
            banner_message="Test mode",
        )


class FakeBroker:
    def __init__(self, portfolio=None, names=None, raises=False):
        self.portfolio = portfolio or {"total_amount_portfolio": 0, "positions": []}
        self.names = names or {}
        self.raises = raises
        self.portfolio_calls = []

    def get_portfolio(self, token, *, sandbox):
        self.portfolio_calls.append({"token": token, "sandbox": sandbox})
        if self.raises:
            raise RuntimeError("broker unavailable")
        return self.portfolio

    def get_instrument_name(self, token, figi):
        return self.names.get(figi)


class PortfolioServiceTests(unittest.TestCase):
    def test_missing_token_returns_empty_error_without_broker_call(self):
        broker = FakeBroker()
        service = PortfolioService(
            broker=broker,
            mode_service=FakeModeService(),
            token_provider=lambda: None,
        )

        view = service.get_portfolio_view()

        self.assertTrue(view.empty)
        self.assertEqual(view.total_value, 0.0)
        self.assertIn("No broker token", view.error)
        self.assertEqual(broker.portfolio_calls, [])

    def test_maps_raw_portfolio_positions_to_view_values(self):
        broker = FakeBroker(
            portfolio={
                "total_amount_portfolio": "1000",
                "positions": [
                    {
                        "ticker": "SBER",
                        "figi": "FIGI-SBER",
                        "quantity": "2",
                        "average_position_price": "400",
                        "current_price": "1000",
                        "current_price_one": "500",
                        "expected_yield": "200",
                    }
                ],
            },
            names={"FIGI-SBER": "Sber"},
        )
        service = PortfolioService(
            broker=broker,
            mode_service=FakeModeService(),
            token_provider=lambda: "token",
        )

        view = service.get_portfolio_view()

        self.assertFalse(view.empty)
        self.assertEqual(view.total_value, 1000.0)
        self.assertEqual(view.total_value_display, "1 000.00 RUB")
        self.assertEqual(broker.portfolio_calls, [{"token": "token", "sandbox": True}])
        position = view.positions[0]
        self.assertEqual(position.ticker, "SBER")
        self.assertEqual(position.name, "Sber")
        self.assertEqual(position.pnl, 200.0)
        self.assertEqual(position.pnl_class, "positive")
        self.assertEqual(position.pnl_display, "+200.00 RUB")
        self.assertEqual(position.return_display, "+25.00%")

    def test_broker_failure_returns_safe_empty_view(self):
        broker = FakeBroker(raises=True)
        service = PortfolioService(
            broker=broker,
            mode_service=FakeModeService(mode="prod", trading_available=False),
            token_provider=lambda: "token",
        )

        view = service.get_portfolio_view()

        self.assertTrue(view.empty)
        self.assertEqual(view.mode.mode, "prod")
        self.assertIn("Portfolio data is unavailable", view.error)


if __name__ == "__main__":
    unittest.main()
