from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]

ACTIVE_TELEGRAM_DATA_HANDLERS = (
    "app/client/handlers/bot/sandbox_info.py",
    "app/client/handlers/dividends/dividends_handler.py",
    "app/client/handlers/instruments/add_instrument.py",
    "app/client/handlers/instruments/delete_all_instruments.py",
    "app/client/handlers/instruments/delete_instrument.py",
    "app/client/handlers/instruments/get_all_instruments.py",
    "app/client/handlers/orders/manual_order_handler.py",
    "app/client/handlers/portfolio/portfolio_handler.py",
    "app/client/handlers/research/research_handler.py",
    "app/client/handlers/statistics/statistics_handler.py",
)

USER_DATA_API_ENDPOINTS = (
    "app/backend/api/endpoints/research.py",
)


class P1UserContextWiringTests(unittest.TestCase):
    def read(self, relative_path: str) -> str:
        return (ROOT / relative_path).read_text(encoding="utf-8")

    def test_active_telegram_data_handlers_do_not_use_legacy_global_clients(self):
        forbidden = (
            "app.client.api.instruments_client",
            "app.client.api.trading_client",
            "get_active_invest_token",
            "def get_tokens(",
        )
        for relative_path in ACTIVE_TELEGRAM_DATA_HANDLERS:
            with self.subTest(path=relative_path):
                source = self.read(relative_path)
                for token in forbidden:
                    self.assertNotIn(token, source)

    def test_active_telegram_data_handlers_resolve_user_context(self):
        for relative_path in ACTIVE_TELEGRAM_DATA_HANDLERS:
            with self.subTest(path=relative_path):
                source = self.read(relative_path)
                self.assertTrue(
                    "get_telegram_services_or_notify" in source
                    or "get_telegram_research_services" in source,
                    f"{relative_path} should resolve Telegram user context",
                )

    def test_web_routes_use_default_web_user_services(self):
        source = self.read("app/backend/web/routes.py")

        self.assertIn("get_web_services", source)
        self.assertNotIn("OrderService(", source)
        self.assertNotIn("WatchlistService(", source)
        self.assertNotIn("StatisticsService(", source)
        self.assertNotIn("OrderHistoryService(", source)

    def test_user_data_api_endpoints_use_default_web_user_db(self):
        for relative_path in USER_DATA_API_ENDPOINTS:
            with self.subTest(path=relative_path):
                source = self.read(relative_path)
                self.assertIn("get_default_web_db", source)
                self.assertNotIn("Depends(get_db)", source)


if __name__ == "__main__":
    unittest.main()
