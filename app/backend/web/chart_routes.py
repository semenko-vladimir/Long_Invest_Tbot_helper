from pathlib import Path
from urllib.parse import quote

from fastapi import APIRouter, Query, Request, Response
from fastapi.responses import JSONResponse, PlainTextResponse
from fastapi.templating import Jinja2Templates

from app.backend.web.context import WebRequestServices, get_web_services
from app.backend.web.csrf import get_csrf_token
from app.backend.web.navigation import NAV_ITEMS
from app.charts.schemas import ChartAnalytics
from app.charts.schemas import POSITION_VALUE_CHART_DISCLAIMER
from app.charts.services import (
    SUPPORTED_CHART_RANGES,
    chart_interval_for_range,
    normalize_chart_interval,
    normalize_chart_mode,
    normalize_chart_range,
)


TEMPLATE_DIR = Path(__file__).resolve().parent / "templates"
templates = Jinja2Templates(directory=str(TEMPLATE_DIR))
router = APIRouter()

CHART_READ_ONLY_NOTICE = (
    "Read-only educational chart. Hindsight-only analytics. Not a trading signal. "
    "Not investment advice. No broker orders were created."
)
POSITION_VALUE_CHART_NOTICE = f"Read-only chart. {POSITION_VALUE_CHART_DISCLAIMER}"
CHART_RANGE_OPTIONS = (
    ("day", "Day"),
    ("week", "Week"),
    ("month", "Month"),
    ("six_months", "Six months"),
    ("year", "Year"),
    ("all", "All"),
)
CHART_MODE_OPTIONS = (
    ("price", "Price chart"),
    ("position_value", "Current quantity value chart"),
)


def base_context(request: Request, *, services: WebRequestServices, title: str = "Charts") -> dict:
    return {
        "request": request,
        "active": "charts",
        "title": title,
        "nav_items": NAV_ITEMS,
        "mode": services.mode_service.current(),
        "current_user": services.user,
        "csrf_token": get_csrf_token(request),
    }


@router.get("/charts")
def charts_page(
    request: Request,
    range_name: str = Query("month", alias="range"),
    chart_mode: str = Query("price", alias="mode"),
):
    ticker_input = request.query_params.get("ticker", "").strip()
    normalized_range = normalize_chart_range(range_name)
    if normalized_range is None:
        return chart_error_response(
            f"Unsupported chart range: {range_name}. Supported ranges: {supported_range_text()}."
        )

    normalized_mode = normalize_chart_mode(chart_mode)
    if normalized_mode is None:
        return chart_error_response("Unsupported chart mode. Use mode=price or mode=position_value.")

    include_analytics = parse_analytics_query(last_query_value(request, "analytics", "1"))
    if include_analytics is None:
        return chart_error_response("Unsupported analytics option. Use analytics=1 or analytics=0.")
    if normalized_mode == "position_value":
        include_analytics = False

    normalized_ticker = normalize_chart_ticker(ticker_input)
    if ticker_input and not normalized_ticker:
        return chart_error_response("Ticker is required and must use letters, numbers, or hyphen.")

    services = get_web_services()
    portfolio_options = portfolio_ticker_options(services)
    context = base_context(request, services=services)
    context.update(
        {
            "ticker": normalized_ticker,
            "ticker_input": ticker_input.upper(),
            "selected_range": normalized_range,
            "selected_mode": normalized_mode,
            "analytics_enabled": include_analytics,
            "range_options": CHART_RANGE_OPTIONS,
            "mode_options": CHART_MODE_OPTIONS,
            "portfolio_ticker_options": portfolio_options,
            "chart_image_url": chart_image_url(
                normalized_ticker,
                normalized_range,
                include_analytics,
                normalized_mode,
            )
            if normalized_ticker
            else "",
            "chart_data_url": chart_data_url(
                normalized_ticker,
                normalized_range,
                include_analytics,
            )
            if normalized_ticker and normalized_mode == "price"
            else "",
            "selected_interval": chart_interval_for_range(normalized_range),
            "read_only_notice": chart_notice(normalized_mode),
        }
    )
    return templates.TemplateResponse("pages/charts.html", context)


