import logging
from pathlib import Path
from urllib.parse import parse_qs, urlencode

from fastapi import APIRouter, Request
from fastapi.templating import Jinja2Templates

from app.backend.web.context import WebRequestServices, get_web_services
from app.backend.web.csrf import get_csrf_token, validate_csrf_form
from app.services.dividends import DEFAULT_DIVIDEND_PERIOD_DAYS
from app.services.orders import (
    OrderConfirmCommand,
    OrderExecutionBlocked,
    OrderPreviewRequest,
    OrderServiceError,
)
from app.services.investment_plans import (
    InvestmentPlanServiceError,
    PlanDefinition,
)
from app.services.trading_policy import TradingPolicyError
from app.services.watchlist import WatchlistServiceError, format_watchlist_sync_summary


logger = logging.getLogger(__name__)
TEMPLATE_DIR = Path(__file__).resolve().parent / "templates"
templates = Jinja2Templates(directory=str(TEMPLATE_DIR))
router = APIRouter()

NAV_ITEMS = (
    {"label": "Portfolio", "url": "/portfolio", "key": "portfolio"},
    {"label": "Buy", "url": "/buy", "key": "buy"},
    {"label": "Sell", "url": "/sell", "key": "sell"},
    {"label": "Dividends", "url": "/dividends", "key": "dividends"},
    {"label": "Watchlist", "url": "/watchlist", "key": "watchlist"},
    {"label": "Plans", "url": "/plans", "key": "plans"},
    {"label": "Stats", "url": "/stats", "key": "stats"},
    {"label": "Settings", "url": "/settings", "key": "settings"},
)

def base_context(request: Request, *, active: str, title: str, services: WebRequestServices = None) -> dict:
    services = services or get_web_services()
    return {
        "request": request,
        "active": active,
        "title": title,
        "nav_items": NAV_ITEMS,
        "mode": services.mode_service.current(),
        "current_user": services.user,
        "csrf_token": get_csrf_token(request),
    }


def order_context(request: Request, *, operation: str, services: WebRequestServices = None, **extra) -> dict:
    services = services or get_web_services()
    title = "Buy" if operation == "buy" else "Sell"
    context = base_context(request, active=operation, title=title, services=services)
    context.update(
        {
            "operation": operation,
            "operation_label": title,
            "preview_url": f"/{operation}/preview",
            "confirm_url": f"/{operation}/confirm",
            "values": {"ticker": "", "lots": "1"},
            "preview": None,
            "result": None,
            "error": None,
        }
    )
    context.update(extra)
    return context


def order_query_values(request: Request) -> dict:
    return {
        "ticker": request.query_params.get("ticker", "").strip().upper(),
        "lots": request.query_params.get("lots", "1").strip() or "1",
    }


async def parse_urlencoded_form(request: Request) -> dict:
    raw_body = (await request.body()).decode("utf-8")
    parsed = parse_qs(raw_body, keep_blank_values=True)
    form = {key: values[-1] if values else "" for key, values in parsed.items()}
    validate_csrf_form(request, form)
    return form


def parse_lots(value: str) -> int:
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise OrderServiceError("Lots must be a whole number.") from exc


def parse_period_days(value: str) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return DEFAULT_DIVIDEND_PERIOD_DAYS


def parse_bool(value: str) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def parse_plan_definition(form: dict) -> PlanDefinition:
    return PlanDefinition(
        ticker=form.get("ticker", ""),
        lots=parse_lots(form.get("lots", "1")),
        schedule=form.get("schedule", "monthly"),
        time=form.get("time", "09:00"),
        price_rule=form.get("price_rule", "current_market"),
        order_type=form.get("order_type", "limit"),
        confirmation_required=parse_bool(form.get("confirmation_required", "true")),
        operation=form.get("operation", "buy"),
        price_limit=form.get("price_limit") or None,
        pct_threshold=form.get("pct_threshold") or None,
        avg_period_days=form.get("avg_period_days") or None,
        confirmation_mode=form.get("confirmation_mode", "telegram_confirm"),
    )


