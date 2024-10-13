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

def get_macd_fast(message):
    chat_id = message.chat.id
    try:
        fast_ema_period = int(message.text)
        user_macd_data[chat_id] = {'fast_ema': fast_ema_period}
        bot.send_message(chat_id, f"Вы выбрали период быстрой EMA: {fast_ema_period}. Теперь введите период медленной EMA:")
        bot.register_next_step_handler(message, get_macd_slow)
    except ValueError:
        msg = bot.send_message(chat_id, "Некорректный ввод. Введите числовое значение для периода быстрой EMA:")
        bot.register_next_step_handler(msg, get_macd_fast)

def get_macd_slow(message):
    chat_id = message.chat.id
    try:
        slow_ema_period = int(message.text)
        user_macd_data[chat_id]['slow_ema'] = slow_ema_period
        bot.send_message(chat_id, f"Вы выбрали период медленной EMA: {slow_ema_period}. Теперь введите период сигнальной линии:")
        bot.register_next_step_handler(message, get_macd_signal)
    except ValueError:
        msg = bot.send_message(chat_id, "Некорректный ввод. Введите числовое значение для периода медленной EMA:")
        bot.register_next_step_handler(msg, get_macd_slow)

def get_macd_signal(message):
    chat_id = message.chat.id
    try:
        signal_period = int(message.text)
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
        
    except ValueError:
        msg = bot.send_message(chat_id, "Некорректный ввод. Введите числовое значение для периода сигнальной линии:")
        bot.register_next_step_handler(msg, get_macd_signal)