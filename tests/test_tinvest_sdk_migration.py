import importlib.metadata
import os
from pathlib import Path
import unittest
from unittest import mock

import t_tech.invest.channels as sdk_channels
from t_tech.invest import CandleInterval, Client, InstrumentIdType, OrderDirection, OrderType
from t_tech.invest.constants import INVEST_GRPC_API, INVEST_GRPC_API_SANDBOX
from t_tech.invest.services import SandboxService

from app.client.utils.tinvest import create_tinvest_client, get_tinvest_target


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


if __name__ == "__main__":
    unittest.main()
