from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Literal, Optional


GapSeverity = Literal["low", "medium", "high"]


@dataclass(frozen=True)
class SourceFreshness:
    source_name: str
    fetched_at: datetime
    as_of_date: Optional[str] = None
    is_stale: bool = False
    notes: Optional[str] = None


@dataclass(frozen=True)
class DataGap:
    category: str
    description: str
    severity: GapSeverity = "medium"


@dataclass(frozen=True)
class AdapterResult:
    source_name: str
    data: dict[str, Any] = field(default_factory=dict)
    freshness: Optional[SourceFreshness] = None
    gaps: list[DataGap] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class InstrumentIdentity:
    ticker: str
    figi: Optional[str] = None
    name: Optional[str] = None
    exchange: Optional[str] = None
    currency: Optional[str] = None


@dataclass(frozen=True)
class MarketSnapshot:
    current_price: Optional[float] = None
    currency: Optional[str] = None
    captured_at: Optional[datetime] = None


@dataclass(frozen=True)
class ResearchReport:
    ticker: str
    generated_at: datetime
    instrument_identity: Optional[InstrumentIdentity] = None
    sources: list[str] = field(default_factory=list)
    freshness: list[SourceFreshness] = field(default_factory=list)
    market_snapshot: Optional[MarketSnapshot] = None
    company_profile: Optional[dict[str, Any]] = None
    financials: Optional[dict[str, Any]] = None
    dividends: Optional[dict[str, Any]] = None
    sector_industry: Optional[dict[str, Any]] = None
    competitors: Optional[list[dict[str, Any]]] = None
    macro_context: Optional[dict[str, Any]] = None
    news_osint: Optional[list[dict[str, Any]]] = None
    risks: list[str] = field(default_factory=list)
    data_gaps: list[DataGap] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    confidence: Optional[float] = None
    disclaimer: str = (
        "Educational long-term research only. This is not personal investment advice "
        "and must not trigger broker orders."
    )
    educational_rating: Optional[str] = None
