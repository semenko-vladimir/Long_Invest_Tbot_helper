from collections.abc import Callable
from dataclasses import dataclass

from app.charts.adapters import FallbackChartDataAdapter
from app.charts.images import ChartImageService
from app.charts.moex_iss_candles_adapter import MOEXISSCandlesAdapter
from app.charts.position_values import PositionValueChartService
from app.charts.services import ChartHistoryService
from app.charts.tinvest_candles_adapter import ReadOnlyInstrumentResolver, TInvestCandlesAdapter
from app.services.portfolio import PortfolioService


@dataclass(frozen=True)
class ChartServiceBundle:
    image_service: ChartImageService
    position_value_service: PositionValueChartService


def build_chart_image_service(
    *,
    broker: ReadOnlyInstrumentResolver,
    token_provider: Callable[[], str | None],
    portfolio_service: PortfolioService | None = None,
) -> ChartImageService:
    adapter = _build_chart_data_adapter(broker=broker, token_provider=token_provider)
    history_service = ChartHistoryService(adapter=adapter)
    position_value_service = (
        PositionValueChartService(
            portfolio_service=portfolio_service,
            history_service=history_service,
        )
        if portfolio_service is not None
        else None
    )
    return ChartImageService(
        history_service=history_service,
        position_value_service=position_value_service,
    )


def build_chart_services(
    *,
    broker: ReadOnlyInstrumentResolver,
    token_provider: Callable[[], str | None],
    portfolio_service: PortfolioService,
) -> ChartServiceBundle:
    adapter = _build_chart_data_adapter(broker=broker, token_provider=token_provider)
    history_service = ChartHistoryService(adapter=adapter)
    position_value_service = PositionValueChartService(
        portfolio_service=portfolio_service,
        history_service=history_service,
    )
    return ChartServiceBundle(
        image_service=ChartImageService(
            history_service=history_service,
            position_value_service=position_value_service,
        ),
        position_value_service=position_value_service,
    )


def _build_chart_data_adapter(
    *,
    broker: ReadOnlyInstrumentResolver,
    token_provider: Callable[[], str | None],
) -> FallbackChartDataAdapter:
    return FallbackChartDataAdapter(
        primary=TInvestCandlesAdapter(broker=broker, token_provider=token_provider),
        fallback=MOEXISSCandlesAdapter(),
    )
