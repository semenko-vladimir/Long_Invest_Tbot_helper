import re
from dataclasses import dataclass
from typing import Optional


_SYMBOL_RE = re.compile(r"^[A-Z0-9_-]{1,32}$")
_SUPPORTED_CANDLE_INTERVALS = {"1d"}
_SUPPORTED_CBR_METRICS = {"key_rate", "usd_rub", "cny_rub"}
_SUPPORTED_ISSUER_DETAILS = {"profile", "dividends"}


class TopicValidationError(ValueError):
    """Raised when a DataHubLite topic cannot be parsed safely."""


@dataclass(frozen=True)
class DataHubTopic:
    raw: str
    normalized: str
    namespace: str
    group: str
    parts: tuple[str, ...]
    ticker: Optional[str] = None
    interval: Optional[str] = None
    provider: Optional[str] = None
    metric: Optional[str] = None
    scope: Optional[str] = None
    detail: Optional[str] = None


def parse_topic(value: str) -> DataHubTopic:
    raw = str(value or "").strip()
    if not raw:
        raise TopicValidationError("DataHub topic is required.")

    segments = raw.split(":")
    if any(not segment for segment in segments):
        raise TopicValidationError(f"Invalid DataHub topic shape: {raw}")
    if len(segments) < 2:
        raise TopicValidationError(f"Invalid DataHub topic shape: {raw}")

    namespace = segments[0].lower()
    group = segments[1].lower()
    parts = segments[2:]

    if namespace != "ru":
        raise TopicValidationError(f"Unsupported DataHub namespace: {segments[0]}")

    if group in {"instrument", "quote"}:
        return _parse_single_ticker_topic(raw, namespace, group, parts)
    if group == "candles":
        return _parse_candles_topic(raw, namespace, group, parts)
    if group == "portfolio":
        return _parse_portfolio_topic(raw, namespace, group, parts)
    if group == "watchlist":
        return _parse_watchlist_topic(raw, namespace, group, parts)
    if group == "macro":
        return _parse_macro_topic(raw, namespace, group, parts)
    if group == "issuer":
        return _parse_issuer_topic(raw, namespace, group, parts)

    raise TopicValidationError(f"Unsupported DataHub topic group: {segments[1]}")


def _parse_single_ticker_topic(raw: str, namespace: str, group: str, parts: list[str]) -> DataHubTopic:
    if len(parts) != 1:
        raise TopicValidationError(f"{group} topics must use ru:{group}:{{ticker}}.")
    ticker = _normalize_symbol(parts[0], "ticker")
    normalized = f"{namespace}:{group}:{ticker}"
    return DataHubTopic(raw=raw, normalized=normalized, namespace=namespace, group=group, parts=(ticker,), ticker=ticker)


def _parse_candles_topic(raw: str, namespace: str, group: str, parts: list[str]) -> DataHubTopic:
    if len(parts) != 2:
        raise TopicValidationError("Candle topics must use ru:candles:{ticker}:1d.")
    ticker = _normalize_symbol(parts[0], "ticker")
    interval = parts[1].lower()
    if interval not in _SUPPORTED_CANDLE_INTERVALS:
        raise TopicValidationError(f"Unsupported candle interval: {parts[1]}")
    normalized = f"{namespace}:{group}:{ticker}:{interval}"
    return DataHubTopic(
        raw=raw,
        normalized=normalized,
        namespace=namespace,
        group=group,
        parts=(ticker, interval),
        ticker=ticker,
        interval=interval,
    )


