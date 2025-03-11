from db.db import get_t_token, update_signal_macd
from bot.bot import bot
from store.store import user_macd_data

@bot.callback_query_handler(func=lambda call: call.data == 'signal_macd')
def macd_handler(call):
    chat_id = call.message.chat.id
    token = get_t_token(chat_id)
    
    if token is not None:
        msg = bot.send_message(chat_id, "Введите период быстрой EMA:")
        bot.register_next_step_handler(msg, get_macd_fast)

def validate_number(value):
    """Проверка, что значение является целым числом от 1 до 100."""
    try:
        num = int(value)
        if num < 1 or num > 100:
            return False
        return True
    except ValueError:
        return False

def get_macd_fast(message):
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
    chat_id = message.chat.id
    signal_period = message.text
    
    if not validate_number(signal_period):
        msg = bot.send_message(chat_id, "Число должно быть целым, больше 0 и меньше 100. Попробуйте снова:")
        bot.register_next_step_handler(msg, get_macd_signal)
        return
    
    signal_period = int(signal_period)
    user_macd_data[chat_id]['signal_period'] = signal_period
    
    # Сохраняем настройки MACD и активируем стратегию
    fast_ema = user_macd_data[chat_id]['fast_ema']
    slow_ema = user_macd_data[chat_id]['slow_ema']

    update_signal_macd(chat_id, fast_ema, slow_ema, signal_period)
    
    bot.send_message(chat_id, 
                     f"Стратегия MACD настроена с параметрами:\n"
                     f"Период быстрой EMA: {fast_ema}\n"
                     f"Период медленной EMA: {slow_ema}\n"
                     f"Период сигнальной линии: {signal_period}")
    
    # Очищаем временные данные после использования
    del user_macd_data[chat_id]