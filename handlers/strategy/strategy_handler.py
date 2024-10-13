from db.db import get_t_token
from telebot import types
from bot.bot import bot
from handlers.strategy.sandbox_info import sandbox_info_handler
from handlers.strategy.account_selection import get_account_handler
from handlers.strategy.strategy_set import set_signals
from handlers.strategy.strategy_remove import remove_strategy_handler
from handlers.strategy.signals.signals_handler import show_signals_handler

@bot.message_handler(func=lambda message: message.text == 'Стратегии')
def strategy_handler(message):
    chat_id = message.chat.id
    token = get_t_token(chat_id)
    if token is not None:
        inline_keyboard = types.InlineKeyboardMarkup()
        buttons = [
            types.InlineKeyboardButton(text='Настроить сигналы', callback_data='signals_set'),
            types.InlineKeyboardButton(text='Настроить стратегию', callback_data='strategy_set'),
            types.InlineKeyboardButton(text='Отключить стратегию', callback_data='strategy_remove'),
            types.InlineKeyboardButton(text='Выбор счета', callback_data='account_selection'),
            types.InlineKeyboardButton(text='Информация о песочнице', callback_data='sandbox_info'),
        ]
        inline_keyboard.add(*buttons)
        bot.send_message(chat_id, 'Выберите опцию', reply_markup=inline_keyboard)