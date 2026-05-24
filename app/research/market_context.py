from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Optional, Sequence

from app.data_sources.schemas import (
    DATA_SOURCE_MOEX_ISS,
    DELAY_STATUS_DELAYED_PUBLIC_ISS,
    FRESHNESS_DELAYED_PUBLIC_DATA,
)
from app.integrations.moex_iss import (
    MOEXISSClient,
    MOEX_SOURCE_NAME,
    configured_moex_index_tickers,
    normalize_moex_ticker,
    sanitize_error_message,
)
from app.research.schemas import AdapterResult, DataGap, SourceFreshness


MARKET_CONTEXT_SOURCE_NAME = DATA_SOURCE_MOEX_ISS
DEFAULT_MARKET_CONTEXT_PERIOD_DAYS = 31
DEFAULT_MARKET_CONTEXT_PERIOD_LABEL = "month"


@dataclass(frozen=True)
class MarketContextResult:
    payload: dict[str, Any]
    data_gaps: list[DataGap]
    errors: list[str]


class MarketContextService:
    """Read-only MOEX index context for research reports."""

    def __init__(
        self,
        *,
        client: Optional[MOEXISSClient] = None,
        index_tickers: Optional[Sequence[str]] = None,
        period_days: int = DEFAULT_MARKET_CONTEXT_PERIOD_DAYS,
        period_label: str = DEFAULT_MARKET_CONTEXT_PERIOD_LABEL,
        now_provider=None,
    ):
        self.now_provider = now_provider or datetime.utcnow
        self.client = client or MOEXISSClient(now_provider=self.now_provider)
        self.index_tickers = (
            _normalize_index_tickers(index_tickers)
            if index_tickers is not None
            else configured_moex_index_tickers()
        )
        self.period_days = _normalize_period_days(period_days)
        self.period_label = str(period_label or DEFAULT_MARKET_CONTEXT_PERIOD_LABEL).strip() or DEFAULT_MARKET_CONTEXT_PERIOD_LABEL

    def get_context(self) -> MarketContextResult:
        fetched_at = self.now_provider()
        from_date = fetched_at.date() - timedelta(days=self.period_days)
        till_date = fetched_at.date()
        gaps: list[DataGap] = []
        errors: list[str] = []
        indexes: list[dict[str, Any]] = []

        if not self.index_tickers:
            gap = DataGap("market_context", "No MOEX market context indexes are configured.", "low")
            gaps.append(gap)

        for ticker in self.index_tickers:
            index_payload, index_gaps, index_errors = self._fetch_index_context(
                ticker,
                from_date=from_date,
                till_date=till_date,
            )
            indexes.append(index_payload)
            gaps.extend(index_gaps)
            errors.extend(index_errors)

        as_of_date = _latest_as_of_date(indexes)
        payload = {
            "source": MOEX_SOURCE_NAME,
            "fetched_at": fetched_at,
            "as_of_date": as_of_date,
            "freshness": FRESHNESS_DELAYED_PUBLIC_DATA,
            "delay_status": DELAY_STATUS_DELAYED_PUBLIC_ISS,
            "period": self.period_label,
            "period_days": self.period_days,
            "indexes": indexes,
            "data_gaps": [_gap_payload(gap) for gap in gaps],
            "errors": list(errors),
        }
        return MarketContextResult(payload=payload, data_gaps=gaps, errors=errors)

    def _fetch_index_context(
        self,
        ticker: str,
        *,
        from_date,
        till_date,
    ) -> tuple[dict[str, Any], list[DataGap], list[str]]:
        gaps: list[DataGap] = []
        errors: list[str] = []
        payload = {
            "ticker": ticker,
            "latest_close": None,
            "recent_change_pct": None,
            "period": self.period_label,
            "period_days": self.period_days,
            "source": MOEX_SOURCE_NAME,
            "fetched_at": None,
            "as_of_date": None,
            "freshness": FRESHNESS_DELAYED_PUBLIC_DATA,
            "delay_status": DELAY_STATUS_DELAYED_PUBLIC_ISS,
            "data_gaps": [],
            "errors": [],
        }

        try:
            result = self.client.get_index_daily_candles_result(
                ticker,
                from_date=from_date,
                till_date=till_date,
            )
        except Exception as exc:
            gap = DataGap("market_context", f"MOEX index candles are unavailable for {ticker}.", "medium")
            error = f"MOEX ISS index candle lookup failed: {sanitize_error_message(exc)}"
            gaps.append(gap)
            errors.append(error)
            payload["data_gaps"] = [_gap_payload(gap)]
            payload["errors"] = [error]
            return payload, gaps, errors

        payload["source"] = result.source or MOEX_SOURCE_NAME
        payload["fetched_at"] = result.fetched_at
        gaps.extend(_map_moex_gaps(result.data_gaps))
        errors.extend(result.errors)

        candles = sorted(result.candles, key=lambda item: item.begin)
        if candles:
            first = candles[0]
            latest = candles[-1]
            payload["latest_close"] = latest.close
            payload["as_of_date"] = latest.trade_date.isoformat()
            if len(candles) >= 2 and first.close > 0:
                payload["recent_change_pct"] = ((latest.close - first.close) / first.close) * 100
            else:
                gaps.append(
                    DataGap(
                        "market_context",
                        f"Not enough MOEX index candles to calculate period change for {ticker}.",
                        "low",
                    )
                )
        elif not any(gap.category == "price_history" for gap in gaps):
            gaps.append(DataGap("price_history", f"No MOEX index candles were returned for {ticker}.", "low"))

        payload["data_gaps"] = [_gap_payload(gap) for gap in gaps]
        payload["errors"] = list(errors)
        return payload, gaps, errors


