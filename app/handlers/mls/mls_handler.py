from db.db import get_t_token
from bot.bot import bot
from telebot import types
from handlers.mls.mls_rsi import mls_rsi_handler
from handlers.mls.mls_sma import mls_sma_handler
from handlers.mls.mls_alligator import mls_alligator_handler
from handlers.mls.mls_bollinger import mls_bollinger_handler
from handlers.mls.mls_macd import mls_macd_handler
from handlers.mls.mls_ema import mls_ema_handler

@bot.message_handler(func=lambda message: message.text == 'Middle/Long сигналы')
def mls_handler(message):
    chat_id = message.chat.id
    token = get_t_token(chat_id)

    if token is not None:
        inline_keyboard = types.InlineKeyboardMarkup()
        buttons = [
            types.InlineKeyboardButton(text='RSI', callback_data='calc_mls_rsi'),
            types.InlineKeyboardButton(text='SMA', callback_data='calc_mls_sma'),
            types.InlineKeyboardButton(text='EMA', callback_data='calc_mls_ema'),
            types.InlineKeyboardButton(text='Alligator', callback_data='calc_mls_alligator'),
            types.InlineKeyboardButton(text='Bollinger', callback_data='calc_mls_bollinger'),
            types.InlineKeyboardButton(text='MACD', callback_data='calc_mls_macd'),
        ]
        inline_keyboard.add(*buttons)
        bot.send_message(chat_id, 'Выберите сигнал', reply_markup=inline_keyboard)