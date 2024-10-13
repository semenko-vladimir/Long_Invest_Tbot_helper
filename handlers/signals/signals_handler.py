from db.db import get_t_token
from telebot import types
from bot.bot import bot

from handlers.signals.rsi_handler import rsi_handler
from handlers.signals.sma_handler import sma_handler
from handlers.signals.bollinger_handler import bollinger_handler
from handlers.signals.macd_handler import macd_handler
from handlers.signals.tpsl_handler import tpsl_handler
from handlers.signals.gpt_handler import gpt_handler

@bot.message_handler(func=lambda message: message.text == 'Настройка сигналов')
def show_signals_handler(message):
    chat_id = message.chat.id
    token = get_t_token(chat_id)
    if token is not None:
        inline_keyboard = types.InlineKeyboardMarkup()
        buttons = [
            types.InlineKeyboardButton(text='Take Profit/Stop Loss', callback_data='signal_tpsl'),
            types.InlineKeyboardButton(text='RSI', callback_data='signal_rsi'),
            types.InlineKeyboardButton(text='SMA', callback_data='signal_sma'),
            types.InlineKeyboardButton(text='Alligator', callback_data='signal_alligator'),
            types.InlineKeyboardButton(text='GPT', callback_data='signal_gpt'),
            types.InlineKeyboardButton(text='Bollinger', callback_data='signal_bollinger'),
            types.InlineKeyboardButton(text='MACD', callback_data='signal_macd'),
        ]
        inline_keyboard.add(*buttons)
        bot.send_message(chat_id, 'Выберите сигнал для настройки', reply_markup=inline_keyboard)