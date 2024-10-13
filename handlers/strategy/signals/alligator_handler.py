from db.db import get_t_token, update_signal_alligator
from store.store import user_alligator_data
from bot.bot import bot

@bot.callback_query_handler(func=lambda call: call.data == 'signal_alligator')
def alligator_on(call):
    chat_id = call.message.chat.id
    token = get_t_token(chat_id)
    
    if token is not None:
        msg = bot.send_message(chat_id, "Введите период для челюстей (Jaw):")
        bot.register_next_step_handler(msg, get_alligator_jaw_period)

def get_alligator_jaw_period(message):
    chat_id = message.chat.id
    try:
        jaw_period = int(message.text)
        user_alligator_data[chat_id] = {'jaw_period': jaw_period}  # Сохраняем период для челюстей
        bot.send_message(chat_id, f"Вы выбрали период {jaw_period} для челюстей. Теперь введите смещение для челюстей (Jaw shift):")
        bot.register_next_step_handler(message, get_alligator_jaw_shift)
    except ValueError:
        msg = bot.send_message(chat_id, "Некорректный ввод. Введите числовое значение для периода челюстей:")
        bot.register_next_step_handler(msg, get_alligator_jaw_period)

def get_alligator_jaw_shift(message):
    chat_id = message.chat.id
    try:
        jaw_shift = int(message.text)
        user_alligator_data[chat_id]['jaw_shift'] = jaw_shift  # Сохраняем смещение для челюстей
        bot.send_message(chat_id, f"Вы выбрали смещение {jaw_shift} для челюстей. Теперь введите период для зубов (Teeth):")
        bot.register_next_step_handler(message, get_alligator_teeth_period)
    except ValueError:
        msg = bot.send_message(chat_id, "Некорректный ввод. Введите числовое значение для смещения челюстей:")
        bot.register_next_step_handler(msg, get_alligator_jaw_shift)

def get_alligator_teeth_period(message):
    chat_id = message.chat.id
    try:
        teeth_period = int(message.text)
        user_alligator_data[chat_id]['teeth_period'] = teeth_period  # Сохраняем период для зубов
        bot.send_message(chat_id, f"Вы выбрали период {teeth_period} для зубов. Теперь введите смещение для зубов (Teeth shift):")
        bot.register_next_step_handler(message, get_alligator_teeth_shift)
    except ValueError:
        msg = bot.send_message(chat_id, "Некорректный ввод. Введите числовое значение для периода зубов:")
        bot.register_next_step_handler(msg, get_alligator_teeth_period)

def get_alligator_teeth_shift(message):
    chat_id = message.chat.id
    try:
        teeth_shift = int(message.text)
        user_alligator_data[chat_id]['teeth_shift'] = teeth_shift  # Сохраняем смещение для зубов
        bot.send_message(chat_id, f"Вы выбрали смещение {teeth_shift} для зубов. Теперь введите период для губ (Lips):")
        bot.register_next_step_handler(message, get_alligator_lips_period)
    except ValueError:
        msg = bot.send_message(chat_id, "Некорректный ввод. Введите числовое значение для смещения зубов:")
        bot.register_next_step_handler(msg, get_alligator_teeth_shift)

def get_alligator_lips_period(message):
    chat_id = message.chat.id
    try:
        lips_period = int(message.text)
        user_alligator_data[chat_id]['lips_period'] = lips_period  # Сохраняем период для губ
        bot.send_message(chat_id, f"Вы выбрали период {lips_period} для губ. Теперь введите смещение для губ (Lips shift):")
        bot.register_next_step_handler(message, get_alligator_lips_shift)
    except ValueError:
        msg = bot.send_message(chat_id, "Некорректный ввод. Введите числовое значение для периода губ:")
        bot.register_next_step_handler(msg, get_alligator_lips_period)

def get_alligator_lips_shift(message):
    chat_id = message.chat.id
    try:
        lips_shift = int(message.text)
        user_alligator_data[chat_id]['lips_shift'] = lips_shift  # Сохраняем смещение для губ

        # Получаем все введённые параметры
        jaw_period = user_alligator_data[chat_id]['jaw_period']
        jaw_shift = user_alligator_data[chat_id]['jaw_shift']
        teeth_period = user_alligator_data[chat_id]['teeth_period']
        teeth_shift = user_alligator_data[chat_id]['teeth_shift']
        lips_period = user_alligator_data[chat_id]['lips_period']
        lips_shift = user_alligator_data[chat_id]['lips_shift']

        # Обновляем параметры в базе данных
        update_signal_alligator(chat_id, jaw_period, jaw_shift, teeth_period, teeth_shift, lips_period, lips_shift)
        
        # Подтверждение настройки стратегии
        bot.send_message(chat_id, f"Стратегия Аллигатор настроена с параметрами:\n"
                                  f"Челюсти - Период: {jaw_period}, Смещение: {jaw_shift}\n"
                                  f"Зубы - Период: {teeth_period}, Смещение: {teeth_shift}\n"
                                  f"Губы - Период: {lips_period}, Смещение: {lips_shift}\n")

        # Очищаем временные данные после использования
        del user_alligator_data[chat_id]
    except ValueError:
        msg = bot.send_message(chat_id, "Некорректный ввод. Введите числовое значение для смещения губ:")
        bot.register_next_step_handler(msg, get_alligator_lips_shift)