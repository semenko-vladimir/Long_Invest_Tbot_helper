from telebot import types
from app.client.api.signals_client import SignalsApiClient
from app.client.bot.bot import bot
from app.client.handlers.utils.message_utils import send_or_edit_message

signals_client = SignalsApiClient()

# Временное хранилище для данных пользователя
user_sma_data = {}

@bot.callback_query_handler(func=lambda call: call.data == 'signal_sma')
def sma_handler(call):
    """
    Обработчик для настройки сигнала SMA.
    
    Запрашивает у пользователя параметры сигнала SMA.
    """
    chat_id = call.message.chat.id
    
    # Получаем текущие настройки SMA
    current_settings = signals_client.get_signal_sma()
    
    if current_settings:
        fast_length = current_settings.get('fastLength', 10)
        slow_length = current_settings.get('slowLength', 30)
        
        send_or_edit_message(
            chat_id, 
            f'📈 *Текущие настройки SMA*\n\n'
            f'• Быстрая SMA (Fast): `{fast_length}`\n'
            f'• Медленная SMA (Slow): `{slow_length}`'
        )
    
    # Запрашиваем быстрый период
    msg = send_or_edit_message(chat_id, '📈 *Настройка SMA*\n\nВведите период для быстрой SMA (рекомендуется 10):')
    bot.register_next_step_handler(msg, get_fast_sma)


def validate_number(value):
    """
    Проверка, что значение является целым числом от 1 до 200.
    
    Args:
        value: Проверяемое значение
        
    Returns:
        bool: True, если значение валидно, иначе False
    """
    try:
        num = int(value)
        if num < 1 or num > 200:
            return False
        return True
    except ValueError:
        return False


def get_fast_sma(message):
    """
    Обработчик для получения периода быстрой SMA.
    
    Сохраняет период и запрашивает период медленной SMA.
    """
    chat_id = message.chat.id
    fast_length = message.text
    
    if not validate_number(fast_length):
        msg = send_or_edit_message(chat_id, "❌ *Ошибка ввода*\n\nЧисло должно быть целым, больше 0 и меньше 200. Попробуйте снова:")
        bot.register_next_step_handler(msg, get_fast_sma)
        return
    
    fast_length = int(fast_length)
    user_sma_data[chat_id] = {'fast_length': fast_length}
    msg = send_or_edit_message(chat_id, f"✅ Вы выбрали период быстрой SMA: `{fast_length}`\n\n*Введите период для медленной SMA:*")
    bot.register_next_step_handler(msg, get_slow_sma)


def get_slow_sma(message):
    """
    Обработчик для получения периода медленной SMA.
    
    Сохраняет период и обновляет настройки сигнала SMA.
    """
    chat_id = message.chat.id
    slow_length = message.text
    
    if not validate_number(slow_length):
        msg = send_or_edit_message(chat_id, "❌ *Ошибка ввода*\n\nЧисло должно быть целым, больше 0 и меньше 200. Попробуйте снова:")
        bot.register_next_step_handler(msg, get_slow_sma)
        return
    
    slow_length = int(slow_length)
    fast_length = user_sma_data[chat_id]['fast_length']
    
    if slow_length <= fast_length:
        msg = send_or_edit_message(chat_id, "❌ *Ошибка ввода*\n\nПериод медленной SMA должен быть больше периода быстрой SMA. Попробуйте снова:")
        bot.register_next_step_handler(msg, get_slow_sma)
        return
    
    try:
        # Обновляем параметры через API-клиент
        result = signals_client.update_signal_sma(fast_length, slow_length)
        
        # Подтверждение настройки стратегии
        send_or_edit_message(
            chat_id, 
            f"✅ *Стратегия SMA успешно настроена*\n\n"
            f"• Быстрая SMA (Fast): `{fast_length}`\n"
            f"• Медленная SMA (Slow): `{slow_length}`"
        )
    
    except Exception as e:
        send_or_edit_message(chat_id, f"❌ *Ошибка при обновлении настроек SMA*\n\n`{str(e)}`")
    
    # Очищаем временные данные после использования
    del user_sma_data[chat_id]