def _parse_portfolio_topic(raw: str, namespace: str, group: str, parts: list[str]) -> DataHubTopic:
    if len(parts) != 2:
        raise TopicValidationError("Portfolio topics must use ru:portfolio:summary:default or ru:portfolio:position:{ticker}.")

    detail = parts[0].lower()
    if detail == "summary":
        scope = parts[1].lower()
        if scope != "default":
            raise TopicValidationError(f"Unsupported portfolio summary scope: {parts[1]}")
        normalized = f"{namespace}:{group}:{detail}:{scope}"
        return DataHubTopic(
            raw=raw,
            normalized=normalized,
            namespace=namespace,
            group=group,
            parts=(detail, scope),
            scope=scope,
            detail=detail,
        )

    if detail == "position":
        ticker = _normalize_symbol(parts[1], "ticker")
        normalized = f"{namespace}:{group}:{detail}:{ticker}"
        return DataHubTopic(
            raw=raw,
            normalized=normalized,
            namespace=namespace,
            group=group,
            parts=(detail, ticker),
            ticker=ticker,
            detail=detail,
        )

    raise TopicValidationError(f"Unsupported portfolio topic detail: {parts[0]}")


def _parse_watchlist_topic(raw: str, namespace: str, group: str, parts: list[str]) -> DataHubTopic:
    if len(parts) != 1:
        raise TopicValidationError("Watchlist topics must use ru:watchlist:default.")
    scope = parts[0].lower()
    if scope != "default":
        raise TopicValidationError(f"Unsupported watchlist scope: {parts[0]}")
    normalized = f"{namespace}:{group}:{scope}"
    return DataHubTopic(raw=raw, normalized=normalized, namespace=namespace, group=group, parts=(scope,), scope=scope)


def _parse_macro_topic(raw: str, namespace: str, group: str, parts: list[str]) -> DataHubTopic:
    if len(parts) == 2:
        provider = parts[0].lower()
        metric = parts[1].lower()
        if provider != "cbr":
            raise TopicValidationError(f"Unsupported macro provider: {parts[0]}")
        if metric not in _SUPPORTED_CBR_METRICS:
            raise TopicValidationError(f"Unsupported CBR macro metric: {parts[1]}")
        normalized = f"{namespace}:{group}:{provider}:{metric}"
        return DataHubTopic(
            raw=raw,
            normalized=normalized,
            namespace=namespace,
            group=group,
            parts=(provider, metric),
            provider=provider,
            metric=metric,
        )

    if len(parts) == 3:
        provider = parts[0].lower()
        metric = parts[1].lower()
        if provider != "moex":
            raise TopicValidationError(f"Unsupported macro provider: {parts[0]}")
        if metric != "index":
            raise TopicValidationError(f"Unsupported MOEX macro metric: {parts[1]}")
        ticker = _normalize_symbol(parts[2], "index")
        normalized = f"{namespace}:{group}:{provider}:{metric}:{ticker}"
        return DataHubTopic(
            raw=raw,
            normalized=normalized,
            namespace=namespace,
            group=group,
            parts=(provider, metric, ticker),
            ticker=ticker,
            provider=provider,
            metric=metric,
        )

    raise TopicValidationError("Macro topics must use ru:macro:cbr:{metric} or ru:macro:moex:index:{index}.")


def _parse_issuer_topic(raw: str, namespace: str, group: str, parts: list[str]) -> DataHubTopic:
    if len(parts) != 2:
        raise TopicValidationError("Issuer topics must use ru:issuer:{ticker}:profile or ru:issuer:{ticker}:dividends.")
    ticker = _normalize_symbol(parts[0], "ticker")
    detail = parts[1].lower()
    if detail not in _SUPPORTED_ISSUER_DETAILS:
        raise TopicValidationError(f"Unsupported issuer topic detail: {parts[1]}")
    normalized = f"{namespace}:{group}:{ticker}:{detail}"
    return DataHubTopic(
        raw=raw,
        normalized=normalized,
        namespace=namespace,
        group=group,
        parts=(ticker, detail),
        ticker=ticker,
        detail=detail,
    )


def _normalize_symbol(value: str, label: str) -> str:
    symbol = value.upper()
    if not _SYMBOL_RE.fullmatch(symbol):
        raise TopicValidationError(f"Invalid {label} in DataHub topic: {value}")
    return symbol
