from contextlib import ExitStack
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

    def config_patches(self, **overrides):
        values = {
            "get_tokens": {"sandbox_token": "sandbox-secret", "token": ""},
            "allow_prod_trading": False,
            "background_schedulers_enabled": True,
            "investment_plans_enabled": True,
            "get_api_base_url": "http://localhost:8000",
            "investor_reminders_enabled": False,
            "get_investor_reminder_time": "09:30",
            "anti_greedy_policy_enabled": True,
            "get_anti_greedy_profit_pct": 20.0,
            "get_anti_greedy_check_time": "18:30",
            "web_auth_enabled": True,
            "get_web_auth_token": "owner-secret",
        }
        values.update(overrides)
        return [
            mock.patch(f"app.services.settings_view.{name}", return_value=value)
            for name, value in values.items()
        ]

    def test_current_reads_runtime_flags_from_config_helpers(self):
        with ExitStack() as stack:
            for patcher in self.config_patches():
                stack.enter_context(patcher)
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
        self.assertTrue(view.anti_greedy_policy_enabled)
        self.assertEqual(view.anti_greedy_profit_pct, 20.0)
        self.assertEqual(view.anti_greedy_check_time, "18:30")
        self.assertTrue(view.web_auth_enabled)
        self.assertTrue(view.web_auth_token_configured)

    def test_placeholder_tokens_are_reported_as_not_configured(self):
        with ExitStack() as stack:
            for patcher in self.config_patches(
                get_tokens={"sandbox_token": "your_sandbox_token", "token": "your_token"},
                background_schedulers_enabled=False,
                investment_plans_enabled=False,
                get_investor_reminder_time="09:00",
                anti_greedy_policy_enabled=False,
                web_auth_enabled=False,
                get_web_auth_token=None,
            ):
                stack.enter_context(patcher)
            view = self.build_service().current()

        self.assertFalse(view.sandbox_token_configured)
        self.assertFalse(view.token_configured)
        self.assertFalse(view.web_auth_enabled)
        self.assertFalse(view.web_auth_token_configured)
        self.assertFalse(view.anti_greedy_policy_enabled)


if __name__ == "__main__":
    unittest.main()
