from app.client.bot.bot import bot
from app.backend.api_client import ApiClient
from telebot import types

from app.client.handlers.knowledge_base.instruments_base import base_instruments_handler
from app.client.handlers.knowledge_base.portfolio_base import base_portfolio_handler
from app.client.handlers.knowledge_base.notifications_base import base_notifications_handler
from app.client.handlers.knowledge_base.market_base import base_market_handler
from app.client.handlers.knowledge_base.dividends_base import base_dividends_handler
from app.client.handlers.knowledge_base.bot_base import base_bot_handler
from app.client.handlers.knowledge_base.mls_base import base_mls_handler
from app.client.handlers.knowledge_base.signals_base import base_signals_handler

# Создаем экземпляр API-клиента
api_client = ApiClient()


@bot.message_handler(func=lambda message: message.text == 'База знаний')
def knowledge_base_handler(message):
    """
    Основной обработчик для раздела "База знаний".
    
    Отображает меню с доступными разделами базы знаний.
    """
    chat_id = message.chat.id
    
    inline_keyboard = types.InlineKeyboardMarkup()
    buttons = [
        types.InlineKeyboardButton(text='Портфолио', callback_data='base_portfolio'),
        types.InlineKeyboardButton(text='Инструменты', callback_data='base_instruments'),
        types.InlineKeyboardButton(text='Уведомления', callback_data='base_notifications'),
        types.InlineKeyboardButton(text='Состояние рынка', callback_data='base_market'),
        types.InlineKeyboardButton(text='Дивиденды', callback_data='base_dividends'),
        types.InlineKeyboardButton(text='Торговый робот', callback_data='base_bot'),
        types.InlineKeyboardButton(text='Middle/Long сигналы(Графики)', callback_data='base_mls'),
        types.InlineKeyboardButton(text='Сигналы и их настройка', callback_data='base_signals'),
    ]
    
    for button in buttons:
        inline_keyboard.add(button)
    
    bot.send_message(chat_id, 'База знаний', reply_markup=inline_keyboard)
