from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any, Optional
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen

from app.data_sources.schemas import (
    DATA_SOURCE_MOEX_ISS,
    DELAY_STATUS_DELAYED_PUBLIC_ISS,
    FRESHNESS_DELAYED_PUBLIC_DATA,
)


MOEX_SOURCE_NAME = DATA_SOURCE_MOEX_ISS
MOEX_DISPLAY_NAME = "MOEX ISS"
MOEX_BASE_URL = "https://iss.moex.com/iss"
DEFAULT_ENGINE = "stock"
DEFAULT_MARKET = "shares"
DEFAULT_BOARD = "TQBR"
INDEX_MARKET = "index"
MOEX_MARKET_CONTEXT_INDEXES_ENV = "MOEX_MARKET_CONTEXT_INDEXES"
DEFAULT_MARKET_CONTEXT_INDEXES = ("IMOEX", "RTSI")
DEFAULT_TIMEOUT_SECONDS = 5.0
DEFAULT_MAX_PAGES = 100
USER_AGENT = "Tbot-v1 MOEX ISS read-only adapter"
SENSITIVE_ENV_PARTS = ("token", "secret", "password", "authorization", "api_key", "apikey")
SENSITIVE_ASSIGNMENT_RE = re.compile(
    r"(?i)\b(token|secret|password|authorization|api[_-]?key)\s*[:=]\s*[^\s;,&]+"
)
SENSITIVE_VALUE_RE = re.compile(r"(?i)\b[^\s;,&]*(?:secret|token|password|api[_-]?key)[^\s;,&]*\b")


@dataclass(frozen=True)
class MOEXDataGap:
    category: str
    description: str
    severity: str = "medium"


@dataclass(frozen=True)
class MOEXSecurityMetadata:
    ticker: str
    fetched_at: datetime
    source: str = MOEX_SOURCE_NAME
    as_of_date: Optional[str] = None
    freshness: str = FRESHNESS_DELAYED_PUBLIC_DATA
    delay_status: str = DELAY_STATUS_DELAYED_PUBLIC_ISS
    secid: Optional[str] = None
    name: Optional[str] = None
    short_name: Optional[str] = None
    isin: Optional[str] = None
    board: str = DEFAULT_BOARD
    engine: str = DEFAULT_ENGINE
    market: str = DEFAULT_MARKET
    currency: Optional[str] = None
    lot_size: Optional[int] = None
    security_type: Optional[str] = None
    group: Optional[str] = None
    data_gaps: list[MOEXDataGap] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class MOEXMarketData:
    ticker: str
    fetched_at: datetime
    source: str = MOEX_SOURCE_NAME
    as_of_date: Optional[str] = None
    freshness: str = FRESHNESS_DELAYED_PUBLIC_DATA
    delay_status: str = DELAY_STATUS_DELAYED_PUBLIC_ISS
    board: str = DEFAULT_BOARD
    trade_date: Optional[date] = None
    open: Optional[float] = None
    high: Optional[float] = None
    low: Optional[float] = None
    close: Optional[float] = None
    last: Optional[float] = None
    volume: Optional[int] = None
    value: Optional[float] = None
    currency: Optional[str] = None
    data_gaps: list[MOEXDataGap] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class MOEXDailyCandle:
    ticker: str
    begin: datetime
    end: Optional[datetime]
    trade_date: date
    open: float
    high: float
    low: float
    close: float
    fetched_at: datetime
    source: str = MOEX_SOURCE_NAME
    freshness: str = FRESHNESS_DELAYED_PUBLIC_DATA
    delay_status: str = DELAY_STATUS_DELAYED_PUBLIC_ISS
    volume: Optional[int] = None
    value: Optional[float] = None


@dataclass(frozen=True)
class MOEXDailyCandlesResult:
    ticker: str
    fetched_at: datetime
    source: str = MOEX_SOURCE_NAME
    as_of_date: Optional[str] = None
    freshness: str = FRESHNESS_DELAYED_PUBLIC_DATA
    delay_status: str = DELAY_STATUS_DELAYED_PUBLIC_ISS
    candles: list[MOEXDailyCandle] = field(default_factory=list)
    data_gaps: list[MOEXDataGap] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


class MOEXISSParseError(ValueError):
    """Raised when a MOEX ISS response cannot be parsed as expected."""


def normalize_moex_ticker(ticker: object) -> str:
    normalized = str(ticker or "").strip().upper()
    return normalized if normalized.replace("-", "").isalnum() else ""


