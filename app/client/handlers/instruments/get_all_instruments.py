from app.client.bot.bot import bot
from app.client.handlers.user_context import get_telegram_services_or_notify
from app.client.handlers.utils.message_utils import send_or_edit_message


@bot.callback_query_handler(func=lambda call: call.data == 'get_all_instruments')
def get_all_instruments_handler(call):
    """
    Обработчик для получения списка всех инструментов.
    
    Отображает список всех доступных инструментов.
    """
    chat_id = call.message.chat.id
    
    try:
        # Отправляем сообщение о начале обработки
        send_or_edit_message(chat_id, '⏳ *Обработка запроса*\n\nПолучаем список инструментов...')

        services = get_telegram_services_or_notify(chat_id)
        if services is None:
            return

        watchlist = services.watchlist_service.list_items()
        if watchlist.error:
            send_or_edit_message(chat_id, f'❌ *Ошибка при получении списка инструментов*\n\n`{watchlist.error}`')
            return

        if not watchlist.items:
            send_or_edit_message(chat_id, '📋 *Список инструментов*\n\n❌ У вас нет активных инструментов')
        else:
            text = "📋 *СПИСОК ИНСТРУМЕНТОВ*\n\n"
            for i, instrument in enumerate(watchlist.items, 1):
                text += f"{i}. *{instrument.ticker}*\n   FIGI: `{instrument.figi}`\n\n"
            
            send_or_edit_message(chat_id, text)
    
    except Exception as e:
        send_or_edit_message(chat_id, f'❌ *Ошибка при получении списка инструментов*\n\n`{str(e)}`')
