from app.client.api.instruments_client import InstrumentsApiClient
from app.client.bot.bot import bot
from app.client.handlers.utils.message_utils import send_or_edit_message

instruments_client = InstrumentsApiClient()


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
        
        # Удаляем все инструменты через API-клиент
        result = instruments_client.delete_all_instruments()
        count = result.get('count', 0)
        send_or_edit_message(chat_id, f"🗑️ *Удаление инструментов*\n\n✅ Все инструменты были удалены\n\nВсего удалено: `{count}` инструментов")
    
    except Exception as e:
        send_or_edit_message(chat_id, f"❌ *Ошибка при удалении инструментов*\n\n`{str(e)}`")
