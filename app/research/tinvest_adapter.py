from datetime import datetime
from typing import Callable, Optional, Protocol

from app.research.schemas import (
    AdapterResult,
    DataGap,
    InstrumentIdentity,
    MarketSnapshot,
    SourceFreshness,
)


DEFAULT_DIVIDEND_LOOKAHEAD_DAYS = 365


class ReadOnlyTInvestBroker(Protocol):
    def resolve_unique_instrument(self, token: str, ticker: str):
        ...

    def get_price(self, token: str, figi: str, operation: str) -> float:
        ...

    def get_dividend_info(self, token: str, figi: str, period_days: int):
        ...


class TInvestDataAdapter:
    """Read-only research adapter backed by existing T-Invest lookup helpers."""

    source_name = "t-invest"

    def __init__(
        self,
        broker: Optional[ReadOnlyTInvestBroker] = None,
        token_provider: Optional[Callable[[], Optional[str]]] = None,
        now_provider: Optional[Callable[[], datetime]] = None,
        dividend_lookahead_days: int = DEFAULT_DIVIDEND_LOOKAHEAD_DAYS,
    ):
        self.broker = broker
        self.token_provider = token_provider
        self.now_provider = now_provider or datetime.utcnow
        self.dividend_lookahead_days = dividend_lookahead_days

    def fetch(self, ticker: str) -> AdapterResult:
        fetched_at = self.now_provider()
        freshness = SourceFreshness(
            source_name=self.source_name,
            fetched_at=fetched_at,
            as_of_date=fetched_at.date().isoformat(),
            notes="Read-only T-Invest research snapshot.",
        )
        data = {"ticker": self._normalize_ticker(ticker)}
        gaps: list[DataGap] = []
        errors: list[str] = []

        normalized_ticker = data["ticker"]
        if not normalized_ticker:
            gaps.append(DataGap("instrument_identity", "Ticker is required.", "high"))
            return AdapterResult(self.source_name, data=data, freshness=freshness, gaps=gaps, errors=errors)

        token = self._get_token()
        if not token:
            errors.append("No broker token is configured for the current mode.")
            gaps.extend(
                [
                    DataGap("instrument_identity", "T-Invest token is unavailable.", "high"),
                    DataGap("market_snapshot", "Current price requires a resolved instrument.", "medium"),
                    DataGap("dividends", "Dividend lookup requires a resolved instrument.", "medium"),
                ]
            )
            return AdapterResult(self.source_name, data=data, freshness=freshness, gaps=gaps, errors=errors)

        broker = self._get_broker()
        identity = self._fetch_identity(broker, token, normalized_ticker, gaps, errors)
        if identity is None:
            gaps.extend(
                [
                    DataGap("market_snapshot", "Current price requires a resolved instrument.", "medium"),
                    DataGap("dividends", "Dividend lookup requires a resolved instrument.", "medium"),
                ]
            )
            return AdapterResult(self.source_name, data=data, freshness=freshness, gaps=gaps, errors=errors)

        data["instrument_identity"] = identity
        self._fetch_market_snapshot(broker, token, identity, fetched_at, data, gaps, errors)
        self._fetch_dividends(broker, token, identity, data, gaps, errors)
        return AdapterResult(self.source_name, data=data, freshness=freshness, gaps=gaps, errors=errors)

    def _fetch_identity(
        self,
        broker: ReadOnlyTInvestBroker,
        token: str,
        ticker: str,
        gaps: list[DataGap],
        errors: list[str],
    ) -> Optional[InstrumentIdentity]:
        try:
            instrument = broker.resolve_unique_instrument(token, ticker)
            identity = InstrumentIdentity(
                ticker=str(getattr(instrument, "ticker", ticker) or ticker).upper(),
                figi=getattr(instrument, "figi", None),
                name=getattr(instrument, "name", None),
            )
            if not identity.figi:
                gaps.append(DataGap("instrument_identity", "Instrument FIGI is unavailable.", "medium"))
            return identity
        except Exception as exc:
            errors.append(f"Instrument identity lookup failed: {str(exc)}")
            gaps.append(DataGap("instrument_identity", f"Could not resolve ticker {ticker}.", "high"))
            return None

    def _fetch_market_snapshot(
        self,
        broker: ReadOnlyTInvestBroker,
        token: str,
        identity: InstrumentIdentity,
        captured_at: datetime,
        data: dict,
        gaps: list[DataGap],
        errors: list[str],
    ) -> None:
        if not identity.figi:
            gaps.append(DataGap("market_snapshot", "Current price requires FIGI.", "medium"))
            return

        try:
            current_price = broker.get_price(token, identity.figi, "buy")
            data["market_snapshot"] = MarketSnapshot(
                current_price=current_price,
                currency=identity.currency,
                captured_at=captured_at,
            )
        except Exception as exc:
            errors.append(f"Market snapshot lookup failed: {str(exc)}")
            gaps.append(DataGap("market_snapshot", "Current market price is unavailable.", "medium"))

    def _fetch_dividends(
        self,
        broker: ReadOnlyTInvestBroker,
        token: str,
        identity: InstrumentIdentity,
        data: dict,
        gaps: list[DataGap],
        errors: list[str],
    ) -> None:
        if not identity.figi:
            gaps.append(DataGap("dividends", "Dividend lookup requires FIGI.", "medium"))
            return

        try:
            dividend = broker.get_dividend_info(token, identity.figi, self.dividend_lookahead_days)
            if dividend is None:
                gaps.append(DataGap("dividends", "No dividend data returned for the selected period.", "low"))
                return

            data["dividends"] = {
                "dividend_net": getattr(dividend, "dividend_net", ""),
                "payment_date": getattr(dividend, "payment_date", ""),
                "declared_date": getattr(dividend, "declared_date", ""),
                "last_buy_date": getattr(dividend, "last_buy_date", ""),
                "record_date": getattr(dividend, "record_date", ""),
                "yield_value": getattr(dividend, "yield_value", ""),
            }
        except Exception as exc:
            errors.append(f"Dividend lookup failed: {str(exc)}")
            gaps.append(DataGap("dividends", "Dividend data is unavailable.", "low"))

    def _get_broker(self) -> ReadOnlyTInvestBroker:
        if self.broker is not None:
            return self.broker

        from app.integrations.tinvest import TInvestBroker

        self.broker = TInvestBroker()
        return self.broker

    def _get_token(self) -> Optional[str]:
        if self.token_provider is not None:
            return self.token_provider()

        from app.client.config import get_active_invest_token

        return get_active_invest_token()

    def _normalize_ticker(self, ticker: str) -> str:
        normalized = str(ticker or "").strip().upper()
        return normalized if normalized.replace("-", "").isalnum() else ""
