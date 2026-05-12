from dataclasses import dataclass
from typing import Optional

from app.backend.models.trading import Order
from app.services.portfolio import money
from app.services.user_database import SessionFactory, get_default_session_factory


@dataclass(frozen=True)
class OrderRowView:
    order_id: str
    order_id_display: str
    ticker: str
    operation_type: str
    operation_label: str
    operation_class: str
    bm_value: float
    bm_value_display: str


@dataclass(frozen=True)
class OrderHistoryView:
    orders: list[OrderRowView]
    empty: bool
    error: Optional[str] = None


class OrderHistoryService:
    def __init__(self, *, session_factory: Optional[SessionFactory] = None):
        self.session_factory = session_factory or get_default_session_factory()

    def list_orders(self) -> OrderHistoryView:
        db = self.session_factory()
        try:
            rows = db.query(Order).order_by(Order.id.desc()).all()
            orders = [self._to_row(row) for row in rows]
            return OrderHistoryView(orders=orders, empty=len(orders) == 0)
        except Exception:
            return OrderHistoryView(
                orders=[],
                empty=True,
                error="Order history could not be loaded right now.",
            )
        finally:
            db.close()

    def _to_row(self, order: Order) -> OrderRowView:
        operation = str(order.operation_type or "").strip().lower()
        order_id = str(order.order_id or "").strip()

        return OrderRowView(
            order_id=order_id,
            order_id_display=self._truncate_order_id(order_id),
            ticker=str(order.ticker or "-").strip().upper() or "-",
            operation_type=operation,
            operation_label=self._operation_label(operation),
            operation_class=self._operation_class(operation),
            bm_value=float(order.bm_value or 0.0),
            bm_value_display=money(float(order.bm_value or 0.0)),
        )

    def _truncate_order_id(self, order_id: str) -> str:
        if not order_id:
            return "-"
        if len(order_id) <= 12:
            return order_id
        return f"{order_id[:12]}..."

    def _operation_label(self, operation: str) -> str:
        if operation == "buy":
            return "Buy"
        if operation == "sell":
            return "Sell"
        return operation.title() if operation else "-"

    def _operation_class(self, operation: str) -> str:
        if operation == "buy":
            return "buy"
        if operation == "sell":
            return "sell"
        return "neutral"
