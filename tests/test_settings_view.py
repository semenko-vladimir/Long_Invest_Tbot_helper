import unittest
from unittest import mock

from app.services.mode import ModeContext
from app.services.settings_view import SettingsViewService


class FakeModeService:
    def __init__(self, mode: ModeContext):
        self.mode = mode

    def current(self) -> ModeContext:
        return self.mode


class SettingsViewServiceTests(unittest.TestCase):
    def build_service(self) -> SettingsViewService:
        mode = ModeContext(
            mode="sandbox",
            is_sandbox=True,
            prod_trading_allowed=False,
            trading_available=True,
            banner_title="Mode: sandbox",
            banner_message="Sandbox orders are available. Production trading is not active.",
        )
        return SettingsViewService(mode_service=FakeModeService(mode))

    def test_current_reads_runtime_flags_from_config_helpers(self):
        with mock.patch(
            "app.services.settings_view.get_tokens",
            return_value={"sandbox_token": "sandbox-secret", "token": ""},
        ), mock.patch(
            "app.services.settings_view.allow_prod_trading",
            return_value=False,
        ), mock.patch(
            "app.services.settings_view.background_schedulers_enabled",
            return_value=True,
        ), mock.patch(
            "app.services.settings_view.investment_plans_enabled",
            return_value=True,
        ), mock.patch(
            "app.services.settings_view.get_api_base_url",
            return_value="http://localhost:8000",
        ), mock.patch(
            "app.services.settings_view.investor_reminders_enabled",
            return_value=False,
        ), mock.patch(
            "app.services.settings_view.get_investor_reminder_time",
            return_value="09:30",
        ):
            view = self.build_service().current()

        self.assertEqual(view.active_mode, "sandbox")
        self.assertTrue(view.sandbox_token_configured)
        self.assertFalse(view.token_configured)
        self.assertFalse(view.allow_prod_trading)
        self.assertTrue(view.background_schedulers_enabled)
        self.assertTrue(view.investment_plans_enabled)
        self.assertEqual(view.api_base_url, "http://localhost:8000")
        self.assertFalse(view.investor_reminders_enabled)
        self.assertEqual(view.investor_reminder_time, "09:30")

    def test_placeholder_tokens_are_reported_as_not_configured(self):
        with mock.patch(
            "app.services.settings_view.get_tokens",
            return_value={"sandbox_token": "your_sandbox_token", "token": "your_token"},
        ), mock.patch(
            "app.services.settings_view.allow_prod_trading",
            return_value=False,
        ), mock.patch(
            "app.services.settings_view.background_schedulers_enabled",
            return_value=False,
        ), mock.patch(
            "app.services.settings_view.investment_plans_enabled",
            return_value=False,
        ), mock.patch(
            "app.services.settings_view.get_api_base_url",
            return_value="http://localhost:8000",
        ), mock.patch(
            "app.services.settings_view.investor_reminders_enabled",
            return_value=False,
        ), mock.patch(
            "app.services.settings_view.get_investor_reminder_time",
            return_value="09:00",
        ):
            view = self.build_service().current()

        self.assertFalse(view.sandbox_token_configured)
        self.assertFalse(view.token_configured)


if __name__ == "__main__":
    unittest.main()
