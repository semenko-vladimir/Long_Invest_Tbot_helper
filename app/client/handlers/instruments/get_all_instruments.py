from app.client.api.instruments_client import InstrumentsApiClient
from app.client.bot.bot import bot

instruments_client = InstrumentsApiClient()


@bot.callback_query_handler(func=lambda call: call.data == 'get_all_instruments')
def get_all_instruments_handler(call):
    """
    Обработчик для получения списка всех инструментов.
    
    Отображает список всех доступных инструментов.
    """
    chat_id = call.message.chat.id
    
    try:
        # Получаем список всех инструментов через API-клиент
        instruments = instruments_client.get_all_instruments()
        
        if not instruments:
            bot.send_message(chat_id, 'У вас нет активных инструментов')
        else:
            text = "Ваши инструменты:\n"
            for instrument in instruments:
                ticker = instrument.get('ticker')
                figi = instrument.get('figi')
                text += f"{ticker} (FIGI: {figi})\n"
            
            bot.send_message(chat_id, text)
    
    except Exception as e:
        bot.send_message(chat_id, f'Ошибка при получении списка инструментов: {str(e)}')
