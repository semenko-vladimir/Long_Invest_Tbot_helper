from dataclasses import dataclass
from typing import Optional

from app.charts.factory import build_chart_services
from app.charts.images import ChartImageService
from app.charts.position_values import PositionValueChartService
from app.client.config import get_invest_mode
from app.client.handlers.utils.message_utils import send_or_edit_message
from app.integrations.tinvest import TInvestBroker
from app.research.local_fundamentals_adapter import LocalFundamentalsAdapter
from app.research.market_context import MOEXMarketContextAdapter
from app.research.moex_iss_adapter import MOEXISSResearchAdapter
from app.research.services import ResearchReportService, TickerResearchService
from app.research.tinvest_adapter import TInvestDataAdapter
from app.services.dividends import DividendsService
from app.services.mode import ModeService
from app.services.orders import OrderService
from app.services.portfolio import PortfolioService
from app.services.statistics import StatisticsService
from app.services.user_context import UnknownUserError, UserContext, UserContextResolver
from app.services.user_database import session_factory_for_user
from app.services.watchlist import WatchlistService


@dataclass
class TelegramUserServices:
    user: UserContext
    broker: TInvestBroker
    portfolio_service: PortfolioService
    order_service: OrderService
    watchlist_service: WatchlistService
    dividends_service: DividendsService
    statistics_service: StatisticsService
    ticker_research: TickerResearchService
    report_builder: ResearchReportService
    chart_image_service: ChartImageService
    position_value_chart_service: PositionValueChartService


_resolver = UserContextResolver()
_service_cache: dict[str, TelegramUserServices] = {}


def resolve_telegram_user(chat_id: int | str) -> UserContext:
    return _resolver.resolve_telegram_chat(chat_id)


def get_telegram_services(chat_id: int | str) -> TelegramUserServices:
    user = resolve_telegram_user(chat_id)
    services = _service_cache.get(user.user_id)
    if services is None:
        services = build_telegram_services(user)
        _service_cache[user.user_id] = services
    return services


def get_telegram_services_or_notify(chat_id: int | str) -> Optional[TelegramUserServices]:
    try:
        return get_telegram_services(chat_id)
    except UnknownUserError:
        send_or_edit_message(
            int(chat_id),
            "This Telegram chat is not authorized for this local investor assistant.",
        )
        return None


def build_telegram_services(user: UserContext) -> TelegramUserServices:
    session_factory = session_factory_for_user(user)
    token_provider = lambda: user.active_token(get_invest_mode())
    mode_service = ModeService()
    broker = TInvestBroker(session_factory=session_factory)
    portfolio_service = PortfolioService(
        broker=broker,
        mode_service=mode_service,
        token_provider=token_provider,
    )
    watchlist_service = WatchlistService(
        broker=broker,
        session_factory=session_factory,
        token_provider=token_provider,
    )
    chart_services = build_chart_services(
        broker=broker,
        token_provider=token_provider,
        portfolio_service=portfolio_service,
    )
    return TelegramUserServices(
        user=user,
        broker=broker,
        portfolio_service=portfolio_service,
        order_service=OrderService(
            broker=broker,
            mode_service=mode_service,
            token_provider=token_provider,
        ),
        watchlist_service=watchlist_service,
        dividends_service=DividendsService(
            watchlist_service=watchlist_service,
            broker=broker,
            mode_service=mode_service,
            token_provider=token_provider,
        ),
        statistics_service=StatisticsService(session_factory=session_factory),
        ticker_research=TickerResearchService(
            [
                TInvestDataAdapter(broker=broker, token_provider=token_provider),
                MOEXISSResearchAdapter(),
                LocalFundamentalsAdapter(),
                MOEXMarketContextAdapter(),
            ]
        ),
        report_builder=ResearchReportService(),
        chart_image_service=chart_services.image_service,
        position_value_chart_service=chart_services.position_value_service,
    )


def clear_telegram_service_cache() -> None:
    _service_cache.clear()
