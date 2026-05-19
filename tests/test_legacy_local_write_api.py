import unittest
from unittest import mock

from fastapi.testclient import TestClient

from app.backend.main_api import app


class LegacyLocalWriteApiGateTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def test_legacy_trading_orders_post_disabled_by_default(self):
        with mock.patch("app.backend.auth.web_auth_enabled", return_value=False), mock.patch(
            "app.backend.api.dependencies.legacy_local_write_api_enabled",
            return_value=False,
        ):
            response = self.client.post(
                "/api/trading/orders/",
                json={
                    "order_id": "ord-1",
                    "ticker": "SBER",
                    "signal": "manual",
                    "bm_value": 100.0,
                    "operation_type": "buy",
                },
            )

        self.assertEqual(response.status_code, 403)
        self.assertIn("Legacy local-write API", response.json()["detail"])

    def test_legacy_trading_orders_delete_disabled_by_default(self):
        with mock.patch("app.backend.auth.web_auth_enabled", return_value=False), mock.patch(
            "app.backend.api.dependencies.legacy_local_write_api_enabled",
            return_value=False,
        ):
            response = self.client.delete("/api/trading/orders/missing")

        self.assertEqual(response.status_code, 403)

    def test_legacy_instruments_post_disabled_by_default(self):
        with mock.patch("app.backend.auth.web_auth_enabled", return_value=False), mock.patch(
            "app.backend.api.dependencies.legacy_local_write_api_enabled",
            return_value=False,
        ):
            response = self.client.post(
                "/api/instruments/",
                json={"ticker": "SBER", "figi": "FIGI-SBER"},
            )

        self.assertEqual(response.status_code, 403)

    def test_legacy_instruments_delete_all_disabled_by_default(self):
        with mock.patch("app.backend.auth.web_auth_enabled", return_value=False), mock.patch(
            "app.backend.api.dependencies.legacy_local_write_api_enabled",
            return_value=False,
        ):
            response = self.client.delete("/api/instruments/all")

        self.assertEqual(response.status_code, 403)

    def test_legacy_instruments_read_endpoints_remain_accessible(self):
        from types import SimpleNamespace

        fake_db = SimpleNamespace(
            close=lambda: None,
            query=lambda *a, **k: SimpleNamespace(
                offset=lambda *a, **k: SimpleNamespace(
                    limit=lambda *a, **k: SimpleNamespace(all=lambda: [])
                )
            ),
        )

        def fake_get_db():
            yield fake_db

        with mock.patch("app.backend.auth.web_auth_enabled", return_value=False):
            app.dependency_overrides[__import__("app.backend.api.dependencies", fromlist=["get_default_web_db"]).get_default_web_db] = fake_get_db
            try:
                response = self.client.get("/api/instruments/")
            finally:
                app.dependency_overrides.clear()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), [])


if __name__ == "__main__":
    unittest.main()