class MOEXMarketContextAdapter:
    """Research adapter that adds read-only MOEX index context to reports."""

    source_name = MARKET_CONTEXT_SOURCE_NAME

    def __init__(
        self,
        *,
        service: Optional[MarketContextService] = None,
        now_provider=None,
    ):
        self.now_provider = now_provider or datetime.utcnow
        self.service = service or MarketContextService(now_provider=self.now_provider)

    def fetch(self, ticker: str) -> AdapterResult:
        fetched_at = self.now_provider()
        normalized_ticker = normalize_moex_ticker(ticker)
        freshness = SourceFreshness(
            source_name=self.source_name,
            fetched_at=fetched_at,
            as_of_date=fetched_at.date().isoformat(),
            freshness=FRESHNESS_DELAYED_PUBLIC_DATA,
            delay_status=DELAY_STATUS_DELAYED_PUBLIC_ISS,
            notes="Read-only public MOEX ISS index context. No broker token is used.",
        )

        if not normalized_ticker:
            gap = DataGap("ticker", "Ticker is required and must use letters, numbers, or hyphen.", "high")
            return AdapterResult(
                source_name=self.source_name,
                data={"ticker": ""},
                freshness=freshness,
                gaps=[gap],
                errors=["Ticker is required and must use letters, numbers, or hyphen."],
            )

        context = self.service.get_context()
        as_of_date = context.payload.get("as_of_date")
        if isinstance(as_of_date, str) and as_of_date:
            freshness = SourceFreshness(
                source_name=self.source_name,
                fetched_at=fetched_at,
                as_of_date=as_of_date,
                freshness=FRESHNESS_DELAYED_PUBLIC_DATA,
                delay_status=DELAY_STATUS_DELAYED_PUBLIC_ISS,
                notes="Read-only public MOEX ISS index context. No broker token is used.",
            )

        return AdapterResult(
            source_name=self.source_name,
            data={"ticker": normalized_ticker, "market_context": context.payload},
            freshness=freshness,
            gaps=context.data_gaps,
            errors=context.errors,
        )


def _normalize_index_tickers(index_tickers: Sequence[str]) -> tuple[str, ...]:
    tickers: list[str] = []
    seen: set[str] = set()
    for ticker in index_tickers:
        normalized = normalize_moex_ticker(ticker)
        if not normalized or normalized in seen:
            continue
        tickers.append(normalized)
        seen.add(normalized)
    return tuple(tickers)


def _normalize_period_days(period_days: int) -> int:
    try:
        parsed = int(period_days)
    except (TypeError, ValueError):
        parsed = DEFAULT_MARKET_CONTEXT_PERIOD_DAYS
    return max(parsed, 1)


def _map_moex_gaps(gaps) -> list[DataGap]:
    result: list[DataGap] = []
    for gap in gaps:
        severity = str(getattr(gap, "severity", "medium") or "medium")
        if severity not in {"low", "medium", "high"}:
            severity = "medium"
        result.append(
            DataGap(
                category=str(getattr(gap, "category", "market_context") or "market_context"),
                description=str(getattr(gap, "description", "") or "MOEX market context data gap."),
                severity=severity,
            )
        )
    return result


def _gap_payload(gap: DataGap) -> dict[str, str]:
    return {
        "category": gap.category,
        "description": gap.description,
        "severity": gap.severity,
    }


def _latest_as_of_date(indexes: Sequence[dict[str, Any]]) -> Optional[str]:
    dates = [
        str(index.get("as_of_date"))
        for index in indexes
        if index.get("as_of_date")
    ]
    return max(dates) if dates else None
