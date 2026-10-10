"""Independent scheduler for read-only statistics and opted-in stock updates."""

from io import BytesIO
import logging


logger = logging.getLogger(__name__)
stock_scheduler = None


def configure_stock_scheduler():
    global stock_scheduler
    from apscheduler.schedulers.background import BackgroundScheduler
    from app.client.bot.bot import bot
    from app.client.config.users import load_runtime_users_config
    from app.client.handlers.user_context import get_telegram_services

    if stock_scheduler is not None:
        stock_scheduler.shutdown(wait=False)
    scheduler = BackgroundScheduler(timezone="Europe/Moscow")

    def photo(chat_id, png, caption):
        stream = BytesIO(png)
        stream.name = "stock.png"
        return bot.send_photo(chat_id, stream, caption=caption)

    for user in load_runtime_users_config().enabled_users:
        services = get_telegram_services(user.telegram_chat_id)
        tracker = services.stock_tracking_service
        tracker.send_text = lambda chat_id, text: bot.send_message(chat_id, text)
        tracker.send_photo = photo

        def tick(services=services):
            try:
                services.stock_market_service.poll()
                services.stock_tracking_service.run()
            except Exception as exc:
                logger.warning("Stock refresh unavailable user_id=%s error=%s", services.user.user_id, type(exc).__name__)

        scheduler.add_job(tick, "interval", minutes=1, id=f"stock_updates_{user.user_id}",
            max_instances=1, coalesce=True, misfire_grace_time=60)
    scheduler.start()
    stock_scheduler = scheduler
