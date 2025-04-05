from telebot import types
from app.client.bot.bot import bot
from app.client.handlers.bot.sandbox_info import sandbox_info_handler
from app.client.handlers.bot.account_selection import get_account_handler
from app.client.handlers.bot.strategy_set import set_signals
from app.client.handlers.bot.strategy_remove import remove_strategy_handler

@bot.message_handler(func=lambda message: message.text == 'Торговый робот')
def bot_handler(message):
    """
    Основной обработчик для раздела "Торговый робот".
    
    Отображает меню с доступными опциями для работы с торговым роботом.
    """
    chat_id = message.chat.id
    
    inline_keyboard = types.InlineKeyboardMarkup()
    buttons = [
        types.InlineKeyboardButton(text='Настроить стратегию', callback_data='strategy_set'),
        types.InlineKeyboardButton(text='Отключить стратегию', callback_data='strategy_remove'),
        types.InlineKeyboardButton(text='Выбор счета', callback_data='account_selection'),
        types.InlineKeyboardButton(text='Информация о песочнице', callback_data='sandbox_info'),
    ]
    
    for button in buttons:
        inline_keyboard.add(button)
    
    bot.send_message(chat_id, 'Выберите опцию', reply_markup=inline_keyboard)
