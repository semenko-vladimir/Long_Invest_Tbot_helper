from telebot import types
from app.client.bot.bot import bot
from app.client.handlers.utils.message_utils import last_messages
from app.client.handlers.bot.sandbox_info import sandbox_info_handler

@bot.message_handler(func=lambda message: message.text in {'Settings', 'Инвестор'})
def bot_handler(message):
    """
    Основной обработчик для раздела долгосрочного инвестора.
    
    Отображает sandbox-first меню без сигналов и автоторговли.
    """
    chat_id = message.chat.id
    
    inline_keyboard = types.InlineKeyboardMarkup()
    buttons = [
        types.InlineKeyboardButton(text='Sandbox info', callback_data='sandbox_info'),
        types.InlineKeyboardButton(text='Watchlist', callback_data='settings_instruments'),
        types.InlineKeyboardButton(text='Help', callback_data='investor_help'),
    ]
    
    for button in buttons:
        inline_keyboard.add(button)
    
    # Отправляем новое сообщение для первого обработчика
    msg = bot.send_message(
        chat_id=chat_id, 
        text='*Investor tools*\n\nInvestor v1 uses sandbox mode by default, manual orders, and no signal automation.',
        reply_markup=inline_keyboard,
        parse_mode='Markdown'
    )
    
    # Сохраняем ID сообщения для последующего редактирования
    last_messages[chat_id] = msg.message_id


@bot.callback_query_handler(func=lambda call: call.data == 'investor_help')
def investor_help_callback(call):
    from app.client.handlers.help.help_handler import send_help

    send_help(call.message.chat.id)
