from app.client.bot.bot import bot
from app.client.config import get_investor_reminder_time, investor_reminders_enabled, require_env
from app.client.log.logger import setup_logger


logger = setup_logger(__name__)
investor_reminder_scheduler = None


def send_investor_reminder(chat_id: str):
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
        chat_id = require_env("CHAT_ID")
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
        investor_reminder_scheduler.add_job(
            send_investor_reminder,
            "cron",
            hour=hour,
            minute=minute,
            args=[chat_id],
            id="investor_daily_reminder",
            replace_existing=True,
        )
        investor_reminder_scheduler.start()
        logger.info("Investor reminder scheduled at %s Europe/Moscow", reminder_time)
    except ImportError:
        logger.error("Investor reminders require APScheduler. Install requirements-v1.txt.")
    except Exception as e:
        logger.error("Investor reminder scheduler failed: %s", str(e))
