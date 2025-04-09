from telebot import types
from app.client.api.signals_client import SignalsApiClient
from app.client.bot.bot import bot
from app.client.handlers.utils.message_utils import send_or_edit_message

signals_client = SignalsApiClient()


# Временное хранилище для данных пользователя
user_tpsl_data = {}


def validate_number(value):
    """
    Проверка, что число больше 0 и меньше 100, может быть как целым, так и дробным.
    
    Args:
        value: Проверяемое значение
        
    Returns:
        float: Проверенное значение, если оно валидно, иначе None
    """
    try:
        # Заменяем запятую на точку для корректной конвертации
        if isinstance(value, str):
            value = value.replace(',', '.')
            
        value = float(value)
        
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
    current_settings = signals_client.get_signal_tpsl()
    
    if current_settings:
        take_profit = current_settings.get('take_profit', 10)
        stop_loss = current_settings.get('stop_loss', 5)
        
        send_or_edit_message(
            chat_id, 
            f'🎯 *Текущие настройки Take Profit/Stop Loss*\n\n'
            f'• Take Profit: `{take_profit}`\n'
            f'• Stop Loss: `{stop_loss}`'
        )
    
    # Запрашиваем значение для Take Profit
    msg = send_or_edit_message(chat_id, '🎯 *Настройка Take Profit/Stop Loss*\n\nВведите значение для Take Profit:')
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
        msg = send_or_edit_message(chat_id, '❌ *Ошибка ввода*\n\nВведите целое число больше 0 и меньше 100 для Take Profit:')
        # Повторно запрашиваем значение
        bot.register_next_step_handler_by_chat_id(chat_id, get_tp_value)
        return  # Прерываем обработку, если значение некорректное

    user_tpsl_data[chat_id] = {'tp_value': tp_value}
    msg = send_or_edit_message(chat_id, f'✅ Take Profit установлен: `{tp_value}`\n\n*Введите значение для Stop Loss:*')
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
        msg = send_or_edit_message(chat_id, '❌ *Ошибка ввода*\n\nВведите целое число больше 0 и меньше 100 для Stop Loss:')
        # Повторно запрашиваем значение
        bot.register_next_step_handler_by_chat_id(chat_id, get_sl_value)
        return  # Прерываем обработку, если значение некорректное

    user_tpsl_data[chat_id]['sl_value'] = sl_value
    tp_value = user_tpsl_data[chat_id]['tp_value']
    
    try:
        # Обновляем параметры через API-клиент
        result = signals_client.update_signal_tpsl(tp_value, sl_value)
        
        # Подтверждение настройки стратегии
        send_or_edit_message(
            chat_id, 
            f'✅ *Take Profit/Stop Loss успешно настроены*\n\n'
            f'• Take Profit = `{tp_value}`\n'
            f'• Stop Loss = `{sl_value}`'
        )
    
    except Exception as e:
        send_or_edit_message(chat_id, f"❌ *Ошибка при обновлении настроек*\n\n`{str(e)}`")
    
    # Очищаем временные данные
    del user_tpsl_data[chat_id]
