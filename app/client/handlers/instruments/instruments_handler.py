from telebot import types
from app.client.bot.bot import bot
from app.client.handlers.utils.message_utils import last_messages

# Импортируем обработчики для инструментов
from app.client.handlers.instruments.add_instrument import add_instrument_handler
from app.client.handlers.instruments.delete_instrument import delete_instrument_handler
from app.client.handlers.instruments.delete_all_instruments import delete_all_instruments_handler
from app.client.handlers.instruments.get_all_instruments import get_all_instruments_handler


def send_instruments_menu(chat_id):
    inline_keyboard = types.InlineKeyboardMarkup()
    buttons = [
        types.InlineKeyboardButton(text='Add ticker', callback_data='add_instrument'),
        types.InlineKeyboardButton(text='Show watchlist', callback_data='get_all_instruments'),
        types.InlineKeyboardButton(text='Remove ticker', callback_data='delete_instrument'),
        types.InlineKeyboardButton(text='Clear watchlist', callback_data='delete_all_instruments'),
    ]
    
    for button in buttons:
        inline_keyboard.add(button)
    
    # Всегда отправляем новое сообщение для первого обработчика
    msg = bot.send_message(
        chat_id=chat_id, 
        text='*Watchlist*\n\nMaintain the tickers you want to follow for dividends and long-term review.',
        reply_markup=inline_keyboard,
        parse_mode='Markdown',
    )
    
    # Сохраняем ID сообщения для последующего редактирования
    last_messages[chat_id] = msg.message_id


@bot.message_handler(func=lambda message: message.text in {'Watchlist', 'Instruments', 'Инструменты'})
def instruments_handler(message):
    """
    Основной обработчик для раздела "Инструменты".

    Отображает меню с доступными действиями для работы с инструментами.
    """
    send_instruments_menu(message.chat.id)


@bot.callback_query_handler(func=lambda call: call.data == 'settings_instruments')
def settings_instruments_handler(call):
    send_instruments_menu(call.message.chat.id)
