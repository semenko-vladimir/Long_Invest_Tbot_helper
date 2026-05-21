from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal, Optional


ChartRange = Literal["day", "week", "month", "six_months", "year", "all"]
GapSeverity = Literal["low", "medium", "high"]


@dataclass(frozen=True)
class ChartDataGap:
    category: str
    description: str
    severity: GapSeverity = "medium"


@dataclass(frozen=True)
class PriceCandle:
    time: datetime
    open: float
    high: float
    low: float
    close: float
    volume: Optional[int] = None


@dataclass(frozen=True)
class ChartAdapterResult:
    source_name: str
    ticker: str
    figi: Optional[str] = None
    candles: list[PriceCandle] = field(default_factory=list)
    data_gaps: list[ChartDataGap] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class ChartHistory:
    ticker: str
    figi: Optional[str]
    range: str
    candles: list[PriceCandle]
    generated_at: datetime
    source: str
    data_gaps: list[ChartDataGap] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    disclaimer: str = (
        "Read-only historical price data for educational review only. "
        "This is not personal investment advice and must not trigger broker orders."
    )
