from telebot import types
from app.client.bot.bot import bot
from app.backend.api_client import ApiClient

# Создаем экземпляр API-клиента
api_client = ApiClient()

# Временное хранилище для данных пользователя
user_alligator_data = {}


@bot.callback_query_handler(func=lambda call: call.data == 'signal_alligator')
def alligator_on(call):
    """
    Обработчик для настройки сигнала Alligator.
    
    Запрашивает у пользователя параметры сигнала Alligator.
    """
    chat_id = call.message.chat.id
    
    # Получаем текущие настройки Alligator
    current_settings = api_client.get_signal_alligator()
    
    if current_settings:
        jaw_period = current_settings.get('jaw_period', 13)
        jaw_shift = current_settings.get('jaw_shift', 8)
        teeth_period = current_settings.get('teeth_period', 8)
        teeth_shift = current_settings.get('teeth_shift', 5)
        lips_period = current_settings.get('lips_period', 5)
        lips_shift = current_settings.get('lips_shift', 3)
        
        bot.send_message(
            chat_id, 
            f'Текущие настройки Alligator:\n'
            f'Челюсти - Период: {jaw_period}, Смещение: {jaw_shift}\n'
            f'Зубы - Период: {teeth_period}, Смещение: {teeth_shift}\n'
            f'Губы - Период: {lips_period}, Смещение: {lips_shift}'
        )
    
    # Запрашиваем период для челюстей
    msg = bot.send_message(chat_id, "Введите период для челюстей (Jaw):")
    bot.register_next_step_handler(msg, get_alligator_jaw_period)


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


def get_alligator_jaw_period(message):
    """
    Обработчик для получения периода челюстей Alligator.
    
    Сохраняет период челюстей и запрашивает смещение челюстей.
    """
    chat_id = message.chat.id
    jaw_period = message.text
    
    if not validate_number(jaw_period, min_value=1, max_value=100):
        msg = bot.send_message(chat_id, "Период для челюстей должен быть целым числом от 1 до 100. Попробуйте снова:")
        bot.register_next_step_handler(msg, get_alligator_jaw_period)
        return
    
    jaw_period = int(jaw_period)
    user_alligator_data[chat_id] = {'jaw_period': jaw_period}  # Сохраняем период для челюстей
    bot.send_message(chat_id, f"Вы выбрали период {jaw_period} для челюстей. Теперь введите смещение для челюстей (Jaw shift):")
    bot.register_next_step_handler(message, get_alligator_jaw_shift)


def get_alligator_jaw_shift(message):
    """
    Обработчик для получения смещения челюстей Alligator.
    
    Сохраняет смещение челюстей и запрашивает период зубов.
    """
    chat_id = message.chat.id
    jaw_shift = message.text
    
    if not validate_number(jaw_shift, min_value=0):
        msg = bot.send_message(chat_id, "Смещение для челюстей должно быть неотрицательным числом. Попробуйте снова:")
        bot.register_next_step_handler(msg, get_alligator_jaw_shift)
        return
    
    jaw_shift = int(jaw_shift)  # Преобразуем в целое число
    user_alligator_data[chat_id]['jaw_shift'] = jaw_shift  # Сохраняем смещение для челюстей
    bot.send_message(chat_id, f"Вы выбрали смещение {jaw_shift} для челюстей. Теперь введите период для зубов (Teeth):")
    bot.register_next_step_handler(message, get_alligator_teeth_period)


def get_alligator_teeth_period(message):
    """
    Обработчик для получения периода зубов Alligator.
    
    Сохраняет период зубов и запрашивает смещение зубов.
    """
    chat_id = message.chat.id
    teeth_period = message.text
    
    if not validate_number(teeth_period, min_value=1, max_value=100):
        msg = bot.send_message(chat_id, "Период для зубов должен быть целым числом от 1 до 100. Попробуйте снова:")
        bot.register_next_step_handler(msg, get_alligator_teeth_period)
        return
    
    teeth_period = int(teeth_period)  # Преобразуем в целое число
    user_alligator_data[chat_id]['teeth_period'] = teeth_period  # Сохраняем период для зубов
    bot.send_message(chat_id, f"Вы выбрали период {teeth_period} для зубов. Теперь введите смещение для зубов (Teeth shift):")
    bot.register_next_step_handler(message, get_alligator_teeth_shift)


