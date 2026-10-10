"""Shared fresh reads and durable per-account snapshots for Telegram views."""

from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
import json
from threading import RLock
from zoneinfo import ZoneInfo

from app.backend.models.accounts import PortfolioSnapshot, PositionSnapshot
from app.backend.models.stocks import StockAccountRefresh, StockRefreshState
from app.integrations.stock_market import StockMarketAdapter
from app.integrations.moex_iss import MOEXISSClient
from app.services.portfolio import PortfolioPosition, money, signed_money, percent, format_quantity


MOSCOW = ZoneInfo("Europe/Moscow")


def utc(value=None):
    value = value or datetime.now(timezone.utc)
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def naive(value):
    return utc(value).replace(tzinfo=None)


def instrument_key(position):
    key = position.instrument_uid or position.figi
    if not key:
        raise ValueError("У бумаги отсутствует однозначный идентификатор.")
    return key


def delta(price, reference):
    return (price / reference - 1) * 100 if price is not None and reference and reference > 0 else None


@dataclass(frozen=True)
class AccountSnapshotView:
    account: object
    total_value: float | None
    positions: tuple[PortfolioPosition, ...]
    captured_at: datetime | None
    stale: bool
    error: str | None = None


class StockMarketService:
    def __init__(self, factory, user, portfolio, registry, *, adapter=None, index_client=None, now_provider=utc):
        self.factory, self.user, self.portfolio, self.registry = factory, user, portfolio, registry
        self.adapter = adapter or StockMarketAdapter()
        self.index_client = index_client or MOEXISSClient(timeout_seconds=10)
        self.now = now_provider
        self.lock = RLock()
        self._last_forced = None

    def token(self):
        return self.user.active_token(self.portfolio.mode_service.current().mode)

    def accounts(self):
        contexts = self.registry.list_enabled_accounts()
        with self.factory() as db:
            state = db.get(StockRefreshState, 1)
            ids = set(json.loads(state.account_ids_json)) if state and state.account_ids_json is not None else None
        return tuple(c for c in contexts if ids is None or c.investment_account_id in ids)

    def snapshots(self):
        now, views = utc(self.now()), []
        with self.factory() as db:
            refresh = db.get(StockRefreshState, 1)
            discovery_stale = bool(refresh and refresh.error_text and "список счетов" in refresh.error_text)
        for context in self.accounts():
            with self.factory() as db:
                snap = db.query(PortfolioSnapshot).filter_by(investment_account_id=context.investment_account_id).order_by(
                    PortfolioSnapshot.captured_at.desc(), PortfolioSnapshot.id.desc()).first()
                state = db.get(StockAccountRefresh, context.investment_account_id)
                stale = not snap or now - utc(snap.captured_at) > timedelta(minutes=6) or bool(state and state.error_text) or discovery_stale
                positions = []
                if snap:
                    for row in db.query(PositionSnapshot).filter_by(portfolio_snapshot_id=snap.id,
                            investment_account_id=context.investment_account_id):
                        average, price, value = row.average_price or 0, row.current_price or 0, row.market_value or 0
                        pnl = value - average * row.quantity if average else row.expected_yield or 0
                        ret = pnl / (average * row.quantity) * 100 if average * row.quantity else None
                        positions.append(PortfolioPosition(row.ticker, row.ticker, row.quantity, format_quantity(row.quantity),
                            average, money(average, row.currency), price, money(price, row.currency), pnl, ret, row.currency,
                            "positive" if pnl > 0 else "negative" if pnl < 0 else "neutral", signed_money(pnl, row.currency), percent(ret),
                            row.figi or "", row.instrument_uid or "", value, context.investment_account_id, context.account_name))
                views.append(AccountSnapshotView(context, snap.total_value if snap else None, tuple(positions),
                    utc(snap.captured_at) if snap else None, stale, state.error_text if state else None))
        return tuple(views)

    def refresh(self, *, force=False, now=None):
        now = utc(now or self.now())
        with self.lock:
            if force and self._last_forced and now - self._last_forced < timedelta(seconds=5):
                return self.snapshots()
            with self.factory() as db:
                state = db.get(StockRefreshState, 1)
                due = not state or not state.last_attempt_at or now - utc(state.last_attempt_at) >= timedelta(minutes=5)
            if not force and not due:
                return self.snapshots()
            try:
                contexts = self.registry.sync_accounts().accounts
            except Exception:
                contexts = self.accounts()
                discovery_error = "Не удалось обновить список счетов."
            else:
                discovery_error = None
            if force:
                self._last_forced = now
            errors = [discovery_error] if discovery_error else []
            for context in contexts:
                view = self.portfolio.get_account_portfolio(context)
                with self.factory() as db:
                    row = db.get(StockAccountRefresh, context.investment_account_id) or StockAccountRefresh(
                        investment_account_id=context.investment_account_id)
                    db.add(row)
                    row.checked_at, row.error_text = naive(now), "Не удалось обновить счёт." if view.error else None
                    if not view.error:
                        row.success_at = naive(now)
                    else:
                        errors.append(row.error_text)
                    db.commit()
            with self.factory() as db:
                state = db.get(StockRefreshState, 1) or StockRefreshState(id=1)
                db.add(state)
                state.last_attempt_at = naive(now)
                state.error_text = " ".join(errors) or None
                if not discovery_error:
                    state.account_ids_json = json.dumps([c.investment_account_id for c in contexts])
                if not errors:
                    state.last_success_at = naive(now)
                db.commit()
            self.refresh_quotes(now=now, force=force)
            self.refresh_index(now=now)
            return self.snapshots()

    def refresh_quotes(self, *, now=None, force=False):
        now = utc(now or self.now())
        with self.lock:
            with self.factory() as db:
                state = db.get(StockRefreshState, 1)
                if state and state.quotes_checked_at and now - utc(state.quotes_checked_at) < timedelta(seconds=60):
                    return json.loads(state.quotes_json)
            keys = {instrument_key(p) for a in self.snapshots() for p in a.positions if p.quantity and (p.instrument_uid or p.figi)}
            token = self.token()
            try:
                values = self.adapter.quotes(token, keys, sandbox=self.portfolio.mode_service.current().is_sandbox) if token else {}
            except Exception:
                return self.quotes()
            for value in values.values():
                value["fetched_at"] = now.isoformat()
            with self.factory() as db:
                state = db.get(StockRefreshState, 1) or StockRefreshState(id=1)
                db.add(state)
                state.quotes_json, state.quotes_checked_at = json.dumps(values), naive(now)
                db.commit()
            return values

    def quotes(self):
        with self.factory() as db:
            state = db.get(StockRefreshState, 1)
            return json.loads(state.quotes_json) if state else {}

    def quote(self, position):
        return self.quotes().get(instrument_key(position), {})

    def refresh_index(self, *, now=None):
        now = utc(now or self.now())
        try:
            current = self.index_client.get_index_market_data("IMOEX")
            if current.errors or not (current.last or current.close):
                return
            session_day = current.trade_date or (date.fromisoformat(current.as_of_date) if current.as_of_date else now.astimezone(MOSCOW).date())
            result = self.index_client.get_index_daily_candles_result("IMOEX",
                from_date=session_day - timedelta(days=10), till_date=session_day - timedelta(days=1))
            prior = sorted(result.candles, key=lambda bar: bar.begin)
            value = {"price": current.last or current.close, "change_pct": delta(current.last or current.close, prior[-1].close if prior else None),
                     "fetched_at": now.isoformat(), "as_of_date": current.as_of_date, "source": "MOEX ISS (возможна задержка)"}
            with self.factory() as db:
                state = db.get(StockRefreshState, 1) or StockRefreshState(id=1)
                db.add(state)
                state.index_json = json.dumps(value)
                db.commit()
        except Exception:
            pass

    def position(self, account_id, key):
        self.registry.get_account_context(account_id)
        account = next((view for view in self.snapshots() if view.account.investment_account_id == account_id), None)
        if not account:
            raise ValueError("Счёт недоступен.")
        position = next((p for p in account.positions if p.quantity and instrument_key(p) == key), None)
        return account, position

    def poll(self):
        """Only actual exchange statuses enable background portfolio refreshes."""
        now = utc(self.now())
        with self.factory() as db:
            state = db.get(StockRefreshState, 1)
            initial = not state or state.account_ids_json is None
        if initial:
            return self.refresh(now=now)
        views = self.snapshots()
        if not views or not any(a.positions for a in views):
            # Discover an initially empty/new account at most every five minutes.
            return self.refresh(now=now)
        values = self.refresh_quotes(now=now)
        if any(value.get("trading") and self.quote_is_current(value, now) for value in values.values()):
            self.refresh(now=now)

    @staticmethod
    def quote_is_current(value, now):
        try:
            age = utc(now) - utc(datetime.fromisoformat(value["fetched_at"]))
            return timedelta(0) <= age <= timedelta(seconds=90)
        except (KeyError, ValueError, TypeError):
            return False
