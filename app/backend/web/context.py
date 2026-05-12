from dataclasses import dataclass

from app.client.config import get_invest_mode
from app.integrations.tinvest import TInvestBroker
from app.research.local_fundamentals_adapter import LocalFundamentalsAdapter
from app.research.services import ResearchReportService, TickerResearchService
from app.research.tinvest_adapter import TInvestDataAdapter
from app.services.dividends import DividendsService
from app.services.investment_plans import InvestmentPlanService
from app.services.mode import ModeService
from app.services.order_history import OrderHistoryService
from app.services.orders import OrderService
from app.services.portfolio import PortfolioService
from app.services.settings_view import SettingsViewService
from app.services.statistics import StatisticsService
from app.services.user_context import UserContext, UserContextResolver
from app.services.user_database import SessionFactory, session_factory_for_user
from app.services.watchlist import WatchlistService


@dataclass
class WebRequestServices:
    user: UserContext
    session_factory: SessionFactory
    mode_service: ModeService
    portfolio_service: PortfolioService
    order_service: OrderService
    watchlist_service: WatchlistService
    dividends_service: DividendsService
    investment_plan_service: InvestmentPlanService
    statistics_service: StatisticsService
    settings_view_service: SettingsViewService
    order_history_service: OrderHistoryService
    ticker_research: TickerResearchService
    report_builder: ResearchReportService


_resolver = UserContextResolver()
_service_cache: dict[str, WebRequestServices] = {}


def get_web_services() -> WebRequestServices:
    user = _resolver.default_web_user()
    services = _service_cache.get(user.user_id)
    if services is None:
        services = build_web_services(user)
        _service_cache[user.user_id] = services
    return services


def build_web_services(user: UserContext) -> WebRequestServices:
    session_factory = session_factory_for_user(user)
    token_provider = lambda: user.active_token(get_invest_mode())
    mode_service = ModeService()
    broker = TInvestBroker(session_factory=session_factory)
    order_service = OrderService(broker=broker, mode_service=mode_service, token_provider=token_provider)
    watchlist_service = WatchlistService(
        broker=broker,
        session_factory=session_factory,
        token_provider=token_provider,
    )
    return WebRequestServices(
        user=user,
        session_factory=session_factory,
        mode_service=mode_service,
        portfolio_service=PortfolioService(
            broker=broker,
            mode_service=mode_service,
            token_provider=token_provider,
        ),
        order_service=order_service,
        watchlist_service=watchlist_service,
        dividends_service=DividendsService(
            watchlist_service=watchlist_service,
            broker=broker,
            token_provider=token_provider,
        ),
        investment_plan_service=InvestmentPlanService(
            order_service=order_service,
            session_factory=session_factory,
        ),
        statistics_service=StatisticsService(session_factory=session_factory),
        settings_view_service=SettingsViewService(mode_service=mode_service),
        order_history_service=OrderHistoryService(session_factory=session_factory),
        ticker_research=TickerResearchService(
            [
                TInvestDataAdapter(broker=broker, token_provider=token_provider),
                LocalFundamentalsAdapter(),
            ]
        ),
        report_builder=ResearchReportService(),
    )


def clear_web_service_cache() -> None:
    _service_cache.clear()
