from telebot import types
from app.client.api.signals_client import SignalsApiClient
from app.client.bot.bot import bot
from app.client.handlers.utils.message_utils import send_or_edit_message

signals_client = SignalsApiClient()


# Временное хранилище для данных пользователя
user_bollinger_data = {}


@bot.callback_query_handler(func=lambda call: call.data == 'signal_bollinger')
def bollinger_handler(call):
    """
    Обработчик для настройки сигнала Bollinger Bands.
    
    Запрашивает у пользователя параметры сигнала Bollinger Bands.
    """
    chat_id = call.message.chat.id
    
    # Получаем текущие настройки Bollinger
    current_settings = signals_client.get_signal_bollinger()
    
    if current_settings:
        period = current_settings.get('period', 20)
        deviation = current_settings.get('deviation', 2)
        type_ma = current_settings.get('type_ma', 'sma')
        
        send_or_edit_message(
            chat_id, 
            f'📊 *Текущие настройки Bollinger Bands*\n\n'
            f'• Период: `{period}`\n'
            f'• Стандартные отклонения: `{deviation}`\n'
            f'• Тип скользящей средней: `{type_ma.upper()}`'
        )
    
    # Запрашиваем период
    msg = send_or_edit_message(chat_id, "📊 *Настройка Bollinger Bands*\n\nВведите период для расчета скользящей средней:")
    bot.register_next_step_handler(msg, get_bollinger_period)


def validate_number(value, min_value=None, max_value=None):
    """
    Проверка, что значение является целым числом с возможной дополнительной проверкой на диапазон.
    
    Args:
        value: Проверяемое значение
        min_value: Минимальное допустимое значение (опционально)
        max_value: Максимальное допустимое значение (опционально)
        
    Returns:
        bool: True, если значение валидно, иначе False
    """
    try:
        num = int(value)
        
        # Проверка на диапазон
        if min_value is not None and num < min_value:
            return False
        if max_value is not None and num > max_value:
            return False
        
        return True
    except ValueError:
        return False


def get_bollinger_period(message):
    """
    Обработчик для получения периода Bollinger Bands.
    
    Сохраняет период и запрашивает количество стандартных отклонений.
    """
    chat_id = message.chat.id
    period = message.text
    
    if not validate_number(period, min_value=1, max_value=100):
        msg = send_or_edit_message(chat_id, "❌ *Ошибка ввода*\n\nПериод должен быть целым числом от 1 до 100. Попробуйте снова:")
        bot.register_next_step_handler(msg, get_bollinger_period)
        return
    
    period = int(period)
    user_bollinger_data[chat_id] = {'period': period}  # Сохраняем период
    msg = send_or_edit_message(chat_id, f"✅ Вы выбрали период `{period}`.\n\n*Введите количество стандартных отклонений:*")
    bot.register_next_step_handler(msg, get_bollinger_stddev)


def get_bollinger_stddev(message):
    """
    Обработчик для получения количества стандартных отклонений Bollinger Bands.
    
    Сохраняет количество стандартных отклонений и запрашивает тип скользящей средней.
    """
    chat_id = message.chat.id
    stddev = message.text
    
    try:
        stddev = float(stddev)
        if stddev <= 0:
            raise ValueError("Количество стандартных отклонений должно быть положительным числом")
        
        user_bollinger_data[chat_id]['stddev'] = stddev  # Сохраняем количество стандартных отклонений
        msg = send_or_edit_message(chat_id, f"✅ Вы выбрали количество стандартных отклонений `{stddev}`.\n\n*Выберите тип скользящей средней (SMA или EMA):*")
        bot.register_next_step_handler(msg, get_bollinger_ma_type)
    
    except ValueError as e:
        msg = send_or_edit_message(chat_id, f"❌ *Ошибка ввода*\n\n{str(e)}. Попробуйте снова:")
        bot.register_next_step_handler(msg, get_bollinger_stddev)


def get_bollinger_ma_type(message):
    """
    Обработчик для получения типа скользящей средней Bollinger Bands.
    
    Сохраняет тип скользящей средней и обновляет настройки сигнала Bollinger Bands.
    """
    chat_id = message.chat.id
    ma_type = message.text.strip().upper()
    
    if ma_type not in ['SMA', 'EMA']:
        msg = send_or_edit_message(chat_id, "❌ *Ошибка ввода*\n\nНекорректный ввод. Введите 'SMA' или 'EMA' для типа скользящей средней:")
        bot.register_next_step_handler(msg, get_bollinger_ma_type)
        return
    
    user_bollinger_data[chat_id]['ma_type'] = ma_type.lower()  # Сохраняем тип скользящей средней
    period = user_bollinger_data[chat_id]['period']
    stddev = user_bollinger_data[chat_id]['stddev']
    ma_type = user_bollinger_data[chat_id]['ma_type']
    
    try:
        # Обновляем параметры через API-клиент
        result = signals_client.update_signal_bollinger(period, stddev, ma_type)
        
        # Подтверждение настроек стратегии
        send_or_edit_message(
            chat_id, 
            f"✅ *Стратегия полос Боллинджера успешно настроена*\n\n"
            f"• Период: `{period}`\n"
            f"• Стандартные отклонения: `{stddev}`\n"
            f"• Тип скользящей средней: `{ma_type.upper()}`"
        )
    
    except Exception as e:
        send_or_edit_message(chat_id, f"❌ *Ошибка при обновлении настроек*\n\n`{str(e)}`")
    
    # Очищаем временные данные
    del user_bollinger_data[chat_id]
