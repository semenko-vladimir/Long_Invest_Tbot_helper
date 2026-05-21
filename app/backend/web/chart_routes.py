from pathlib import Path
from urllib.parse import quote

from fastapi import APIRouter, Query, Request, Response
from fastapi.responses import PlainTextResponse
from fastapi.templating import Jinja2Templates

from app.backend.web.context import WebRequestServices, get_web_services
from app.backend.web.csrf import get_csrf_token
from app.backend.web.navigation import NAV_ITEMS
from app.charts.schemas import POSITION_VALUE_CHART_DISCLAIMER
from app.charts.services import SUPPORTED_CHART_RANGES, normalize_chart_mode, normalize_chart_range


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
            "read_only_notice": chart_notice(normalized_mode),
        }
    )
    return templates.TemplateResponse("pages/charts.html", context)


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
