from db.db import get_all_tickers, get_config, get_t_token, update_config_collapse
from bot.bot import bot
from telebot import types
from store.store import chat_schedulers
from config.schedulers_config import configure_market_scheduler


@bot.callback_query_handler(func=lambda call: call.data == 'user_add_market_updates')
def add_market_updates_handler(call):
    config_data = get_config()

    for row in config_data:
        chat_id = row[1]
        market_updates = row[4]

        if market_updates and call.message.chat.id == chat_id:
            bot.send_message(call.message.chat.id, 'Вы уже подписаны на обновления рынка')
            return

    bot.send_message(call.message.chat.id, 'Вы автоматически будете отписаны от обновлений падений рынка')
    chat_id = call.message.chat.id
    token = get_t_token(chat_id)
    if token is not None:
        tickers = get_all_tickers(chat_id)

        if not tickers:
            bot.send_message(chat_id, 'У вас нет активных тикеров')
        else:
            inline_keyboard = types.InlineKeyboardMarkup()
            buttons = [
                types.InlineKeyboardButton(text='10 минут', callback_data='uinterval_10 минут'),
                types.InlineKeyboardButton(text='пол часа', callback_data='uinterval_пол_часа'),
                types.InlineKeyboardButton(text='час', callback_data='uinterval_час'),
            ]
            inline_keyboard.add(*buttons)
            bot.send_message(chat_id, 'Выберите интервал для получения обновлений', reply_markup=inline_keyboard)

@bot.callback_query_handler(func=lambda call: call.data.startswith('uinterval_'))
def percent_handler(call):
    data = call.data.split('_')
    interval = data[1]
    chat_id = call.message.chat.id

    if chat_id in chat_schedulers:
        scheduler = chat_schedulers[chat_id]
        scheduler.shutdown()
        del chat_schedulers[chat_id]

    time = 0

    if interval == '10 минут':
        time = 10
    elif interval == 'пол часа':
        time = 30
    elif interval == 'час':
        time = 60


    update_config_collapse(chat_id, 0, False, time, True)
    print("РАБОТАЮТ ОБНОВЛЕНИЯ РЫНКА")
    configure_market_scheduler()


@bot.callback_query_handler(func=lambda call: call.data == 'remove_market_updates')
def remove_market_updates_handler(call):
    chat_id = call.message.chat.id
    update_config_collapse(chat_id, 0, False, 0, False)
    if chat_id in chat_schedulers:
        scheduler = chat_schedulers[chat_id]
        scheduler.shutdown()
        del chat_schedulers[chat_id]
        bot.send_message(chat_id, 'Вы отписались от обновлений')
    else:
        bot.send_message(chat_id, 'Вы не подписаны на обновления')