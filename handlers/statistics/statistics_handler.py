from bot.bot import bot
from db.db import get_t_token
from telebot import types
from handlers.statistics.calculate_statistics import calculate_statistics

@bot.message_handler(func=lambda message: message.text == 'Статистика')
def statistics_handler(message):
    chat_id = message.chat.id
    token = get_t_token(chat_id)

    if token is not None:
        inline_keyboard = types.InlineKeyboardMarkup()
        buttons = [
            types.InlineKeyboardButton(text='Интервал', callback_data='stat_interval'),
            types.InlineKeyboardButton(text='Общая статистика', callback_data='stat_full'),
        ]
        inline_keyboard.add(*buttons)
        bot.send_message(chat_id, 'Выберите действие', reply_markup=inline_keyboard)


@bot.callback_query_handler(func=lambda call: call.data == 'stat_interval')
def stat_interval_handler(call):
    chat_id = call.message.chat.id
    token = get_t_token(chat_id)
    if token is not None:
        msg = bot.send_message(chat_id, "Введите количество дней для расчета статистики:")
        bot.register_next_step_handler(msg, validate_days)

def validate_days(message):
    chat_id = message.chat.id
    try:
        days = int(message.text)
        if 1 <= days <= 365:
            days = str(days)
            calculate_statistics(days, chat_id)
        else:
            bot.send_message(message.chat.id, "Некорректное количество дней. Пожалуйста, введите значение от 1 до 365.")
            stat_interval_handler(message)
    except ValueError:
        bot.send_message(message.chat.id, "Некорректный ввод. Пожалуйста, введите целое число.")
        stat_interval_handler(message)


@bot.callback_query_handler(func=lambda call: call.data == 'stat_full')
def stat_interval_handler(call):
    chat_id = call.message.chat.id
    token = get_t_token(chat_id)
    if token is not None:
        calculate_statistics('full', chat_id)