@router.get("/charts/{ticker}.json")
def chart_json(
    ticker: str,
    range_name: str = Query("month", alias="range"),
    interval: str = Query("auto"),
    analytics: str = Query("1"),
    refresh: str = Query("1"),
):
    normalized_range = normalize_chart_range(range_name)
    if normalized_range is None:
        return chart_json_error(
            f"Unsupported chart range: {range_name}. Supported ranges: {supported_range_text()}."
        )

    normalized_interval = normalize_chart_interval(interval, normalized_range)
    if normalized_interval is None:
        return chart_json_error("Unsupported chart interval. Use interval=auto, interval=hour, or interval=day.")

    include_analytics = parse_analytics_query(analytics)
    if include_analytics is None:
        return chart_json_error("Unsupported analytics option. Use analytics=1 or analytics=0.")

    refresh_enabled = parse_analytics_query(refresh)
    if refresh_enabled is None:
        return chart_json_error("Unsupported refresh option. Use refresh=1 or refresh=0.")

    normalized_ticker = normalize_chart_ticker(ticker)
    if not normalized_ticker:
        return chart_json_error("Ticker is required and must use letters, numbers, or hyphen.")

    try:
        snapshot = get_web_services().chart_snapshot_service.get_snapshot(
            normalized_ticker,
            normalized_range,
            interval_name=normalized_interval,
            refresh=refresh_enabled,
        )
    except Exception as exc:
        return chart_json_error(f"Chart data could not be generated: {str(exc)}")

    status_code = 200 if snapshot.ok else 400
    return JSONResponse(
        serialize_chart_snapshot(snapshot, include_analytics=include_analytics),
        status_code=status_code,
    )


@router.get("/charts/{ticker}.png")
def chart_png(
    ticker: str,
    range_name: str = Query("month", alias="range"),
    analytics: str = Query("1"),
    chart_mode: str = Query("price", alias="mode"),
):
    normalized_range = normalize_chart_range(range_name)
    if normalized_range is None:
        return chart_error_response(
            f"Unsupported chart range: {range_name}. Supported ranges: {supported_range_text()}."
        )

    normalized_mode = normalize_chart_mode(chart_mode)
    if normalized_mode is None:
        return chart_error_response("Unsupported chart mode. Use mode=price or mode=position_value.")

    include_analytics = parse_analytics_query(analytics)
    if include_analytics is None:
        return chart_error_response("Unsupported analytics option. Use analytics=1 or analytics=0.")
    if normalized_mode == "position_value":
        include_analytics = False

    normalized_ticker = normalize_chart_ticker(ticker)
    if not normalized_ticker:
        return chart_error_response("Ticker is required and must use letters, numbers, or hyphen.")

    try:
        result = get_web_services().chart_image_service.render_png(
            normalized_ticker,
            normalized_range,
            include_analytics=include_analytics,
            mode=normalized_mode,
        )
    except Exception as exc:
        return chart_error_response(f"Chart could not be generated: {str(exc)}", mode=normalized_mode)

    if not result.ok or result.png_bytes is None:
        return chart_error_response(chart_result_error_text(result), mode=normalized_mode)

    return Response(content=result.png_bytes, media_type=result.content_type or "image/png")


def chart_image_url(
    ticker: str,
    range_name: str,
    include_analytics: bool = True,
    mode: str = "price",
) -> str:
    analytics_value = "1" if include_analytics else "0"
    return (
        f"/charts/{quote(ticker)}.png?range={quote(range_name)}"
        f"&mode={quote(mode)}&analytics={analytics_value}"
    )


def chart_data_url(
    ticker: str,
    range_name: str,
    include_analytics: bool = True,
    interval: str = "auto",
) -> str:
    analytics_value = "1" if include_analytics else "0"
    return (
        f"/charts/{quote(ticker)}.json?range={quote(range_name)}"
        f"&interval={quote(interval)}&analytics={analytics_value}"
    )


def normalize_chart_ticker(ticker: str) -> str:
    normalized = str(ticker or "").strip().upper()
    return normalized if normalized.replace("-", "").isalnum() else ""


def supported_range_text() -> str:
    return ", ".join(label for label, _ in CHART_RANGE_OPTIONS if label in SUPPORTED_CHART_RANGES)


def last_query_value(request: Request, key: str, default: str) -> str:
    values = request.query_params.getlist(key)
    return values[-1] if values else default


def parse_analytics_query(value: str) -> bool | None:
    normalized = str(value or "").strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    return None


def chart_notice(mode: str) -> str:
    return POSITION_VALUE_CHART_NOTICE if mode == "position_value" else CHART_READ_ONLY_NOTICE


def chart_error_response(message: str, mode: str = "price") -> PlainTextResponse:
    return PlainTextResponse(
        f"{message}\n\n{chart_notice(mode)}",
        status_code=400,
    )


