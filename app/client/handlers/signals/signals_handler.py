from telebot import types
from app.client.bot.bot import bot

from app.client.handlers.signals.rsi_handler import rsi_handler
from app.client.handlers.signals.sma_handler import sma_handler
from app.client.handlers.signals.ema_handler import ema_handler
from app.client.handlers.signals.bollinger_handler import bollinger_handler
from app.client.handlers.signals.macd_handler import macd_handler
from app.client.handlers.signals.tpsl_handler import tpsl_handler
from app.client.handlers.signals.gpt_handler import gpt_handler
from app.client.handlers.signals.alligator_handler import alligator_on


@bot.message_handler(func=lambda message: message.text == 'Настройка сигналов')
def show_signals_handler(message):
    """
    Основной обработчик для раздела "Настройка сигналов".
    
    Отображает меню с доступными сигналами для настройки.
    """
    chat_id = message.chat.id
    
    inline_keyboard = types.InlineKeyboardMarkup()
    buttons = [
        types.InlineKeyboardButton(text='Take Profit/Stop Loss', callback_data='signal_tpsl'),
        types.InlineKeyboardButton(text='RSI', callback_data='signal_rsi'),
        types.InlineKeyboardButton(text='SMA', callback_data='signal_sma'),
        types.InlineKeyboardButton(text='EMA', callback_data='signal_ema'),
        types.InlineKeyboardButton(text='Alligator', callback_data='signal_alligator'),
        types.InlineKeyboardButton(text='GPT', callback_data='signal_gpt'),
        types.InlineKeyboardButton(text='Bollinger', callback_data='signal_bollinger'),
        types.InlineKeyboardButton(text='MACD', callback_data='signal_macd'),
    ]
    
    # Добавляем кнопки в клавиатуру
    for button in buttons:
        inline_keyboard.add(button)
    
    bot.send_message(chat_id, 'Выберите сигнал для настройки', reply_markup=inline_keyboard)
