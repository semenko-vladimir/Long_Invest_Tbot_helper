"""Read-only research terminal foundation for Tbot v1."""

from app.research.adapters import DataSourceAdapter
from app.research.schemas import (
    AdapterResult,
    DataGap,
    InstrumentIdentity,
    MarketSnapshot,
    ResearchReport,
    SourceFreshness,
)
from app.research.services import ResearchReportService, TickerResearchService
from app.research.tinvest_adapter import TInvestDataAdapter

__all__ = [
    "AdapterResult",
    "DataGap",
    "DataSourceAdapter",
    "InstrumentIdentity",
    "MarketSnapshot",
    "ResearchReportService",
    "ResearchReport",
    "SourceFreshness",
    "TickerResearchService",
    "TInvestDataAdapter",
]
