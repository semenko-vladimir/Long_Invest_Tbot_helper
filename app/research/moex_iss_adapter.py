from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from app.data_sources.schemas import (
    DATA_SOURCE_MOEX_ISS,
    DELAY_STATUS_DELAYED_PUBLIC_ISS,
    FRESHNESS_DELAYED_PUBLIC_DATA,
)
from app.integrations.moex_iss import (
    MOEXDataGap,
    MOEXISSClient,
    MOEXMarketData,
    MOEXSecurityMetadata,
    normalize_moex_ticker,
    sanitize_error_message,
)
from app.research.schemas import AdapterResult, DataGap, InstrumentIdentity, SourceFreshness


class MOEXISSResearchAdapter:
    """Read-only research adapter for delayed public MOEX ISS reference data."""

    source_name = DATA_SOURCE_MOEX_ISS

    def __init__(self, client: Optional[MOEXISSClient] = None, now_provider=None):
        self.now_provider = now_provider or datetime.utcnow
        self.client = client or MOEXISSClient(now_provider=self.now_provider)

    def fetch(self, ticker: str) -> AdapterResult:
        fetched_at = self.now_provider()
        normalized_ticker = normalize_moex_ticker(ticker)
        data: dict[str, Any] = {"ticker": normalized_ticker}
        gaps: list[DataGap] = []
        errors: list[str] = []
        freshness = self._freshness(fetched_at)

        if not normalized_ticker:
            gaps.append(DataGap("ticker", "Ticker is required and must use letters, numbers, or hyphen.", "high"))
            return AdapterResult(self.source_name, data=data, freshness=freshness, gaps=gaps, errors=errors)

        metadata = self._fetch_metadata(normalized_ticker, gaps, errors)
        market_data = self._fetch_market_data(normalized_ticker, gaps, errors)

        as_of_date = self._best_as_of_date(metadata, market_data, fetched_at)
        freshness = self._freshness(fetched_at, as_of_date=as_of_date)

        exchange_reference: dict[str, Any] = {
            "source": self.source_name,
            "fetched_at": fetched_at.isoformat(),
            "as_of_date": as_of_date,
            "freshness": FRESHNESS_DELAYED_PUBLIC_DATA,
            "delay_status": DELAY_STATUS_DELAYED_PUBLIC_ISS,
            "instrument": None,
            "latest_public_market_data": None,
        }

        if metadata is not None and (metadata.secid or metadata.name or metadata.short_name):
            data["instrument_identity"] = InstrumentIdentity(
                ticker=metadata.secid or normalized_ticker,
                figi=None,
                name=metadata.name or metadata.short_name,
                exchange="MOEX",
                currency=metadata.currency or (market_data.currency if market_data is not None else None),
            )
            exchange_reference["instrument"] = _metadata_payload(metadata)

        if market_data is not None and any(
            value is not None for value in (market_data.trade_date, market_data.close, market_data.last)
        ):
            exchange_reference["latest_public_market_data"] = _market_data_payload(market_data)

        if exchange_reference["instrument"] is not None or exchange_reference["latest_public_market_data"] is not None:
            data["exchange_reference"] = exchange_reference

        return AdapterResult(
            source_name=self.source_name,
            data=data,
            freshness=freshness,
            gaps=gaps,
            errors=errors,
        )

    def _fetch_metadata(
        self,
        ticker: str,
        gaps: list[DataGap],
        errors: list[str],
    ) -> Optional[MOEXSecurityMetadata]:
        try:
            metadata = self.client.get_security_metadata(ticker)
        except Exception as exc:
            gaps.append(DataGap("instrument_identity", f"MOEX ISS metadata is unavailable for {ticker}.", "medium"))
            errors.append(f"MOEX ISS metadata lookup failed: {sanitize_error_message(exc)}")
            return None

        gaps.extend(_research_gaps(metadata.data_gaps))
        errors.extend(metadata.errors)
        return metadata

    def _fetch_market_data(
        self,
        ticker: str,
        gaps: list[DataGap],
        errors: list[str],
    ) -> Optional[MOEXMarketData]:
        try:
            market_data = self.client.get_market_data(ticker)
        except Exception as exc:
            gaps.append(DataGap("market_data", f"MOEX ISS market data is unavailable for {ticker}.", "medium"))
            errors.append(f"MOEX ISS market data lookup failed: {sanitize_error_message(exc)}")
            return None

        gaps.extend(_research_gaps(market_data.data_gaps))
        errors.extend(market_data.errors)
        return market_data

    def _freshness(self, fetched_at: datetime, as_of_date: Optional[str] = None) -> SourceFreshness:
        return SourceFreshness(
            source_name=self.source_name,
            fetched_at=fetched_at,
            as_of_date=as_of_date or fetched_at.date().isoformat(),
            freshness=FRESHNESS_DELAYED_PUBLIC_DATA,
            delay_status=DELAY_STATUS_DELAYED_PUBLIC_ISS,
            notes="Read-only delayed public MOEX ISS reference data. No broker token is used.",
        )

    def _best_as_of_date(
        self,
        metadata: Optional[MOEXSecurityMetadata],
        market_data: Optional[MOEXMarketData],
        fetched_at: datetime,
    ) -> str:
        return (
            (market_data.as_of_date if market_data is not None else None)
            or (metadata.as_of_date if metadata is not None else None)
            or fetched_at.date().isoformat()
        )


def _research_gaps(gaps: list[MOEXDataGap]) -> list[DataGap]:
    return [DataGap(gap.category, gap.description, gap.severity) for gap in gaps]


def _metadata_payload(metadata: MOEXSecurityMetadata) -> dict[str, Any]:
    return {
        "ticker": metadata.ticker,
        "secid": metadata.secid,
        "name": metadata.name,
        "short_name": metadata.short_name,
        "isin": metadata.isin,
        "board": metadata.board,
        "engine": metadata.engine,
        "market": metadata.market,
        "currency": metadata.currency,
        "lot_size": metadata.lot_size,
        "security_type": metadata.security_type,
        "group": metadata.group,
        "source": metadata.source,
        "fetched_at": metadata.fetched_at.isoformat(),
        "as_of_date": metadata.as_of_date,
        "freshness": metadata.freshness,
        "delay_status": metadata.delay_status,
    }


def _market_data_payload(market_data: MOEXMarketData) -> dict[str, Any]:
    return {
        "ticker": market_data.ticker,
        "board": market_data.board,
        "trade_date": market_data.trade_date.isoformat() if market_data.trade_date else None,
        "open": market_data.open,
        "high": market_data.high,
        "low": market_data.low,
        "close": market_data.close,
        "last": market_data.last,
        "volume": market_data.volume,
        "value": market_data.value,
        "currency": market_data.currency,
        "source": market_data.source,
        "fetched_at": market_data.fetched_at.isoformat(),
        "as_of_date": market_data.as_of_date,
        "freshness": market_data.freshness,
        "delay_status": market_data.delay_status,
    }
