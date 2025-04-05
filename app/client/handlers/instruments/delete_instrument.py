from telebot import types
from app.client.api.instruments_client import InstrumentsApiClient
from app.client.bot.bot import bot

instruments_client = InstrumentsApiClient()


@bot.callback_query_handler(func=lambda call: call.data == 'delete_instrument')
def delete_instrument_handler(call):
    """
    Обработчик для удаления инструмента.
    
    Отображает список доступных инструментов для удаления.
    """
    chat_id = call.message.chat.id
    
    try:
        # Получаем список всех инструментов через API-клиент
        instruments = instruments_client.get_all_instruments()
        
        if not instruments:
            bot.send_message(chat_id, 'У вас нет активных инструментов')
        else:
            inline_keyboard = types.InlineKeyboardMarkup()
            for instrument in instruments:
                ticker = instrument.get('ticker')
                button = types.InlineKeyboardButton(text=ticker, callback_data=f'ticker_{ticker}')
                inline_keyboard.add(button)
            
            bot.send_message(chat_id, 'Выберите инструмент для удаления', reply_markup=inline_keyboard)
    
    except Exception as e:
        bot.send_message(chat_id, f'Ошибка при получении списка инструментов: {str(e)}')


@bot.callback_query_handler(func=lambda call: call.data.startswith('ticker_'))
def delete_ticker_step(call):
    """
    Обработчик для удаления выбранного инструмента.
    
    Удаляет инструмент по выбранному тикеру.
    """
    chat_id = call.message.chat.id
    ticker = call.data.replace('ticker_', '')
    
    try:
        # Удаляем инструмент через API-клиент
        instruments_client.delete_instrument(ticker)
        bot.send_message(chat_id, f'Инструмент "{ticker}" успешно удален')
    
    except Exception as e:
        bot.send_message(chat_id, f'Ошибка при удалении инструмента: {str(e)}')
