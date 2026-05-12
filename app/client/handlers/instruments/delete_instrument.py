from telebot import types
from app.client.bot.bot import bot
from app.client.handlers.user_context import get_telegram_services_or_notify
from app.client.handlers.utils.message_utils import send_or_edit_message


@bot.callback_query_handler(func=lambda call: call.data == 'delete_instrument')
def delete_instrument_handler(call):
    """
    Обработчик для удаления инструмента.
    
    Отображает список доступных инструментов для удаления.
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
            send_or_edit_message(chat_id, '❌ *Удаление инструмента*\n\nУ вас нет активных инструментов')
        else:
            inline_keyboard = types.InlineKeyboardMarkup()
            for instrument in watchlist.items:
                button = types.InlineKeyboardButton(text=f"❌ {instrument.ticker}", callback_data=f'ticker_{instrument.ticker}')
                inline_keyboard.add(button)
            
            send_or_edit_message(
                chat_id, 
                '🗑️ *Удаление инструмента*\n\nВыберите инструмент для удаления:', 
                reply_markup=inline_keyboard
            )
    
    except Exception as e:
        send_or_edit_message(chat_id, f'❌ *Ошибка при получении списка инструментов*\n\n`{str(e)}`')


@bot.callback_query_handler(func=lambda call: call.data.startswith('ticker_'))
def delete_ticker_step(call):
    """
    Обработчик для удаления выбранного инструмента.
    
    Удаляет инструмент по выбранному тикеру.
    """
    chat_id = call.message.chat.id
    ticker = call.data.replace('ticker_', '')
    
    try:
        # Отправляем сообщение о начале обработки
        send_or_edit_message(chat_id, f'⏳ *Обработка запроса*\n\nУдаляем инструмент `{ticker}`...')

        services = get_telegram_services_or_notify(chat_id)
        if services is None:
            return

        watchlist = services.watchlist_service.remove_ticker(ticker)
        if watchlist.error:
            send_or_edit_message(chat_id, f'❌ *Ошибка при удалении инструмента*\n\n`{watchlist.error}`')
            return

        send_or_edit_message(chat_id, f'✅ *Успешно*\n\n{watchlist.notice or f"Инструмент `{ticker}` успешно удален"}')
    
    except Exception as e:
        send_or_edit_message(chat_id, f'❌ *Ошибка при удалении инструмента*\n\n`{str(e)}`')
