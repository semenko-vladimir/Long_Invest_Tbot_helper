from db.db import get_t_token, update_signal_rsi
from bot.bot import bot
from store.store import user_rsi_data


@bot.callback_query_handler(func=lambda call: call.data == 'signal_rsi')
def rsi_handler(call):
    chat_id = call.message.chat.id
    token = get_t_token(chat_id)
    
    if token is not None:
        msg = bot.send_message(chat_id, "Введите период RSI:")
        bot.register_next_step_handler(msg, get_rsi_period)

def validate_number(value):
    """Проверка, что значение является целым числом от 1 до 100."""
    try:
        num = int(value)
        if num < 1 or num > 100:
            return False
        return True
    except ValueError:
        return False

def get_rsi_period(message):
    chat_id = message.chat.id
    period = message.text
    
    if not validate_number(period):
        msg = bot.send_message(chat_id, "Число должно быть целым, больше 0 и меньше 100. Попробуйте снова:")
        bot.register_next_step_handler(msg, get_rsi_period)
        return
    
    period = int(period)
    user_rsi_data[chat_id] = {'period': period}  # Сохраняем период
    bot.send_message(chat_id, f"Вы выбрали период {period}. Теперь введите уровень перекупленности:")
    bot.register_next_step_handler(message, get_rsi_overbought)

def get_rsi_overbought(message):
    chat_id = message.chat.id
    overbought = message.text
    
    if not validate_number(overbought):
        msg = bot.send_message(chat_id, "Число должно быть целым, больше 0 и меньше 100. Попробуйте снова:")
        bot.register_next_step_handler(msg, get_rsi_overbought)
        return
    
    overbought = int(overbought)
    user_rsi_data[chat_id]['overbought'] = overbought  # Сохраняем уровень перекупленности
    bot.send_message(chat_id, f"Вы выбрали уровень перекупленности {overbought}. Теперь введите уровень перепроданности:")
    bot.register_next_step_handler(message, get_rsi_oversold)

def get_rsi_oversold(message):
    chat_id = message.chat.id
    oversold = message.text
    
    if not validate_number(oversold):
        msg = bot.send_message(chat_id, "Число должно быть целым, больше 0 и меньше 100. Попробуйте снова:")
        bot.register_next_step_handler(msg, get_rsi_oversold)
        return
    
    oversold = int(oversold)
    user_rsi_data[chat_id]['oversold'] = oversold  # Сохраняем уровень перепроданности

    period = user_rsi_data[chat_id]['period']
    overbought = user_rsi_data[chat_id]['overbought']
    oversold = user_rsi_data[chat_id]['oversold']

    update_signal_rsi(chat_id, period, overbought, oversold)
    
    # Подтверждение настройки стратегии
    bot.send_message(chat_id, f"Стратегия RSI настроена с параметрами:\n"
                            f"Период: {period}\n"
                            f"Перекупленность: {overbought}\n"
                            f"Перепроданность: {oversold}\n")

    # Очищаем временные данные после использования
    del user_rsi_data[chat_id]