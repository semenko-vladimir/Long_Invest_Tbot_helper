from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Literal, Optional


DataHubGapSeverity = Literal["low", "medium", "high"]
DataHubFreshness = Literal[
    "current",
    "latest_available",
    "delayed_public_data",
    "stale",
    "partial",
    "unavailable",
]
DataHubDelayStatus = Literal[
    "broker_api",
    "moex_delayed",
    "official_date_based",
    "local_curated",
    "cache_fallback",
    "unknown",
]


@dataclass(frozen=True)
class DataHubDataGap:
    category: str
    description: str
    severity: DataHubGapSeverity = "medium"


@dataclass(frozen=True)
class DataHubError:
    message: str
    category: str = "source"
    severity: DataHubGapSeverity = "medium"


@dataclass(frozen=True)
class DataHubMetadata:
    topic: str
    source: str
    fetched_at: datetime
    as_of_date: Optional[str] = None
    freshness: Optional[DataHubFreshness] = None
    delay_status: Optional[DataHubDelayStatus] = None
    ttl_seconds: Optional[int] = None
    cached: bool = False
    cache_key: Optional[str] = None


@dataclass(frozen=True)
class DataHubResult:
    topic: str
    data: dict[str, Any] = field(default_factory=dict)
    metadata: Optional[DataHubMetadata] = None
    data_gaps: list[DataHubDataGap] = field(default_factory=list)
    errors: list[DataHubError] = field(default_factory=list)
