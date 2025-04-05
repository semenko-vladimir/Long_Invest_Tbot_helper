from telebot import types
from app.client.api.signals_client import SignalsApiClient
from app.client.bot.bot import bot

signals_client = SignalsApiClient()


# Временное хранилище для данных пользователя
user_macd_data = {}


@bot.callback_query_handler(func=lambda call: call.data == 'signal_macd')
def macd_handler(call):
    """
    Обработчик для настройки сигнала MACD.
    
    Запрашивает у пользователя параметры сигнала MACD.
    """
    chat_id = call.message.chat.id
    
    # Получаем текущие настройки MACD
    current_settings = signals_client.get_signal_macd()
    
    if current_settings:
        fast_length = current_settings.get('fastLength', 12)
        slow_length = current_settings.get('slowLength', 26)
        signal_length = current_settings.get('signalLength', 9)
        
        bot.send_message(
            chat_id, 
            f'Текущие настройки MACD:\n'
            f'Период быстрой EMA: {fast_length}\n'
            f'Период медленной EMA: {slow_length}\n'
            f'Период сигнальной линии: {signal_length}'
        )
    
    # Запрашиваем период быстрой EMA
    msg = bot.send_message(chat_id, "Введите период быстрой EMA:")
    bot.register_next_step_handler(msg, get_macd_fast)


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


def get_macd_fast(message):
    """
    Обработчик для получения периода быстрой EMA для MACD.
    
    Сохраняет период быстрой EMA и запрашивает период медленной EMA.
    """
    chat_id = message.chat.id
    fast_ema_period = message.text
    
    if not validate_number(fast_ema_period):
        msg = bot.send_message(chat_id, "Число должно быть целым, больше 0 и меньше 100. Попробуйте снова:")
        bot.register_next_step_handler(msg, get_macd_fast)
        return
    
    fast_ema_period = int(fast_ema_period)
    user_macd_data[chat_id] = {'fast_ema': fast_ema_period}
    bot.send_message(chat_id, f"Вы выбрали период быстрой EMA: {fast_ema_period}. Теперь введите период медленной EMA:")
    bot.register_next_step_handler(message, get_macd_slow)


def get_macd_slow(message):
    """
    Обработчик для получения периода медленной EMA для MACD.
    
    Сохраняет период медленной EMA и запрашивает период сигнальной линии.
    """
    chat_id = message.chat.id
    slow_ema_period = message.text
    
    if not validate_number(slow_ema_period):
        msg = bot.send_message(chat_id, "Число должно быть целым, больше 0 и меньше 100. Попробуйте снова:")
        bot.register_next_step_handler(msg, get_macd_slow)
        return
    
    slow_ema_period = int(slow_ema_period)
    user_macd_data[chat_id]['slow_ema'] = slow_ema_period
    bot.send_message(chat_id, f"Вы выбрали период медленной EMA: {slow_ema_period}. Теперь введите период сигнальной линии:")
    bot.register_next_step_handler(message, get_macd_signal)


def get_macd_signal(message):
    """
    Обработчик для получения периода сигнальной линии для MACD.
    
    Сохраняет период сигнальной линии и обновляет настройки сигнала MACD.
    """
    chat_id = message.chat.id
    signal_period = message.text
    
    if not validate_number(signal_period):
        msg = bot.send_message(chat_id, "Число должно быть целым, больше 0 и меньше 100. Попробуйте снова:")
        bot.register_next_step_handler(msg, get_macd_signal)
        return
    
    signal_period = int(signal_period)
    user_macd_data[chat_id]['signal_period'] = signal_period
    
    # Получаем все введённые параметры
    fast_ema = user_macd_data[chat_id]['fast_ema']
    slow_ema = user_macd_data[chat_id]['slow_ema']
    
    try:
        # Обновляем параметры через API-клиент
        result = signals_client.update_signal_macd(fast_ema, slow_ema, signal_period)
        
        # Подтверждение настройки стратегии
        bot.send_message(
            chat_id, 
            f"Стратегия MACD настроена с параметрами:\n"
            f"Период быстрой EMA: {fast_ema}\n"
            f"Период медленной EMA: {slow_ema}\n"
            f"Период сигнальной линии: {signal_period}"
        )
    
    except Exception as e:
        bot.send_message(chat_id, f"Ошибка при обновлении настроек MACD: {str(e)}")
    
    # Очищаем временные данные после использования
    del user_macd_data[chat_id]
