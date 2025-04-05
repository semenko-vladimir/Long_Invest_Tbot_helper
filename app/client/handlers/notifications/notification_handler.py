from telebot import types
from app.client.bot.bot import bot
from app.client.handlers.notifications.updates_market import add_market_updates_handler, remove_market_updates_handler
from app.client.handlers.notifications.collapse_market import add_collapse_market_handler, remove_collapse_market_handler

@bot.message_handler(func=lambda message: message.text == 'Уведомления')
def notification_handler(message):
    """
    Основной обработчик для раздела "Уведомления".
    
    Отображает меню с доступными опциями для работы с уведомлениями.
    """
    chat_id = message.chat.id
    
    inline_keyboard = types.InlineKeyboardMarkup()
    buttons = [
        types.InlineKeyboardButton(text='Подписаться на обновления падений рынка', callback_data='user_update_collapse_market'),
        types.InlineKeyboardButton(text='Отписаться от обновлений падений рынка', callback_data='remove_collapse_market'),
        types.InlineKeyboardButton(text='Подписаться на обновления рынка', callback_data='user_add_market_updates'),
        types.InlineKeyboardButton(text='Отписаться от обновлений рынка', callback_data='remove_market_updates'),
    ]
    
    for button in buttons:
        inline_keyboard.add(button)
    
    bot.send_message(chat_id, 'Выберите действие', reply_markup=inline_keyboard)
