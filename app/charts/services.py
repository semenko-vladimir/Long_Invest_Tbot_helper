from datetime import datetime, timedelta
from typing import Callable, Optional

from app.charts.adapters import ChartDataAdapter
from app.charts.schemas import ChartCandleInterval, ChartDataGap, ChartHistory, ChartMode, ChartRange


CHART_DISCLAIMER = (
    "Read-only historical price data for educational review only. "
    "Hindsight-only analytics. Not a trading signal. Not investment advice. "
    "No broker orders were created. This is not personal investment advice "
    "and must not trigger broker orders."
)

SUPPORTED_CHART_RANGES: set[ChartRange] = {
    "day",
    "week",
    "month",
    "six_months",
    "year",
    "all",
}
SUPPORTED_CHART_MODES: set[ChartMode] = {"price", "position_value"}


class ChartHistoryService:
    def __init__(
        self,
        adapter: ChartDataAdapter,
        now_provider: Optional[Callable[[], datetime]] = None,
        disclaimer: str = CHART_DISCLAIMER,
    ):
        self.adapter = adapter
        self.now_provider = now_provider or datetime.utcnow
        self.disclaimer = disclaimer

    def get_history(self, ticker: str, range_name: str = "month") -> ChartHistory:
        generated_at = self.now_provider()
        normalized_ticker = self._normalize_ticker(ticker)
        normalized_range = normalize_chart_range(range_name)
        errors: list[str] = []
        gaps: list[ChartDataGap] = []

        if not normalized_ticker:
            message = "Ticker is required and must use letters, numbers, or hyphen."
            errors.append(message)
            gaps.append(ChartDataGap("ticker", message, "high"))

        if normalized_range is None:
            supported = ", ".join(sorted(SUPPORTED_CHART_RANGES))
            message = f"Unsupported chart range: {range_name}. Supported ranges: {supported}."
            errors.append(message)
            gaps.append(ChartDataGap("range", message, "high"))

        if errors:
            return ChartHistory(
                ticker=normalized_ticker,
                figi=None,
                range=normalized_range or str(range_name or "").strip(),
                interval=chart_interval_for_range(normalized_range) if normalized_range else None,
                candles=[],
                generated_at=generated_at,
                source=self._adapter_source_name(),
                fetched_at=generated_at,
                as_of_date=generated_at.date().isoformat(),
                data_gaps=gaps,
                errors=errors,
                disclaimer=self.disclaimer,
            )

        try:
            result = self.adapter.fetch_candles(normalized_ticker, normalized_range)
        except Exception as exc:
            return ChartHistory(
                ticker=normalized_ticker,
                figi=None,
                range=normalized_range,
                interval=chart_interval_for_range(normalized_range),
                candles=[],
                generated_at=generated_at,
                source=self._adapter_source_name(),
                fetched_at=generated_at,
                as_of_date=generated_at.date().isoformat(),
                data_gaps=[ChartDataGap("adapter", "Chart adapter failed before returning data.", "medium")],
                errors=[f"{self._adapter_source_name()} adapter failed: {str(exc)}"],
                disclaimer=self.disclaimer,
            )

        data_gaps = list(result.data_gaps)
        if not result.candles and not any(gap.category == "price_history" for gap in data_gaps):
            data_gaps.append(
                ChartDataGap(
                    "price_history",
                    "No candles were returned for the selected ticker and range.",
                    "low",
                )
            )

        return ChartHistory(
            ticker=result.ticker or normalized_ticker,
            figi=result.figi,
            range=normalized_range,
            interval=result.interval or chart_interval_for_range(normalized_range),
            candles=list(result.candles),
            generated_at=generated_at,
            source=result.source_name or self._adapter_source_name(),
            fetched_at=result.fetched_at or generated_at,
            as_of_date=result.as_of_date or self._candles_as_of_date(result.candles),
            freshness=result.freshness,
            delay_status=result.delay_status,
            data_gaps=data_gaps,
            errors=list(result.errors),
            disclaimer=self.disclaimer,
        )

    def _adapter_source_name(self) -> str:
        return str(getattr(self.adapter, "source_name", self.adapter.__class__.__name__) or self.adapter.__class__.__name__)

    def _normalize_ticker(self, ticker: str) -> str:
        normalized = str(ticker or "").strip().upper()
        return normalized if normalized.replace("-", "").isalnum() else ""

    def _candles_as_of_date(self, candles) -> Optional[str]:
        if not candles:
            return None
        return max(candle.time for candle in candles).date().isoformat()


def normalize_chart_range(range_name: str) -> Optional[ChartRange]:
    normalized = str(range_name or "").strip().lower().replace("-", "_").replace(" ", "_")
    aliases = {
        "1d": "day",
        "7d": "week",
        "1w": "week",
        "1m": "month",
        "6m": "six_months",
        "six_month": "six_months",
        "6_months": "six_months",
        "1y": "year",
        "max": "all",
    }
    normalized = aliases.get(normalized, normalized)
    if normalized in SUPPORTED_CHART_RANGES:
        return normalized
    return None


def normalize_chart_mode(mode: str) -> Optional[ChartMode]:
    normalized = str(mode or "").strip().lower().replace("-", "_").replace(" ", "_")
    aliases = {
        "current_quantity_value": "position_value",
        "current_position_value": "position_value",
        "value": "position_value",
    }
    normalized = aliases.get(normalized, normalized)
    if normalized in SUPPORTED_CHART_MODES:
        return normalized
    return None


def normalize_chart_interval(interval_name: str, range_name: ChartRange) -> Optional[ChartCandleInterval]:
    normalized = str(interval_name or "").strip().lower().replace("-", "_").replace(" ", "_")
    if normalized in {"", "auto"}:
        return chart_interval_for_range(range_name)

    aliases = {
        "1h": "hour",
        "h": "hour",
        "hourly": "hour",
        "1d": "day",
        "d": "day",
        "daily": "day",
    }
    normalized = aliases.get(normalized, normalized)
    if normalized == "hour" and range_name == "day":
        return "hour"
    if normalized == "day":
        return "day"
    return None


def chart_interval_for_range(range_name: ChartRange) -> ChartCandleInterval:
    return "hour" if range_name == "day" else "day"


def chart_range_start(range_name: ChartRange, now: datetime) -> datetime | None:
    days_by_range = {
        "day": 1,
        "week": 7,
        "month": 31,
        "six_months": 183,
        "year": 366,
        "all": None,
    }
    days = days_by_range[range_name]
    if days is None:
        return None
    return now - timedelta(days=days)
