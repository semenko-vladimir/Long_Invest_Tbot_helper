from dataclasses import dataclass
from typing import Callable, Optional

from app.client.config import get_active_invest_token
from app.integrations.tinvest import TInvestBroker
from app.services.watchlist import WatchlistItem, WatchlistService


DEFAULT_DIVIDEND_PERIOD_DAYS = 365


@dataclass(frozen=True)
class DividendItem:
    ticker: str
    name: str
    next_dividend_date: str
    expected_dividend: str
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


class DividendsService:
    def __init__(
        self,
        watchlist_service: Optional[WatchlistService] = None,
        broker: Optional[TInvestBroker] = None,
        token_provider: Optional[Callable[[], Optional[str]]] = None,
    ):
        self.watchlist_service = watchlist_service or WatchlistService()
        self.broker = broker or TInvestBroker()
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

        items = [self._build_dividend_item(token, period_days, item) for item in watchlist.items]
        return DividendsView(period_days=period_days, items=items, empty_watchlist=False)

    def _build_dividend_item(self, token: str, period_days: int, item: WatchlistItem) -> DividendItem:
        name = item.name
        try:
            name = self.broker.get_instrument_name(token, item.figi) or item.name
        except Exception:
            name = item.name

        try:
            dividend = self.broker.get_dividend_info(token, item.figi, period_days)
        except Exception:
            dividend = None

        if dividend is None:
            return DividendItem(
                ticker=item.ticker,
                name=name,
                next_dividend_date="-",
                expected_dividend="-",
                estimated_yield="-",
                last_buy_date="-",
                record_date="-",
                status="No dividend data available for the selected period.",
                has_data=False,
            )

        return DividendItem(
            ticker=item.ticker,
            name=name,
            next_dividend_date=dividend.payment_date or "-",
            expected_dividend=f"{dividend.dividend_net} RUB" if dividend.dividend_net else "-",
            estimated_yield=f"{dividend.yield_value}%" if dividend.yield_value else "-",
            last_buy_date=dividend.last_buy_date or "-",
            record_date=dividend.record_date or "-",
            status="Dividend data available.",
            has_data=True,
        )

    def _normalize_period(self, period_days: int) -> int:
        try:
            value = int(period_days)
        except (TypeError, ValueError):
            return DEFAULT_DIVIDEND_PERIOD_DAYS

        return min(max(value, 1), 1825)
