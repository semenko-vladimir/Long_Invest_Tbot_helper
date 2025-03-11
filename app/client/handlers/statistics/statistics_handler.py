from app.client.bot.bot import bot
from app.backend.api_client import ApiClient
from telebot import types
from app.client.handlers.statistics.calculate_statistics import calculate_statistics

# Создаем экземпляр API-клиента
api_client = ApiClient()


@bot.message_handler(func=lambda message: message.text == 'Статистика')
def statistics_handler(message):
    """
    Основной обработчик для раздела "Статистика".
    
    Отображает меню с доступными опциями для работы со статистикой.
    """
    chat_id = message.chat.id
    
    inline_keyboard = types.InlineKeyboardMarkup()
    buttons = [
        types.InlineKeyboardButton(text='Интервал', callback_data='stat_interval'),
        types.InlineKeyboardButton(text='Общая статистика', callback_data='stat_full'),
    ]
    
    for button in buttons:
        inline_keyboard.add(button)
    
    bot.send_message(chat_id, 'Выберите действие', reply_markup=inline_keyboard)


@bot.callback_query_handler(func=lambda call: call.data == 'stat_interval')
def stat_interval_handler(call):
    """
    Обработчик для выбора интервала статистики.
    
    Запрашивает у пользователя количество дней для расчета статистики.
    """
    chat_id = call.message.chat.id
    
    try:
        msg = bot.send_message(chat_id, "Введите количество дней для расчета статистики:")
        bot.register_next_step_handler(msg, validate_days)
    
    except Exception as e:
        bot.send_message(chat_id, f"Ошибка при выборе интервала: {str(e)}")


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
            calculate_statistics(days, chat_id)
        else:
            bot.send_message(chat_id, "Некорректное количество дней. Пожалуйста, введите значение от 1 до 365.")
            # Создаем новое сообщение для повторного запроса
            msg = bot.send_message(chat_id, "Введите количество дней для расчета статистики:")
            bot.register_next_step_handler(msg, validate_days)
    
    except ValueError:
        bot.send_message(chat_id, "Некорректный ввод. Пожалуйста, введите целое число.")
        # Создаем новое сообщение для повторного запроса
        msg = bot.send_message(chat_id, "Введите количество дней для расчета статистики:")
        bot.register_next_step_handler(msg, validate_days)
    
    except Exception as e:
        bot.send_message(chat_id, f"Ошибка при обработке ввода: {str(e)}")


@bot.callback_query_handler(func=lambda call: call.data == 'stat_full')
def stat_full_handler(call):
    """
    Обработчик для получения общей статистики.
    
    Вызывает функцию расчета статистики с параметром 'full'.
    """
    chat_id = call.message.chat.id
    
    try:
        calculate_statistics('full', chat_id)
    
    except Exception as e:
        bot.send_message(chat_id, f"Ошибка при получении общей статистики: {str(e)}")
