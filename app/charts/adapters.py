from typing import Protocol

from app.data_sources.schemas import DATA_SOURCE_T_INVEST_THEN_MOEX_ISS_FALLBACK
from app.charts.schemas import ChartAdapterResult, ChartDataGap, ChartRange


class ChartDataAdapter(Protocol):
    """Read-only adapter for chart candles; never exposes broker order methods."""

    @property
    def source_name(self) -> str:
        ...

    def fetch_candles(self, ticker: str, range_name: ChartRange) -> ChartAdapterResult:
        ...


class FallbackChartDataAdapter:
    """Read-only primary/fallback adapter composition for chart candles."""

    source_name = DATA_SOURCE_T_INVEST_THEN_MOEX_ISS_FALLBACK

    def __init__(self, primary: ChartDataAdapter, fallback: ChartDataAdapter):
        self.primary = primary
        self.fallback = fallback

    def fetch_candles(self, ticker: str, range_name: ChartRange) -> ChartAdapterResult:
        primary_result = self._fetch_safely(self.primary, ticker, range_name)
        if primary_result.candles:
            return primary_result

        fallback_result = self._fetch_safely(self.fallback, ticker, range_name)
        if fallback_result.candles:
            return ChartAdapterResult(
                source_name=DATA_SOURCE_T_INVEST_THEN_MOEX_ISS_FALLBACK,
                ticker=fallback_result.ticker or primary_result.ticker or ticker,
                figi=fallback_result.figi or primary_result.figi,
                fetched_at=fallback_result.fetched_at,
                as_of_date=fallback_result.as_of_date,
                freshness=fallback_result.freshness,
                delay_status=fallback_result.delay_status,
                candles=list(fallback_result.candles),
                data_gaps=list(primary_result.data_gaps)
                + list(fallback_result.data_gaps)
                + [self._fallback_gap(primary_result, fallback_result.source_name)],
                errors=list(fallback_result.errors),
            )

        message = (
            f"No candles are available from {primary_result.source_name} "
            f"or {fallback_result.source_name}."
        )
        gaps = list(primary_result.data_gaps) + list(fallback_result.data_gaps)
        if not any(gap.category == "price_history" for gap in gaps):
            gaps.append(ChartDataGap("price_history", message, "medium"))

        errors = list(primary_result.errors) + list(fallback_result.errors)
        if not errors:
            errors.append(message)

        return ChartAdapterResult(
            source_name=DATA_SOURCE_T_INVEST_THEN_MOEX_ISS_FALLBACK,
            ticker=fallback_result.ticker or primary_result.ticker or ticker,
            figi=primary_result.figi or fallback_result.figi,
            fetched_at=fallback_result.fetched_at or primary_result.fetched_at,
            as_of_date=fallback_result.as_of_date or primary_result.as_of_date,
            freshness=fallback_result.freshness or primary_result.freshness,
            delay_status=fallback_result.delay_status or primary_result.delay_status,
            candles=[],
            data_gaps=gaps,
            errors=errors,
        )

    def _fetch_safely(
        self,
        adapter: ChartDataAdapter,
        ticker: str,
        range_name: ChartRange,
    ) -> ChartAdapterResult:
        source_name = self._adapter_source_name(adapter)
        try:
            return adapter.fetch_candles(ticker, range_name)
        except Exception as exc:
            return ChartAdapterResult(
                source_name=source_name,
                ticker=ticker,
                data_gaps=[ChartDataGap("adapter", f"{source_name} failed before returning data.", "medium")],
                errors=[f"{source_name} adapter failed: {str(exc)}"],
            )

    def _fallback_gap(self, primary_result: ChartAdapterResult, fallback_source_name: str) -> ChartDataGap:
        if primary_result.errors:
            description = (
                f"{primary_result.source_name} did not provide usable candles; "
                f"using {fallback_source_name}."
            )
        else:
            description = (
                f"{primary_result.source_name} returned no usable candles; "
                f"using {fallback_source_name}."
            )
        return ChartDataGap("source_fallback", description, "low")

    def _adapter_source_name(self, adapter: ChartDataAdapter) -> str:
        return str(getattr(adapter, "source_name", adapter.__class__.__name__) or adapter.__class__.__name__)
