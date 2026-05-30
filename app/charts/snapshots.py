from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime, timedelta, timezone
from typing import Callable, Optional

from app.data_sources.schemas import DATA_SOURCE_MOEX_ISS, DATA_SOURCE_T_INVEST
from app.charts.analytics import ChartAnalyticsService
from app.charts.repository import PriceCandleRepository
from app.charts.schemas import (
    ChartAnalytics,
    ChartCacheStatus,
    ChartDataGap,
    ChartDataStatus,
    ChartDelayStatus,
    ChartFreshness,
    ChartHistory,
    ChartRefreshStatus,
    PriceCandle,
)
from app.charts.services import (
    CHART_DISCLAIMER,
    chart_interval_for_range,
    chart_range_start,
    normalize_chart_interval,
    normalize_chart_range,
)


@dataclass(frozen=True)
class ChartRefreshResult:
    history: ChartHistory
    interval: str
    changed_count: int
    refreshed_at: datetime

    @property
    def ok(self) -> bool:
        return not self.history.errors


@dataclass(frozen=True)
class ChartSnapshot:
    history: ChartHistory
    analytics: ChartAnalytics
    interval: str
    data_status: ChartDataStatus
    cache: ChartCacheStatus
    refresh_status: ChartRefreshStatus
    educational_only: bool = True

    @property
    def ok(self) -> bool:
        return bool(self.history.candles)

    @property
    def cache_candle_count(self) -> int:
        return self.cache.candle_count

    @property
    def refreshed(self) -> bool:
        return self.cache.refreshed


class ChartDataRefreshService:
    """Refreshes read-only chart candles into the local cache."""

    def __init__(
        self,
        history_service,
        repository: PriceCandleRepository,
        now_provider: Optional[Callable[[], datetime]] = None,
    ):
        self.history_service = history_service
        self.repository = repository
        self.now_provider = now_provider or datetime.utcnow

    def refresh_ticker(self, ticker: str, range_name: str = "day") -> ChartRefreshResult:
        normalized_range = normalize_chart_range(range_name)
        if normalized_range is None:
            now = self.now_provider()
            message = f"Unsupported chart range: {range_name}."
            return ChartRefreshResult(
                history=ChartHistory(
                    ticker=self._normalize_ticker(ticker),
                    figi=None,
                    range=str(range_name or "").strip(),
                    interval=None,
                    candles=[],
                    generated_at=now,
                    source=self.history_service._adapter_source_name(),
                    fetched_at=now,
                    as_of_date=now.date().isoformat(),
                    data_gaps=[ChartDataGap("range", message, "high")],
                    errors=[message],
                    disclaimer=CHART_DISCLAIMER,
                ),
                interval="",
                changed_count=0,
                refreshed_at=now,
            )

        cache_interval = chart_interval_for_range(normalized_range)
        latest_cached_time = self.repository.latest_candle_time(ticker=ticker, interval=cache_interval)
        history = self._fetch_history(ticker, normalized_range, latest_cached_time)
        history = replace(history, interval=cache_interval)
        changed_count = 0
        if history.candles and not history.errors:
            changed_count = self.repository.upsert_candles(
                ticker=history.ticker,
                figi=history.figi,
                interval=cache_interval,
                candles=history.candles,
                source=history.source,
                fetched_at=history.fetched_at,
                as_of_date=history.as_of_date,
                freshness=history.freshness,
                delay_status=history.delay_status,
            )

        return ChartRefreshResult(
            history=history,
            interval=cache_interval,
            changed_count=changed_count,
            refreshed_at=self.now_provider(),
        )

    def _fetch_history(self, ticker: str, range_name: str, since: datetime | None) -> ChartHistory:
        adapter = getattr(self.history_service, "adapter", None)
        fetch_since = getattr(adapter, "fetch_candles_since", None)
        if since is None or fetch_since is None:
            return self.history_service.get_history(ticker, range_name)

        generated_at = self.now_provider()
        try:
            result = fetch_since(ticker, range_name, since)
        except Exception:
            return self.history_service.get_history(ticker, range_name)

        return ChartHistory(
            ticker=result.ticker or self._normalize_ticker(ticker),
            figi=result.figi,
            range=range_name,
            interval=result.interval or chart_interval_for_range(range_name),
            candles=list(result.candles),
            generated_at=generated_at,
            source=result.source_name or self.history_service._adapter_source_name(),
            fetched_at=result.fetched_at or generated_at,
            as_of_date=result.as_of_date or self._candles_as_of_date(result.candles),
            freshness=result.freshness,
            delay_status=result.delay_status,
            data_gaps=list(result.data_gaps),
            errors=list(result.errors),
            disclaimer=CHART_DISCLAIMER,
        )

    def _normalize_ticker(self, ticker: str) -> str:
        normalized = str(ticker or "").strip().upper()
        return normalized if normalized.replace("-", "").isalnum() else ""

    def _candles_as_of_date(self, candles) -> str | None:
        if not candles:
            return None
        return max(candle.time for candle in candles).date().isoformat()


