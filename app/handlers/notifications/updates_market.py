from bot.bot import bot
from db.db import get_all_tickers, get_config, get_t_token, update_config_collapse
from telebot import types
from config.schedulers_config import configure_market_scheduler
from handlers.notifications.utils.utils import stop_scheduler, get_interval_from_callback

@bot.callback_query_handler(func=lambda call: call.data == 'user_add_market_updates')
def add_market_updates_handler(call):
    chat_id = call.message.chat.id
    config_data = get_config()

    for row in config_data:
        if row[4] and chat_id == row[1]:
            bot.send_message(chat_id, 'Вы уже подписаны на обновления рынка')
            return

    bot.send_message(chat_id, 'Вы автоматически будете отписаны от обновлений рынка')
    token = get_t_token(chat_id)
    if token is not None:
        tickers = get_all_tickers(chat_id)
        if not tickers:
            bot.send_message(chat_id, 'У вас нет активных тикеров')
        else:
            inline_keyboard = types.InlineKeyboardMarkup()
            buttons = [types.InlineKeyboardButton(text=t, callback_data=f'uinterval_{t}') for t in ['10 минут', 'пол часа', 'час']]
            inline_keyboard.add(*buttons)
            bot.send_message(chat_id, 'Выберите интервал для получения обновлений', reply_markup=inline_keyboard)

@bot.callback_query_handler(func=lambda call: call.data.startswith('uinterval_'))
def market_interval_handler(call):
    chat_id = call.message.chat.id
    stop_scheduler(chat_id)
    
    time = get_interval_from_callback(call.data)
    update_config_collapse(chat_id, 0, False, time, True)
    print("РАБОТАЮТ ОБНОВЛЕНИЯ РЫНКА")
    configure_market_scheduler()

@bot.callback_query_handler(func=lambda call: call.data == 'remove_market_updates')
def remove_market_updates_handler(call):
    chat_id = call.message.chat.id
    update_config_collapse(chat_id, 0, False, 0, False)
    stop_scheduler(chat_id)
    bot.send_message(chat_id, 'Вы отписались от обновлений')
