from dataclasses import dataclass
from datetime import datetime
from typing import Callable, Optional, Protocol

from app.data_sources.schemas import (
    DATA_SOURCE_T_INVEST,
    DELAY_STATUS_BROKER_API,
    FRESHNESS_CURRENT_OR_LATEST,
)
from app.research.schemas import (
    AdapterResult,
    DataGap,
    InstrumentIdentity,
    MarketSnapshot,
    SourceFreshness,
)


DEFAULT_DIVIDEND_LOOKAHEAD_DAYS = 365


@dataclass(frozen=True)
class TokenContext:
    token: Optional[str]
    mode: str
    selected_env_var: str
    token_present: bool


class ReadOnlyTInvestBroker(Protocol):
    def resolve_unique_instrument(self, token: str, ticker: str):
        ...

    def get_price(self, token: str, figi: str, operation: str) -> float:
        ...

    def get_dividend_info(self, token: str, figi: str, period_days: int):
        ...


class TInvestDataAdapter:
    """Read-only research adapter backed by existing T-Invest lookup helpers."""

    source_name = DATA_SOURCE_T_INVEST

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
        data = {"ticker": self._normalize_ticker(ticker)}
        gaps: list[DataGap] = []
        errors: list[str] = []

        normalized_ticker = data["ticker"]
        if not normalized_ticker:
            freshness = self._build_freshness(fetched_at)
            gaps.append(DataGap("instrument_identity", "Ticker is required.", "high"))
            return AdapterResult(self.source_name, data=data, freshness=freshness, gaps=gaps, errors=errors)

        token_context = self._get_token_context()
        freshness = self._build_freshness(fetched_at, token_context)
        if not token_context.token:
            errors.append(
                f"No T-Invest token is configured for {token_context.mode} mode; "
                f"selected {token_context.selected_env_var}."
            )
            gaps.extend(
                [
                    DataGap(
                        "instrument_identity",
                        f"T-Invest token is unavailable from {token_context.selected_env_var}.",
                        "high",
                    ),
                    DataGap("market_snapshot", "Current price requires a resolved instrument.", "medium"),
                    DataGap("dividends", "Dividend lookup requires a resolved instrument.", "medium"),
                ]
            )
            return AdapterResult(self.source_name, data=data, freshness=freshness, gaps=gaps, errors=errors)

        broker = self._get_broker()
        identity = self._fetch_identity(broker, token_context, normalized_ticker, gaps, errors)
        if identity is None:
            gaps.extend(
                [
                    DataGap("market_snapshot", "Current price requires a resolved instrument.", "medium"),
                    DataGap("dividends", "Dividend lookup requires a resolved instrument.", "medium"),
                ]
            )
            return AdapterResult(self.source_name, data=data, freshness=freshness, gaps=gaps, errors=errors)

        data["instrument_identity"] = identity
        self._fetch_market_snapshot(broker, token_context, identity, fetched_at, data, gaps, errors)
        self._fetch_dividends(broker, token_context, identity, data, gaps, errors)
        return AdapterResult(self.source_name, data=data, freshness=freshness, gaps=gaps, errors=errors)

    def _fetch_identity(
        self,
        broker: ReadOnlyTInvestBroker,
        token_context: TokenContext,
        ticker: str,
        gaps: list[DataGap],
        errors: list[str],
    ) -> Optional[InstrumentIdentity]:
        try:
            instrument = broker.resolve_unique_instrument(token_context.token, ticker)
            identity = InstrumentIdentity(
                ticker=str(getattr(instrument, "ticker", ticker) or ticker).upper(),
                figi=getattr(instrument, "figi", None),
                name=getattr(instrument, "name", None),
            )
            if not identity.figi:
                gaps.append(DataGap("instrument_identity", "Instrument FIGI is unavailable.", "medium"))
            return identity
        except Exception as exc:
            errors.append(self._format_lookup_error("Instrument identity lookup", exc, token_context))
            gaps.append(DataGap("instrument_identity", f"Could not resolve ticker {ticker}.", "high"))
            return None

    def _fetch_market_snapshot(
        self,
        broker: ReadOnlyTInvestBroker,
        token_context: TokenContext,
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
            current_price = broker.get_price(token_context.token, identity.figi, "buy")
            data["market_snapshot"] = MarketSnapshot(
                current_price=current_price,
                currency=identity.currency,
                captured_at=captured_at,
            )
        except Exception as exc:
            errors.append(self._format_lookup_error("Market snapshot lookup", exc, token_context))
            gaps.append(DataGap("market_snapshot", "Current market price is unavailable.", "medium"))

    def _fetch_dividends(
        self,
        broker: ReadOnlyTInvestBroker,
        token_context: TokenContext,
        identity: InstrumentIdentity,
        data: dict,
        gaps: list[DataGap],
        errors: list[str],
    ) -> None:
        if not identity.figi:
            gaps.append(DataGap("dividends", "Dividend lookup requires FIGI.", "medium"))
            return

        try:
            dividend = broker.get_dividend_info(
                token_context.token,
                identity.figi,
                self.dividend_lookahead_days,
            )
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
            errors.append(self._format_lookup_error("Dividend lookup", exc, token_context))
            gaps.append(DataGap("dividends", "Dividend data is unavailable.", "low"))

    def _get_broker(self) -> ReadOnlyTInvestBroker:
        if self.broker is not None:
            return self.broker

        from app.integrations.tinvest import TInvestBroker

        self.broker = TInvestBroker()
        return self.broker

    def _get_token_context(self) -> TokenContext:
        if self.token_provider is not None:
            from app.client.config import is_placeholder_value

            raw_token = self.token_provider()
            token = self._clean_token(raw_token)
            token_present = bool(token) and not is_placeholder_value(raw_token)
            return TokenContext(
                token=token if token_present else None,
                mode="custom",
                selected_env_var="custom token provider",
                token_present=token_present,
            )

        from app.client.config import get_invest_mode, get_tokens, is_placeholder_value

        mode = get_invest_mode()
        tokens = get_tokens()
        token_key = "sandbox_token" if mode == "sandbox" else "token"
        selected_env_var = "SANDBOX_TOKEN" if mode == "sandbox" else "TOKEN"
        raw_token = tokens.get(token_key)
        token = self._clean_token(raw_token)
        token_present = bool(token) and not is_placeholder_value(raw_token)

        return TokenContext(
            token=token if token_present else None,
            mode=mode,
            selected_env_var=selected_env_var,
            token_present=token_present,
        )

    def _normalize_ticker(self, ticker: str) -> str:
        normalized = str(ticker or "").strip().upper()
        return normalized if normalized.replace("-", "").isalnum() else ""

    def _clean_token(self, token: Optional[str]) -> str:
        return "" if token is None else str(token).strip().strip('"').strip("'")

    def _build_freshness(
        self,
        fetched_at: datetime,
        token_context: Optional[TokenContext] = None,
    ) -> SourceFreshness:
        notes = "Read-only T-Invest research snapshot."
        if token_context is not None:
            token_state = "present" if token_context.token_present else "missing"
            notes = (
                f"{notes} Mode: {token_context.mode}; "
                f"selected token variable: {token_context.selected_env_var}; "
                f"token is {token_state}."
            )

        return SourceFreshness(
            source_name=self.source_name,
            fetched_at=fetched_at,
            as_of_date=fetched_at.date().isoformat(),
            freshness=FRESHNESS_CURRENT_OR_LATEST,
            delay_status=DELAY_STATUS_BROKER_API,
            notes=notes,
        )

    def _format_lookup_error(self, label: str, exc: Exception, token_context: TokenContext) -> str:
        if self._is_auth_error(exc):
            return (
                f"{label} failed: selected {token_context.selected_env_var} appears invalid "
                f"for {token_context.mode} mode."
            )
        message = str(exc)
        if token_context.token:
            message = message.replace(token_context.token, "[redacted]")
        return f"{label} failed: {message}"

    def _is_auth_error(self, exc: Exception) -> bool:
        parts = [str(exc)]
        parts.extend(str(arg) for arg in getattr(exc, "args", ()))
        text = " ".join(parts).lower()
        return (
            "unauthenticated" in text
            or "40003" in text
            or "authentication token is missing or invalid" in text
        )
