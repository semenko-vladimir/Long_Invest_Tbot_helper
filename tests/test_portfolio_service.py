import unittest

from app.services.accounts import InvestmentAccountContext
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


def account(account_id: int, external_id: str, name: str) -> InvestmentAccountContext:
    return InvestmentAccountContext(
        user_id="user-1",
        investment_account_id=account_id,
        broker_connection_id=1,
        broker_provider="tinvest",
        broker_connection_key="default",
        external_account_id=external_id,
        account_name=name,
        account_type="BROKER",
        status="OPEN",
        access_level="FULL_ACCESS",
    )


class FakeRegistry:
    def __init__(self, accounts):
        self.accounts = tuple(accounts)

    def sync_accounts(self):
        return type("Result", (), {"accounts": self.accounts})()

    def list_enabled_accounts(self):
        return self.accounts

    def validate_account_context(self, account_context):
        return account_context


class FakeBroker:
    provider_key = "tinvest"

    def __init__(self, portfolios=None, names=None, failing_ids=()):
        self.portfolios = portfolios or {}
        self.names = names or {}
        self.failing_ids = set(failing_ids)
        self.portfolio_calls = []

    def get_portfolio(self, token, *, account_id, sandbox):
        self.portfolio_calls.append({"token": token, "account_id": account_id, "sandbox": sandbox})
        if account_id in self.failing_ids:
            raise RuntimeError("broker unavailable")
        return self.portfolios.get(account_id, {"total_amount_portfolio": 0, "positions": []})

    def get_instrument_name(self, token, figi):
        return self.names.get(figi)


class PortfolioServiceTests(unittest.TestCase):
    def service(self, broker, accounts, token="token", mode="sandbox"):
        return PortfolioService(
            broker=broker,
            mode_service=FakeModeService(mode=mode, trading_available=mode == "sandbox"),
            token_provider=lambda: token,
            account_registry=FakeRegistry(accounts),
        )

    def test_missing_token_returns_account_error_without_broker_call(self):
        broker = FakeBroker()
        context = account(1, "ext-a", "Account A")
        view = self.service(broker, [context], token=None).get_account_portfolio(context)

        self.assertTrue(view.empty)
        self.assertIn("No broker token", view.error)
        self.assertEqual(broker.portfolio_calls, [])

    def test_account_portfolio_uses_exact_external_account_id_and_attributes_positions(self):
        context = account(2, "ext-b", "Account B")
        broker = FakeBroker(
            portfolios={
                "ext-b": {
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
                }
            },
            names={"FIGI-SBER": "Sber"},
        )

        view = self.service(broker, [context], mode="prod").get_account_portfolio(context)

        self.assertEqual(
            broker.portfolio_calls,
            [{"token": "token", "account_id": "ext-b", "sandbox": False}],
        )
        self.assertEqual(view.total_value, 1000.0)
        self.assertEqual(view.positions[0].investment_account_id, 2)
        self.assertEqual(view.positions[0].account_name, "Account B")
        self.assertEqual(view.positions[0].pnl, 200.0)

    def test_aggregate_keeps_same_ticker_positions_separate_and_sums_account_totals(self):
        account_a = account(1, "ext-a", "Account A")
        account_b = account(2, "ext-b", "Account B")
        position = {
            "ticker": "SBER",
            "figi": "FIGI-SBER",
            "quantity": 1,
            "average_position_price": 100,
            "current_price": 110,
            "current_price_one": 110,
        }
        broker = FakeBroker(
            portfolios={
                "ext-a": {"total_amount_portfolio": 110, "positions": [position]},
                "ext-b": {"total_amount_portfolio": 220, "positions": [{**position, "quantity": 2, "current_price": 220}]},
            }
        )

        view = self.service(broker, [account_a, account_b]).get_aggregate_portfolio()

        self.assertEqual(view.total_value, 330)
        self.assertEqual(len(view.accounts), 2)
        self.assertEqual(len(view.positions), 2)
        self.assertEqual({item.investment_account_id for item in view.positions}, {1, 2})

    def test_partial_failure_is_explicit_and_successful_total_is_not_presented_as_complete(self):
        account_a = account(1, "ext-a", "Account A")
        account_b = account(2, "ext-b", "Account B")
        broker = FakeBroker(
            portfolios={"ext-a": {"total_amount_portfolio": 100, "positions": []}},
            failing_ids={"ext-b"},
        )

        view = self.service(broker, [account_a, account_b]).get_aggregate_portfolio()

        self.assertTrue(view.partial)
        self.assertEqual(view.total_value, 100)
        self.assertIsNone(view.accounts[0].error)
        self.assertIn("Portfolio data is unavailable", view.accounts[1].error)

    def test_single_account_aggregate_remains_supported(self):
        context = account(1, "only-account", "Only Account")
        broker = FakeBroker(portfolios={"only-account": {"total_amount_portfolio": 42, "positions": []}})

        view = self.service(broker, [context]).get_portfolio_view()

        self.assertEqual(view.total_value, 42)
        self.assertFalse(view.partial)
        self.assertIsNone(view.error)


if __name__ == "__main__":
    unittest.main()
