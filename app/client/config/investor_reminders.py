from app.client.bot.bot import bot
from app.client.config import get_investor_reminder_time, investor_reminders_enabled
from app.client.log.logger import setup_logger
from app.services.user_context import UserContextResolver


logger = setup_logger(__name__)
investor_reminder_scheduler = None


def send_investor_reminder(chat_id: int):
    text = (
        "*Investor reminder*\n\n"
        "A calm check-in for your long-term portfolio:\n"
        "- Review `Portfolio`\n"
        "- Check `Dividends`\n"
        "- Update `Watchlist`\n"
        "- Open `Stats` if you made manual trades\n\n"
        "No signals or auto-trading are used."
    )
    bot.send_message(chat_id, text, parse_mode="Markdown")


def configure_investor_reminders():
    global investor_reminder_scheduler

    if not investor_reminders_enabled():
        logger.info("Investor reminders disabled")
        return

    try:
        users = UserContextResolver().enabled_users()
    except Exception as e:
        logger.error("Investor reminder configuration failed: %s", str(e))
        return

    if not users:
        logger.warning("Investor reminders enabled but no users are configured.")
        return

    try:
        reminder_time = get_investor_reminder_time()
        hour_text, minute_text = reminder_time.split(":", 1)
        hour = int(hour_text)
        minute = int(minute_text)

        if not (0 <= hour <= 23 and 0 <= minute <= 59):
            raise ValueError
    except ValueError:
        logger.error("Invalid INVESTOR_REMINDER_TIME. Use HH:MM, for example 09:00.")
        return
    except Exception as e:
        logger.error("Investor reminder configuration failed: %s", str(e))
        return

    try:
        from apscheduler.schedulers.background import BackgroundScheduler

        if investor_reminder_scheduler:
            investor_reminder_scheduler.shutdown()

        investor_reminder_scheduler = BackgroundScheduler(timezone="Europe/Moscow")
        for user in users:
            investor_reminder_scheduler.add_job(
                send_investor_reminder,
                "cron",
                hour=hour,
                minute=minute,
                args=[user.telegram_chat_id],
                id=f"investor_daily_reminder_{user.user_id}",
                replace_existing=True,
            )
        investor_reminder_scheduler.start()
        logger.info(
            "Investor reminder scheduled at %s Europe/Moscow for %d user(s)",
            reminder_time,
            len(users),
        )
    except ImportError:
        logger.error("Investor reminders require APScheduler. Install requirements-v1.txt.")
    except Exception as e:
        logger.error("Investor reminder scheduler failed: %s", str(e))
