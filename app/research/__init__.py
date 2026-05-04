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

__all__ = [
    "AdapterResult",
    "DataGap",
    "DataSourceAdapter",
    "InstrumentIdentity",
    "MarketSnapshot",
    "ResearchReport",
    "SourceFreshness",
]
