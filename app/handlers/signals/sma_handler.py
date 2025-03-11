from db.db import get_t_token, update_signal_rsi, update_signal_sma
from bot.bot import bot
from store.store import user_sma_data

@bot.callback_query_handler(func=lambda call: call.data == 'signal_sma')
def sma_handler(call):
    chat_id = call.message.chat.id
    token = get_t_token(chat_id)
    
    if token is not None:
        msg = bot.send_message(chat_id, "Введите кол-во точек для расчета быстрого тренда:")
        bot.register_next_step_handler(msg, get_sma_fast)

def validate_number(value):
    """Проверка, что значение является целым числом от 1 до 100."""
    try:
        num = int(value)
        if num < 1 or num > 100:
            return False
        return True
    except ValueError:
        return False

def get_sma_fast(message):
    chat_id = message.chat.id
    fastLength = message.text
    
    if not validate_number(fastLength):
        msg = bot.send_message(chat_id, "Число должно быть целым, больше 0 и меньше 100. Попробуйте снова:")
        bot.register_next_step_handler(msg, get_sma_fast)
        return
    
    fastLength = int(fastLength)
    user_sma_data[chat_id] = {'fastLength': fastLength}  # Сохраняем период
    bot.send_message(chat_id, f"Вы выбрали кол-во точек для расчета быстрого тренда {fastLength}. Теперь введите количество точек для расчета медленного тренда:")
    bot.register_next_step_handler(message, get_sma_slow)


def get_sma_slow(message):
    chat_id = message.chat.id
    slowLength = message.text
    
    if not validate_number(slowLength):
        msg = bot.send_message(chat_id, "Число должно быть целым, больше 0 и меньше 100. Попробуйте снова:")
        bot.register_next_step_handler(msg, get_sma_slow)
        return
    
    slowLength = int(slowLength)
    user_sma_data[chat_id]['slowLength'] = slowLength  # Сохраняем период
    bot.send_message(chat_id, f"Вы выбрали кол-во точек для расчета медленного тренда {slowLength}.")
    fastLength = user_sma_data[chat_id]['fastLength']

    update_signal_sma(chat_id, fastLength, slowLength)

    # Подтверждение активации стратегии
    bot.send_message(chat_id, 
                     f"Стратегия SMA настроена с параметрами:\n"
                     f"Кол-во точек для расчета быстрого тренда: {fastLength}\n"
                     f"Кол-во точек для расчета медленного тренда: {slowLength}\n"
                     )

    # Очищаем временные данные после использования
    del user_sma_data[chat_id]
        