class ChartSnapshotService:
    """Builds the JSON-ready chart snapshot used by the web terminal."""

    def __init__(
        self,
        history_service,
        repository: Optional[PriceCandleRepository] = None,
        refresh_service: Optional[ChartDataRefreshService] = None,
        analytics_service: Optional[ChartAnalyticsService] = None,
        now_provider: Optional[Callable[[], datetime]] = None,
    ):
        self.history_service = history_service
        self.repository = repository
        self.refresh_service = refresh_service
        self.analytics_service = analytics_service or ChartAnalyticsService()
        self.now_provider = now_provider or datetime.utcnow

    def get_snapshot(
        self,
        ticker: str,
        range_name: str = "month",
        *,
        interval_name: str = "auto",
        refresh: bool = True,
    ) -> ChartSnapshot:
        now = self.now_provider()
        normalized_ticker = self._normalize_ticker(ticker)
        normalized_range = normalize_chart_range(range_name)
        errors: list[str] = []
        gaps: list[ChartDataGap] = []

        if not normalized_ticker:
            message = "Ticker is required and must use letters, numbers, or hyphen."
            errors.append(message)
            gaps.append(ChartDataGap("ticker", message, "high"))

        interval = None
        if normalized_range is None:
            message = f"Unsupported chart range: {range_name}."
            errors.append(message)
            gaps.append(ChartDataGap("range", message, "high"))
        else:
            interval = normalize_chart_interval(interval_name, normalized_range)
            if interval is None:
                message = "Unsupported chart interval. Use interval=auto, interval=hour, or interval=day."
                errors.append(message)
                gaps.append(ChartDataGap("interval", message, "high"))

        if errors:
            history = ChartHistory(
                ticker=normalized_ticker,
                figi=None,
                range=normalized_range or str(range_name or "").strip(),
                interval=interval,
                candles=[],
                generated_at=now,
                source=self.history_service._adapter_source_name(),
                fetched_at=now,
                as_of_date=now.date().isoformat(),
                data_gaps=gaps,
                errors=errors,
                disclaimer=CHART_DISCLAIMER,
            )
            cache_status = ChartCacheStatus()
            return self._snapshot(
                history=history,
                analytics=ChartAnalytics(),
                interval=interval or "",
                cache=cache_status,
                refresh_status=ChartRefreshStatus(requested=refresh),
            )

        assert normalized_range is not None
        assert interval is not None

        refresh_result: ChartRefreshResult | None = None
        if refresh and self.refresh_service is not None:
            refresh_result = self.refresh_service.refresh_ticker(normalized_ticker, normalized_range)

        if self.repository is None:
            history = refresh_result.history if refresh_result is not None else self.history_service.get_history(
                normalized_ticker, normalized_range
            )
            data_gaps, errors = self._status_gaps_and_errors(
                history=history,
                data_gaps=list(history.data_gaps),
                errors=list(history.errors),
                candles=list(history.candles),
                now=now,
                cache_fallback=False,
            )
            history = replace(
                history,
                data_gaps=data_gaps,
                errors=errors,
                freshness=self._freshness(
                    history=history,
                    candles=list(history.candles),
                    now=now,
                    data_gaps=data_gaps,
                    errors=errors,
                    cache_fallback=False,
                ),
            delay_status=self._delay_status(history.source, history.delay_status, cache_fallback=False),
            )
            cache_status = ChartCacheStatus(
                used=False,
                refreshed=refresh_result is not None,
                candle_count=len(history.candles),
                latest_candle_at=self._latest_candle_at(history.candles),
                oldest_candle_at=self._oldest_candle_at(history.candles),
            )
            return self._snapshot(
                history=history,
                analytics=self.analytics_service.calculate(history.candles),
                interval=history.interval or interval,
                cache=cache_status,
                refresh_status=ChartRefreshStatus(
                    requested=refresh,
                    attempted=refresh_result is not None,
                    refreshed=refresh_result is not None and refresh_result.ok,
                    errors=list(refresh_result.history.errors) if refresh_result is not None else [],
                ),
            )

        from_time = chart_range_start(normalized_range, now)
        candles = self.repository.list_candles(
            ticker=normalized_ticker,
            interval=interval,
            from_time=from_time,
            to_time=now,
        )
        metadata = self.repository.metadata(ticker=normalized_ticker, interval=interval)
        data_gaps = list(refresh_result.history.data_gaps) if refresh_result is not None else []
        refresh_errors = list(refresh_result.history.errors) if refresh_result is not None else []
        errors = list(refresh_errors)

        if not candles and refresh_result is not None and refresh_result.history.candles:
            candles = list(refresh_result.history.candles)
            metadata_source = refresh_result.history.source
            metadata_figi = refresh_result.history.figi
            metadata_fetched_at = refresh_result.history.fetched_at
            metadata_as_of_date = refresh_result.history.as_of_date
            metadata_freshness = refresh_result.history.freshness
            metadata_delay_status = refresh_result.history.delay_status
        else:
            metadata_source = metadata.source
            metadata_figi = metadata.figi
            metadata_fetched_at = metadata.fetched_at
            metadata_as_of_date = metadata.as_of_date or self._candles_as_of_date(candles)
            metadata_freshness = metadata.freshness
            metadata_delay_status = metadata.delay_status

        cache_fallback = bool(candles) and refresh_result is not None and (
            bool(refresh_result.history.errors) or not refresh_result.history.candles
        )
        cache_only = bool(candles) and refresh_result is None
        if cache_fallback:
            if not any(gap.category == "local_cache" for gap in data_gaps):
                data_gaps.append(
                    ChartDataGap(
                        "local_cache",
                        "Live chart refresh did not provide usable candles; showing local cached candles.",
                        "medium",
                    )
                )
            errors = []

        if not candles:
            message = "No chart data available for the selected ticker and range."
            if not any(gap.category == "price_history" for gap in data_gaps):
                data_gaps.append(
                    ChartDataGap(
                        "price_history",
                        message,
                        "high",
                    )
                )
            if not any(message.lower() in error.lower() for error in errors):
                errors.append(message)

        data_gaps, errors = self._status_gaps_and_errors(
            history=ChartHistory(
                ticker=normalized_ticker,
                figi=metadata_figi,
                range=normalized_range,
                interval=interval,
                candles=candles,
                generated_at=now,
                source=metadata_source or self.history_service._adapter_source_name(),
                fetched_at=metadata_fetched_at,
                as_of_date=metadata_as_of_date,
                data_gaps=data_gaps,
                errors=errors,
                disclaimer=CHART_DISCLAIMER,
            ),
            data_gaps=data_gaps,
            errors=errors,
            candles=candles,
            now=now,
            cache_fallback=cache_fallback,
        )
        freshness = self._freshness(
            history=ChartHistory(
                ticker=normalized_ticker,
                figi=metadata_figi,
                range=normalized_range,
                interval=interval,
                candles=candles,
                generated_at=now,
                source=metadata_source or self.history_service._adapter_source_name(),
                fetched_at=metadata_fetched_at,
                as_of_date=metadata_as_of_date,
                freshness=metadata_freshness,
                delay_status=metadata_delay_status,
                data_gaps=data_gaps,
                errors=errors,
                disclaimer=CHART_DISCLAIMER,
            ),
            candles=candles,
            now=now,
            data_gaps=data_gaps,
            errors=errors,
            cache_fallback=cache_fallback,
            refresh_attempted=refresh_result is not None,
        )
        delay_status = self._delay_status(
            metadata_source,
            metadata_delay_status,
            cache_fallback=cache_fallback,
            cache_only=cache_only,
        )

        history = ChartHistory(
            ticker=normalized_ticker,
            figi=metadata_figi,
            range=normalized_range,
            interval=interval,
            candles=candles,
            generated_at=now,
            source=metadata_source or self.history_service._adapter_source_name(),
            fetched_at=metadata_fetched_at,
            as_of_date=metadata_as_of_date,
            freshness=freshness,
            delay_status=delay_status,
            data_gaps=data_gaps,
            errors=errors,
            disclaimer=CHART_DISCLAIMER,
        )
        cache_status = ChartCacheStatus(
            used=bool(candles),
            refreshed=refresh_result is not None and refresh_result.ok and bool(refresh_result.history.candles),
            candle_count=metadata.candle_count if metadata.candle_count else len(candles),
            latest_candle_at=self._latest_candle_at(candles),
            oldest_candle_at=self._oldest_candle_at(candles),
        )
        return self._snapshot(
            history=history,
            analytics=self.analytics_service.calculate(candles),
            interval=interval,
            cache=cache_status,
            refresh_status=ChartRefreshStatus(
                requested=refresh,
                attempted=refresh_result is not None,
                refreshed=cache_status.refreshed,
                errors=refresh_errors,
            ),
        )

    def _normalize_ticker(self, ticker: str) -> str:
        normalized = str(ticker or "").strip().upper()
        return normalized if normalized.replace("-", "").isalnum() else ""

    def _candles_as_of_date(self, candles) -> str | None:
        if not candles:
            return None
        return max(candle.time for candle in candles).date().isoformat()

    def _snapshot(
        self,
        *,
        history: ChartHistory,
        analytics: ChartAnalytics,
        interval: str,
        cache: ChartCacheStatus,
        refresh_status: ChartRefreshStatus,
    ) -> ChartSnapshot:
        data_status = ChartDataStatus(
            source=self._status_source(history.source, cache_fallback=history.delay_status == "cached"),
            freshness=self._coerce_freshness(history.freshness),
            delay_status=self._coerce_delay_status(history.delay_status),
            fetched_at=history.fetched_at,
            as_of_date=history.as_of_date,
            candle_count=len(history.candles),
            data_gaps=list(history.data_gaps),
            errors=list(history.errors),
            educational_only=True,
        )
        return ChartSnapshot(
            history=history,
            analytics=analytics,
            interval=interval,
            data_status=data_status,
            cache=cache,
            refresh_status=refresh_status,
        )

    def _status_gaps_and_errors(
        self,
        *,
        history: ChartHistory,
        data_gaps: list[ChartDataGap],
        errors: list[str],
        candles: list[PriceCandle],
        now: datetime,
        cache_fallback: bool,
    ) -> tuple[list[ChartDataGap], list[str]]:
        if candles and cache_fallback:
            return data_gaps, []

        if candles and self._latest_candle_is_older_than_expected(history, candles, now):
            if not any(gap.category == "freshness" for gap in data_gaps):
                data_gaps.append(
                    ChartDataGap(
                        "freshness",
                        "The latest available candle is older than the conservative freshness window.",
                        "low",
                    )
                )
        return data_gaps, errors

    def _freshness(
        self,
        *,
        history: ChartHistory,
        candles: list[PriceCandle],
        now: datetime,
        data_gaps: list[ChartDataGap],
        errors: list[str],
        cache_fallback: bool,
        refresh_attempted: bool = True,
    ) -> ChartFreshness:
        if cache_fallback:
            return "stale"
        if candles and errors:
            return "partial"
        if candles and self._has_partial_gap(data_gaps):
            return "partial"
        if not candles:
            return "stale"
        if self._latest_candle_is_older_than_expected(history, candles, now):
            return "latest_available"

        fetched_at = history.fetched_at
        if fetched_at is not None and self._utc_date(fetched_at) == self._utc_date(now):
            return "current"
        if not refresh_attempted:
            return "stale"
        return "latest_available"

    def _delay_status(
        self,
        source: str | None,
        raw_delay_status: str | None,
        *,
        cache_fallback: bool,
        cache_only: bool = False,
    ) -> ChartDelayStatus:
        if cache_fallback or cache_only:
            return "cached"

        source_text = str(source or "").lower()
        delay_text = str(raw_delay_status or "").lower()
        if "moex" in source_text or "iss" in delay_text or "delayed" in delay_text:
            return "moex_delayed"
        if "cache" in source_text or "cached" in delay_text:
            return "cached"
        return "broker_api"

    def _status_source(self, source: str | None, *, cache_fallback: bool) -> str:
        if cache_fallback:
            return "local cache"
        source_text = str(source or "").strip()
        if source_text == DATA_SOURCE_T_INVEST:
            return "T-Invest"
        if source_text == DATA_SOURCE_MOEX_ISS:
            return "MOEX ISS"
        return source_text or "unknown"

    def _coerce_freshness(self, value: str | None) -> ChartFreshness:
        normalized = str(value or "").strip()
        if normalized in {"current", "latest_available", "stale", "partial"}:
            return normalized  # type: ignore[return-value]
        return "latest_available"

    def _coerce_delay_status(self, value: str | None) -> ChartDelayStatus:
        normalized = str(value or "").strip()
        if normalized in {"broker_api", "moex_delayed", "cached"}:
            return normalized  # type: ignore[return-value]
        return self._delay_status(None, normalized, cache_fallback=False)

    def _has_partial_gap(self, data_gaps: list[ChartDataGap]) -> bool:
        for gap in data_gaps:
            text = f"{gap.category} {gap.description}".lower()
            if "invalid" in text or "skipped" in text:
                return True
        return False

    def _latest_candle_is_older_than_expected(
        self,
        history: ChartHistory,
        candles: list[PriceCandle],
        now: datetime,
    ) -> bool:
        latest = self._latest_candle_at(candles)
        if latest is None:
            return False
        if history.interval == "hour" or history.range == "day":
            return self._as_utc_naive(latest) < self._as_utc_naive(now) - timedelta(days=1)
        return self._as_utc_naive(latest) < self._as_utc_naive(now) - timedelta(days=7)

    def _latest_candle_at(self, candles: list[PriceCandle]) -> datetime | None:
        if not candles:
            return None
        return max(candle.time for candle in candles)

    def _oldest_candle_at(self, candles: list[PriceCandle]) -> datetime | None:
        if not candles:
            return None
        return min(candle.time for candle in candles)

    def _utc_date(self, value: datetime) -> object:
        return self._as_utc_naive(value).date()

    def _as_utc_naive(self, value: datetime) -> datetime:
        if value.tzinfo is not None:
            return value.astimezone(timezone.utc).replace(tzinfo=None)
        return value
