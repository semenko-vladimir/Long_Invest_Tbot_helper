from contextlib import contextmanager
import os
from types import SimpleNamespace
import unittest
from unittest import mock

from fastapi.testclient import TestClient

from app.backend.main_api import app
from app.client import config as app_config
from app.services.mode import ModeContext
from app.services.portfolio import PortfolioView
from app.services.settings_view import SettingsView
from app.services.trading_policy import TradingPolicyStatus


OWNER_TOKEN = "owner-secret-token"


@contextmanager
def patched_web_auth(*, enabled: bool, token: str | None = OWNER_TOKEN):
    with mock.patch("app.backend.auth.web_auth_enabled", return_value=enabled), mock.patch(
        "app.backend.auth.get_web_auth_token",
        return_value=token,
    ):
        yield


class WebAuthMiddlewareTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def mode(self) -> ModeContext:
        return ModeContext(
            mode="sandbox",
            is_sandbox=True,
            prod_trading_allowed=False,
            trading_available=True,
            banner_title="Mode: sandbox",
            banner_message="Sandbox mode.",
        )

    def plan_policy(self) -> TradingPolicyStatus:
        mode = self.mode()
        return TradingPolicyStatus(
            plans_enabled=True,
            auto_investing_allowed=False,
            max_order_rub=0.0,
            max_order_rub_display="0.00 RUB",
            max_daily_invest_rub=0.0,
            max_daily_invest_rub_display="0.00 RUB",
            daily_used_rub=0.0,
            daily_used_rub_display="0.00 RUB",
            daily_remaining_rub=0.0,
            daily_remaining_rub_display="0.00 RUB",
            mode=mode,
            automation_mode_allowed=True,
            summary="Manual proposals only.",
            blocked_reasons=[],
        )

    def services(self, settings: SettingsView | None = None):
        mode = self.mode()
        return SimpleNamespace(
            user=SimpleNamespace(display_name="Test User", user_id="test", db_path=":memory:"),
            mode_service=SimpleNamespace(current=lambda: mode),
            portfolio_service=SimpleNamespace(
                get_portfolio_view=lambda: PortfolioView(
                    mode=mode,
                    total_value=0.0,
                    total_value_display="0.00 RUB",
                    positions=[],
                    empty=True,
                )
            ),
            settings_view_service=SimpleNamespace(current=lambda: settings or self.settings_view()),
            investment_plan_service=SimpleNamespace(policy_status=self.plan_policy),
        )

    def settings_view(self) -> SettingsView:
        mode = self.mode()
        return SettingsView(
            mode=mode,
            active_mode="sandbox",
            active_mode_meaning="Sandbox mode.",
            sandbox_token_configured=True,
            token_configured=False,
            allow_prod_trading=False,
            background_schedulers_enabled=False,
            investment_plans_enabled=True,
            api_base_url="http://localhost:8000",
            investor_reminders_enabled=False,
            investor_reminder_time="09:00",
            web_auth_enabled=True,
            web_auth_token_configured=True,
        )

    def test_auth_disabled_keeps_portfolio_available(self):
        with patched_web_auth(enabled=False), mock.patch(
            "app.backend.web.routes.get_web_services",
            return_value=self.services(),
        ):
            response = self.client.get("/portfolio")

        self.assertEqual(response.status_code, 200)

    def test_auth_enabled_blocks_portfolio_without_authorization(self):
        with patched_web_auth(enabled=True):
            response = self.client.get("/portfolio")

        self.assertEqual(response.status_code, 401)

    def test_auth_enabled_blocks_wrong_bearer_token(self):
        with patched_web_auth(enabled=True):
            response = self.client.get("/portfolio", headers={"Authorization": "Bearer wrong-token"})

        self.assertEqual(response.status_code, 401)

    def test_auth_enabled_allows_correct_bearer_token(self):
        with patched_web_auth(enabled=True), mock.patch(
            "app.backend.web.routes.get_web_services",
            return_value=self.services(),
        ):
            response = self.client.get("/portfolio", headers={"Authorization": f"Bearer {OWNER_TOKEN}"})

        self.assertEqual(response.status_code, 200)

    def test_auth_enabled_allows_owner_cookie(self):
        with patched_web_auth(enabled=True), mock.patch(
            "app.backend.web.routes.get_web_services",
            return_value=self.services(),
        ):
            response = self.client.get("/portfolio", cookies={"web_auth_token": OWNER_TOKEN})

        self.assertEqual(response.status_code, 200)

    def test_static_files_do_not_require_auth(self):
        with patched_web_auth(enabled=True):
            response = self.client.get("/static/css/app.css")

        self.assertEqual(response.status_code, 200)

    def test_health_endpoint_does_not_require_auth(self):
        with patched_web_auth(enabled=True):
            response = self.client.get("/api/health")

        self.assertEqual(response.status_code, 200)

    def test_settings_page_shows_auth_status_without_token_value(self):
        settings = self.settings_view()
        with patched_web_auth(enabled=False), mock.patch(
            "app.backend.web.routes.get_web_services",
            return_value=self.services(settings),
        ):
            response = self.client.get("/settings")

        self.assertEqual(response.status_code, 200)
        self.assertIn("Web auth", response.text)
        self.assertIn("Web auth token configured", response.text)
        self.assertIn("Enabled", response.text)
        self.assertNotIn(OWNER_TOKEN, response.text)


class WebAuthConfigTests(unittest.TestCase):
    def test_startup_guard_blocks_exposed_host_without_web_auth_token(self):
        with mock.patch.dict(
            os.environ,
            {"API_HOST": "0.0.0.0", "WEB_AUTH_ENABLED": "false", "WEB_AUTH_TOKEN": ""},
            clear=True,
        ), mock.patch("app.client.config.load_dotenv"):
            with self.assertRaisesRegex(app_config.ConfigError, "WEB_AUTH_ENABLED=true"):
                app_config.validate_startup_config()

    def test_localhost_host_can_leave_web_auth_disabled(self):
        with mock.patch.dict(
            os.environ,
            {"API_HOST": "127.0.0.1", "WEB_AUTH_ENABLED": "false", "WEB_AUTH_TOKEN": ""},
            clear=True,
        ), mock.patch("app.client.config.load_dotenv"):
            app_config.validate_web_auth_config()


class FastApiLifespanGuardTests(unittest.TestCase):
    """Direct `uvicorn app.backend.main_api:app` launches must still run the web-auth gate."""

    def test_lifespan_rejects_non_localhost_host_without_auth(self):
        with mock.patch.dict(
            os.environ,
            {"API_HOST": "0.0.0.0", "WEB_AUTH_ENABLED": "false", "WEB_AUTH_TOKEN": ""},
            clear=True,
        ), mock.patch("app.client.config.load_dotenv"):
            with self.assertRaises(app_config.ConfigError):
                with TestClient(app):
                    pass

    def test_lifespan_allows_localhost_without_auth(self):
        with mock.patch.dict(
            os.environ,
            {"API_HOST": "127.0.0.1", "WEB_AUTH_ENABLED": "false", "WEB_AUTH_TOKEN": ""},
            clear=True,
        ), mock.patch("app.client.config.load_dotenv"):
            with TestClient(app) as client:
                response = client.get("/api/health")
                self.assertEqual(response.status_code, 200)


if __name__ == "__main__":
    unittest.main()
