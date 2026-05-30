from datetime import datetime

from app.client.config import (
    anti_greedy_policy_enabled,
    background_schedulers_enabled,
    chart_data_refresh_enabled,
    get_anti_greedy_check_time,
    get_anti_greedy_profit_pct,
    get_chart_data_refresh_interval_seconds,
    get_chart_data_refresh_ranges,
    get_invest_mode,
    investment_plans_enabled,
)
from app.client.log.logger import setup_logger

logger = setup_logger(__name__)
plan_scheduler = None
anti_greedy_scheduler = None
chart_data_scheduler = None
confirmation_service = None


def configure_market_scheduler():
    """
    Compatibility no-op for the legacy market scheduler.

    Market notifications are not part of the active investor v1 runtime.
    """
    logger.info("Legacy market scheduling is disabled for investor v1.")


def configure_schedulers():
    if not background_schedulers_enabled():
        logger.info("Фоновые планировщики отключены для sandbox-first v1")
        return

    configure_market_scheduler()
    configure_chart_data_scheduler()
    configure_plan_scheduler()
    configure_anti_greedy_scheduler()


def configure_chart_data_scheduler():
    global chart_data_scheduler

    if not chart_data_refresh_enabled():
        logger.info("Chart data refresh scheduler disabled because ENABLE_CHART_DATA_REFRESH=false")
        return

    try:
        from apscheduler.schedulers.background import BackgroundScheduler

        from app.charts.factory import build_chart_services
        from app.charts.refresh_scheduler import ChartDataRefreshRunner
        from app.integrations.tinvest import TInvestBroker
        from app.services.mode import ModeService
        from app.services.portfolio import PortfolioService
        from app.services.user_context import UserContextResolver
        from app.services.user_database import session_factory_for_user
        from app.services.watchlist import WatchlistService
    except ImportError as exc:
        logger.error("Chart data refresh scheduler requires active runtime dependencies: %s", exc)
        return

    try:
        interval_seconds = get_chart_data_refresh_interval_seconds()
        ranges = get_chart_data_refresh_ranges()
    except Exception as exc:
        logger.error("Chart data refresh scheduler has invalid config: %s", exc)
        return

    if chart_data_scheduler:
        chart_data_scheduler.shutdown()

    scheduler = BackgroundScheduler(timezone="Europe/Moscow")
    scheduled_count = 0

    try:
        users = UserContextResolver().enabled_users()
    except Exception as exc:
        logger.error("Chart data refresh scheduler could not load users: %s", exc)
        return

    for user in users:
        session_factory = session_factory_for_user(user)
        token_provider = lambda user=user: user.active_token(get_invest_mode())
        mode_service = ModeService()
        broker = TInvestBroker(session_factory=session_factory)
        portfolio_service = PortfolioService(
            broker=broker,
            mode_service=mode_service,
            token_provider=token_provider,
        )
        watchlist_service = WatchlistService(
            broker=broker,
            session_factory=session_factory,
            token_provider=token_provider,
        )
        chart_services = build_chart_services(
            broker=broker,
            token_provider=token_provider,
            portfolio_service=portfolio_service,
            session_factory=session_factory,
        )
        runner = ChartDataRefreshRunner(
            watchlist_service=watchlist_service,
            portfolio_service=portfolio_service,
            refresh_service=chart_services.refresh_service,
            ranges=ranges,
        )
        scheduler.add_job(
            runner.run,
            "interval",
            seconds=interval_seconds,
            id=f"chart_data_refresh_{user.user_id}",
            replace_existing=True,
        )
        scheduled_count += 1

    scheduler.start()
    chart_data_scheduler = scheduler
    logger.info(
        "Chart data refresh scheduler started with %d user job(s), interval %d seconds",
        scheduled_count,
        interval_seconds,
    )


