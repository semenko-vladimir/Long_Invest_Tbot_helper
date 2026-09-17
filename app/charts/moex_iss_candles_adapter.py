from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Callable, Optional, Sequence

from app.data_sources.schemas import DELAY_STATUS_DELAYED_PUBLIC_ISS, FRESHNESS_DELAYED_PUBLIC_DATA
from app.charts.schemas import ChartAdapterResult, ChartDataGap, ChartRange, PriceCandle
from app.integrations.moex_iss import (
    MOEXISSClient,
    MOEX_SOURCE_NAME,
    MOEXDailyCandle,
    configured_moex_index_tickers,
    sanitize_error_message,
)


@dataclass(frozen=True)
class MOEXChartRangeSpec:
    days: Optional[int]


class MOEXISSCandlesAdapter:
    """Read-only MOEX ISS daily candle adapter for chart data."""

    source_name = MOEX_SOURCE_NAME

    def __init__(
        self,
        client: Optional[MOEXISSClient] = None,
        index_tickers: Optional[Sequence[str]] = None,
        now_provider: Optional[Callable[[], datetime]] = None,
    ):
        self.now_provider = now_provider or (lambda: datetime.now(timezone.utc))
        self.client = client or MOEXISSClient(now_provider=self.now_provider)
        self.index_tickers = self._normalize_index_tickers(
            index_tickers if index_tickers is not None else configured_moex_index_tickers()
        )

    def fetch_candles(self, ticker: str, range_name: ChartRange) -> ChartAdapterResult:
        fetched_at = self.now_provider()
        normalized_ticker = self._normalize_ticker(ticker)
        if not normalized_ticker:
            return ChartAdapterResult(
                source_name=self.source_name,
                ticker="",
                fetched_at=fetched_at,
                as_of_date=fetched_at.date().isoformat(),
                freshness=FRESHNESS_DELAYED_PUBLIC_DATA,
                delay_status=DELAY_STATUS_DELAYED_PUBLIC_ISS,
                data_gaps=[ChartDataGap("ticker", "Ticker is required.", "high")],
                interval="day",
            )

        from_date, till_date = self._date_window(range_name)
        try:
            if normalized_ticker in self.index_tickers:
                result = self.client.get_index_daily_candles_result(
                    normalized_ticker,
                    from_date=from_date,
                    till_date=till_date,
                )
            else:
                result = self.client.get_daily_candles_result(
                    normalized_ticker,
                    from_date=from_date,
                    till_date=till_date,
                )
        except Exception as exc:
            message = f"MOEX ISS candle lookup failed: {sanitize_error_message(exc)}"
            return ChartAdapterResult(
                source_name=self.source_name,
                ticker=normalized_ticker,
                fetched_at=fetched_at,
                as_of_date=fetched_at.date().isoformat(),
                freshness=FRESHNESS_DELAYED_PUBLIC_DATA,
                delay_status=DELAY_STATUS_DELAYED_PUBLIC_ISS,
                data_gaps=[
                    ChartDataGap(
                        "price_history",
                        f"MOEX ISS daily candles are unavailable for {normalized_ticker}.",
                        "medium",
                    )
                ],
                errors=[message],
                interval="day",
            )

        data_gaps = [self._map_gap(gap) for gap in result.data_gaps]
        candles, skipped_count = self._map_candles(result.candles)
        if skipped_count:
            data_gaps.append(
                ChartDataGap(
                    "price_history",
                    f"Skipped {skipped_count} MOEX ISS candles with invalid OHLC data.",
                    "medium",
                )
            )

        if range_name == "day":
            data_gaps.append(
                ChartDataGap(
                    "granularity",
                    "MOEX ISS provides daily candles for day charts; intraday data was not synthesized.",
                    "low",
                )
            )

        return ChartAdapterResult(
            source_name=result.source or self.source_name,
            ticker=result.ticker or normalized_ticker,
            figi=None,
            fetched_at=result.fetched_at,
            as_of_date=result.as_of_date,
            freshness=result.freshness or FRESHNESS_DELAYED_PUBLIC_DATA,
            delay_status=result.delay_status or DELAY_STATUS_DELAYED_PUBLIC_ISS,
            candles=candles,
            data_gaps=data_gaps,
            errors=list(result.errors),
            interval="day",
        )

    def _date_window(self, range_name: ChartRange) -> tuple[Optional[date], date]:
        spec = moex_chart_range_spec(range_name)
        till_date = self.now_provider().date()
        if spec.days is None:
            return None, till_date
        return till_date - timedelta(days=spec.days), till_date

    def _map_candles(self, candles: list[MOEXDailyCandle]) -> tuple[list[PriceCandle], int]:
        mapped: list[PriceCandle] = []
        skipped_count = 0
        for candle in candles:
            price_candle = self._map_candle(candle)
            if price_candle is None:
                skipped_count += 1
                continue
            mapped.append(price_candle)
        return sorted(mapped, key=lambda item: item.time), skipped_count

    def _map_candle(self, candle: MOEXDailyCandle) -> Optional[PriceCandle]:
        values = (candle.open, candle.high, candle.low, candle.close)
        if any(value is None or float(value) <= 0 for value in values):
            return None

        return PriceCandle(
            time=candle.begin,
            open=float(candle.open),
            high=float(candle.high),
            low=float(candle.low),
            close=float(candle.close),
            volume=candle.volume,
        )

    def _map_gap(self, gap) -> ChartDataGap:
        severity = str(getattr(gap, "severity", "medium") or "medium")
        if severity not in {"low", "medium", "high"}:
            severity = "medium"
        return ChartDataGap(
            category=str(getattr(gap, "category", "") or "moex_iss"),
            description=str(getattr(gap, "description", "") or "MOEX ISS data gap."),
            severity=severity,
        )

    def _normalize_ticker(self, ticker: object) -> str:
        normalized = str(ticker or "").strip().upper()
        return normalized if normalized.replace("-", "").isalnum() else ""

    def _normalize_index_tickers(self, index_tickers: Sequence[str]) -> set[str]:
        return {
            normalized
            for normalized in (self._normalize_ticker(ticker) for ticker in index_tickers)
            if normalized
        }


def moex_chart_range_spec(range_name: ChartRange) -> MOEXChartRangeSpec:
    specs = {
        "day": MOEXChartRangeSpec(days=1),
        "week": MOEXChartRangeSpec(days=7),
        "month": MOEXChartRangeSpec(days=31),
        "six_months": MOEXChartRangeSpec(days=183),
        "year": MOEXChartRangeSpec(days=366),
        "all": MOEXChartRangeSpec(days=None),
    }
    return specs[range_name]
