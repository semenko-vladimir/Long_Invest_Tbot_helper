from app.client.api.instruments_client import InstrumentsApiClient
from app.client.bot.bot import bot
from app.client.handlers.utils.message_utils import send_or_edit_message

instruments_client = InstrumentsApiClient()


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
        
        # Получаем список всех инструментов через API-клиент
        instruments = instruments_client.get_all_instruments()
        
        if not instruments:
            send_or_edit_message(chat_id, '📋 *Список инструментов*\n\n❌ У вас нет активных инструментов')
        else:
            text = "📋 *СПИСОК ИНСТРУМЕНТОВ*\n\n"
            for i, instrument in enumerate(instruments, 1):
                ticker = instrument.get('ticker')
                figi = instrument.get('figi')
                text += f"{i}. *{ticker}*\n   FIGI: `{figi}`\n\n"
            
            send_or_edit_message(chat_id, text)
    
    except Exception as e:
        send_or_edit_message(chat_id, f'❌ *Ошибка при получении списка инструментов*\n\n`{str(e)}`')
