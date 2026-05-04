from telebot import types
from app.client.bot.bot import bot
from app.client.handlers.utils.message_utils import send_or_edit_message, last_messages
from app.client.handlers.bot.sandbox_info import sandbox_info_handler
from app.client.handlers.bot.account_selection import get_account_handler
from app.client.handlers.bot.strategy_set import set_signals
from app.client.handlers.bot.strategy_remove import remove_strategy_handler

@bot.message_handler(func=lambda message: message.text == 'Торговый робот')
def bot_handler(message):
    """
    Основной обработчик legacy-раздела стратегий, не входящего в активный investor v1 runtime.
    
    Отображает legacy-меню для обратной совместимости без представления его как активного v1 workflow.
    """
    chat_id = message.chat.id
    
    inline_keyboard = types.InlineKeyboardMarkup()
    buttons = [
        types.InlineKeyboardButton(text='⚙️ Legacy strategy settings', callback_data='strategy_set'),
        types.InlineKeyboardButton(text='🛑 Legacy strategy stop', callback_data='strategy_remove'),
        types.InlineKeyboardButton(text='💼 Account selection (legacy)', callback_data='account_selection'),
        types.InlineKeyboardButton(text='ℹ️ Sandbox info', callback_data='sandbox_info'),
    ]
    
    for button in buttons:
        inline_keyboard.add(button)
    
    # Отправляем новое сообщение для первого обработчика
    msg = bot.send_message(
        chat_id=chat_id, 
        text='*Legacy strategy tools*\n\nThis area is retained for migration safety and is not part of the active investor v1 manual workflow.',
        reply_markup=inline_keyboard
    )
    
    # Сохраняем ID сообщения для последующего редактирования
    last_messages[chat_id] = msg.message_id
