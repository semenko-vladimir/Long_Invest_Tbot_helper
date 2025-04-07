from app.client.bot.bot import bot
from telebot import types
from app.client.handlers.utils.message_utils import send_or_edit_message


@bot.callback_query_handler(func=lambda call: call.data == 'base_instruments')
def base_instruments_handler(call):
    """
    Обработчик для раздела базы знаний об инструментах.
    """
    chat_id = call.message.chat.id
    
    text = (
        "🔧 *РАЗДЕЛ: ИНСТРУМЕНТЫ*\n\n"
        "Этот раздел позволяет управлять финансовыми инструментами в вашем портфеле.\n\n"
        "*Основные действия:*\n"
        "🔹 Добавление инструмента - добавляйте новые акции, ETF и другие активы\n"
        "🔹 Получение списка - просматривайте все ваши активные инструменты с FIGI\n"
        "🔹 Удаление инструмента - удаляйте отдельные инструменты по выбору\n"
        "🔹 Удаление всех инструментов - быстрая очистка всего списка инструментов\n\n"
        "💡 *Совет:* Для начала работы добавьте несколько инструментов через раздел 'Инструменты' в главном меню."
    )
    
    # Создаем кнопку для возврата в меню базы знаний
    inline_keyboard = types.InlineKeyboardMarkup()
    back_button = types.InlineKeyboardButton(text='◀️ Назад к базе знаний', callback_data='back_to_knowledge_base')
    inline_keyboard.add(back_button)
    
    send_or_edit_message(chat_id, text, reply_markup=inline_keyboard)