def chart_json_error(message: str) -> JSONResponse:
    return JSONResponse(
        {
            "ok": False,
            "errors": [message],
            "data_gaps": [{"category": "request", "description": message, "severity": "high"}],
            "data_status": {
                "source": "unknown",
                "freshness": "stale",
                "delay_status": "cached",
                "fetched_at": None,
                "as_of_date": None,
                "candle_count": 0,
                "data_gaps": [{"category": "request", "description": message, "severity": "high"}],
                "errors": [message],
                "educational_only": True,
            },
            "cache": {
                "used": False,
                "refreshed": False,
                "candle_count": 0,
                "latest_candle_at": None,
                "oldest_candle_at": None,
            },
            "refresh": {
                "requested": False,
                "attempted": False,
                "refreshed": False,
                "errors": [],
            },
            "educational_only": True,
            "disclaimer": CHART_READ_ONLY_NOTICE,
        },
        status_code=400,
    )


def chart_result_error_text(result) -> str:
    errors = [str(error).strip() for error in getattr(result, "errors", []) if str(error).strip()]
    if errors:
        return "Chart could not be generated: " + "; ".join(errors)

    gaps = [
        str(getattr(gap, "description", "")).strip()
        for gap in getattr(result, "data_gaps", [])
        if str(getattr(gap, "description", "")).strip()
    ]
    if gaps:
        return "Chart could not be generated: " + "; ".join(gaps)

    return "Chart could not be generated for the selected ticker and range."


def serialize_chart_snapshot(snapshot, *, include_analytics: bool = True) -> dict:
    history = snapshot.history
    analytics = snapshot.analytics if include_analytics else ChartAnalytics()
    cache = getattr(snapshot, "cache", None)
    refresh_status = getattr(snapshot, "refresh_status", None)
    return {
        "ok": snapshot.ok,
        "ticker": history.ticker,
        "figi": history.figi,
        "range": history.range,
        "interval": snapshot.interval,
        "source": history.source,
        "generated_at": iso_or_none(history.generated_at),
        "fetched_at": iso_or_none(history.fetched_at),
        "as_of_date": history.as_of_date,
        "freshness": history.freshness,
        "delay_status": history.delay_status,
        "data_status": serialize_data_status(getattr(snapshot, "data_status", None), history=history),
        "cache": {
            "used": bool(getattr(cache, "used", False)),
            "refreshed": bool(getattr(cache, "refreshed", getattr(snapshot, "refreshed", False))),
            "candle_count": int(getattr(cache, "candle_count", getattr(snapshot, "cache_candle_count", 0)) or 0),
            "latest_candle_at": iso_or_none(getattr(cache, "latest_candle_at", None)),
            "oldest_candle_at": iso_or_none(getattr(cache, "oldest_candle_at", None)),
        },
        "refresh": {
            "requested": bool(getattr(refresh_status, "requested", False)),
            "attempted": bool(getattr(refresh_status, "attempted", getattr(snapshot, "refreshed", False))),
            "refreshed": bool(getattr(refresh_status, "refreshed", getattr(snapshot, "refreshed", False))),
            "errors": list(getattr(refresh_status, "errors", [])),
        },
        "educational_only": bool(getattr(snapshot, "educational_only", True)),
        "candles": [
            {
                "time": iso_or_none(candle.time),
                "open": float(candle.open),
                "high": float(candle.high),
                "low": float(candle.low),
                "close": float(candle.close),
                "volume": candle.volume,
            }
            for candle in history.candles
        ],
        "analytics": serialize_analytics(analytics),
        "data_gaps": [
            {
                "category": gap.category,
                "description": gap.description,
                "severity": gap.severity,
            }
            for gap in history.data_gaps
        ],
        "errors": list(history.errors),
        "disclaimer": history.disclaimer,
    }


def serialize_data_status(status, *, history=None) -> dict:
    if status is None and history is not None:
        data_gaps = list(getattr(history, "data_gaps", []))
        errors = list(getattr(history, "errors", []))
        return {
            "source": getattr(history, "source", "unknown") or "unknown",
            "freshness": getattr(history, "freshness", None) or "latest_available",
            "delay_status": getattr(history, "delay_status", None) or "broker_api",
            "fetched_at": iso_or_none(getattr(history, "fetched_at", None)),
            "as_of_date": getattr(history, "as_of_date", None),
            "candle_count": len(getattr(history, "candles", []) or []),
            "data_gaps": [
                {
                    "category": gap.category,
                    "description": gap.description,
                    "severity": gap.severity,
                }
                for gap in data_gaps
            ],
            "errors": errors,
            "educational_only": True,
        }
    return {
        "source": status.source,
        "freshness": status.freshness,
        "delay_status": status.delay_status,
        "fetched_at": iso_or_none(status.fetched_at),
        "as_of_date": status.as_of_date,
        "candle_count": status.candle_count,
        "data_gaps": [
            {
                "category": gap.category,
                "description": gap.description,
                "severity": gap.severity,
            }
            for gap in status.data_gaps
        ],
        "errors": list(status.errors),
        "educational_only": status.educational_only,
    }


