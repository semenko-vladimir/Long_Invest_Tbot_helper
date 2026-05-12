import unittest
from types import SimpleNamespace
from unittest import mock

from fastapi.testclient import TestClient

from app.backend.main_api import app
from app.services.mode import ModeContext
from app.services.order_history import OrderHistoryService, OrderHistoryView, OrderRowView
from app.services.statistics import StatisticsView


class FakeQuery:
    def __init__(self, rows):
        self.rows = rows

    def order_by(self, *_args, **_kwargs):
        return self

    def all(self):
        return self.rows


class FakeSession:
    def __init__(self, rows):
        self.rows = rows
        self.closed = False

    def query(self, _model):
        return FakeQuery(self.rows)

    def close(self):
        self.closed = True


class OrderHistoryServiceTests(unittest.TestCase):
    def test_list_orders_returns_formatted_rows(self):
        session = FakeSession(
            [
                SimpleNamespace(
                    order_id="12345678901234567890",
                    ticker="sber",
                    operation_type="buy",
                    bm_value=1234.5,
                ),
                SimpleNamespace(
                    order_id="short-id",
                    ticker="gazp",
                    operation_type="sell",
                    bm_value=0,
                ),
            ]
        )

        view = OrderHistoryService(session_factory=lambda: session).list_orders()

        self.assertFalse(view.empty)
        self.assertTrue(session.closed)
        self.assertEqual(view.orders[0].order_id_display, "123456789012...")
        self.assertEqual(view.orders[0].ticker, "SBER")
        self.assertEqual(view.orders[0].operation_label, "Buy")
        self.assertEqual(view.orders[0].operation_class, "buy")
        self.assertEqual(view.orders[0].bm_value_display, "1 234.50 RUB")
        self.assertEqual(view.orders[1].order_id_display, "short-id")
        self.assertEqual(view.orders[1].operation_label, "Sell")
        self.assertEqual(view.orders[1].operation_class, "sell")

    def test_list_orders_returns_empty_view(self):
        view = OrderHistoryService(session_factory=lambda: FakeSession([])).list_orders()

        self.assertTrue(view.empty)
        self.assertEqual(view.orders, [])
        self.assertIsNone(view.error)

    def test_list_orders_returns_error_view_when_query_fails(self):
        class FailingSession(FakeSession):
            def query(self, _model):
                raise RuntimeError("db offline")

        view = OrderHistoryService(session_factory=lambda: FailingSession([])).list_orders()

        self.assertTrue(view.empty)
        self.assertEqual(view.orders, [])
        self.assertIn("could not be loaded", view.error)


class OrderHistoryRouteTests(unittest.TestCase):
    def fake_mode(self):
        return ModeContext(
            mode="sandbox",
            is_sandbox=True,
            prod_trading_allowed=False,
            trading_available=True,
            banner_title="Mode: sandbox",
            banner_message="Sandbox mode.",
        )

    def fake_web_services(self, *, order_history=None, stats=None):
        mode = self.fake_mode()
        return SimpleNamespace(
            user=SimpleNamespace(display_name="Test User", user_id="test", db_path="test.db"),
            mode_service=SimpleNamespace(current=lambda: mode),
            order_history_service=SimpleNamespace(list_orders=lambda: order_history),
            statistics_service=SimpleNamespace(get_statistics_view=lambda period_days=None: stats),
        )

    def test_orders_page_renders_history(self):
        view = OrderHistoryView(
            orders=[
                OrderRowView(
                    order_id="12345678901234567890",
                    order_id_display="123456789012...",
                    ticker="SBER",
                    operation_type="buy",
                    operation_label="Buy",
                    operation_class="buy",
                    bm_value=1000.0,
                    bm_value_display="1 000.00 RUB",
                )
            ],
            empty=False,
        )

        with mock.patch("app.backend.web.routes.get_web_services", return_value=self.fake_web_services(order_history=view)):
            response = TestClient(app).get("/orders")

        self.assertEqual(response.status_code, 200)
        self.assertIn("Order history", response.text)
        self.assertIn("123456789012...", response.text)
        self.assertIn("SBER", response.text)
        self.assertIn("Buy", response.text)
        self.assertIn("1 000.00 RUB", response.text)

    def test_stats_page_links_to_order_history(self):
        stats = StatisticsView(
            period_label="All time",
            period_days=None,
            order_count=0,
            order_buy_count=0,
            order_sell_count=0,
            order_value=0.0,
            order_value_display="0.00 RUB",
            buy_record_count=0,
            buy_record_value=0.0,
            buy_record_value_display="0.00 RUB",
            margin_record_count=0,
            margin_record_total=0.0,
            top_tickers=[],
            empty=True,
            orders_no_timestamp_note=False,
        )

        with mock.patch("app.backend.web.routes.get_web_services", return_value=self.fake_web_services(stats=stats)):
            response = TestClient(app).get("/stats")

        self.assertEqual(response.status_code, 200)
        self.assertIn("/orders", response.text)
        self.assertIn("View order history", response.text)


if __name__ == "__main__":
    unittest.main()
