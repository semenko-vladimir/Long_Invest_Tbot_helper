from datetime import datetime
from typing import Callable, Optional

from app.charts.adapters import ChartDataAdapter
from app.charts.schemas import ChartDataGap, ChartHistory, ChartRange


CHART_DISCLAIMER = (
    "Read-only historical price data for educational review only. "
    "This is not personal investment advice and must not trigger broker orders."
)

SUPPORTED_CHART_RANGES: set[ChartRange] = {
    "day",
    "week",
    "month",
    "six_months",
    "year",
    "all",
}


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
                candles=[],
                generated_at=generated_at,
                source=self._adapter_source_name(),
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
                candles=[],
                generated_at=generated_at,
                source=self._adapter_source_name(),
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
            candles=list(result.candles),
            generated_at=generated_at,
            source=result.source_name or self._adapter_source_name(),
            data_gaps=data_gaps,
            errors=list(result.errors),
            disclaimer=self.disclaimer,
        )

    def _adapter_source_name(self) -> str:
        return str(getattr(self.adapter, "source_name", self.adapter.__class__.__name__) or self.adapter.__class__.__name__)

    def _normalize_ticker(self, ticker: str) -> str:
        normalized = str(ticker or "").strip().upper()
        return normalized if normalized.replace("-", "").isalnum() else ""


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
