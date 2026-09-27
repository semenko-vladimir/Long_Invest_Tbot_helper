from app.client.log.logger import setup_logger


logger = setup_logger(__name__)
monitoring_scheduler = None


def configure_monitoring_scheduler():
    """Start read-only polling; disabled subscriptions do no network work."""
    global monitoring_scheduler
    from apscheduler.schedulers.background import BackgroundScheduler

    from app.client.bot.bot import bot
    from app.client.config.users import load_runtime_users_config
    from app.services.monitoring import MonitoringRunner
    from app.services.user_context import UserContext
    from app.client.handlers.monitoring_handler import send_cached_chart

    if monitoring_scheduler is not None:
        monitoring_scheduler.shutdown(wait=False)
    scheduler = BackgroundScheduler(timezone="Europe/Moscow")
    for config in load_runtime_users_config().enabled_users:
        user = UserContext.from_config(config)
        runner = MonitoringRunner(
            user,
            send_text=lambda chat_id, message: bot.send_message(chat_id, message, disable_web_page_preview=True),
            send_chart=send_cached_chart,
        )
        scheduler.add_job(runner.run, "interval", minutes=5, id=f"monitoring_{user.user_id}",
                          replace_existing=True, max_instances=1, coalesce=True)
    scheduler.start()
    monitoring_scheduler = scheduler
    logger.info("Read-only monitoring scheduler started for %d users", len(load_runtime_users_config().enabled_users))
