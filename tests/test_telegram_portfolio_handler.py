import unittest
from types import SimpleNamespace
from unittest import mock

from app.client.handlers.menu.main_menu import build_main_menu
from app.client.handlers.portfolio import portfolio_handler
from app.services.accounts import InvestmentAccountContext, UnknownInvestmentAccountError
from app.services.mode import ModeContext
from app.services.portfolio import AccountPortfolioView, AggregatePortfolioView


def mode(*, trading_available=False):
    return ModeContext(
        mode="prod",
        is_sandbox=False,
        prod_trading_allowed=trading_available,
        trading_available=trading_available,
        banner_title="Mode: prod",
        banner_message="Test",
    )


def account(account_id=1):
    return InvestmentAccountContext(
        user_id="user-1",
        investment_account_id=account_id,
        broker_connection_id=1,
        broker_provider="tinvest",
        broker_connection_key="default",
        external_account_id="broker-secret-looking-id",
        account_name="Main brokerage",
        account_type="BROKER",
        status="OPEN",
        access_level="FULL_ACCESS",
    )


class TelegramPortfolioHandlerTests(unittest.TestCase):
    def test_prod_read_only_main_menu_has_no_actionable_order_buttons(self):
        keyboard = build_main_menu(mode(trading_available=False))
        labels = {button["text"] for row in keyboard.keyboard for button in row}

        self.assertNotIn("Buy", labels)
        self.assertNotIn("Sell", labels)
        self.assertIn("Portfolio", labels)

    def test_account_selector_uses_internal_id_not_external_broker_id(self):
        context = account(37)
        account_view = AccountPortfolioView(
            mode=mode(),
            account=context,
            total_value=100,
            total_value_display="100.00 RUB",
            positions=(),
            empty=True,
        )
        aggregate = AggregatePortfolioView(
            mode=mode(),
            total_value=100,
            total_value_display="100.00 RUB",
            accounts=(account_view,),
            empty=True,
            partial=False,
        )

        keyboard = portfolio_handler.build_aggregate_portfolio_keyboard(aggregate)
        callback_data = keyboard.keyboard[0][0].callback_data

        self.assertEqual(callback_data, "portfolio:account:37")
        self.assertNotIn(context.external_account_id, callback_data)

    def test_unknown_or_stale_account_callback_is_rejected_without_portfolio_load(self):
        registry = mock.Mock()
        registry.get_account_context.side_effect = UnknownInvestmentAccountError("stale")
        portfolio_service = mock.Mock()
        services = SimpleNamespace(account_registry=registry, portfolio_service=portfolio_service)
        call = SimpleNamespace(
            id="callback-id",
            data="portfolio:account:999",
            message=SimpleNamespace(chat=SimpleNamespace(id=42)),
        )

        with mock.patch.object(portfolio_handler, "get_telegram_services_or_notify", return_value=services), \
            mock.patch.object(portfolio_handler.bot, "answer_callback_query"), \
            mock.patch.object(portfolio_handler.bot, "send_message") as send_message:
            portfolio_handler.portfolio_account_callback(call)

        portfolio_service.get_account_portfolio.assert_not_called()
        self.assertIn("unavailable", send_message.call_args.args[1])


if __name__ == "__main__":
    unittest.main()