def get_alligator_teeth_shift(message):
    """
    Обработчик для получения смещения зубов Alligator.
    
    Сохраняет смещение зубов и запрашивает период губ.
    """
    chat_id = message.chat.id
    teeth_shift = message.text
    
    if not validate_number(teeth_shift, min_value=0):
        msg = bot.send_message(chat_id, "Смещение для зубов должно быть неотрицательным числом. Попробуйте снова:")
        bot.register_next_step_handler(msg, get_alligator_teeth_shift)
        return
    
    teeth_shift = int(teeth_shift)  # Преобразуем в целое число
    user_alligator_data[chat_id]['teeth_shift'] = teeth_shift  # Сохраняем смещение для зубов
    bot.send_message(chat_id, f"Вы выбрали смещение {teeth_shift} для зубов. Теперь введите период для губ (Lips):")
    bot.register_next_step_handler(message, get_alligator_lips_period)


def get_alligator_lips_period(message):
    """
    Обработчик для получения периода губ Alligator.
    
    Сохраняет период губ и запрашивает смещение губ.
    """
    chat_id = message.chat.id
    lips_period = message.text
    
    if not validate_number(lips_period, min_value=1, max_value=100):
        msg = bot.send_message(chat_id, "Период для губ должен быть целым числом от 1 до 100. Попробуйте снова:")
        bot.register_next_step_handler(msg, get_alligator_lips_period)
        return
    
    lips_period = int(lips_period)  # Преобразуем в целое число
    user_alligator_data[chat_id]['lips_period'] = lips_period  # Сохраняем период для губ
    bot.send_message(chat_id, f"Вы выбрали период {lips_period} для губ. Теперь введите смещение для губ (Lips shift):")
    bot.register_next_step_handler(message, get_alligator_lips_shift)


def get_alligator_lips_shift(message):
    """
    Обработчик для получения смещения губ Alligator.
    
    Сохраняет смещение губ и обновляет настройки сигнала Alligator.
    """
    chat_id = message.chat.id
    lips_shift = message.text
    
    if not validate_number(lips_shift, min_value=0):
        msg = bot.send_message(chat_id, "Смещение для губ должно быть неотрицательным числом. Попробуйте снова:")
        bot.register_next_step_handler(msg, get_alligator_lips_shift)
        return
    
    lips_shift = int(lips_shift)  # Преобразуем в целое число
    user_alligator_data[chat_id]['lips_shift'] = lips_shift  # Сохраняем смещение для губ

    # Получаем все введённые параметры
    jaw_period = user_alligator_data[chat_id]['jaw_period']
    jaw_shift = user_alligator_data[chat_id]['jaw_shift']
    teeth_period = user_alligator_data[chat_id]['teeth_period']
    teeth_shift = user_alligator_data[chat_id]['teeth_shift']
    lips_period = user_alligator_data[chat_id]['lips_period']
    
    try:
        # Обновляем параметры через API-клиент
        result = api_client.update_signal_alligator(
            jaw_period, jaw_shift, teeth_period, teeth_shift, lips_period, lips_shift
        )
        
        # Подтверждение настройки стратегии
        bot.send_message(
            chat_id, 
            f"Стратегия Аллигатор настроена с параметрами:\n"
            f"Челюсти - Период: {jaw_period}, Смещение: {jaw_shift}\n"
            f"Зубы - Период: {teeth_period}, Смещение: {teeth_shift}\n"
            f"Губы - Период: {lips_period}, Смещение: {lips_shift}"
        )
    
    except Exception as e:
        bot.send_message(chat_id, f"Ошибка при обновлении настроек Alligator: {str(e)}")
    
    # Очищаем временные данные после использования
    del user_alligator_data[chat_id]
