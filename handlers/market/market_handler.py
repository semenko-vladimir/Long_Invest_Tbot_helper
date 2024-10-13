from telebot import types
from bot.bot import bot
from db.db import get_t_token
from handlers.market.get_market_collapse import get_market_collapse_handler
from handlers.market.get_market_growth import get_market_growth_handler
from handlers.market.get_market_change import get_market_change_handler

@bot.message_handler(func=lambda message: message.text == 'Состояние рынка')
def market_handler(message):
    chat_id = message.chat.id
    token = get_t_token(chat_id)
    if token is not None:
        inline_keyboard = types.InlineKeyboardMarkup()
        buttons = [
            types.InlineKeyboardButton(text='Получить обвал рынка по тикерам', callback_data='get_market_collapse'),
            types.InlineKeyboardButton(text='Получить рост рынка по тикерам', callback_data='get_market_growth'),
            types.InlineKeyboardButton(text='Получить изменение состояния рынка по тикерам', callback_data='get_market_change'),
        ]
        inline_keyboard.add(*buttons)
        bot.send_message(chat_id, 'Выберите действие', reply_markup=inline_keyboard)