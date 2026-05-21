import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional

from tinkoff.invest import CandleInterval, Client, InstrumentIdType, OrderDirection, OrderType
from tinkoff.invest.services import SandboxService

from app.backend.models.trading import Order
from app.client.utils.helpers import cast_money
from app.client.utils.methods import (
    check_enough_currency,
    get_dividends_data,
    get_available_qty,
    get_current_price,
    get_lotSize,
)
from app.services.user_database import SessionFactory, get_default_session_factory


SUPPORTED_INSTRUMENT_METHODS = ("shares", "bonds", "etfs", "currencies", "futures")


@dataclass(frozen=True)
class InstrumentLookup:
    figi: str
    ticker: str
    name: str
    instrument_type: str


@dataclass(frozen=True)
class BrokerOrderResult:
    order_id: str
    price: float
    total_value: float
    warning: Optional[str] = None


@dataclass(frozen=True)
class DividendLookup:
    dividend_net: str
    payment_date: str
    declared_date: str
    last_buy_date: str
    record_date: str
    yield_value: str


class BrokerPortfolioError(RuntimeError):
    """Raised when broker portfolio data cannot be loaded safely."""


class TInvestBroker:
    """Small adapter that keeps T-Invest SDK details out of services and views."""

    def __init__(self, *, session_factory: Optional[SessionFactory] = None):
        self.session_factory = session_factory or get_default_session_factory()

    def get_portfolio(self, token: str, *, sandbox: bool) -> dict:
        try:
            with Client(token) as client:
                if sandbox:
                    account_id = self._get_sandbox_account_id(client, create_if_missing=True)
                    portfolio = client.sandbox.get_sandbox_portfolio(account_id=account_id)
                else:
                    account_id = self._get_prod_account_id(client)
                    portfolio = client.operations.get_portfolio(account_id=account_id)

                return self._portfolio_response_to_dict(client, portfolio)
        except BrokerPortfolioError:
            raise
        except Exception as exc:
            raise BrokerPortfolioError(_safe_broker_error_message(exc)) from exc

    def get_instrument_name(self, token: str, figi: str) -> Optional[str]:
        try:
            with Client(token) as client:
                response = client.instruments.get_instrument_by(
                    id=figi,
                    id_type=InstrumentIdType.INSTRUMENT_ID_TYPE_FIGI,
                )
                return getattr(response.instrument, "name", None)
        except Exception:
            return None

    def resolve_unique_instrument(self, token: str, ticker: str) -> InstrumentLookup:
        normalized_ticker = ticker.upper()
        matches: dict[str, InstrumentLookup] = {}

        with Client(token) as client:
            for method_name in SUPPORTED_INSTRUMENT_METHODS:
                data = getattr(client.instruments, method_name)().instruments
                for instrument in data:
                    instrument_ticker = str(getattr(instrument, "ticker", "") or "")
                    if instrument_ticker.upper() != normalized_ticker:
                        continue

                    matches[instrument.figi] = InstrumentLookup(
                        figi=instrument.figi,
                        ticker=instrument_ticker.upper(),
                        name=str(getattr(instrument, "name", "") or instrument_ticker.upper()),
                        instrument_type=method_name,
                    )

        if not matches:
            raise ValueError(f"Ticker {normalized_ticker} was not found.")

        if len(matches) > 1:
            details = ", ".join(
                f"{item.ticker} / {item.instrument_type} / {figi}"
                for figi, item in sorted(matches.items())
            )
            raise ValueError(f"Ticker {normalized_ticker} is ambiguous: {details}.")

        return next(iter(matches.values()))

    def get_price(self, token: str, figi: str, operation: str) -> float:
        with Client(token) as client:
            price_sell, price_buy = get_current_price(figi, client, "fast")
            price = price_buy if operation == "buy" else price_sell
            if price is None:
                raise ValueError("Current price is unavailable.")
            return cast_money(price)

    def get_lot_size(self, token: str, figi: str) -> int:
        with Client(token) as client:
            return get_lotSize(token, figi, client)

    def has_enough_cash(self, token: str, figi: str, lots: int, sandbox: bool) -> bool:
        with Client(token) as client:
            _, price_buy = get_current_price(figi, client, "fast")
            if price_buy is None:
                raise ValueError("Current buy price is unavailable.")
            return check_enough_currency(token, figi, client, price_buy, lots, sandbox)

    def get_available_quantity(self, token: str, figi: str, sandbox: bool) -> float:
        with Client(token) as client:
            return float(get_available_qty(token, figi, client, sandbox))

    def get_dividend_info(self, token: str, figi: str, period_days: int) -> Optional[DividendLookup]:
        data = get_dividends_data(token, period_days, figi)
        if not data:
            return None

        return DividendLookup(
            dividend_net=str(data.get("dividend_net", "")),
            payment_date=str(data.get("payment_date", "")),
            declared_date=str(data.get("declared_date", "")),
            last_buy_date=str(data.get("last_buy_date", "")),
            record_date=str(data.get("record_date", "")),
            yield_value=str(data.get("yield_value", "")),
        )

    def get_closing_prices(self, token: str, ticker: str, days: int) -> list[float]:
        """
        Return daily closing prices for the ticker over the last N calendar days.
        """
        period_days = max(int(days), 1)
        instrument = self.resolve_unique_instrument(token, ticker)
        now = datetime.now(timezone.utc)
        with Client(token) as client:
            response = client.market_data.get_candles(
                figi=instrument.figi,
                from_=now - timedelta(days=period_days),
                to=now,
                interval=CandleInterval.CANDLE_INTERVAL_DAY,
            )

        prices = []
        for candle in response.candles:
            close = cast_money(candle.close)
            if close > 0:
                prices.append(close)
        return prices

    def get_previous_day_average_price(self, token: str, ticker: str, lookback_days: int = 10) -> Optional[float]:
        """
        Return the latest completed daily candle OHLC average before today.
        """
        period_days = max(int(lookback_days), 2)
        instrument = self.resolve_unique_instrument(token, ticker)
        now = datetime.now(timezone.utc)
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

        with Client(token) as client:
            response = client.market_data.get_candles(
                figi=instrument.figi,
                from_=today_start - timedelta(days=period_days),
                to=today_start,
                interval=CandleInterval.CANDLE_INTERVAL_DAY,
            )

        candles = sorted(
            response.candles,
            key=lambda candle: getattr(candle, "time", datetime.min.replace(tzinfo=timezone.utc)),
            reverse=True,
        )
        for candle in candles:
            average = _daily_candle_average(candle)
            if average is not None:
                return average
        return None

    def place_order(self, token: str, figi: str, ticker: str, lots: int, operation: str, sandbox: bool) -> BrokerOrderResult:
        with Client(token) as client:
            account_id = self._get_account_id(client, sandbox)
            price_sell, price_buy = get_current_price(figi, client, "fast")
            price = price_buy if operation == "buy" else price_sell
            if price is None:
                raise ValueError("Current price is unavailable.")

            order_id = str(uuid.uuid4())
            direction = (
                OrderDirection.ORDER_DIRECTION_BUY
                if operation == "buy"
                else OrderDirection.ORDER_DIRECTION_SELL
            )

            if sandbox:
                sb: SandboxService = client.sandbox
                sb.post_sandbox_order(
                    figi=figi,
                    quantity=lots,
                    price=price,
                    account_id=account_id,
                    order_id=order_id,
                    direction=direction,
                    order_type=OrderType.ORDER_TYPE_LIMIT,
                )
            else:
                client.orders.post_order(
                    figi=figi,
                    quantity=lots,
                    price=price,
                    account_id=account_id,
                    order_id=order_id,
                    direction=direction,
                    order_type=OrderType.ORDER_TYPE_LIMIT,
                )

            lot_size = get_lotSize(token, figi, client)
            total_value = cast_money(price) * lot_size * lots
            warning = None
            try:
                self._record_order(order_id, ticker, total_value, operation)
            except Exception:
                warning = "Order was submitted, but local order history could not be updated."
            return BrokerOrderResult(
                order_id=order_id,
                price=cast_money(price),
                total_value=total_value,
                warning=warning,
            )

    def _get_account_id(self, client: Client, sandbox: bool) -> str:
        if sandbox:
            return self._get_sandbox_account_id(client, create_if_missing=True)

        return self._get_prod_account_id(client)

    def _get_sandbox_account_id(self, client: Client, *, create_if_missing: bool) -> str:
        sb: SandboxService = client.sandbox
        accounts = sb.get_sandbox_accounts().accounts
        if accounts:
            return _account_id(accounts[0])
        if not create_if_missing:
            raise BrokerPortfolioError("Sandbox broker account was not found.")
        account = sb.open_sandbox_account()
        return _account_id(account)

    def _get_prod_account_id(self, client: Client) -> str:
        accounts = client.users.get_accounts().accounts
        if not accounts:
            raise BrokerPortfolioError("Broker account was not found.")
        return _account_id(accounts[0])

    def _portfolio_response_to_dict(self, client: Client, portfolio) -> dict:
        positions = []
        for position in portfolio.positions:
            quantity = _cast_money_or_zero(position.quantity)
            current_price_one = _cast_money_or_zero(position.current_price)
            positions.append(
                {
                    "ticker": self._position_ticker(client, position) or "Нет информации",
                    "type": _position_type_label(str(position.instrument_type or "")),
                    "figi": position.figi,
                    "quantity": quantity,
                    "average_position_price": _cast_money_or_zero(position.average_position_price),
                    "expected_yield": _cast_money_or_zero(position.expected_yield),
                    "current_price": round(current_price_one * quantity, 2),
                    "current_price_one": current_price_one,
                    "blocked": "Заблокирована" if position.blocked else "Активна",
                }
            )

        return {
            "total_amount_shares": _cast_money_or_zero(portfolio.total_amount_shares),
            "total_amount_bonds": _cast_money_or_zero(portfolio.total_amount_bonds),
            "total_amount_etf": _cast_money_or_zero(portfolio.total_amount_etf),
            "total_amount_currencies": _cast_money_or_zero(portfolio.total_amount_currencies),
            "expected_yield": _cast_money_or_zero(portfolio.expected_yield),
            "total_amount_portfolio": _cast_money_or_zero(portfolio.total_amount_portfolio),
            "positions": positions,
        }

    def _position_ticker(self, client: Client, position) -> Optional[str]:
        try:
            response = client.instruments.get_instrument_by(
                id=position.figi,
                id_type=InstrumentIdType.INSTRUMENT_ID_TYPE_FIGI,
            )
            ticker = getattr(response.instrument, "ticker", None)
            return str(ticker).upper() if ticker else None
        except Exception:
            return None

    def _record_order(self, order_id: str, ticker: str, total_value: float, operation: str) -> None:
        db = self.session_factory()
        try:
            db.add(
                Order(
                    order_id=order_id,
                    ticker=ticker,
                    signal="manual",
                    bm_value=total_value,
                    operation_type=operation,
                )
            )
            db.commit()
        finally:
            db.close()


def _account_id(account) -> str:
    account_id = getattr(account, "id", None) or getattr(account, "account_id", None)
    if not account_id:
        raise BrokerPortfolioError("Broker account id is missing in API response.")
    return str(account_id)


def _cast_money_or_zero(value) -> float:
    try:
        return cast_money(value)
    except Exception:
        return 0.0


def _daily_candle_average(candle) -> Optional[float]:
    try:
        values = [
            cast_money(candle.open),
            cast_money(candle.high),
            cast_money(candle.low),
            cast_money(candle.close),
        ]
    except Exception:
        return None

    if any(value <= 0 for value in values):
        return None
    return sum(values) / len(values)


def _position_type_label(instrument_type: str) -> str:
    return {
        "share": "Акция",
        "bond": "Облигация",
        "etf": "Фонд",
        "currency": "Валюта",
        "future": "Фьючерс",
    }.get(instrument_type.lower(), "")


def _safe_broker_error_message(exc: Exception) -> str:
    message = str(exc).strip()
    if not message:
        message = exc.__class__.__name__
    if len(message) > 500:
        message = f"{message[:500]}..."
    return f"Broker API request failed: {message}"
