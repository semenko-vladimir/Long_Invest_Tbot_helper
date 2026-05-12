from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional

import pytz

from app.backend.models.trading import Buy, Margin, Order
from app.services.user_database import SessionFactory, get_default_session_factory


MOSCOW_TZ = pytz.timezone("Europe/Moscow")
_TIME_FORMAT = "%d-%m-%Y %H:%M"


@dataclass(frozen=True)
class TickerCount:
    ticker: str
    count: int


@dataclass(frozen=True)
class StatisticsView:
    period_label: str
    period_days: Optional[int]
    order_count: int
    order_buy_count: int
    order_sell_count: int
    order_value: float
    order_value_display: str
    buy_record_count: int
    buy_record_value: float
    buy_record_value_display: str
    margin_record_count: int
    margin_record_total: float
    top_tickers: list[TickerCount]
    empty: bool
    orders_no_timestamp_note: bool
    error: Optional[str] = None


def _money(value: float) -> str:
    return f"{value:,.2f} RUB".replace(",", " ")


def _parse_time(value) -> Optional[datetime]:
    if isinstance(value, datetime):
        dt = value.astimezone(MOSCOW_TZ) if value.tzinfo else MOSCOW_TZ.localize(value)
        return dt
    try:
        return MOSCOW_TZ.localize(datetime.strptime(str(value), _TIME_FORMAT))
    except (ValueError, TypeError):
        return None


def _filter_by_days(rows, days: int) -> list:
    now = datetime.now(MOSCOW_TZ)
    cutoff = (now.replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=days - 1))
    result = []
    for row in rows:
        t = _parse_time(row.time)
        if t and cutoff <= t <= now:
            result.append(row)
    return result


class StatisticsService:
    def __init__(self, *, session_factory: Optional[SessionFactory] = None):
        self.session_factory = session_factory or get_default_session_factory()

    def get_statistics_view(self, *, period_days: Optional[int] = None) -> StatisticsView:
        db = self.session_factory()
        try:
            buys = db.query(Buy).all()
            margins = db.query(Margin).all()
            orders = db.query(Order).all()
        except Exception as exc:
            return StatisticsView(
                period_label="all time",
                period_days=None,
                order_count=0,
                order_buy_count=0,
                order_sell_count=0,
                order_value=0.0,
                order_value_display=_money(0.0),
                buy_record_count=0,
                buy_record_value=0.0,
                buy_record_value_display=_money(0.0),
                margin_record_count=0,
                margin_record_total=0.0,
                top_tickers=[],
                empty=True,
                orders_no_timestamp_note=False,
                error="Statistics could not be loaded right now.",
            )
        finally:
            db.close()

        if period_days is not None and period_days > 0:
            period_label = f"Last {period_days} days"
            buys = _filter_by_days(buys, period_days)
            margins = _filter_by_days(margins, period_days)
            # Orders have no timestamp column — show all time with a note
            orders_filtered = False
        else:
            period_label = "All time"
            orders_filtered = False

        orders_no_timestamp_note = period_days is not None and bool(orders)

        order_buy_count = sum(1 for o in orders if str(o.operation_type or "").lower() == "buy")
        order_sell_count = sum(1 for o in orders if str(o.operation_type or "").lower() == "sell")
        order_value = sum(float(o.bm_value or 0) for o in orders)
        buy_value = sum(float(b.price or 0) for b in buys)
        margin_total = sum(float(m.margin or 0) for m in margins)

        ticker_counter: Counter = Counter()
        for b in buys:
            if b.ticker:
                ticker_counter[b.ticker.upper()] += 1
        for m in margins:
            if m.ticker:
                ticker_counter[m.ticker.upper()] += 1
        for o in orders:
            if o.ticker:
                ticker_counter[o.ticker.upper()] += 1

        top_tickers = [TickerCount(ticker=t, count=c) for t, c in ticker_counter.most_common(5)]
        empty = not buys and not margins and not orders

        return StatisticsView(
            period_label=period_label,
            period_days=period_days,
            order_count=len(orders),
            order_buy_count=order_buy_count,
            order_sell_count=order_sell_count,
            order_value=order_value,
            order_value_display=_money(order_value),
            buy_record_count=len(buys),
            buy_record_value=buy_value,
            buy_record_value_display=_money(buy_value),
            margin_record_count=len(margins),
            margin_record_total=margin_total,
            top_tickers=top_tickers,
            empty=empty,
            orders_no_timestamp_note=orders_no_timestamp_note,
            error=None,
        )
