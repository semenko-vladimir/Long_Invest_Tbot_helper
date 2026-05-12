from app.client.bot.bot import bot
from telebot import types
from app.client.handlers.user_context import get_telegram_services_or_notify
from app.client.handlers.statistics.calculate_statistics import calculate_statistics
from app.client.handlers.utils.message_utils import send_or_edit_message, last_messages

@bot.message_handler(func=lambda message: message.text in {'Stats', 'Statistics', 'Статистика'})
def statistics_handler(message):
    """
    Основной обработчик для раздела "Статистика".
    
    Отображает меню с доступными опциями для работы со статистикой.
    """
    chat_id = message.chat.id
    
    inline_keyboard = types.InlineKeyboardMarkup()
    buttons = [
        types.InlineKeyboardButton(text='Interval', callback_data='stat_interval'),
        types.InlineKeyboardButton(text='Full statistics', callback_data='stat_full'),
    ]
    
    for button in buttons:
        inline_keyboard.add(button)
    
    # Отправляем новое сообщение для первого обработчика
    msg = bot.send_message(
        chat_id=chat_id, 
        text='*Statistics*\n\nChoose a statistics view:',
        reply_markup=inline_keyboard,
        parse_mode='Markdown'
    )
    
    # Сохраняем ID сообщения для последующего редактирования
    last_messages[chat_id] = msg.message_id


@bot.callback_query_handler(func=lambda call: call.data == 'stat_interval')
def stat_interval_handler(call):
    """
    Обработчик для выбора интервала статистики.
    
    Запрашивает у пользователя количество дней для расчета статистики.
    """
    chat_id = call.message.chat.id
    
    try:
        msg = send_or_edit_message(chat_id, "*Interval*\n\nEnter the number of days to include (1 to 365):")
        bot.register_next_step_handler(msg, validate_days)
    
    except Exception as e:
        send_or_edit_message(chat_id, f"*Interval error*\n\n`{str(e)}`")


def validate_days(message):
    """
    Обработчик для валидации количества дней.
    
    Проверяет, что введенное значение является целым числом от 1 до 365.
    """
    chat_id = message.chat.id
    
    try:
        days = int(message.text)
        
        if 1 <= days <= 365:
            days = str(days)
            services = get_telegram_services_or_notify(chat_id)
            if services is None:
                return
            send_or_edit_message(chat_id, f"*Processing*\n\nCalculating statistics for the last {days} days...")
            calculate_statistics(days, chat_id, services.statistics_service)
        else:
            msg = send_or_edit_message(chat_id, "*Input error*\n\nEnter a value from 1 to 365:")
            bot.register_next_step_handler(msg, validate_days)
    
    except ValueError:
        msg = send_or_edit_message(chat_id, "*Input error*\n\nEnter an integer:")
        bot.register_next_step_handler(msg, validate_days)
    
    except Exception as e:
        send_or_edit_message(chat_id, f"*Input processing error*\n\n`{str(e)}`")


@bot.callback_query_handler(func=lambda call: call.data == 'stat_full')
def stat_full_handler(call):
    """
    Обработчик для получения общей статистики.
    
    Вызывает функцию расчета статистики с параметром 'full'.
    """
    chat_id = call.message.chat.id
    
    try:
        services = get_telegram_services_or_notify(chat_id)
        if services is None:
            return
        send_or_edit_message(chat_id, "*Processing*\n\nCalculating full statistics...")
        calculate_statistics('full', chat_id, services.statistics_service)
    
    except Exception as e:
        send_or_edit_message(chat_id, f"*Statistics error*\n\n`{str(e)}`")
