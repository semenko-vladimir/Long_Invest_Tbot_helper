from telebot import types
from app.client.bot.bot import bot

# Импортируем обработчики для инструментов
from app.client.handlers.instruments.add_instrument import add_instrument_handler
from app.client.handlers.instruments.delete_instrument import delete_instrument_handler
from app.client.handlers.instruments.delete_all_instruments import delete_all_instruments_handler
from app.client.handlers.instruments.get_all_instruments import get_all_instruments_handler


@bot.message_handler(func=lambda message: message.text == 'Инструменты')
def instruments_handler(message):
    """
    Основной обработчик для раздела "Инструменты".
    
    Отображает меню с доступными действиями для работы с инструментами.
    """
    chat_id = message.chat.id
    
    inline_keyboard = types.InlineKeyboardMarkup()
    buttons = [
        types.InlineKeyboardButton(text='Добавить инструмент', callback_data='add_instrument'),
        types.InlineKeyboardButton(text='Получить мои инструменты', callback_data='get_all_instruments'),
        types.InlineKeyboardButton(text='Удалить мои инструменты', callback_data='delete_all_instruments'),
        types.InlineKeyboardButton(text='Удалить инструмент', callback_data='delete_instrument'),
    ]
    
    for button in buttons:
        inline_keyboard.add(button)
    
    bot.send_message(chat_id, 'Выберите действие', reply_markup=inline_keyboard)
