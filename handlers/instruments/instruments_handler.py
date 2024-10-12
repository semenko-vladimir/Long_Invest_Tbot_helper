from db import get_t_token
from telebot import types
from bot import bot

from handlers.instruments.add_instrument import add_instrument_handler
from handlers.instruments.delete_instrument import delete_instrument_handler
from handlers.instruments.delete_all_instruments import delete_all_instruments_handler
from handlers.instruments.get_all_instruments import get_all_instruments_handler


@bot.message_handler(func=lambda message: message.text == 'Инструменты')
def instruments_handler(message):
    chat_id = message.chat.id
    token = get_t_token(chat_id)
    if token is not None:
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