def plans_context(
    request: Request,
    *,
    services: WebRequestServices = None,
    notice: str = None,
    error: str = None,
    proposal=None,
) -> dict:
    services = services or get_web_services()
    context = base_context(request, active="plans", title="Investment Plans", services=services)
    context["plan_policy"] = services.investment_plan_service.policy_status()
    context["plans"] = services.investment_plan_service.list_plans(notice=notice, error=error)
    context["proposal"] = proposal
    context["plan_defaults"] = {
        "ticker": "",
        "lots": "1",
        "schedule": "daily",
        "time": "09:00",
        "price_rule": "previous_day_average_discount",
        "price_limit": "",
        "pct_threshold": "0.5",
        "avg_period_days": "",
        "order_type": "limit",
        "confirmation_required": True,
        "operation": "buy",
        "confirmation_mode": "telegram_confirm",
    }
    return context


def plan_proposal_context(request: Request, *, services: WebRequestServices, proposal) -> dict:
    context = base_context(request, active="plans", title="Plan Proposal", services=services)
    context["proposal"] = proposal
    context["buy_url"] = "/buy?" + urlencode(
        {
            "ticker": proposal.plan.ticker,
            "lots": str(proposal.proposed_lots),
        }
    )
    return context


def refresh_plan_scheduler_if_enabled() -> None:
    try:
        from app.client.config import background_schedulers_enabled, investment_plans_enabled

        if not (background_schedulers_enabled() and investment_plans_enabled()):
            return

        from app.client.config.schedulers_config import configure_plan_scheduler

        configure_plan_scheduler()
    except Exception:
        # A scheduler refresh failure must not make the saved plan disappear from the UI.
        logger.exception("Failed to refresh plan scheduler after web edit.")


@router.get("/")
@router.get("/portfolio")
def portfolio_page(request: Request):
    services = get_web_services()
    portfolio = services.portfolio_service.get_portfolio_view()
    context = base_context(request, active="portfolio", title="Portfolio", services=services)
    context["mode"] = portfolio.mode
    context["portfolio"] = portfolio
    return templates.TemplateResponse("pages/portfolio.html", context)


@router.get("/buy")
def buy_page(request: Request):
    services = get_web_services()
    return templates.TemplateResponse(
        "pages/buy.html",
        order_context(request, operation="buy", services=services, values=order_query_values(request)),
    )


@router.post("/buy/preview")
async def preview_buy(request: Request):
    return await preview_order(request, "buy")


@router.post("/buy/confirm")
async def confirm_buy(request: Request):
    return await confirm_order(request, "buy")


@router.get("/sell")
def sell_page(request: Request):
    services = get_web_services()
    return templates.TemplateResponse(
        "pages/sell.html",
        order_context(request, operation="sell", services=services),
    )


@router.post("/sell/preview")
async def preview_sell(request: Request):
    return await preview_order(request, "sell")


@router.post("/sell/confirm")
async def confirm_sell(request: Request):
    return await confirm_order(request, "sell")


async def preview_order(request: Request, operation: str):
    form = await parse_urlencoded_form(request)
    services = get_web_services()
    values = {
        "ticker": form.get("ticker", "").strip().upper(),
        "lots": form.get("lots", "1").strip() or "1",
    }

    try:
        preview = services.order_service.preview(
            OrderPreviewRequest(
                operation=operation,
                ticker=values["ticker"],
                lots=parse_lots(values["lots"]),
            )
        )
        values = {"ticker": preview.ticker, "lots": str(preview.lots)}
        return templates.TemplateResponse(
            f"pages/{operation}.html",
            order_context(request, operation=operation, services=services, values=values, preview=preview),
        )
    except OrderServiceError as exc:
        return templates.TemplateResponse(
            f"pages/{operation}.html",
            order_context(request, operation=operation, services=services, values=values, error=str(exc)),
            status_code=400,
        )


