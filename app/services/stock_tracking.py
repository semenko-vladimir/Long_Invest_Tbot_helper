"""Durable observation-only updates; no order service is available here."""

from dataclasses import dataclass
from datetime import timedelta
import re

from app.backend.models.stocks import StockTracking
from app.services.stock_market import delta, naive, utc, MOSCOW
from app.services.portfolio import money, percent


def parse_interval(text):
    match = re.fullmatch(r"\s*(\d+)\s*(мин(?:ут[аы]?)?|m|min)?\s*", str(text or ""), re.IGNORECASE)
    if not match or not 5 <= int(match[1]) <= 1440:
        raise ValueError("Введите целое число минут от 5 до 1440, например 15 или 90.")
    return int(match[1])


@dataclass(frozen=True)
class TrackingView:
    id: int
    account_id: int
    instrument_key: str
    ticker: str
    interval_minutes: int
    chart_range: str
    status: str
    error: str | None


class StockTrackingService:
    def __init__(self, market, charts, *, send_text=None, send_photo=None):
        self.market, self.charts = market, charts
        self.send_text, self.send_photo = send_text, send_photo

    def get(self, account_id, key):
        self.market.registry.get_account_context(account_id)
        with self.market.factory() as db:
            row = self._query(db, account_id, key).first()
            return self._view(row) if row else None

    def configure(self, account_id, key, *, interval_minutes=30, chart_range="day", now=None):
        minutes = parse_interval(interval_minutes)
        if chart_range not in {"day", "week", "month"}:
            raise ValueError("Выберите день, неделю или месяц.")
        account, position = self.market.position(account_id, key)
        if not position or account.stale:
            raise ValueError("Обновите позицию перед включением слежения.")
        now = utc(now or self.market.now())
        with self.market.factory() as db:
            row = self._query(db, account_id, key).first()
            if row is None:
                row = StockTracking(user_id=self.market.user.user_id, investment_account_id=account_id,
                    instrument_key=key, ticker=position.ticker)
                db.add(row)
            row.interval_minutes, row.chart_range, row.status = minutes, chart_range, "active"
            row.next_due_at, row.updated_at = naive(now + timedelta(minutes=minutes)), naive(now)
            row.error_text, row.closure_notice_pending = None, False
            db.commit()
            return self._view(row)

    def set_status(self, account_id, key, status):
        if status not in {"active", "paused", "disabled"}:
            raise ValueError("Неизвестный режим слежения.")
        self.market.registry.get_account_context(account_id)
        current = self.get(account_id, key)
        if current is None:
            raise ValueError("Слежение ещё не настроено.")
        if status == "active":
            return self.configure(account_id, key, interval_minutes=current.interval_minutes, chart_range=current.chart_range)
        with self.market.factory() as db:
            row = self._query(db, account_id, key).one()
            row.status, row.updated_at = status, naive(self.market.now())
            row.closure_notice_pending = False
            db.commit()
            return self._view(row)

    def run(self, *, now=None):
        now = utc(now or self.market.now())
        with self.market.factory() as db:
            ids = [row.id for row in db.query(StockTracking).filter_by(user_id=self.market.user.user_id).filter(
                (StockTracking.status == "active") | StockTracking.closure_notice_pending.is_(True))]
        for tracking_id in ids:
            try:
                self._process(tracking_id, now)
            except Exception as exc:
                # Store a class name, never an external exception containing credentials.
                with self.market.factory() as db:
                    row = db.get(StockTracking, tracking_id)
                    if row:
                        row.error_text = type(exc).__name__
                        db.commit()

    def _process(self, tracking_id, now):
        with self.market.factory() as db:
            row = db.get(StockTracking, tracking_id)
            account_id, key, pending = row.investment_account_id, row.instrument_key, row.closure_notice_pending
            ticker = row.ticker
        if pending:
            self._closure_notice(tracking_id, ticker, now)
            return
        try:
            account, position = self.market.position(account_id, key)
        except (ValueError, LookupError):
            self._pause_closed(tracking_id)
            return
        if account.stale:
            return  # Failed reads must never look like a closed position.
        if position is None:
            self._pause_closed(tracking_id)
            self._closure_notice(tracking_id, ticker, now)
            return
        quote = self.market.quote(position)
        if not quote.get("price") or not quote.get("trading") or not self.market.quote_is_current(quote, now):
            return
        with self.market.factory() as db:
            row = db.get(StockTracking, tracking_id)
            if row.status != "active" or utc(row.next_due_at) > now:
                return
            previous, range_name = row.last_sent_price, row.chart_range
            version = row.updated_at
            claimed = db.query(StockTracking).filter_by(id=tracking_id, status="active").filter(
                StockTracking.next_due_at <= naive(now)).update({StockTracking.next_due_at: naive(now + timedelta(minutes=row.interval_minutes)),
                    StockTracking.attempt_at: naive(now)}, synchronize_session=False)
            db.commit()
            if not claimed:
                return
        chart, chart_error = None, ""
        try:
            chart = self.charts.render(position, range_name, now=now)
        except Exception:
            chart_error = "\nГрафик сейчас недоступен."
        text = (f"{ticker} · {account.account.account_name}\nЦена: {money(quote['price'], position.currency)}\n"
                f"За день: {percent(delta(quote['price'], quote.get('previous_close')))}\n"
                f"С прошлого сообщения: {percent(delta(quote['price'], previous))}\n"
                f"Прибыль позиции: {position.pnl_display} ({position.return_display})\n"
                f"Снимок позиции: {utc(account.captured_at).astimezone(MOSCOW):%H:%M} МСК.\n"
                f"Цена последней сделки: {utc_from_text(quote.get('time'), now).astimezone(MOSCOW):%d.%m %H:%M} МСК."
                + ("\n" + chart.summary if chart else chart_error))
        with self.market.factory() as db:
            row = db.get(StockTracking, tracking_id)
            if row.status != "active" or row.updated_at != version:
                return
        try:
            if chart and self.send_photo:
                sent = self.send_photo(self.market.user.telegram_chat_id, chart.png_bytes, text[:1000])
            elif self.send_text:
                sent = self.send_text(self.market.user.telegram_chat_id, text[:3900])
            else:
                raise RuntimeError("Tracking sender is unavailable")
        except Exception as exc:
            with self.market.factory() as db:
                row = db.get(StockTracking, tracking_id)
                row.error_text = "Доставка не подтверждена: " + type(exc).__name__
                db.commit()
            return
        with self.market.factory() as db:
            row = db.get(StockTracking, tracking_id)
            row.last_sent_price, row.last_sent_at = quote["price"], naive(now)
            row.last_message_id, row.error_text = getattr(sent, "message_id", None), None
            db.commit()

    def _pause_closed(self, tracking_id):
        with self.market.factory() as db:
            row = db.get(StockTracking, tracking_id)
            row.status, row.closure_notice_pending = "paused", True
            row.error_text = "Позиция закрыта или счёт недоступен."
            db.commit()

    def _closure_notice(self, tracking_id, ticker, now):
        with self.market.factory() as db:
            row = db.get(StockTracking, tracking_id)
            if not row.closure_notice_pending:
                return
            # Claim once before sending: avoid replay after ambiguous delivery/restart.
            row.closure_notice_pending, row.attempt_at = False, naive(now)
            db.commit()
        if self.send_text:
            self.send_text(self.market.user.telegram_chat_id, f"Слежение за {ticker} приостановлено: позиция закрыта или счёт недоступен.")

    def _query(self, db, account_id, key):
        return db.query(StockTracking).filter_by(user_id=self.market.user.user_id,
            investment_account_id=account_id, instrument_key=key)

    @staticmethod
    def _view(row):
        return TrackingView(row.id, row.investment_account_id, row.instrument_key, row.ticker,
            row.interval_minutes, row.chart_range, row.status, row.error_text)


def utc_from_text(text, fallback):
    from datetime import datetime
    try:
        return utc(datetime.fromisoformat(text))
    except (TypeError, ValueError):
        return utc(fallback)
