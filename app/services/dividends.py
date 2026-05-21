from dataclasses import dataclass
from typing import Callable, Optional

from app.client.config import get_active_invest_token
from app.integrations.tinvest import TInvestBroker
from app.services.mode import ModeService
from app.services.portfolio import as_float, format_quantity, money, portfolio_error_message
from app.services.watchlist import WatchlistItem, WatchlistService


DEFAULT_DIVIDEND_PERIOD_DAYS = 365
UNAVAILABLE_DISPLAY = "-"


@dataclass(frozen=True)
class DividendItem:
    ticker: str
    name: str
    next_dividend_date: str
    expected_dividend: str
    position_quantity: float
    position_quantity_display: str
    expected_dividend_per_share_display: str
    expected_total_dividend: Optional[float]
    expected_total_dividend_display: str
    estimated_yield: str
    last_buy_date: str
    record_date: str
    status: str
    has_data: bool


@dataclass(frozen=True)
class DividendsView:
    period_days: int
    items: list[DividendItem]
    empty_watchlist: bool
    error: Optional[str] = None
    portfolio_error: Optional[str] = None


class DividendsService:
    def __init__(
        self,
        watchlist_service: Optional[WatchlistService] = None,
        broker: Optional[TInvestBroker] = None,
        mode_service: Optional[ModeService] = None,
        token_provider: Optional[Callable[[], Optional[str]]] = None,
    ):
        self.watchlist_service = watchlist_service or WatchlistService()
        self.broker = broker or TInvestBroker()
        self.mode_service = mode_service or ModeService()
        self.token_provider = token_provider or get_active_invest_token

    def get_dividends_view(self, period_days: int = DEFAULT_DIVIDEND_PERIOD_DAYS) -> DividendsView:
        period_days = self._normalize_period(period_days)
        watchlist = self.watchlist_service.list_items()
        if watchlist.empty:
            return DividendsView(period_days=period_days, items=[], empty_watchlist=True)

        token = self.token_provider()
        if not token:
            return DividendsView(
                period_days=period_days,
                items=[],
                empty_watchlist=False,
                error="No broker token is configured for the current mode.",
            )

        position_quantities, portfolio_error = self._load_position_quantities(token)
        items = [
            self._build_dividend_item(token, period_days, item, position_quantities)
            for item in watchlist.items
        ]
        return DividendsView(
            period_days=period_days,
            items=items,
            empty_watchlist=False,
            portfolio_error=portfolio_error,
        )

    def _build_dividend_item(
        self,
        token: str,
        period_days: int,
        item: WatchlistItem,
        position_quantities: Optional[dict[str, float]],
    ) -> DividendItem:
        name = item.name
        try:
            name = self.broker.get_instrument_name(token, item.figi) or item.name
        except Exception:
            name = item.name

        position_quantity = self._position_quantity(item.ticker, position_quantities)
        position_quantity_display = self._position_quantity_display(position_quantity, position_quantities)

        try:
            dividend = self.broker.get_dividend_info(token, item.figi, period_days)
        except Exception:
            dividend = None

        if dividend is None:
            return DividendItem(
                ticker=item.ticker,
                name=name,
                next_dividend_date=UNAVAILABLE_DISPLAY,
                expected_dividend=UNAVAILABLE_DISPLAY,
                position_quantity=position_quantity,
                position_quantity_display=position_quantity_display,
                expected_dividend_per_share_display=UNAVAILABLE_DISPLAY,
                expected_total_dividend=None,
                expected_total_dividend_display=UNAVAILABLE_DISPLAY,
                estimated_yield=UNAVAILABLE_DISPLAY,
                last_buy_date=UNAVAILABLE_DISPLAY,
                record_date=UNAVAILABLE_DISPLAY,
                status="No dividend data available for the selected period.",
                has_data=False,
            )

        dividend_per_share = parse_optional_float(getattr(dividend, "dividend_net", None))
        expected_total_dividend = self._expected_total_dividend(dividend_per_share, position_quantity, position_quantities)
        expected_dividend_per_share_display = (
            money(dividend_per_share) if dividend_per_share is not None else UNAVAILABLE_DISPLAY
        )

        return DividendItem(
            ticker=item.ticker,
            name=name,
            next_dividend_date=dividend.payment_date or UNAVAILABLE_DISPLAY,
            expected_dividend=expected_dividend_per_share_display,
            position_quantity=position_quantity,
            position_quantity_display=position_quantity_display,
            expected_dividend_per_share_display=expected_dividend_per_share_display,
            expected_total_dividend=expected_total_dividend,
            expected_total_dividend_display=(
                money(expected_total_dividend)
                if expected_total_dividend is not None
                else UNAVAILABLE_DISPLAY
            ),
            estimated_yield=f"{dividend.yield_value}%" if dividend.yield_value else UNAVAILABLE_DISPLAY,
            last_buy_date=dividend.last_buy_date or UNAVAILABLE_DISPLAY,
            record_date=dividend.record_date or UNAVAILABLE_DISPLAY,
            status="Dividend data available.",
            has_data=True,
        )

    def _load_position_quantities(self, token: str) -> tuple[Optional[dict[str, float]], Optional[str]]:
        try:
            mode = self.mode_service.current()
            raw_portfolio = self.broker.get_portfolio(token, sandbox=mode.is_sandbox)
        except Exception as exc:
            return None, portfolio_error_message(exc)

        quantities: dict[str, float] = {}
        for position in raw_portfolio.get("positions", []):
            ticker = str(position.get("ticker") or "").strip().upper()
            if not ticker:
                continue
            quantities[ticker] = quantities.get(ticker, 0.0) + as_float(position.get("quantity"))
        return quantities, None

    def _position_quantity(
        self,
        ticker: str,
        position_quantities: Optional[dict[str, float]],
    ) -> float:
        if position_quantities is None:
            return 0.0
        return position_quantities.get(ticker.upper(), 0.0)

    def _position_quantity_display(
        self,
        position_quantity: float,
        position_quantities: Optional[dict[str, float]],
    ) -> str:
        if position_quantities is None:
            return UNAVAILABLE_DISPLAY
        return format_quantity(position_quantity)

    def _expected_total_dividend(
        self,
        dividend_per_share: Optional[float],
        position_quantity: float,
        position_quantities: Optional[dict[str, float]],
    ) -> Optional[float]:
        if dividend_per_share is None or position_quantities is None:
            return None
        return dividend_per_share * position_quantity

    def _normalize_period(self, period_days: int) -> int:
        try:
            value = int(period_days)
        except (TypeError, ValueError):
            return DEFAULT_DIVIDEND_PERIOD_DAYS

        return min(max(value, 1), 1825)


def parse_optional_float(value) -> Optional[float]:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)

    text = str(value).strip()
    if not text or text == UNAVAILABLE_DISPLAY:
        return None

    normalized = "".join(char for char in text if char.isdigit() or char in {",", ".", "-", "+"})
    if not normalized or normalized in {",", ".", "-", "+"}:
        return None

    comma_index = normalized.rfind(",")
    dot_index = normalized.rfind(".")
    if comma_index >= 0 and dot_index >= 0:
        decimal_separator = "," if comma_index > dot_index else "."
        thousands_separator = "." if decimal_separator == "," else ","
        normalized = normalized.replace(thousands_separator, "")
        normalized = normalized.replace(decimal_separator, ".")
    elif comma_index >= 0:
        normalized = normalized.replace(",", ".")

    if normalized.count(".") > 1:
        head, tail = normalized.rsplit(".", 1)
        normalized = f"{head.replace('.', '')}.{tail}"

    try:
        return float(normalized)
    except ValueError:
        return None
