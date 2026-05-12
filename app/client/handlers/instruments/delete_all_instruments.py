from app.client.bot.bot import bot
from app.client.handlers.user_context import get_telegram_services_or_notify
from app.client.handlers.utils.message_utils import send_or_edit_message


@bot.callback_query_handler(func=lambda call: call.data == 'delete_all_instruments')
def delete_all_instruments_handler(call):
    """
    Обработчик для удаления всех инструментов.
    
    Удаляет все инструменты из базы данных.
    """
    chat_id = call.message.chat.id
    
    try:
        # Отправляем сообщение о начале обработки
        send_or_edit_message(chat_id, '⏳ *Обработка запроса*\n\nУдаляем все инструменты...')

        services = get_telegram_services_or_notify(chat_id)
        if services is None:
            return

        watchlist = services.watchlist_service.clear()
        if watchlist.error:
            send_or_edit_message(chat_id, f"❌ *Ошибка при удалении инструментов*\n\n`{watchlist.error}`")
            return

        send_or_edit_message(chat_id, f"🗑️ *Удаление инструментов*\n\n✅ {watchlist.notice}\n")
    
    except Exception as e:
        send_or_edit_message(chat_id, f"❌ *Ошибка при удалении инструментов*\n\n`{str(e)}`")
