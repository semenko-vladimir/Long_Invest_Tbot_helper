from telebot import types
from app.client.api.signals_client import SignalsApiClient
from app.client.bot.bot import bot
from app.client.handlers.utils.message_utils import send_or_edit_message

signals_client = SignalsApiClient()


# Временное хранилище для данных пользователя
user_rsi_data = {}


@bot.callback_query_handler(func=lambda call: call.data == 'signal_rsi')
def rsi_handler(call):
    """
    Обработчик для настройки сигнала RSI.
    
    Запрашивает у пользователя параметры сигнала RSI.
    """
    chat_id = call.message.chat.id
    
    # Получаем текущие настройки RSI
    current_settings = signals_client.get_signal_rsi()
    
    if current_settings:
        period = current_settings.get('period', 14)
        high_level = current_settings.get('hightLevel', 70)
        low_level = current_settings.get('lowLevel', 30)
        
        send_or_edit_message(
            chat_id, 
            f'📊 *Текущие настройки RSI*\n\n'
            f'• Период: `{period}`\n'
            f'• Верхний уровень: `{high_level}`\n'
            f'• Нижний уровень: `{low_level}`'
        )
    
    # Запрашиваем период
    msg = send_or_edit_message(chat_id, '📊 *Настройка RSI*\n\nВведите период для RSI (рекомендуется 14):')
    bot.register_next_step_handler(msg, get_rsi_period)


def validate_number(value):
    """
    Проверка, что значение является целым числом от 1 до 100.
    
    Args:
        value: Проверяемое значение
        
    Returns:
        bool: True, если значение валидно, иначе False
    """
    try:
        num = int(value)
        if num < 1 or num > 100:
            return False
        return True
    except ValueError:
        return False


def get_rsi_period(message):
    """
    Обработчик для получения периода RSI.
    
    Сохраняет период и запрашивает уровень перекупленности.
    """
    chat_id = message.chat.id
    period = message.text
    
    if not validate_number(period):
        msg = send_or_edit_message(chat_id, "❌ *Ошибка ввода*\n\nЧисло должно быть целым, больше 0 и меньше 100. Попробуйте снова:")
        bot.register_next_step_handler(msg, get_rsi_period)
        return
    
    period = int(period)
    user_rsi_data[chat_id] = {'period': period}  # Сохраняем период
    msg = send_or_edit_message(chat_id, f"✅ Вы выбрали период `{period}`\n\n*Введите уровень перекупленности:*")
    bot.register_next_step_handler(msg, get_rsi_overbought)


def get_rsi_overbought(message):
    """
    Обработчик для получения уровня перекупленности RSI.
    
    Сохраняет уровень перекупленности и запрашивает уровень перепроданности.
    """
    chat_id = message.chat.id
    overbought = message.text
    
    if not validate_number(overbought):
        msg = send_or_edit_message(chat_id, "❌ *Ошибка ввода*\n\nЧисло должно быть целым, больше 0 и меньше 100. Попробуйте снова:")
        bot.register_next_step_handler(msg, get_rsi_overbought)
        return
    
    overbought = int(overbought)
    user_rsi_data[chat_id]['overbought'] = overbought  # Сохраняем уровень перекупленности
    msg = send_or_edit_message(chat_id, f"✅ Вы выбрали уровень перекупленности `{overbought}`\n\n*Введите уровень перепроданности:*")
    bot.register_next_step_handler(msg, get_rsi_oversold)


def get_rsi_oversold(message):
    """
    Обработчик для получения уровня перепроданности RSI.
    
    Сохраняет уровень перепроданности и обновляет настройки сигнала RSI.
    """
    chat_id = message.chat.id
    oversold = message.text
    
    if not validate_number(oversold):
        msg = send_or_edit_message(chat_id, "❌ *Ошибка ввода*\n\nЧисло должно быть целым, больше 0 и меньше 100. Попробуйте снова:")
        bot.register_next_step_handler(msg, get_rsi_oversold)
        return
    
    oversold = int(oversold)
    user_rsi_data[chat_id]['oversold'] = oversold  # Сохраняем уровень перепроданности

    period = user_rsi_data[chat_id]['period']
    overbought = user_rsi_data[chat_id]['overbought']
    
    try:
        # Обновляем параметры через API-клиент
        result = signals_client.update_signal_rsi(period, overbought, oversold)
        
        # Подтверждение настройки стратегии
        send_or_edit_message(
            chat_id, 
            f"✅ *Стратегия RSI успешно настроена*\n\n"
            f"• Период: `{period}`\n"
            f"• Перекупленность: `{overbought}`\n"
            f"• Перепроданность: `{oversold}`"
        )
    
    except Exception as e:
        send_or_edit_message(chat_id, f"❌ *Ошибка при обновлении настроек RSI*\n\n`{str(e)}`")
    
    # Очищаем временные данные после использования
    del user_rsi_data[chat_id]
