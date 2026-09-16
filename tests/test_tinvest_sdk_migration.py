import importlib.metadata
import os
from pathlib import Path
import unittest
from types import SimpleNamespace
from unittest import mock

import t_tech.invest.channels as sdk_channels
from t_tech.invest import CandleInterval, Client, InstrumentIdType, OrderDirection, OrderType
from t_tech.invest.constants import INVEST_GRPC_API, INVEST_GRPC_API_SANDBOX
from t_tech.invest.services import SandboxService

from app.client.utils.tinvest import create_tinvest_client, get_tinvest_target
from app.integrations.tinvest import BrokerPortfolioError, TInvestBroker


ROOT = Path(__file__).resolve().parents[1]


class TInvestSdkMigrationTests(unittest.TestCase):
    def test_current_sdk_namespace_and_required_symbols_are_available(self):
        version = tuple(int(part) for part in importlib.metadata.version("t-tech-investments").split(".")[:2])

        self.assertGreaterEqual(version, (1, 49))
        self.assertTrue(all((CandleInterval, Client, InstrumentIdType, OrderDirection, OrderType)))
        self.assertIsNotNone(SandboxService)

    def test_client_factory_uses_official_mode_endpoints(self):
        self.assertEqual(get_tinvest_target(True), INVEST_GRPC_API_SANDBOX)
        self.assertEqual(get_tinvest_target(False), INVEST_GRPC_API)

        with mock.patch("app.client.utils.tinvest.Client") as client:
            create_tinvest_client("token", sandbox=True)
            client.assert_called_once_with("token", target=INVEST_GRPC_API_SANDBOX)

    def test_tls_setting_uses_bundled_certificate_without_disabling_verification(self):
        env = {"SSL_TBANK_VERIFY": "True"}
        with mock.patch.dict(os.environ, env, clear=False), \
            mock.patch.object(sdk_channels.grpc, "ssl_channel_credentials", return_value="credentials") as ssl_credentials, \
            mock.patch.object(sdk_channels.grpc, "secure_channel", return_value=object()):
            sdk_channels.create_channel(target=INVEST_GRPC_API_SANDBOX)

        root_certificates = ssl_credentials.call_args.kwargs["root_certificates"]
        self.assertIn(b"BEGIN CERTIFICATE", root_certificates)
        example = (ROOT / ".env.example").read_text(encoding="utf-8")
        self.assertIn('SSL_TBANK_VERIFY = "True"', example)
        self.assertNotIn("verify=False", example)

    def test_production_portfolio_uses_exact_requested_account_without_listing_fallback(self):
        broker = TInvestBroker(session_factory=lambda: None)
        client = mock.MagicMock()
        client.operations.get_portfolio.return_value = object()
        client.users.get_accounts.side_effect = AssertionError("portfolio must not list accounts")
        context_manager = mock.MagicMock()
        context_manager.__enter__.return_value = client
        context_manager.__exit__.return_value = False

        with mock.patch("app.integrations.tinvest.create_tinvest_client", return_value=context_manager), \
            mock.patch.object(broker, "_portfolio_response_to_dict", return_value={"positions": []}):
            broker.get_portfolio("token", account_id="requested-account", sandbox=False)

        client.operations.get_portfolio.assert_called_once_with(account_id="requested-account")
        client.users.get_accounts.assert_not_called()

    def test_account_scoped_portfolio_rejects_missing_account_id(self):
        broker = TInvestBroker(session_factory=lambda: None)
        with self.assertRaisesRegex(BrokerPortfolioError, "explicit broker account id"):
            broker.get_portfolio("token", account_id="", sandbox=False)

    def test_production_order_without_explicit_account_fails_before_client_use(self):
        broker = TInvestBroker(session_factory=lambda: None)

        with mock.patch("app.integrations.tinvest.create_tinvest_client") as client_factory:
            with self.assertRaisesRegex(BrokerPortfolioError, "explicit broker account id"):
                broker.place_order(
                    "token",
                    "FIGI-SBER",
                    "SBER",
                    1,
                    "buy",
                    False,
                )

        client_factory.assert_not_called()

    def test_production_order_uses_only_explicit_account_id(self):
        broker = TInvestBroker(session_factory=lambda: None)
        client = mock.MagicMock()
        price = SimpleNamespace(units=100, nano=0)
        context_manager = mock.MagicMock()
        context_manager.__enter__.return_value = client
        context_manager.__exit__.return_value = False

        with mock.patch("app.integrations.tinvest.create_tinvest_client", return_value=context_manager), \
            mock.patch("app.integrations.tinvest.get_current_price", return_value=(price, price)), \
            mock.patch("app.integrations.tinvest.get_lotSize", return_value=10), \
            mock.patch.object(broker, "_record_order"):
            broker.place_order(
                "token",
                "FIGI-SBER",
                "SBER",
                1,
                "buy",
                False,
                account_id="explicit-prod-account",
            )

        client.users.get_accounts.assert_not_called()
        client.orders.post_order.assert_called_once()
        self.assertEqual(
            client.orders.post_order.call_args.kwargs["account_id"],
            "explicit-prod-account",
        )

    def test_ambiguous_sandbox_order_target_fails_without_posting(self):
        broker = TInvestBroker(session_factory=lambda: None)
        client = mock.MagicMock()
        client.sandbox.get_sandbox_accounts.return_value.accounts = [
            SimpleNamespace(id="sandbox-a"),
            SimpleNamespace(id="sandbox-b"),
        ]
        context_manager = mock.MagicMock()
        context_manager.__enter__.return_value = client
        context_manager.__exit__.return_value = False

        with mock.patch("app.integrations.tinvest.create_tinvest_client", return_value=context_manager):
            with self.assertRaisesRegex(BrokerPortfolioError, "multiple sandbox accounts"):
                broker.place_order("token", "FIGI-SBER", "SBER", 1, "buy", True)

        client.sandbox.open_sandbox_account.assert_not_called()
        client.sandbox.post_sandbox_order.assert_not_called()

    def test_account_discovery_normalizes_broker_metadata_without_mutation(self):
        broker = TInvestBroker(session_factory=lambda: None)
        account = mock.Mock()
        account.id = "stable-account-id"
        account.name = "Broker-provided name"
        account.type = "ACCOUNT_TYPE_TINKOFF"
        account.status = "ACCOUNT_STATUS_OPEN"
        account.access_level = "ACCOUNT_ACCESS_LEVEL_FULL_ACCESS"
        client = mock.MagicMock()
        client.users.get_accounts.return_value.accounts = [account]
        context_manager = mock.MagicMock()
        context_manager.__enter__.return_value = client
        context_manager.__exit__.return_value = False

        with mock.patch("app.integrations.tinvest.create_tinvest_client", return_value=context_manager):
            result = broker.list_accounts("token", sandbox=False)

        self.assertEqual(result[0].external_account_id, "stable-account-id")
        self.assertEqual(result[0].name, "Broker-provided name")
        self.assertEqual(result[0].account_type, "brokerage")
        self.assertEqual(result[0].status, "open")
        self.assertEqual(result[0].access_level, "full_access")
        client.users.get_accounts.assert_called_once_with()
        client.orders.post_order.assert_not_called()

    def test_account_discovery_fallback_name_does_not_expose_external_id(self):
        broker = TInvestBroker(session_factory=lambda: None)
        account = mock.Mock()
        account.id = "stable-sensitive-looking-account-id"
        account.name = ""
        account.type = "ACCOUNT_TYPE_TINKOFF_IIS"
        account.status = "ACCOUNT_STATUS_OPEN"
        account.access_level = "ACCOUNT_ACCESS_LEVEL_READ_ONLY"
        client = mock.MagicMock()
        client.users.get_accounts.return_value.accounts = [account]
        context_manager = mock.MagicMock()
        context_manager.__enter__.return_value = client
        context_manager.__exit__.return_value = False

        with mock.patch("app.integrations.tinvest.create_tinvest_client", return_value=context_manager):
            result = broker.list_accounts("token", sandbox=False)

        self.assertEqual(result[0].name, "T-Invest account")
        self.assertNotIn(account.id, result[0].name)
        self.assertEqual(result[0].account_type, "iis")

    def test_empty_sandbox_discovery_does_not_open_an_account(self):
        broker = TInvestBroker(session_factory=lambda: None)
        client = mock.MagicMock()
        client.sandbox.get_sandbox_accounts.return_value.accounts = []
        context_manager = mock.MagicMock()
        context_manager.__enter__.return_value = client
        context_manager.__exit__.return_value = False

        with mock.patch("app.integrations.tinvest.create_tinvest_client", return_value=context_manager):
            result = broker.list_accounts("token", sandbox=True)

        self.assertEqual(result, [])
        client.sandbox.open_sandbox_account.assert_not_called()
        client.sandbox.post_sandbox_order.assert_not_called()


if __name__ == "__main__":
    unittest.main()
