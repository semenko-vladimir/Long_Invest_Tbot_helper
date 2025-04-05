from app.client.api.instruments_client import InstrumentsApiClient
from app.client.bot.bot import bot

instruments_client = InstrumentsApiClient()


@bot.callback_query_handler(func=lambda call: call.data == 'delete_all_instruments')
def delete_all_instruments_handler(call):
    """
    Обработчик для удаления всех инструментов.
    
    Удаляет все инструменты из базы данных.
    """
    chat_id = call.message.chat.id
    
    try:
        # Удаляем все инструменты через API-клиент
        result = instruments_client.delete_all_instruments()
        count = result.get('count', 0)
        bot.send_message(chat_id, f"Все инструменты были удалены (всего: {count})")
    
    except Exception as e:
        bot.send_message(chat_id, f"Ошибка при удалении инструментов: {str(e)}")
