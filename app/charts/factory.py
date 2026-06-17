from collections.abc import Callable
from dataclasses import dataclass

from app.charts.adapters import FallbackChartDataAdapter
from app.charts.images import ChartImageService
from app.charts.moex_iss_candles_adapter import MOEXISSCandlesAdapter
from app.charts.position_values import PositionValueChartService
from app.charts.repository import PriceCandleRepository
from app.charts.services import ChartHistoryService
from app.charts.snapshots import ChartDataRefreshService, ChartSnapshotService
from app.charts.tinvest_candles_adapter import ReadOnlyInstrumentResolver, TInvestCandlesAdapter
from app.services.portfolio import PortfolioService
from app.services.user_database import SessionFactory


@dataclass(frozen=True)
class ChartServiceBundle:
    image_service: ChartImageService
    position_value_service: PositionValueChartService
    candle_repository: PriceCandleRepository
    refresh_service: ChartDataRefreshService
    snapshot_service: ChartSnapshotService


def build_chart_image_service(
    *,
    broker: ReadOnlyInstrumentResolver,
    token_provider: Callable[[], str | None],
    portfolio_service: PortfolioService | None = None,
    session_factory: SessionFactory | None = None,
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


def build_moex_chart_image_service() -> ChartImageService:
    history_service = ChartHistoryService(adapter=MOEXISSCandlesAdapter())
    return ChartImageService(history_service=history_service)


def build_chart_services(
    *,
    broker: ReadOnlyInstrumentResolver,
    token_provider: Callable[[], str | None],
    portfolio_service: PortfolioService,
    session_factory: SessionFactory,
) -> ChartServiceBundle:
    adapter = _build_chart_data_adapter(broker=broker, token_provider=token_provider)
    history_service = ChartHistoryService(adapter=adapter)
    candle_repository = PriceCandleRepository(session_factory=session_factory)
    refresh_service = ChartDataRefreshService(
        history_service=history_service,
        repository=candle_repository,
    )
    snapshot_service = ChartSnapshotService(
        history_service=history_service,
        repository=candle_repository,
        refresh_service=refresh_service,
    )
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
        candle_repository=candle_repository,
        refresh_service=refresh_service,
        snapshot_service=snapshot_service,
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
