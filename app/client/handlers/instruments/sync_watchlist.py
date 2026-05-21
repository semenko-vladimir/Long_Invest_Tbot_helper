from app.client.bot.bot import bot
from app.client.handlers.user_context import get_telegram_services_or_notify
from app.client.handlers.utils.message_utils import send_or_edit_message
from app.services.watchlist import WatchlistSyncResult, format_watchlist_sync_summary


@bot.callback_query_handler(func=lambda call: call.data == 'sync_watchlist')
def sync_watchlist_handler(call):
    sync_watchlist_for_chat(call.message.chat.id)


@bot.message_handler(func=lambda message: str(message.text or "").strip().lower() == "sync_watchlist")
def sync_watchlist_command(message):
    sync_watchlist_for_chat(message.chat.id)


def sync_watchlist_for_chat(chat_id):
    send_or_edit_message(
        chat_id,
        '⏳ *Обработка запроса*\n\nСинхронизируем тикеры портфеля с watchlist...',
    )

    services = get_telegram_services_or_notify(chat_id)
    if services is None:
        return

    result = services.watchlist_service.sync_from_portfolio(services.portfolio_service)
    prefix = '✅ *Watchlist sync*\n\n' if result.ok else '❌ *Watchlist sync failed*\n\n'
    send_or_edit_message(chat_id, prefix + format_telegram_watchlist_sync_summary(result))


def format_telegram_watchlist_sync_summary(result: WatchlistSyncResult) -> str:
    return format_watchlist_sync_summary(result)
