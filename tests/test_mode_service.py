import os
import unittest
from unittest import mock

from app.client.config import allow_prod_trading, get_invest_mode, is_sandbox_mode
from app.services.mode import ModeService


class ModeServiceTests(unittest.TestCase):
    def test_config_defaults_to_sandbox_with_prod_trading_disabled(self):
        with mock.patch.dict(os.environ, {}, clear=True), mock.patch("app.client.config.load_dotenv"):
            self.assertEqual(get_invest_mode(), "sandbox")
            self.assertTrue(is_sandbox_mode())
            self.assertFalse(allow_prod_trading())

    def test_config_reads_prod_mode_and_explicit_trading_flag(self):
        with mock.patch.dict(
            os.environ,
            {"APP_MODE": "prod", "ALLOW_PROD_TRADING": "true"},
            clear=True,
        ), mock.patch("app.client.config.load_dotenv"):
            self.assertEqual(get_invest_mode(), "prod")
            self.assertFalse(is_sandbox_mode())
            self.assertTrue(allow_prod_trading())

    def test_mode_service_allows_sandbox_trading_by_default(self):
        with mock.patch("app.services.mode.get_invest_mode", return_value="sandbox"), \
            mock.patch("app.services.mode.is_sandbox_mode", return_value=True), \
            mock.patch("app.services.mode.allow_prod_trading", return_value=False):
            mode = ModeService().current()

        self.assertEqual(mode.mode, "sandbox")
        self.assertTrue(mode.trading_available)
        self.assertFalse(mode.prod_trading_allowed)

    def test_mode_service_blocks_prod_when_flag_is_disabled(self):
        with mock.patch("app.services.mode.get_invest_mode", return_value="prod"), \
            mock.patch("app.services.mode.is_sandbox_mode", return_value=False), \
            mock.patch("app.services.mode.allow_prod_trading", return_value=False):
            mode = ModeService().current()

        self.assertEqual(mode.mode, "prod")
        self.assertFalse(mode.trading_available)
        self.assertIn("trading disabled", mode.banner_title)

    def test_mode_service_allows_prod_only_when_flag_is_enabled(self):
        with mock.patch("app.services.mode.get_invest_mode", return_value="prod"), \
            mock.patch("app.services.mode.is_sandbox_mode", return_value=False), \
            mock.patch("app.services.mode.allow_prod_trading", return_value=True):
            mode = ModeService().current()

        self.assertEqual(mode.mode, "prod")
        self.assertTrue(mode.trading_available)
        self.assertTrue(mode.prod_trading_allowed)


if __name__ == "__main__":
    unittest.main()