async def confirm_order(request: Request, operation: str):
    form = await parse_urlencoded_form(request)
    services = get_web_services()
    values = {
        "ticker": form.get("ticker", "").strip().upper(),
        "lots": form.get("lots", "1").strip() or "1",
    }

    try:
        result = services.order_service.execute(
            OrderConfirmCommand(
                operation=operation,
                ticker=values["ticker"],
                lots=parse_lots(values["lots"]),
                confirm_token=form.get("confirm_token", ""),
                ticker_confirmation=form.get("ticker_confirmation", ""),
            )
        )
        values = {"ticker": result.ticker, "lots": str(result.lots)}
        return templates.TemplateResponse(
            f"pages/{operation}.html",
            order_context(request, operation=operation, services=services, values=values, result=result),
        )
    except OrderExecutionBlocked as exc:
        return templates.TemplateResponse(
            f"pages/{operation}.html",
            order_context(request, operation=operation, services=services, values=values, error=str(exc)),
            status_code=403,
        )
    except OrderServiceError as exc:
        return templates.TemplateResponse(
            f"pages/{operation}.html",
            order_context(request, operation=operation, services=services, values=values, error=str(exc)),
            status_code=400,
        )


@router.get("/dividends")
def dividends_page(request: Request):
    services = get_web_services()
    period_days = parse_period_days(request.query_params.get("period_days", str(DEFAULT_DIVIDEND_PERIOD_DAYS)))
    dividends = services.dividends_service.get_dividends_view(period_days)
    context = base_context(request, active="dividends", title="Dividends", services=services)
    context["dividends"] = dividends
    return templates.TemplateResponse(
        "pages/dividends.html",
        context,
    )


@router.get("/watchlist")
def watchlist_page(request: Request):
    services = get_web_services()
    watchlist = services.watchlist_service.list_items()
    context = base_context(request, active="watchlist", title="Watchlist", services=services)
    context["watchlist"] = watchlist
    return templates.TemplateResponse(
        "pages/watchlist.html",
        context,
    )


@router.post("/watchlist/add")
async def add_watchlist_item(request: Request):
    form = await parse_urlencoded_form(request)
    services = get_web_services()
    try:
        watchlist = services.watchlist_service.add_ticker(form.get("ticker", ""))
    except WatchlistServiceError as exc:
        watchlist = services.watchlist_service.list_items(error=str(exc))

    context = base_context(request, active="watchlist", title="Watchlist", services=services)
    context["watchlist"] = watchlist
    return templates.TemplateResponse(
        "pages/watchlist.html",
        context,
        status_code=400 if watchlist.error else 200,
    )


@router.post("/watchlist/remove")
async def remove_watchlist_item(request: Request):
    form = await parse_urlencoded_form(request)
    services = get_web_services()
    try:
        watchlist = services.watchlist_service.remove_ticker(form.get("ticker", ""))
    except WatchlistServiceError as exc:
        watchlist = services.watchlist_service.list_items(error=str(exc))

    context = base_context(request, active="watchlist", title="Watchlist", services=services)
    context["watchlist"] = watchlist
    return templates.TemplateResponse(
        "pages/watchlist.html",
        context,
        status_code=400 if watchlist.error else 200,
    )


@router.post("/watchlist/sync-portfolio")
async def sync_watchlist_from_portfolio(request: Request):
    await parse_urlencoded_form(request)
    services = get_web_services()
    sync_result = services.watchlist_service.sync_from_portfolio(services.portfolio_service)
    summary = format_watchlist_sync_summary(sync_result)
    watchlist = services.watchlist_service.list_items(
        notice=summary if sync_result.ok else None,
        error=None if sync_result.ok else summary,
    )

    context = base_context(request, active="watchlist", title="Watchlist", services=services)
    context["watchlist"] = watchlist
    context["sync_result"] = sync_result
    return templates.TemplateResponse(
        "pages/watchlist.html",
        context,
        status_code=200 if sync_result.ok else 400,
    )


@router.get("/plans")
def plans_page(request: Request):
    return templates.TemplateResponse(
        "pages/plans.html",
        plans_context(request),
    )


@router.post("/plans")
@router.post("/plans/create")
async def create_plan(request: Request):
    form = await parse_urlencoded_form(request)
    services = get_web_services()
    try:
        plan = services.investment_plan_service.create_plan(parse_plan_definition(form))
        refresh_plan_scheduler_if_enabled()
        context = plans_context(request, services=services, notice=f"Plan for {plan.ticker} was created.")
        return templates.TemplateResponse("pages/plans.html", context)
    except (InvestmentPlanServiceError, OrderServiceError, TradingPolicyError) as exc:
        context = plans_context(request, services=services, error=str(exc))
        return templates.TemplateResponse("pages/plans.html", context, status_code=400)


