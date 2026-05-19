import re
import unittest
from types import SimpleNamespace
from unittest import mock

from fastapi.testclient import TestClient

from app.backend.main_api import app
from app.services.mode import ModeContext


class FakeWatchlistService:
    def __init__(self):
        self.add_calls = []

    def list_items(self, error=None):
        return SimpleNamespace(error=error, notice=None, empty=True, items=[])

    def add_ticker(self, ticker):
        self.add_calls.append(ticker)
        return SimpleNamespace(
            error=None,
            notice=f"{ticker.upper()} was added to the watchlist.",
            empty=False,
            items=[],
        )


class WebCsrfTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def mode(self):
        return ModeContext(
            mode="sandbox",
            is_sandbox=True,
            prod_trading_allowed=False,
            trading_available=True,
            banner_title="Mode: sandbox",
            banner_message="Sandbox mode.",
        )

    def services(self, watchlist_service):
        mode = self.mode()
        return SimpleNamespace(
            user=SimpleNamespace(display_name="Test User", user_id="test", db_path=":memory:"),
            mode_service=SimpleNamespace(current=lambda: mode),
            watchlist_service=watchlist_service,
        )

    def csrf_token(self, response):
        match = re.search(r'name="csrf_token" value="([^"]+)"', response.text)
        self.assertIsNotNone(match)
        return match.group(1)

    def test_get_web_form_sets_csrf_cookie_and_hidden_input(self):
        watchlist = FakeWatchlistService()
        with mock.patch("app.backend.auth.web_auth_enabled", return_value=False), mock.patch(
            "app.backend.web.routes.get_web_services",
            return_value=self.services(watchlist),
        ):
            response = self.client.get("/watchlist")

        self.assertEqual(response.status_code, 200)
        self.assertIn("web_csrf_token", response.cookies)
        self.assertEqual(self.csrf_token(response), response.cookies["web_csrf_token"])
        set_cookie = response.headers.get("set-cookie", "")
        self.assertNotIn("Secure", set_cookie)

    def test_csrf_cookie_is_secure_over_https(self):
        watchlist = FakeWatchlistService()
        with mock.patch("app.backend.auth.web_auth_enabled", return_value=False), mock.patch(
            "app.backend.web.routes.get_web_services",
            return_value=self.services(watchlist),
        ):
            response = self.client.get(
                "/watchlist",
                headers={"X-Forwarded-Proto": "https"},
            )

        self.assertEqual(response.status_code, 200)
        set_cookie = response.headers.get("set-cookie", "")
        self.assertIn("web_csrf_token", set_cookie)
        self.assertIn("Secure", set_cookie)

    def test_post_without_csrf_token_is_blocked_before_service_call(self):
        watchlist = FakeWatchlistService()
        with mock.patch("app.backend.auth.web_auth_enabled", return_value=False), mock.patch(
            "app.backend.web.routes.get_web_services",
            return_value=self.services(watchlist),
        ):
            response = self.client.post("/watchlist/add", data={"ticker": "sber"})

        self.assertEqual(response.status_code, 403)
        self.assertEqual(watchlist.add_calls, [])

    def test_post_with_wrong_origin_is_blocked(self):
        watchlist = FakeWatchlistService()
        with mock.patch("app.backend.auth.web_auth_enabled", return_value=False), mock.patch(
            "app.backend.web.routes.get_web_services",
            return_value=self.services(watchlist),
        ):
            form_page = self.client.get("/watchlist")
            response = self.client.post(
                "/watchlist/add",
                data={"ticker": "sber", "csrf_token": self.csrf_token(form_page)},
                headers={"Origin": "http://evil.example"},
            )

        self.assertEqual(response.status_code, 403)
        self.assertEqual(watchlist.add_calls, [])

    def test_post_with_csrf_token_and_same_origin_is_allowed(self):
        watchlist = FakeWatchlistService()
        with mock.patch("app.backend.auth.web_auth_enabled", return_value=False), mock.patch(
            "app.backend.web.routes.get_web_services",
            return_value=self.services(watchlist),
        ):
            form_page = self.client.get("/watchlist")
            response = self.client.post(
                "/watchlist/add",
                data={"ticker": "sber", "csrf_token": self.csrf_token(form_page)},
                headers={"Origin": "http://testserver"},
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(watchlist.add_calls, ["sber"])


if __name__ == "__main__":
    unittest.main()
