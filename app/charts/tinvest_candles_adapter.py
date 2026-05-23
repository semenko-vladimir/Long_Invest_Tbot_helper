from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Callable, Optional, Protocol

from tinkoff.invest import CandleInterval, Client

from app.charts.schemas import ChartAdapterResult, ChartDataGap, ChartRange, PriceCandle
from app.client.utils.helpers import cast_money


@dataclass(frozen=True)
class ChartTokenContext:
    token: Optional[str]
    mode: str
    selected_env_var: str
    token_present: bool


@dataclass(frozen=True)
class CandleRangeSpec:
    days: int
    interval: CandleInterval


class ReadOnlyInstrumentResolver(Protocol):
    def resolve_unique_instrument(self, token: str, ticker: str):
        ...


class TInvestCandlesAdapter:
    """Read-only T-Invest candle adapter for chart data."""

    source_name = "t-invest-candles"

    def __init__(
        self,
        broker: Optional[ReadOnlyInstrumentResolver] = None,
        token_provider: Optional[Callable[[], Optional[str]]] = None,
        now_provider: Optional[Callable[[], datetime]] = None,
    ):
        self.broker = broker
        self.token_provider = token_provider
        self.now_provider = now_provider or (lambda: datetime.now(timezone.utc))

    def fetch_candles(self, ticker: str, range_name: ChartRange) -> ChartAdapterResult:
        fetched_at = self.now_provider()
        normalized_ticker = self._normalize_ticker(ticker)
        gaps: list[ChartDataGap] = []
        errors: list[str] = []

        if not normalized_ticker:
            gaps.append(ChartDataGap("ticker", "Ticker is required.", "high"))
            return ChartAdapterResult(
                self.source_name,
                ticker=normalized_ticker,
                fetched_at=fetched_at,
                data_gaps=gaps,
                errors=errors,
            )

        token_context = self._get_token_context()
        if not token_context.token:
            errors.append(
                f"No T-Invest token is configured for {token_context.mode} mode; "
                f"selected {token_context.selected_env_var}."
            )
            gaps.append(
                ChartDataGap(
                    "authentication",
                    f"T-Invest token is unavailable from {token_context.selected_env_var}.",
                    "high",
                )
            )
            gaps.append(ChartDataGap("price_history", "Candles require a resolved instrument and token.", "medium"))
            return ChartAdapterResult(
                self.source_name,
                ticker=normalized_ticker,
                fetched_at=fetched_at,
                data_gaps=gaps,
                errors=errors,
            )

        broker = self._get_broker()
        try:
            instrument = broker.resolve_unique_instrument(token_context.token, normalized_ticker)
        except Exception as exc:
            errors.append(self._format_lookup_error("Instrument identity lookup", exc, token_context))
            gaps.append(ChartDataGap("instrument_identity", f"Could not resolve ticker {normalized_ticker}.", "high"))
            gaps.append(ChartDataGap("price_history", "Candles require a resolved instrument.", "medium"))
            return ChartAdapterResult(
                self.source_name,
                ticker=normalized_ticker,
                fetched_at=fetched_at,
                data_gaps=gaps,
                errors=errors,
            )

        figi = str(getattr(instrument, "figi", "") or "")
        resolved_ticker = str(getattr(instrument, "ticker", normalized_ticker) or normalized_ticker).upper()
        if not figi:
            gaps.append(ChartDataGap("instrument_identity", "Instrument FIGI is unavailable.", "high"))
            gaps.append(ChartDataGap("price_history", "Candles require FIGI.", "medium"))
            return ChartAdapterResult(
                self.source_name,
                ticker=resolved_ticker,
                fetched_at=fetched_at,
                data_gaps=gaps,
                errors=errors,
            )

        try:
            candles = self._fetch_tinvest_candles(token_context.token, figi, range_name)
        except Exception as exc:
            errors.append(self._format_lookup_error("Candle lookup", exc, token_context))
            gaps.append(ChartDataGap("price_history", "Historical candles are unavailable.", "medium"))
            return ChartAdapterResult(
                self.source_name,
                ticker=resolved_ticker,
                figi=figi,
                fetched_at=fetched_at,
                data_gaps=gaps,
                errors=errors,
            )

        return ChartAdapterResult(
            self.source_name,
            ticker=resolved_ticker,
            figi=figi,
            fetched_at=fetched_at,
            candles=candles,
            data_gaps=gaps,
            errors=errors,
        )

    def _fetch_tinvest_candles(self, token: str, figi: str, range_name: ChartRange) -> list[PriceCandle]:
        spec = candle_range_spec(range_name)
        to_time = self.now_provider()
        if to_time.tzinfo is None:
            to_time = to_time.replace(tzinfo=timezone.utc)
        from_time = to_time - timedelta(days=spec.days)

        with Client(token) as client:
            response = client.market_data.get_candles(
                figi=figi,
                from_=from_time,
                to=to_time,
                interval=spec.interval,
            )

        candles = [candle for candle in (self._map_candle(raw) for raw in response.candles) if candle is not None]
        return sorted(candles, key=lambda candle: candle.time)

    def _map_candle(self, raw_candle) -> Optional[PriceCandle]:
        candle_time = getattr(raw_candle, "time", None)
        if not isinstance(candle_time, datetime):
            return None

        try:
            open_price = cast_money(getattr(raw_candle, "open"))
            high_price = cast_money(getattr(raw_candle, "high"))
            low_price = cast_money(getattr(raw_candle, "low"))
            close_price = cast_money(getattr(raw_candle, "close"))
        except Exception:
            return None

        if any(value <= 0 for value in (open_price, high_price, low_price, close_price)):
            return None

        raw_volume = getattr(raw_candle, "volume", None)
        try:
            volume = int(raw_volume) if raw_volume is not None else None
        except (TypeError, ValueError):
            volume = None

        return PriceCandle(
            time=candle_time,
            open=open_price,
            high=high_price,
            low=low_price,
            close=close_price,
            volume=volume,
        )

    def _get_broker(self) -> ReadOnlyInstrumentResolver:
        if self.broker is not None:
            return self.broker

        from app.integrations.tinvest import TInvestBroker

        self.broker = TInvestBroker()
        return self.broker

    def _get_token_context(self) -> ChartTokenContext:
        if self.token_provider is not None:
            from app.client.config import is_placeholder_value

            raw_token = self.token_provider()
            token = self._clean_token(raw_token)
            token_present = bool(token) and not is_placeholder_value(raw_token)
            return ChartTokenContext(
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

        return ChartTokenContext(
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

    def _format_lookup_error(self, label: str, exc: Exception, token_context: ChartTokenContext) -> str:
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


def candle_range_spec(range_name: ChartRange) -> CandleRangeSpec:
    hour_interval = getattr(CandleInterval, "CANDLE_INTERVAL_HOUR", CandleInterval.CANDLE_INTERVAL_DAY)
    specs = {
        "day": CandleRangeSpec(days=1, interval=hour_interval),
        "week": CandleRangeSpec(days=7, interval=CandleInterval.CANDLE_INTERVAL_DAY),
        "month": CandleRangeSpec(days=31, interval=CandleInterval.CANDLE_INTERVAL_DAY),
        "six_months": CandleRangeSpec(days=183, interval=CandleInterval.CANDLE_INTERVAL_DAY),
        "year": CandleRangeSpec(days=366, interval=CandleInterval.CANDLE_INTERVAL_DAY),
        "all": CandleRangeSpec(days=3650, interval=CandleInterval.CANDLE_INTERVAL_DAY),
    }
    return specs[range_name]
