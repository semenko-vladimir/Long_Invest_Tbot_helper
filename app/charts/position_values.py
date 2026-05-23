from collections.abc import Callable
from datetime import datetime, timezone
from typing import Optional

from app.charts.schemas import (
    ChartDataGap,
    PositionValueChart,
    PositionValuePoint,
    POSITION_VALUE_CHART_DISCLAIMER,
)
from app.charts.services import ChartHistoryService, SUPPORTED_CHART_RANGES, normalize_chart_range
from app.services.portfolio import PortfolioService


class PositionValueChartService:
    """Builds read-only value series from current portfolio quantity and price candles."""

    def __init__(
        self,
        *,
        portfolio_service: PortfolioService,
        history_service: ChartHistoryService,
        now_provider: Optional[Callable[[], datetime]] = None,
        disclaimer: str = POSITION_VALUE_CHART_DISCLAIMER,
    ):
        self.portfolio_service = portfolio_service
        self.history_service = history_service
        self.now_provider = now_provider or (lambda: datetime.now(timezone.utc))
        self.disclaimer = disclaimer

    def get_position_value(self, ticker: str, range_name: str = "month") -> PositionValueChart:
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
            return self._result(
                ticker=normalized_ticker,
                range_name=normalized_range or str(range_name or "").strip(),
                generated_at=generated_at,
                data_gaps=gaps,
                errors=errors,
            )

        portfolio = self.portfolio_service.get_portfolio_view()
        portfolio_error = getattr(portfolio, "error", None)
        if portfolio_error:
            message = (
                f"Portfolio data is unavailable; cannot determine current quantity for "
                f"{normalized_ticker}: {portfolio_error}"
            )
            return self._result(
                ticker=normalized_ticker,
                range_name=normalized_range,
                generated_at=generated_at,
                data_gaps=[ChartDataGap("portfolio", message, "high")],
                errors=[message],
            )

        positions = list(getattr(portfolio, "positions", []) or [])
        position = self._find_position(positions, normalized_ticker)
        if position is None:
            if getattr(portfolio, "empty", not positions):
                message = (
                    "Current portfolio has no positions; cannot build a current quantity value "
                    f"chart for {normalized_ticker}."
                )
            else:
                message = (
                    f"Ticker {normalized_ticker} is not in the current portfolio; current "
                    "quantity value chart requires an open position."
                )
            return self._result(
                ticker=normalized_ticker,
                range_name=normalized_range,
                generated_at=generated_at,
                data_gaps=[ChartDataGap("portfolio_position", message, "medium")],
                errors=[message],
            )

        quantity = self._as_float(getattr(position, "quantity", None))
        if quantity <= 0:
            message = (
                f"Ticker {normalized_ticker} has zero or missing current quantity in the "
                "current portfolio."
            )
            return self._result(
                ticker=normalized_ticker,
                figi=str(getattr(position, "figi", "") or "") or None,
                range_name=normalized_range,
                quantity=quantity,
                generated_at=generated_at,
                data_gaps=[ChartDataGap("position_quantity", message, "medium")],
                errors=[message],
            )

        history = self.history_service.get_history(normalized_ticker, normalized_range)
        if history.errors:
            return self._result(
                ticker=history.ticker or normalized_ticker,
                figi=history.figi,
                range_name=history.range,
                quantity=quantity,
                generated_at=history.generated_at,
                source=history.source,
                fetched_at=history.fetched_at,
                data_gaps=list(history.data_gaps),
                errors=list(history.errors),
            )

        if not history.candles:
            message = (
                f"No candles are available for {normalized_ticker} in the selected range; "
                "current quantity value chart cannot be generated."
            )
            gaps = list(history.data_gaps)
            if not any(gap.category == "price_history" for gap in gaps):
                gaps.append(ChartDataGap("price_history", message, "low"))
            return self._result(
                ticker=history.ticker or normalized_ticker,
                figi=history.figi,
                range_name=history.range,
                quantity=quantity,
                generated_at=history.generated_at,
                source=history.source,
                fetched_at=history.fetched_at,
                data_gaps=gaps,
                errors=[message],
            )

        value_series = [
            PositionValuePoint(
                time=candle.time,
                close_price=float(candle.close),
                value=quantity * float(candle.close),
            )
            for candle in sorted(history.candles, key=lambda candle: candle.time)
        ]
        return self._result(
            ticker=history.ticker or normalized_ticker,
            figi=history.figi,
            range_name=history.range,
            quantity=quantity,
            value_series=value_series,
            generated_at=history.generated_at,
            source=history.source,
            fetched_at=history.fetched_at,
            data_gaps=list(history.data_gaps),
            errors=[],
        )

    def _result(
        self,
        *,
        ticker: str,
        range_name: str,
        generated_at: datetime,
        figi: str | None = None,
        quantity: float = 0.0,
        value_series: list[PositionValuePoint] | None = None,
        source: str = "portfolio-current-quantity",
        fetched_at: datetime | None = None,
        data_gaps: list[ChartDataGap] | None = None,
        errors: list[str] | None = None,
    ) -> PositionValueChart:
        return PositionValueChart(
            ticker=ticker,
            figi=figi,
            range=range_name,
            quantity=quantity,
            value_series=list(value_series or []),
            generated_at=generated_at,
            source=source,
            fetched_at=fetched_at or generated_at,
            data_gaps=list(data_gaps or []),
            errors=list(errors or []),
            disclaimer=self.disclaimer,
        )

    def _find_position(self, positions, ticker: str):
        for position in positions or []:
            position_ticker = self._normalize_ticker(getattr(position, "ticker", ""))
            if position_ticker == ticker:
                return position
        return None

    def _normalize_ticker(self, ticker: str) -> str:
        normalized = str(ticker or "").strip().upper()
        return normalized if normalized.replace("-", "").isalnum() else ""

    def _as_float(self, value) -> float:
        try:
            return float(value)
        except (TypeError, ValueError):
            return 0.0
