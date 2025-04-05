from telebot import types
from app.client.api.signals_client import SignalsApiClient
from app.client.bot.bot import bot

signals_client = SignalsApiClient()


# Временное хранилище для данных пользователя
user_sma_data = {}


@bot.callback_query_handler(func=lambda call: call.data == 'signal_sma')
def sma_handler(call):
    """
    Обработчик для настройки сигнала SMA.
    
    Запрашивает у пользователя параметры сигнала SMA.
    """
    chat_id = call.message.chat.id
    
    # Получаем текущие настройки SMA
    current_settings = signals_client.get_signal_sma()
    
    if current_settings:
        fast_length = current_settings.get('fastLength', 5)
        slow_length = current_settings.get('slowLength', 20)
        
        bot.send_message(
            chat_id, 
            f'Текущие настройки SMA:\n'
            f'Кол-во точек для расчета быстрого тренда: {fast_length}\n'
            f'Кол-во точек для расчета медленного тренда: {slow_length}'
        )
    
    # Запрашиваем кол-во точек для расчета быстрого тренда
    msg = bot.send_message(chat_id, "Введите кол-во точек для расчета быстрого тренда:")
    bot.register_next_step_handler(msg, get_sma_fast)


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


def get_sma_fast(message):
    """
    Обработчик для получения кол-ва точек для расчета быстрого тренда SMA.
    
    Сохраняет кол-во точек и запрашивает кол-во точек для расчета медленного тренда.
    """
    chat_id = message.chat.id
    fast_length = message.text
    
    if not validate_number(fast_length):
        msg = bot.send_message(chat_id, "Число должно быть целым, больше 0 и меньше 100. Попробуйте снова:")
        bot.register_next_step_handler(msg, get_sma_fast)
        return
    
    fast_length = int(fast_length)
    user_sma_data[chat_id] = {'fast_length': fast_length}  # Сохраняем период
    bot.send_message(chat_id, f"Вы выбрали кол-во точек для расчета быстрого тренда {fast_length}. Теперь введите количество точек для расчета медленного тренда:")
    bot.register_next_step_handler(message, get_sma_slow)


def get_sma_slow(message):
    """
    Обработчик для получения кол-ва точек для расчета медленного тренда SMA.
    
    Сохраняет кол-во точек и обновляет настройки сигнала SMA.
    """
    chat_id = message.chat.id
    slow_length = message.text
    
    if not validate_number(slow_length):
        msg = bot.send_message(chat_id, "Число должно быть целым, больше 0 и меньше 100. Попробуйте снова:")
        bot.register_next_step_handler(msg, get_sma_slow)
        return
    
    slow_length = int(slow_length)
    user_sma_data[chat_id]['slow_length'] = slow_length  # Сохраняем период
    
    # Получаем все введённые параметры
    fast_length = user_sma_data[chat_id]['fast_length']
    
    try:
        # Обновляем параметры через API-клиент
        result = signals_client.update_signal_sma(fast_length, slow_length)
        
        # Подтверждение активации стратегии
        bot.send_message(
            chat_id, 
            f"Стратегия SMA настроена с параметрами:\n"
            f"Кол-во точек для расчета быстрого тренда: {fast_length}\n"
            f"Кол-во точек для расчета медленного тренда: {slow_length}"
        )
    
    except Exception as e:
        bot.send_message(chat_id, f"Ошибка при обновлении настроек SMA: {str(e)}")
    
    # Очищаем временные данные после использования
    del user_sma_data[chat_id]
