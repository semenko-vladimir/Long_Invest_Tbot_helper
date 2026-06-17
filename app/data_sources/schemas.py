from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


DATA_SOURCE_T_INVEST = "T_INVEST"
DATA_SOURCE_MOEX_ISS = "MOEX_ISS"
DATA_SOURCE_LOCAL_FUNDAMENTALS = "LOCAL_FUNDAMENTALS"
DATA_SOURCE_T_INVEST_THEN_MOEX_ISS_FALLBACK = "T_INVEST_THEN_MOEX_ISS_FALLBACK"

FRESHNESS_CURRENT_OR_LATEST = "current_or_latest_available"
FRESHNESS_DELAYED_PUBLIC_DATA = "delayed_public_data"
FRESHNESS_LOCAL_SNAPSHOT = "local_snapshot"

DELAY_STATUS_BROKER_API = "broker_api_current_or_latest"
DELAY_STATUS_DELAYED_PUBLIC_ISS = "delayed_public_iss"
DELAY_STATUS_LOCAL_FILE = "local_file"


@dataclass(frozen=True)
class SourceMetadata:
    source: str
    fetched_at: datetime
    as_of_date: Optional[str] = None
    freshness: Optional[str] = None
    delay_status: Optional[str] = None
    data_gaps: list[object] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