def configured_moex_index_tickers(raw_value: Optional[str] = None) -> tuple[str, ...]:
    if raw_value is None:
        raw_value = os.getenv(MOEX_MARKET_CONTEXT_INDEXES_ENV)

    if raw_value is None or not str(raw_value).strip():
        return DEFAULT_MARKET_CONTEXT_INDEXES

    tickers: list[str] = []
    seen: set[str] = set()
    for part in re.split(r"[,;\s]+", str(raw_value)):
        normalized = normalize_moex_ticker(part)
        if not normalized or normalized in seen:
            continue
        tickers.append(normalized)
        seen.add(normalized)

    return tuple(tickers) or DEFAULT_MARKET_CONTEXT_INDEXES


class MOEXISSClient:
    """Small read-only client for public MOEX ISS JSON endpoints."""

    def __init__(
        self,
        *,
        base_url: str = MOEX_BASE_URL,
        engine: str = DEFAULT_ENGINE,
        market: str = DEFAULT_MARKET,
        board: str = DEFAULT_BOARD,
        timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
        max_pages: int = DEFAULT_MAX_PAGES,
        now_provider=None,
    ):
        self.base_url = str(base_url or MOEX_BASE_URL).rstrip("/")
        self.engine = str(engine or DEFAULT_ENGINE).strip() or DEFAULT_ENGINE
        self.market = str(market or DEFAULT_MARKET).strip() or DEFAULT_MARKET
        self.board = str(board or DEFAULT_BOARD).strip().upper() or DEFAULT_BOARD
        self.timeout_seconds = float(timeout_seconds)
        self.max_pages = max(int(max_pages), 1)
        self.now_provider = now_provider or datetime.utcnow

    def get_security_metadata(self, ticker: str) -> MOEXSecurityMetadata:
        return self._get_security_metadata(
            ticker,
            path_builder=lambda normalized_ticker: f"/securities/{quote(normalized_ticker, safe='')}.json",
            engine=self.engine,
            market=self.market,
            default_board=self.board,
        )

    def get_index_security_metadata(self, ticker: str) -> MOEXSecurityMetadata:
        return self._get_security_metadata(
            ticker,
            path_builder=self._index_security_path,
            engine=self.engine,
            market=INDEX_MARKET,
            default_board="",
        )

    def _get_security_metadata(
        self,
        ticker: str,
        *,
        path_builder,
        engine: str,
        market: str,
        default_board: str,
    ) -> MOEXSecurityMetadata:
        fetched_at = self.now_provider()
        normalized_ticker = self._normalize_ticker(ticker)
        gaps: list[MOEXDataGap] = []
        errors: list[str] = []

        if not normalized_ticker:
            gaps.append(MOEXDataGap("ticker", "Ticker is required and must use letters, numbers, or hyphen.", "high"))
            return MOEXSecurityMetadata(
                ticker="",
                fetched_at=fetched_at,
                as_of_date=fetched_at.date().isoformat(),
                board=default_board,
                data_gaps=gaps,
                errors=errors,
            )

        try:
            payload = self._get_json(path_builder(normalized_ticker))
            description_rows = iss_table_to_rows(payload, "description", required=False)
            security_rows = iss_table_to_rows(payload, "securities", required=False)
        except Exception as exc:
            gaps.append(MOEXDataGap("instrument_identity", f"MOEX ISS metadata is unavailable for {normalized_ticker}.", "medium"))
            errors.append(f"MOEX ISS metadata lookup failed: {sanitize_error_message(exc)}")
            return MOEXSecurityMetadata(
                ticker=normalized_ticker,
                fetched_at=fetched_at,
                as_of_date=fetched_at.date().isoformat(),
                board=default_board,
                engine=engine,
                market=market,
                data_gaps=gaps,
                errors=errors,
            )

        description = _description_values(description_rows)
        security = _first_matching_row(security_rows, normalized_ticker)
        if not description and security is None:
            gaps.append(MOEXDataGap("instrument_identity", f"MOEX ISS metadata was empty for {normalized_ticker}.", "low"))
            return MOEXSecurityMetadata(
                ticker=normalized_ticker,
                fetched_at=fetched_at,
                as_of_date=fetched_at.date().isoformat(),
                board=default_board,
                engine=engine,
                market=market,
                data_gaps=gaps,
                errors=errors,
            )

        board = _clean_string(
            _first_present(
                _row_value(security, "primary_boardid"),
                description.get("PRIMARY_BOARDID"),
                _row_value(security, "marketprice_boardid"),
                description.get("MARKETPRICE_BOARDID"),
            )
        ) or default_board
        currency = _normalize_currency(
            _first_present(
                _row_value(security, "faceunit"),
                _row_value(security, "currencyid"),
                description.get("FACEUNIT"),
                description.get("CURRENCYID"),
            )
        )

        return MOEXSecurityMetadata(
            ticker=normalized_ticker,
            fetched_at=fetched_at,
            as_of_date=fetched_at.date().isoformat(),
            secid=_clean_string(_first_present(_row_value(security, "secid"), description.get("SECID"), normalized_ticker)),
            name=_clean_string(_first_present(description.get("NAME"), _row_value(security, "name"), _row_value(security, "secname"))),
            short_name=_clean_string(_first_present(_row_value(security, "shortname"), description.get("SHORTNAME"))),
            isin=_clean_string(_first_present(_row_value(security, "isin"), description.get("ISIN"))),
            board=board,
            engine=engine,
            market=market,
            currency=currency,
            lot_size=_to_int(_first_present(_row_value(security, "lotsize"), description.get("LOTSIZE"))),
            security_type=_clean_string(_first_present(_row_value(security, "type"), description.get("TYPE"))),
            group=_clean_string(_first_present(_row_value(security, "group"), description.get("GROUP"))),
            data_gaps=gaps,
            errors=errors,
        )

    def get_market_data(self, ticker: str) -> MOEXMarketData:
        return self._get_market_data(
            ticker,
            path_builder=self._board_security_path,
            default_board=self.board,
        )

    def get_index_market_data(self, ticker: str) -> MOEXMarketData:
        return self._get_market_data(
            ticker,
            path_builder=self._index_security_path,
            default_board="",
        )

    def _get_market_data(self, ticker: str, *, path_builder, default_board: str) -> MOEXMarketData:
        fetched_at = self.now_provider()
        normalized_ticker = self._normalize_ticker(ticker)
        gaps: list[MOEXDataGap] = []
        errors: list[str] = []

        if not normalized_ticker:
            gaps.append(MOEXDataGap("ticker", "Ticker is required and must use letters, numbers, or hyphen.", "high"))
            return MOEXMarketData(
                ticker="",
                fetched_at=fetched_at,
                as_of_date=fetched_at.date().isoformat(),
                board=default_board,
                data_gaps=gaps,
                errors=errors,
            )

        try:
            payload = self._get_json(path_builder(normalized_ticker))
            security_rows = iss_table_to_rows(payload, "securities", required=False)
            market_rows = iss_table_to_rows(payload, "marketdata", required=False)
        except Exception as exc:
            gaps.append(MOEXDataGap("market_data", f"MOEX ISS market data is unavailable for {normalized_ticker}.", "medium"))
            errors.append(f"MOEX ISS market data lookup failed: {sanitize_error_message(exc)}")
            return MOEXMarketData(
                ticker=normalized_ticker,
                fetched_at=fetched_at,
                as_of_date=fetched_at.date().isoformat(),
                board=default_board,
                data_gaps=gaps,
                errors=errors,
            )

        security = _first_matching_row(security_rows, normalized_ticker)
        market_row = _first_matching_row(market_rows, normalized_ticker)
        if market_row is None:
            gaps.append(MOEXDataGap("market_data", f"MOEX ISS market data was empty for {normalized_ticker}.", "low"))
            return MOEXMarketData(
                ticker=normalized_ticker,
                fetched_at=fetched_at,
                as_of_date=fetched_at.date().isoformat(),
                board=default_board,
                data_gaps=gaps,
                errors=errors,
            )

        close_price = _first_float(market_row, "close", "closeprice", "marketprice", "last", "currentvalue", "lastvalue")
        trade_date = _first_date(market_row, "tradedate", "tradetime", "systime", "updatetime")
        currency = _normalize_currency(
            _first_present(
                _row_value(market_row, "currencyid"),
                _row_value(security, "currencyid"),
                _row_value(security, "faceunit"),
            )
        )

        return MOEXMarketData(
            ticker=normalized_ticker,
            fetched_at=fetched_at,
            as_of_date=trade_date.isoformat() if trade_date else fetched_at.date().isoformat(),
            board=_clean_string(_first_present(_row_value(market_row, "boardid"), _row_value(security, "boardid"))) or default_board,
            trade_date=trade_date,
            open=_first_float(market_row, "open", "openvalue"),
            high=_first_float(market_row, "high", "highvalue"),
            low=_first_float(market_row, "low", "lowvalue"),
            close=close_price,
            last=_first_float(market_row, "last", "currentvalue", "lastvalue"),
            volume=_first_int(market_row, "volume", "voltoday", "qty"),
            value=_first_float(market_row, "value", "valtoday"),
            currency=currency,
            data_gaps=gaps,
            errors=errors,
        )

    def get_daily_candles(
        self,
        ticker: str,
        from_date: Optional[date] = None,
        till_date: Optional[date] = None,
    ) -> list[MOEXDailyCandle]:
        return self.get_daily_candles_result(ticker, from_date=from_date, till_date=till_date).candles

    def get_index_daily_candles(
        self,
        ticker: str,
        from_date: Optional[date] = None,
        till_date: Optional[date] = None,
    ) -> list[MOEXDailyCandle]:
        return self.get_index_daily_candles_result(ticker, from_date=from_date, till_date=till_date).candles

    def get_daily_candles_result(
        self,
        ticker: str,
        from_date: Optional[date] = None,
        till_date: Optional[date] = None,
    ) -> MOEXDailyCandlesResult:
        return self._get_daily_candles_result(
            ticker,
            from_date=from_date,
            till_date=till_date,
            candles_path_builder=lambda normalized_ticker: f"{self._board_security_path(normalized_ticker)}/candles.json",
            unavailable_description="MOEX ISS daily candles are unavailable",
            empty_description="MOEX ISS returned no daily candles",
        )

    def get_index_daily_candles_result(
        self,
        ticker: str,
        from_date: Optional[date] = None,
        till_date: Optional[date] = None,
    ) -> MOEXDailyCandlesResult:
        return self._get_daily_candles_result(
            ticker,
            from_date=from_date,
            till_date=till_date,
            candles_path_builder=self._index_candles_path,
            unavailable_description="MOEX ISS daily index candles are unavailable",
            empty_description="MOEX ISS returned no daily index candles",
        )

    def _get_daily_candles_result(
        self,
        ticker: str,
        from_date: Optional[date] = None,
        till_date: Optional[date] = None,
        *,
        candles_path_builder,
        unavailable_description: str,
        empty_description: str,
    ) -> MOEXDailyCandlesResult:
        fetched_at = self.now_provider()
        normalized_ticker = self._normalize_ticker(ticker)
        gaps: list[MOEXDataGap] = []
        errors: list[str] = []

        if not normalized_ticker:
            gaps.append(MOEXDataGap("ticker", "Ticker is required and must use letters, numbers, or hyphen.", "high"))
            return MOEXDailyCandlesResult(
                ticker="",
                fetched_at=fetched_at,
                as_of_date=fetched_at.date().isoformat(),
                data_gaps=gaps,
                errors=errors,
            )

        params: dict[str, str] = {"interval": "24"}
        if from_date is not None:
            params["from"] = from_date.isoformat()
        if till_date is not None:
            params["till"] = till_date.isoformat()

        try:
            rows = self._get_paged_rows(
                candles_path_builder(normalized_ticker),
                table_name="candles",
                params=params,
            )
        except Exception as exc:
            gaps.append(MOEXDataGap("price_history", f"{unavailable_description} for {normalized_ticker}.", "medium"))
            errors.append(f"MOEX ISS candle lookup failed: {sanitize_error_message(exc)}")
            return MOEXDailyCandlesResult(
                ticker=normalized_ticker,
                fetched_at=fetched_at,
                as_of_date=fetched_at.date().isoformat(),
                data_gaps=gaps,
                errors=errors,
            )

        candles: list[MOEXDailyCandle] = []
        skipped_rows = 0
        for row in rows:
            candle = self._map_daily_candle(normalized_ticker, row, fetched_at)
            if candle is None:
                skipped_rows += 1
                continue
            candles.append(candle)

        if skipped_rows:
            gaps.append(
                MOEXDataGap(
                    "price_history",
                    f"Skipped {skipped_rows} MOEX ISS candle rows with missing or invalid OHLC data.",
                    "medium",
                )
            )

        candles = sorted(candles, key=lambda item: item.begin)
        if not candles:
            gaps.append(MOEXDataGap("price_history", f"{empty_description} for {normalized_ticker}.", "low"))

        return MOEXDailyCandlesResult(
            ticker=normalized_ticker,
            fetched_at=fetched_at,
            as_of_date=candles[-1].trade_date.isoformat() if candles else None,
            candles=candles,
            data_gaps=gaps,
            errors=errors,
        )

    def _map_daily_candle(
        self,
        ticker: str,
        row: dict[str, Any],
        fetched_at: datetime,
    ) -> Optional[MOEXDailyCandle]:
        begin = _parse_datetime(_row_value(row, "begin"))
        if begin is None:
            return None

        open_price = _to_float(_row_value(row, "open"))
        high_price = _to_float(_row_value(row, "high"))
        low_price = _to_float(_row_value(row, "low"))
        close_price = _to_float(_row_value(row, "close"))
        if any(value is None or value <= 0 for value in (open_price, high_price, low_price, close_price)):
            return None

        return MOEXDailyCandle(
            ticker=ticker,
            begin=begin,
            end=_parse_datetime(_row_value(row, "end")),
            trade_date=begin.date(),
            open=open_price,
            high=high_price,
            low=low_price,
            close=close_price,
            volume=_to_int(_row_value(row, "volume")),
            value=_to_float(_row_value(row, "value")),
            fetched_at=fetched_at,
        )

    def _get_paged_rows(
        self,
        path: str,
        *,
        table_name: str,
        params: Optional[dict[str, str]] = None,
    ) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        start = 0
        seen_starts: set[int] = set()

        for _ in range(self.max_pages):
            if start in seen_starts:
                break
            seen_starts.add(start)

            page_params = dict(params or {})
            page_params["start"] = str(start)
            payload = self._get_json(path, page_params)
            page_rows = iss_table_to_rows(payload, table_name)
            rows.extend(page_rows)

            next_start = _next_cursor_start(payload, table_name, start, len(page_rows))
            if next_start is None:
                break
            start = next_start

        return rows

    def _get_json(self, path: str, params: Optional[dict[str, str]] = None) -> dict[str, Any]:
        query = {"iss.meta": "off"}
        query.update(params or {})
        url = f"{self.base_url}{path}?{urlencode(query)}"
        request = Request(url, headers={"User-Agent": USER_AGENT}, method="GET")
        try:
            with urlopen(request, timeout=self.timeout_seconds) as response:
                raw_payload = response.read()
        except HTTPError as exc:
            raise RuntimeError(f"HTTP {exc.code}: {exc.reason}") from exc
        except (URLError, OSError, TimeoutError) as exc:
            raise RuntimeError(str(exc)) from exc

        try:
            payload = json.loads(raw_payload.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise MOEXISSParseError("MOEX ISS response was not valid JSON.") from exc

        if not isinstance(payload, dict):
            raise MOEXISSParseError("MOEX ISS response was malformed: expected a JSON object.")
        return payload

    def _board_security_path(self, ticker: str) -> str:
        return (
            f"/engines/{quote(self.engine, safe='')}"
            f"/markets/{quote(self.market, safe='')}"
            f"/boards/{quote(self.board, safe='')}"
            f"/securities/{quote(ticker, safe='')}.json"
        )

    def _index_security_path(self, ticker: str) -> str:
        return (
            f"/engines/{quote(self.engine, safe='')}"
            f"/markets/{quote(INDEX_MARKET, safe='')}"
            f"/securities/{quote(ticker, safe='')}.json"
        )

    def _index_candles_path(self, ticker: str) -> str:
        return (
            f"/engines/{quote(self.engine, safe='')}"
            f"/markets/{quote(INDEX_MARKET, safe='')}"
            f"/securities/{quote(ticker, safe='')}/candles.json"
        )

    def _normalize_ticker(self, ticker: object) -> str:
        return normalize_moex_ticker(ticker)


def iss_table_to_rows(payload: dict[str, Any], table_name: str, *, required: bool = True) -> list[dict[str, Any]]:
    table = payload.get(table_name)
    if table is None:
        if required:
            raise MOEXISSParseError(f"MOEX ISS response was missing the {table_name} table.")
        return []

    if not isinstance(table, dict):
        raise MOEXISSParseError(f"MOEX ISS {table_name} table was malformed.")

    columns = table.get("columns")
    data = table.get("data")
    if not isinstance(columns, list) or not isinstance(data, list):
        raise MOEXISSParseError(f"MOEX ISS {table_name} table was malformed.")

    normalized_columns = [str(column).strip().lower() for column in columns]
    rows: list[dict[str, Any]] = []
    for raw_row in data:
        if not isinstance(raw_row, list):
            raise MOEXISSParseError(f"MOEX ISS {table_name} row was malformed.")
        row = {
            column: raw_row[index] if index < len(raw_row) else None
            for index, column in enumerate(normalized_columns)
            if column
        }
        rows.append(row)
    return rows


def sanitize_error_message(exc: object) -> str:
    message = str(exc).strip() or exc.__class__.__name__
    for value in _sensitive_environment_values():
        message = message.replace(value, "[redacted]")
    message = SENSITIVE_ASSIGNMENT_RE.sub(lambda match: f"{match.group(1)}=[redacted]", message)
    message = SENSITIVE_VALUE_RE.sub("[redacted]", message)
    if len(message) > 500:
        message = f"{message[:500]}..."
    return message


def _sensitive_environment_values() -> list[str]:
    values: list[str] = []
    for key, value in os.environ.items():
        if not value or len(value) < 4:
            continue
        lowered = key.lower()
        if any(part in lowered for part in SENSITIVE_ENV_PARTS):
            values.append(str(value))
    return sorted(values, key=len, reverse=True)


def _description_values(rows: list[dict[str, Any]]) -> dict[str, Any]:
    values: dict[str, Any] = {}
    for row in rows:
        name = _clean_string(_row_value(row, "name"))
        if not name:
            continue
        values[name.upper()] = _row_value(row, "value")
    return values


def _first_matching_row(rows: list[dict[str, Any]], ticker: str) -> Optional[dict[str, Any]]:
    normalized_ticker = str(ticker or "").upper()
    if not rows:
        return None
    for row in rows:
        if str(_row_value(row, "secid") or "").upper() == normalized_ticker:
            return row
    return rows[0]


def _row_value(row: Optional[dict[str, Any]], key: str) -> Any:
    if row is None:
        return None
    return row.get(key.lower())


def _first_present(*values: Any) -> Any:
    for value in values:
        if value is None:
            continue
        if isinstance(value, str) and not value.strip():
            continue
        return value
    return None


def _first_float(row: dict[str, Any], *keys: str) -> Optional[float]:
    for key in keys:
        value = _to_float(_row_value(row, key))
        if value is not None:
            return value
    return None


def _first_int(row: dict[str, Any], *keys: str) -> Optional[int]:
    for key in keys:
        value = _to_int(_row_value(row, key))
        if value is not None:
            return value
    return None


def _first_date(row: dict[str, Any], *keys: str) -> Optional[date]:
    for key in keys:
        value = _parse_date(_row_value(row, key))
        if value is not None:
            return value
    return None


def _to_float(value: Any) -> Optional[float]:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _to_int(value: Any) -> Optional[int]:
    if value is None or value == "":
        return None
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def _parse_datetime(value: Any) -> Optional[datetime]:
    cleaned = _clean_string(value)
    if cleaned is None:
        return None
    try:
        return datetime.fromisoformat(cleaned)
    except ValueError:
        try:
            return datetime.combine(date.fromisoformat(cleaned[:10]), datetime.min.time())
        except ValueError:
            return None


def _parse_date(value: Any) -> Optional[date]:
    parsed_datetime = _parse_datetime(value)
    return parsed_datetime.date() if parsed_datetime is not None else None


def _clean_string(value: Any) -> Optional[str]:
    if value is None:
        return None
    cleaned = str(value).strip()
    return cleaned or None


def _normalize_currency(value: Any) -> Optional[str]:
    cleaned = _clean_string(value)
    if cleaned is None:
        return None
    upper = cleaned.upper()
    return "RUB" if upper in {"SUR", "RUR"} else upper


def _next_cursor_start(
    payload: dict[str, Any],
    table_name: str,
    current_start: int,
    row_count: int,
) -> Optional[int]:
    cursor_rows = iss_table_to_rows(payload, f"{table_name}.cursor", required=False)
    if not cursor_rows:
        return None

    cursor = cursor_rows[0]
    index = _to_int(_row_value(cursor, "index"))
    total = _to_int(_row_value(cursor, "total"))
    page_size = _to_int(_row_value(cursor, "pagesize"))
    if total is None:
        return None
    if index is None:
        index = current_start
    if page_size is None:
        page_size = row_count
    if page_size <= 0:
        return None

    next_start = index + page_size
    return next_start if next_start < total else None