@router.post("/plans/{plan_id}/update")
async def update_plan(request: Request, plan_id: int):
    form = await parse_urlencoded_form(request)
    services = get_web_services()
    try:
        plan = services.investment_plan_service.update_plan(plan_id, parse_plan_definition(form))
        refresh_plan_scheduler_if_enabled()
        context = plans_context(request, services=services, notice=f"Plan for {plan.ticker} was updated.")
        return templates.TemplateResponse("pages/plans.html", context)
    except (InvestmentPlanServiceError, OrderServiceError, TradingPolicyError) as exc:
        context = plans_context(request, services=services, error=str(exc))
        return templates.TemplateResponse("pages/plans.html", context, status_code=400)


@router.post("/plans/{plan_id}/delete")
async def delete_plan(request: Request, plan_id: int):
    await parse_urlencoded_form(request)
    services = get_web_services()
    try:
        plan = services.investment_plan_service.delete_plan(plan_id)
        refresh_plan_scheduler_if_enabled()
        context = plans_context(request, services=services, notice=f"Plan for {plan.ticker} was deleted.")
        return templates.TemplateResponse("pages/plans.html", context)
    except (InvestmentPlanServiceError, TradingPolicyError) as exc:
        context = plans_context(request, services=services, error=str(exc))
        return templates.TemplateResponse("pages/plans.html", context, status_code=400)


@router.get("/plans/{plan_id}/proposal")
def plan_proposal_page(request: Request, plan_id: int):
    services = get_web_services()
    try:
        proposal = services.investment_plan_service.generate_order_proposal(plan_id)
        return templates.TemplateResponse(
            "pages/plan_proposal.html",
            plan_proposal_context(request, services=services, proposal=proposal),
        )
    except (InvestmentPlanServiceError, OrderServiceError, TradingPolicyError) as exc:
        context = plans_context(request, services=services, error=str(exc))
        return templates.TemplateResponse("pages/plans.html", context, status_code=400)


@router.post("/plans/{plan_id}/proposal")
async def generate_plan_proposal(request: Request, plan_id: int):
    await parse_urlencoded_form(request)
    services = get_web_services()
    try:
        proposal = services.investment_plan_service.generate_order_proposal(plan_id)
        context = plans_context(request, services=services, proposal=proposal)
        return templates.TemplateResponse("pages/plans.html", context)
    except (InvestmentPlanServiceError, OrderServiceError, TradingPolicyError) as exc:
        context = plans_context(request, services=services, error=str(exc))
        return templates.TemplateResponse("pages/plans.html", context, status_code=400)


@router.post("/plans/{plan_id}/proposal/skip")
async def skip_plan_proposal(request: Request, plan_id: int):
    await parse_urlencoded_form(request)
    services = get_web_services()
    return templates.TemplateResponse(
        "pages/plans.html",
        plans_context(request, services=services, notice="Proposal skipped. No order was created."),
    )


@router.get("/stats")
def stats_page(request: Request):
    services = get_web_services()
    raw = request.query_params.get("period_days", "")
    try:
        period_days = int(raw) if raw.strip() else None
    except ValueError:
        period_days = None
    stats = services.statistics_service.get_statistics_view(period_days=period_days)
    context = base_context(request, active="stats", title="Statistics", services=services)
    context["stats"] = stats
    context["period_days_input"] = raw.strip()
    return templates.TemplateResponse("pages/stats.html", context)


@router.get("/orders")
def orders_page(request: Request):
    services = get_web_services()
    order_history = services.order_history_service.list_orders()
    context = base_context(request, active="stats", title="Order History", services=services)
    context["order_history"] = order_history
    return templates.TemplateResponse("pages/orders.html", context)


@router.get("/settings")
def settings_page(request: Request):
    services = get_web_services()
    context = base_context(request, active="settings", title="Settings", services=services)
    settings = services.settings_view_service.current()
    context["settings"] = settings
    context["mode"] = settings.mode
    context["plan_policy"] = services.investment_plan_service.policy_status()
    return templates.TemplateResponse("pages/settings.html", context)
