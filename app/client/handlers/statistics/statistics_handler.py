from app.client.bot.bot import bot
from telebot import types
from app.client.handlers.statistics.calculate_statistics import calculate_statistics
from app.client.handlers.utils.message_utils import send_or_edit_message, last_messages

@bot.message_handler(func=lambda message: message.text == 'Статистика')
def statistics_handler(message):
    """
    Основной обработчик для раздела "Статистика".
    
    Отображает меню с доступными опциями для работы со статистикой.
    """
    chat_id = message.chat.id
    
    inline_keyboard = types.InlineKeyboardMarkup()
    buttons = [
        types.InlineKeyboardButton(text='📅 Интервал', callback_data='stat_interval'),
        types.InlineKeyboardButton(text='📊 Общая статистика', callback_data='stat_full'),
    ]
    
    for button in buttons:
        inline_keyboard.add(button)
    
    # Отправляем новое сообщение для первого обработчика
    msg = bot.send_message(
        chat_id=chat_id, 
        text='📈 *Статистика торговли*\n\nВыберите тип статистики:', 
        reply_markup=inline_keyboard
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
        msg = send_or_edit_message(chat_id, "📅 *Выбор интервала*\n\nВведите количество дней для расчета статистики (от 1 до 365):")
        bot.register_next_step_handler(msg, validate_days)
    
    except Exception as e:
        send_or_edit_message(chat_id, f"❌ *Ошибка при выборе интервала*\n\n`{str(e)}`")


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
            send_or_edit_message(chat_id, f"⏳ *Обработка запроса*\n\nРассчитываем статистику за последние {days} дней...")
            calculate_statistics(days, chat_id)
        else:
            msg = send_or_edit_message(chat_id, "❌ *Ошибка ввода*\n\nНекорректное количество дней. Пожалуйста, введите значение от 1 до 365:")
            bot.register_next_step_handler(msg, validate_days)
    
    except ValueError:
        msg = send_or_edit_message(chat_id, "❌ *Ошибка ввода*\n\nНекорректный ввод. Пожалуйста, введите целое число:")
        bot.register_next_step_handler(msg, validate_days)
    
    except Exception as e:
        send_or_edit_message(chat_id, f"❌ *Ошибка при обработке ввода*\n\n`{str(e)}`")


@bot.callback_query_handler(func=lambda call: call.data == 'stat_full')
def stat_full_handler(call):
    """
    Обработчик для получения общей статистики.
    
    Вызывает функцию расчета статистики с параметром 'full'.
    """
    chat_id = call.message.chat.id
    
    try:
        send_or_edit_message(chat_id, "⏳ *Обработка запроса*\n\nРассчитываем полную статистику торговли...")
        calculate_statistics('full', chat_id)
    
    except Exception as e:
        send_or_edit_message(chat_id, f"❌ *Ошибка при получении общей статистики*\n\n`{str(e)}`")
