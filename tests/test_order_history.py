import unittest
from types import SimpleNamespace

from app.services.order_history import OrderHistoryService


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
                SimpleNamespace(order_id="12345678901234567890", ticker="sber", operation_type="buy", bm_value=1234.5),
                SimpleNamespace(order_id="short-id", ticker="gazp", operation_type="sell", bm_value=0),
            ]
        )

        view = OrderHistoryService(session_factory=lambda: session).list_orders()

        self.assertFalse(view.empty)
        self.assertTrue(session.closed)
        self.assertEqual(view.orders[0].order_id_display, "123456789012...")
        self.assertEqual(view.orders[0].ticker, "SBER")
        self.assertEqual(view.orders[0].operation_label, "Buy")
        self.assertEqual(view.orders[0].bm_value_display, "1 234.50 RUB")
        self.assertEqual(view.orders[1].operation_label, "Sell")

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
        self.assertIn("could not be loaded", view.error)


if __name__ == "__main__":
    unittest.main()
