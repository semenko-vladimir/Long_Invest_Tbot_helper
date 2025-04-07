from telebot import types
from app.client.bot.bot import bot
from app.client.handlers.utils.message_utils import send_or_edit_message, last_messages
from app.client.handlers.market.get_market_collapse import get_market_collapse_handler
from app.client.handlers.market.get_market_growth import get_market_growth_handler
from app.client.handlers.market.get_market_change import get_market_change_handler


@bot.message_handler(func=lambda message: message.text == 'Состояние рынка')
def market_handler(message):
    """
    Основной обработчик для раздела "Состояние рынка".
    
    Отображает меню с доступными опциями для работы с состоянием рынка.
    """
    chat_id = message.chat.id
    
    inline_keyboard = types.InlineKeyboardMarkup()
    buttons = [
        types.InlineKeyboardButton(text='📉 Получить обвал рынка по тикерам', callback_data='get_market_collapse'),
        types.InlineKeyboardButton(text='📈 Получить рост рынка по тикерам', callback_data='get_market_growth'),
        types.InlineKeyboardButton(text='📊 Получить изменение состояния рынка по тикерам', callback_data='get_market_change'),
    ]
    
    for button in buttons:
        inline_keyboard.add(button)
    
    # Отправляем новое сообщение для первого обработчика
    msg = bot.send_message(
        chat_id=chat_id, 
        text='📈 *Состояние рынка*\n\nВыберите действие:', 
        reply_markup=inline_keyboard
    )
    
    # Сохраняем ID сообщения для последующего редактирования
    last_messages[chat_id] = msg.message_id