def configure_plan_scheduler():
    global plan_scheduler

    if not investment_plans_enabled():
        logger.info("Investment plan scheduler disabled because ENABLE_INVESTMENT_PLANS=false")
        return

    try:
        from apscheduler.schedulers.background import BackgroundScheduler

        from app.client.bot.bot import bot
        from app.client.handlers.plans import auto_confirm_handler
        from app.integrations.tinvest import TInvestBroker
        from app.services.investment_plans import InvestmentPlanService
        from app.services.mode import ModeService
        from app.services.orders import OrderService
        from app.services.plan_runner import PlanRunner
        from app.services.price_conditions import PriceConditionService
        from app.services.user_context import UserContextResolver
        from app.services.user_database import session_factory_for_user
    except ImportError as exc:
        logger.error("Investment plan scheduler requires active runtime dependencies: %s", exc)
        return

    if plan_scheduler:
        plan_scheduler.shutdown()

    shared_confirmation_service = _get_confirmation_service()
    scheduler = BackgroundScheduler(timezone="Europe/Moscow")
    scheduled_count = 0

    try:
        users = UserContextResolver().enabled_users()
    except Exception as exc:
        logger.error("Investment plan scheduler could not load users: %s", exc)
        return

    for user in users:
        session_factory = session_factory_for_user(user)
        token_provider = lambda user=user: user.active_token(get_invest_mode())
        mode_service = ModeService()
        broker = TInvestBroker(session_factory=session_factory)
        order_service = OrderService(
            broker=broker,
            mode_service=mode_service,
            token_provider=token_provider,
        )
        plan_service = InvestmentPlanService(
            order_service=order_service,
            session_factory=session_factory,
        )
        price_condition_service = PriceConditionService(
            token_provider=token_provider,
            broker=broker,
        )
        runner = PlanRunner(
            plan_service=plan_service,
            price_condition_service=price_condition_service,
            confirmation_service=shared_confirmation_service,
            order_service=order_service,
            session_factory=session_factory,
            telegram_chat_id=user.telegram_chat_id,
            notify_fn=lambda chat_id, text: bot.send_message(chat_id, text, parse_mode="Markdown"),
            send_confirmation_fn=auto_confirm_handler.send_plan_confirmation_message,
        )

        plans = plan_service.list_plans()
        if plans.error:
            logger.warning("Investment plans for %s could not be loaded: %s", user.user_id, plans.error)
            continue

        for plan in plans.plans:
            trigger_kwargs = _plan_trigger_kwargs(plan)
            if not trigger_kwargs:
                logger.warning("Investment plan %s has unsupported schedule: %s", plan.id, plan.schedule)
                continue
            scheduler.add_job(
                runner.run,
                "cron",
                args=[plan.id],
                id=f"investment_plan_{user.user_id}_{plan.id}",
                replace_existing=True,
                **trigger_kwargs,
            )
            scheduled_count += 1

    scheduler.add_job(
        shared_confirmation_service.expire_old,
        "interval",
        minutes=5,
        id="investment_plan_confirmation_expiry",
        replace_existing=True,
    )
    scheduler.start()
    plan_scheduler = scheduler
    logger.info("Investment plan scheduler started with %d plan job(s)", scheduled_count)


