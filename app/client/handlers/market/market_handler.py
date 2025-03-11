from telebot import types
from app.client.bot.bot import bot
from app.backend.api_client import ApiClient
from app.client.handlers.market.get_market_collapse import get_market_collapse_handler
from app.client.handlers.market.get_market_growth import get_market_growth_handler
from app.client.handlers.market.get_market_change import get_market_change_handler

# Создаем экземпляр API-клиента
api_client = ApiClient()


@bot.message_handler(func=lambda message: message.text == 'Состояние рынка')
def market_handler(message):
    """
    Основной обработчик для раздела "Состояние рынка".
    
    Отображает меню с доступными опциями для работы с состоянием рынка.
    """
    chat_id = message.chat.id
    
    inline_keyboard = types.InlineKeyboardMarkup()
    buttons = [
        types.InlineKeyboardButton(text='Получить обвал рынка по тикерам', callback_data='get_market_collapse'),
        types.InlineKeyboardButton(text='Получить рост рынка по тикерам', callback_data='get_market_growth'),
        types.InlineKeyboardButton(text='Получить изменение состояния рынка по тикерам', callback_data='get_market_change'),
    ]
    
    for button in buttons:
        inline_keyboard.add(button)
    
    bot.send_message(chat_id, 'Выберите действие', reply_markup=inline_keyboard)