def serialize_analytics(analytics: ChartAnalytics) -> dict:
    return {
        "educational_only": True,
        "metrics": [
            metric("range_return_pct", "Range return", analytics.range_return_pct, "pct"),
            metric("latest_change_pct", "Latest change", analytics.latest_change_pct, "pct"),
            metric("hindsight_return_pct", "Best hindsight move", analytics.hindsight_return_pct, "pct"),
            metric("periodic_volatility_pct", "Periodic volatility", analytics.periodic_volatility_pct, "pct"),
            metric("annualized_volatility_pct", "Annualized volatility", analytics.annualized_volatility_pct, "pct"),
            metric(
                "max_drawdown_pct",
                "Max drawdown",
                analytics.max_drawdown.drawdown_pct if analytics.max_drawdown else None,
                "pct",
            ),
            metric(
                "vs_range_high_pct",
                "Latest vs high",
                analytics.range_position.vs_range_high_pct if analytics.range_position else None,
                "pct",
            ),
            metric(
                "vs_range_low_pct",
                "Latest vs low",
                analytics.range_position.vs_range_low_pct if analytics.range_position else None,
                "pct",
            ),
            metric("average_volume", "Average volume", analytics.volume_stats.average_volume, "number"),
            metric(
                "volume_vs_average_pct",
                "Volume vs average",
                analytics.volume_stats.latest_vs_average_pct,
                "pct",
            ),
        ],
        "markers": {
            "entry": serialize_marker(analytics.entry_marker),
            "exit": serialize_marker(analytics.exit_marker),
            "max_drawdown": serialize_drawdown(analytics.max_drawdown),
        },
        "overlays": {
            "sma20": serialize_value_series(analytics.sma20.points),
            "sma50": serialize_value_series(analytics.sma50.points),
            "ema12": serialize_value_series(analytics.ema12.points),
            "ema26": serialize_value_series(analytics.ema26.points),
            "bollinger20": [
                {
                    "time": iso_or_none(point.time),
                    "middle": point.middle,
                    "upper": point.upper,
                    "lower": point.lower,
                }
                for point in analytics.bollinger20.points
            ],
        },
        "panels": {
            "rsi14": serialize_value_series(analytics.rsi14.points),
            "atr14": serialize_value_series(analytics.atr14.points),
            "macd": [
                {
                    "time": iso_or_none(point.time),
                    "macd": point.macd,
                    "signal": point.signal,
                    "histogram": point.histogram,
                }
                for point in analytics.macd.points
            ],
        },
    }


def metric(key: str, label: str, value, unit: str) -> dict:
    numeric = float(value) if value is not None else None
    return {
        "key": key,
        "label": label,
        "value": numeric,
        "unit": unit,
        "display": metric_display(numeric, unit),
    }


def metric_display(value: float | None, unit: str) -> str:
    if value is None:
        return "n/a"
    if unit == "pct":
        return f"{value:+.2f}%"
    return f"{value:,.0f}"


def serialize_value_series(points) -> list[dict]:
    return [{"time": iso_or_none(point.time), "value": point.value} for point in points]


def serialize_marker(marker) -> dict | None:
    if marker is None:
        return None
    return {
        "kind": marker.kind,
        "label": marker.label,
        "time": iso_or_none(marker.time),
        "close": marker.close,
    }


def serialize_drawdown(drawdown) -> dict | None:
    if drawdown is None:
        return None
    return {
        "peak_time": iso_or_none(drawdown.peak_time),
        "peak_close": drawdown.peak_close,
        "trough_time": iso_or_none(drawdown.trough_time),
        "trough_close": drawdown.trough_close,
        "drawdown_pct": drawdown.drawdown_pct,
    }


def iso_or_none(value) -> str | None:
    return value.isoformat() if value is not None else None


def portfolio_ticker_options(services: WebRequestServices) -> list[dict[str, str]]:
    try:
        portfolio = services.portfolio_service.get_portfolio_view()
    except Exception:
        return []

    options: list[dict[str, str]] = []
    seen: set[str] = set()
    for position in getattr(portfolio, "positions", []) or []:
        ticker = normalize_chart_ticker(getattr(position, "ticker", ""))
        if not ticker or ticker in seen:
            continue
        seen.add(ticker)
        quantity_display = str(getattr(position, "quantity_display", "") or "").strip()
        name = str(getattr(position, "name", "") or "").strip()
        label_parts = [part for part in (name, quantity_display) if part]
        options.append({"ticker": ticker, "label": " - ".join(label_parts)})

    return sorted(options, key=lambda option: option["ticker"])
