from db.db import get_t_token, update_signal_ema
from bot.bot import bot
from store.store import user_ema_data

@bot.callback_query_handler(func=lambda call: call.data == 'signal_ema')
def ema_handler(call):
    chat_id = call.message.chat.id
    token = get_t_token(chat_id)
    
    if token is not None:
        msg = bot.send_message(chat_id, "Введите кол-во точек для расчета быстрого тренда:")
        bot.register_next_step_handler(msg, get_ema_fast)

def get_ema_fast(message):
    chat_id = message.chat.id
    try:
        fastLength = int(message.text)
        user_ema_data[chat_id] = {'fastLength': fastLength}
        bot.send_message(chat_id, f"Вы выбрали кол-во точек для расчета быстрого тренда {fastLength}. Теперь введите количество точек для расчета медленного тренда:")
        bot.register_next_step_handler(message, get_ema_slow)
    except ValueError:
        msg = bot.send_message(chat_id, "Некорректный ввод. Введите числовое значение для периода:")
        bot.register_next_step_handler(msg, get_ema_fast)


def get_ema_slow(message):
    chat_id = message.chat.id
    try:
        slowLength = int(message.text)
        user_ema_data[chat_id]['slowLength'] = slowLength # Сохраняем период
        bot.send_message(chat_id, f"Вы выбрали кол-во точек для расчета медленного тренда {slowLength}.")
        fastLength = user_ema_data[chat_id]['fastLength']

        update_signal_ema(chat_id, fastLength, slowLength)

        # Подтверждение активации стратегии
        bot.send_message(chat_id, 
                                f"Стратегия EMA настроена с параметрами:\n"
                                f"Кол-во точек для расчета быстрого тренда: {fastLength}\n"
                                f"Кол-во точек для расчета медленного тренда: {slowLength}\n"
                         )


        # Очищаем временные данные после использования
        del user_ema_data[chat_id]
        
    except ValueError:
        msg = bot.send_message(chat_id, "Некорректный ввод. Введите числовое значение для периода:")
        bot.register_next_step_handler(msg, get_ema_slow)