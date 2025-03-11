from telebot import types
from app.client.bot.bot import bot
from app.backend.api_client import ApiClient

# Создаем экземпляр API-клиента
api_client = ApiClient()

# Временное хранилище для данных пользователя
user_tpsl_data = {}


def validate_number(value):
    """
    Проверка, что число больше 0 и меньше 100, целое и неотрицательное.
    
    Args:
        value: Проверяемое значение
        
    Returns:
        int: Проверенное значение, если оно валидно, иначе None
    """
    try:
        value = int(value)
        if value <= 0 or value >= 100:
            raise ValueError("Число должно быть больше 0 и меньше 100.")
        return value
    except ValueError:
        return None


@bot.callback_query_handler(func=lambda call: call.data == 'signal_tpsl')
def tpsl_handler(call):
    """
    Обработчик для настройки сигнала Take Profit/Stop Loss.
    
    Запрашивает у пользователя параметры сигнала TP/SL.
    """
    chat_id = call.message.chat.id
    
    # Получаем текущие настройки TPSL
    current_settings = api_client.get_signal_tpsl()
    
    if current_settings:
        take_profit = current_settings.get('take_profit', 10)
        stop_loss = current_settings.get('stop_loss', 5)
        
        bot.send_message(
            chat_id, 
            f'Текущие настройки Take Profit/Stop Loss:\n'
            f'Take Profit: {take_profit}\n'
            f'Stop Loss: {stop_loss}'
        )
    
    # Запрашиваем значение для Take Profit
    bot.send_message(chat_id, 'Введите значение для Take Profit')
    bot.register_next_step_handler_by_chat_id(chat_id, get_tp_value)


def get_tp_value(message):
    """
    Обработчик для получения значения Take Profit.
    
    Сохраняет значение Take Profit и запрашивает значение Stop Loss.
    """
    chat_id = message.chat.id
    tp_value = message.text

    # Проверка введенного значения
    tp_value = validate_number(tp_value)
    if tp_value is None:
        bot.send_message(chat_id, 'Ошибка: Введите целое число больше 0 и меньше 100 для Take Profit.')
        # Повторно запрашиваем значение
        bot.register_next_step_handler_by_chat_id(chat_id, get_tp_value)
        return  # Прерываем обработку, если значение некорректное

    user_tpsl_data[chat_id] = {'tp_value': tp_value}
    bot.send_message(chat_id, 'Введите значение для Stop Loss')
    bot.register_next_step_handler_by_chat_id(chat_id, get_sl_value)


def get_sl_value(message):
    """
    Обработчик для получения значения Stop Loss.
    
    Сохраняет значение Stop Loss и обновляет настройки сигнала TP/SL.
    """
    chat_id = message.chat.id
    sl_value = message.text

    # Проверка введенного значения
    sl_value = validate_number(sl_value)
    if sl_value is None:
        bot.send_message(chat_id, 'Ошибка: Введите целое число больше 0 и меньше 100 для Stop Loss.')
        # Повторно запрашиваем значение
        bot.register_next_step_handler_by_chat_id(chat_id, get_sl_value)
        return  # Прерываем обработку, если значение некорректное

    user_tpsl_data[chat_id]['sl_value'] = sl_value
    tp_value = user_tpsl_data[chat_id]['tp_value']
    
    try:
        # Обновляем параметры через API-клиент
        result = api_client.update_signal_tpsl(tp_value, sl_value)
        
        # Подтверждение настройки стратегии
        bot.send_message(
            chat_id, 
            f'Take Profit/Stop Loss настроен с параметрами:\n'
            f'Take Profit = {tp_value}\n'
            f'Stop Loss = {sl_value}'
        )
    
    except Exception as e:
        bot.send_message(chat_id, f"Ошибка при обновлении настроек Take Profit/Stop Loss: {str(e)}")
    
    # Очищаем временные данные
    del user_tpsl_data[chat_id]
