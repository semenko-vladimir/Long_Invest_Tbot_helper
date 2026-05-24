from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal, Optional


ChartRange = Literal["day", "week", "month", "six_months", "year", "all"]
ChartMode = Literal["price", "position_value"]
GapSeverity = Literal["low", "medium", "high"]
ChartAnalyticsMarkerKind = Literal["historical_entry", "historical_exit"]
POSITION_VALUE_CHART_DISCLAIMER = (
    "Uses current position quantity valued at historical close prices; "
    "not historical holdings, not a trading signal, not investment advice, "
    "no broker orders were created."
)


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
class ChartAnalyticsMarker:
    kind: ChartAnalyticsMarkerKind
    label: str
    time: datetime
    close: float


@dataclass(frozen=True)
class ChartDrawdown:
    peak_time: datetime
    peak_close: float
    trough_time: datetime
    trough_close: float
    drawdown_pct: float


@dataclass(frozen=True)
class ChartRangePosition:
    latest_time: datetime
    latest_close: float
    range_high_close: float
    range_low_close: float
    vs_range_high_pct: float
    vs_range_low_pct: float


@dataclass(frozen=True)
class ChartSmaPoint:
    time: datetime
    value: float


@dataclass(frozen=True)
class ChartSmaSeries:
    window: int
    label: str
    points: list[ChartSmaPoint] = field(default_factory=list)


@dataclass(frozen=True)
class ChartAnalytics:
    entry_marker: Optional[ChartAnalyticsMarker] = None
    exit_marker: Optional[ChartAnalyticsMarker] = None
    hindsight_return_pct: Optional[float] = None
    max_drawdown: Optional[ChartDrawdown] = None
    range_position: Optional[ChartRangePosition] = None
    sma20: ChartSmaSeries = field(default_factory=lambda: ChartSmaSeries(window=20, label="SMA20"))
    sma50: ChartSmaSeries = field(default_factory=lambda: ChartSmaSeries(window=50, label="SMA50"))


@dataclass(frozen=True)
class ChartAdapterResult:
    source_name: str
    ticker: str
    figi: Optional[str] = None
    fetched_at: Optional[datetime] = None
    as_of_date: Optional[str] = None
    freshness: Optional[str] = None
    delay_status: Optional[str] = None
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
    fetched_at: Optional[datetime] = None
    as_of_date: Optional[str] = None
    freshness: Optional[str] = None
    delay_status: Optional[str] = None
    data_gaps: list[ChartDataGap] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    disclaimer: str = (
        "Read-only historical price data for educational review only. "
        "This is not personal investment advice and must not trigger broker orders."
    )

    @property
    def source_name(self) -> str:
        return self.source


@dataclass(frozen=True)
class PositionValuePoint:
    time: datetime
    close_price: float
    value: float


@dataclass(frozen=True)
class PositionValueChart:
    ticker: str
    figi: Optional[str]
    range: str
    quantity: float
    value_series: list[PositionValuePoint]
    generated_at: datetime
    source: str
    fetched_at: Optional[datetime] = None
    as_of_date: Optional[str] = None
    freshness: Optional[str] = None
    delay_status: Optional[str] = None
    data_gaps: list[ChartDataGap] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    disclaimer: str = POSITION_VALUE_CHART_DISCLAIMER

    @property
    def ok(self) -> bool:
        return bool(self.value_series) and not self.errors

    @property
    def source_name(self) -> str:
        return self.source


@dataclass(frozen=True)
class ChartImageResult:
    png_bytes: Optional[bytes]
    history: ChartHistory
    content_type: str = "image/png"
    mode: ChartMode = "price"
    analytics: Optional[ChartAnalytics] = None
    position_value: Optional[PositionValueChart] = None
    data_gaps: list[ChartDataGap] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return self.png_bytes is not None and not self.errors

    @property
    def source_name(self) -> str:
        if self.mode == "position_value" and self.position_value is not None:
            return self.position_value.source
        return self.history.source

    @property
    def fetched_at(self) -> Optional[datetime]:
        if self.mode == "position_value" and self.position_value is not None:
            return self.position_value.fetched_at
        return self.history.fetched_at

    @property
    def as_of_date(self) -> Optional[str]:
        if self.mode == "position_value" and self.position_value is not None:
            return self.position_value.as_of_date
        return self.history.as_of_date

    @property
    def freshness(self) -> Optional[str]:
        if self.mode == "position_value" and self.position_value is not None:
            return self.position_value.freshness
        return self.history.freshness

    @property
    def delay_status(self) -> Optional[str]:
        if self.mode == "position_value" and self.position_value is not None:
            return self.position_value.delay_status
        return self.history.delay_status
