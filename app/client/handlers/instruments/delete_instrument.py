from telebot import types
from app.client.api.instruments_client import InstrumentsApiClient
from app.client.bot.bot import bot
from app.client.handlers.utils.message_utils import send_or_edit_message

instruments_client = InstrumentsApiClient()


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
        
        # Получаем список всех инструментов через API-клиент
        instruments = instruments_client.get_all_instruments()
        
        if not instruments:
            send_or_edit_message(chat_id, '❌ *Удаление инструмента*\n\nУ вас нет активных инструментов')
        else:
            inline_keyboard = types.InlineKeyboardMarkup()
            for instrument in instruments:
                ticker = instrument.get('ticker')
                button = types.InlineKeyboardButton(text=f"❌ {ticker}", callback_data=f'ticker_{ticker}')
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
        
        # Удаляем инструмент через API-клиент
        instruments_client.delete_instrument(ticker)
        send_or_edit_message(chat_id, f'✅ *Успешно*\n\nИнструмент `{ticker}` успешно удален')
    
    except Exception as e:
        send_or_edit_message(chat_id, f'❌ *Ошибка при удалении инструмента*\n\n`{str(e)}`')
