import uuid
from dataclasses import dataclass
from typing import Optional

from tinkoff.invest import Client, InstrumentIdType, OrderDirection, OrderType
from tinkoff.invest.services import SandboxService

from app.backend.models.database import SessionLocal
from app.backend.models.trading import Order
from app.client.utils.helpers import cast_money
from app.client.utils.methods import (
    check_enough_currency,
    get_dividends_data,
    get_available_qty,
    get_current_price,
    get_lotSize,
    get_portfolio,
    get_sandbox_portfolio,
)


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


class TInvestBroker:
    """Small adapter that keeps T-Invest SDK details out of services and views."""

    def get_portfolio(self, token: str, *, sandbox: bool) -> dict:
        if sandbox:
            return get_sandbox_portfolio(token)
        return get_portfolio(token)

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
            sb: SandboxService = client.sandbox
            accounts = sb.get_sandbox_accounts().accounts
            if not accounts:
                account = sb.open_sandbox_account()
                return account.account_id
            return accounts[0].id

        accounts = client.users.get_accounts().accounts
        if not accounts:
            raise ValueError("Broker account was not found.")
        return accounts[0].id

    def _record_order(self, order_id: str, ticker: str, total_value: float, operation: str) -> None:
        db = SessionLocal()
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
