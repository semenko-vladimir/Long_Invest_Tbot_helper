from db.db import get_t_token, update_signal_bollinger
from bot.bot import bot
from store.store import user_bollinger_data

@bot.callback_query_handler(func=lambda call: call.data == 'signal_bollinger')
def bollinger_handler(call):
    chat_id = call.message.chat.id
    token = get_t_token(chat_id)
    
    if token is not None:
        msg = bot.send_message(chat_id, "Введите период для расчета скользящей средней:")
        bot.register_next_step_handler(msg, get_bollinger_period)

def get_bollinger_period(message):
    chat_id = message.chat.id
    try:
        period = int(message.text)
        user_bollinger_data[chat_id] = {'period': period}  # Сохраняем период
        bot.send_message(chat_id, f"Вы выбрали период {period}. Теперь введите количество стандартных отклонений:")
        bot.register_next_step_handler(message, get_bollinger_stddev)
    except ValueError:
        msg = bot.send_message(chat_id, "Некорректный ввод. Введите числовое значение для периода:")
        bot.register_next_step_handler(msg, get_bollinger_period)

def get_bollinger_stddev(message):
    chat_id = message.chat.id
    try:
        stddev = float(message.text)
        user_bollinger_data[chat_id]['stddev'] = stddev  # Сохраняем количество стандартных отклонений
        bot.send_message(chat_id, f"Вы выбрали количество стандартных отклонений {stddev}. Теперь выберите тип скользящей средней (SMA или EMA):")
        bot.register_next_step_handler(message, get_bollinger_ma_type)
    except ValueError:
        msg = bot.send_message(chat_id, "Некорректный ввод. Введите числовое значение для стандартного отклонения:")
        bot.register_next_step_handler(msg, get_bollinger_stddev)

def get_bollinger_ma_type(message):
    chat_id = message.chat.id
    ma_type = message.text.strip().upper()
    if ma_type in ['SMA', 'EMA']:
        user_bollinger_data[chat_id]['ma_type'] = str(ma_type).lower()  
        period = user_bollinger_data[chat_id]['period']
        stddev = user_bollinger_data[chat_id]['stddev']
        
        # Обновление стратегии с параметрами
        update_signal_bollinger(chat_id, period, stddev, ma_type)

        # Подтверждение настроек стратегии
        bot.send_message(chat_id, 
                         f"Стратегия полос Боллинджера настроена с параметрами:\n"
                         f"Период: {period}\n"
                         f"Стандартные отклонения: {stddev}\n"
                         f"Тип скользящей средней: {ma_type}\n"
                        )

        # Очищаем временные данные
        del user_bollinger_data[chat_id]
    else:
        msg = bot.send_message(chat_id, "Некорректный ввод. Введите 'SMA' или 'EMA' для типа скользящей средней:")
        bot.register_next_step_handler(msg, get_bollinger_ma_type)