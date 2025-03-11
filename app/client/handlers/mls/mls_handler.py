from app.client.bot.bot import bot
from app.backend.api_client import ApiClient
from telebot import types
from app.client.handlers.mls.mls_rsi import mls_rsi_handler
from app.client.handlers.mls.mls_sma import mls_sma_handler
from app.client.handlers.mls.mls_alligator import mls_alligator_handler
from app.client.handlers.mls.mls_bollinger import mls_bollinger_handler
from app.client.handlers.mls.mls_macd import mls_macd_handler
from app.client.handlers.mls.mls_ema import mls_ema_handler

# Создаем экземпляр API-клиента
api_client = ApiClient()


@bot.message_handler(func=lambda message: message.text == 'Middle/Long сигналы(Графики)')
def mls_handler(message):
    """
    Основной обработчик для раздела "Middle/Long сигналы(Графики)".
    
    Отображает меню с доступными сигналами для построения графиков.
    """
    chat_id = message.chat.id
    
    inline_keyboard = types.InlineKeyboardMarkup()
    buttons = [
        types.InlineKeyboardButton(text='RSI', callback_data='calc_mls_rsi'),
        types.InlineKeyboardButton(text='SMA', callback_data='calc_mls_sma'),
        types.InlineKeyboardButton(text='EMA', callback_data='calc_mls_ema'),
        types.InlineKeyboardButton(text='Alligator', callback_data='calc_mls_alligator'),
        types.InlineKeyboardButton(text='Bollinger', callback_data='calc_mls_bollinger'),
        types.InlineKeyboardButton(text='MACD', callback_data='calc_mls_macd'),
    ]
    
    for button in buttons:
        inline_keyboard.add(button)
    
    bot.send_message(chat_id, 'Выберите сигнал', reply_markup=inline_keyboard)