def configure_anti_greedy_scheduler():
    global anti_greedy_scheduler

    if not anti_greedy_policy_enabled():
        logger.info("Anti-greedy scheduler disabled because ENABLE_ANTI_GREEDY_POLICY=false")
        return

    try:
        from apscheduler.schedulers.background import BackgroundScheduler

        from app.client.bot.bot import bot
        from app.client.handlers.plans import auto_confirm_handler
        from app.integrations.tinvest import TInvestBroker
        from app.services.anti_greedy import AntiGreedyPolicyService, AntiGreedyRunner
        from app.services.mode import ModeService
        from app.services.orders import OrderService
        from app.services.portfolio import PortfolioService
        from app.services.user_context import UserContextResolver
        from app.services.user_database import session_factory_for_user
    except ImportError as exc:
        logger.error("Anti-greedy scheduler requires active runtime dependencies: %s", exc)
        return

    try:
        threshold_pct = get_anti_greedy_profit_pct()
        trigger_kwargs = _daily_time_trigger_kwargs(get_anti_greedy_check_time())
    except Exception as exc:
        logger.error("Anti-greedy scheduler has invalid config: %s", exc)
        return

    if not trigger_kwargs:
        logger.error("Anti-greedy scheduler has invalid ANTI_GREEDY_CHECK_TIME")
        return

    if anti_greedy_scheduler:
        anti_greedy_scheduler.shutdown()

    shared_confirmation_service = _get_confirmation_service()
    scheduler = BackgroundScheduler(timezone="Europe/Moscow")
    scheduled_count = 0

    try:
        users = UserContextResolver().enabled_users()
    except Exception as exc:
        logger.error("Anti-greedy scheduler could not load users: %s", exc)
        return

    for user in users:
        session_factory = session_factory_for_user(user)
        token_provider = lambda user=user: user.active_token(get_invest_mode())
        mode_service = ModeService()
        broker = TInvestBroker(session_factory=session_factory)
        order_service = OrderService(
            broker=broker,
            mode_service=mode_service,
            token_provider=token_provider,
        )
        portfolio_service = PortfolioService(
            broker=broker,
            mode_service=mode_service,
            token_provider=token_provider,
        )
        policy_service = AntiGreedyPolicyService(
            portfolio_service=portfolio_service,
            broker=broker,
            token_provider=token_provider,
            threshold_pct=threshold_pct,
        )
        runner = AntiGreedyRunner(
            policy_service=policy_service,
            confirmation_service=shared_confirmation_service,
            order_service=order_service,
            telegram_chat_id=user.telegram_chat_id,
            notify_fn=lambda chat_id, text: bot.send_message(chat_id, text, parse_mode="Markdown"),
            send_confirmation_fn=auto_confirm_handler.send_anti_greedy_confirmation_message,
        )

        scheduler.add_job(
            runner.run,
            "cron",
            id=f"anti_greedy_{user.user_id}",
            replace_existing=True,
            **trigger_kwargs,
        )
        scheduled_count += 1

    scheduler.add_job(
        shared_confirmation_service.expire_old,
        "interval",
        minutes=5,
        id="anti_greedy_confirmation_expiry",
        replace_existing=True,
    )
    scheduler.start()
    anti_greedy_scheduler = scheduler
    logger.info(
        "Anti-greedy scheduler started with %d user job(s), threshold %.2f%%",
        scheduled_count,
        threshold_pct,
    )


def _get_confirmation_service():
    global confirmation_service

    from app.client.handlers.plans import auto_confirm_handler
    from app.services.plan_confirmation import PlanConfirmationService

    if confirmation_service is None:
        confirmation_service = PlanConfirmationService()
    auto_confirm_handler.plan_confirmation_service = confirmation_service
    return confirmation_service


def _daily_time_trigger_kwargs(time_text: str) -> dict:
    try:
        hour_text, minute_text = str(time_text).split(":", 1)
        hour = int(hour_text)
        minute = int(minute_text)
    except (TypeError, ValueError):
        return {}

    if hour < 0 or hour > 23 or minute < 0 or minute > 59:
        return {}
    return {"hour": hour, "minute": minute}


def _plan_trigger_kwargs(plan) -> dict:
    try:
        hour_text, minute_text = str(plan.time).split(":", 1)
        hour = int(hour_text)
        minute = int(minute_text)
    except (TypeError, ValueError):
        return {}

    if plan.schedule == "daily":
        return {"hour": hour, "minute": minute}

    try:
        next_run = datetime.fromisoformat(plan.next_run_at)
    except (TypeError, ValueError):
        return {}

    if plan.schedule == "weekly":
        return {"day_of_week": next_run.weekday(), "hour": hour, "minute": minute}

    if plan.schedule == "monthly":
        return {"day": next_run.day, "hour": hour, "minute": minute}

    return {}
