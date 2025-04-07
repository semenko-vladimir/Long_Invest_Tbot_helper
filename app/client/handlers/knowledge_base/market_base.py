from app.client.bot.bot import bot
from telebot import types
from app.client.handlers.utils.message_utils import send_or_edit_message


@bot.callback_query_handler(func=lambda call: call.data == 'base_market')
def base_market_handler(call):
    """
    Обработчик для раздела базы знаний о состоянии рынка.
    """
    chat_id = call.message.chat.id
    
    # Сохраняем оригинальный текст, только добавляем форматирование и эмодзи
    text = (
        "📈 *РАЗДЕЛ: СОСТОЯНИЕ РЫНКА*\n\n"
        "Раздел \"Состояние рынка\" позволяет вам получить текущее состояние рынка по выбранной категории.\n\n"
        "Вы можете получить падения, рост или изменения цен ваших инструментов.\n"
        "Вы можете настроить временной интервал и процентные величины.\n\n"
        "*При получении уведомлений вам будет предоставлена следующая информация:*\n"
        "🔹 Название инструмента\n"
        "🔹 Тип инструмента\n"
        "🔹 Тикер инструмента\n"
        "🔹 Изменение цены за выбранный период в %\n"
        "🔹 Цена закрытия последней свечи\n"
        "🔹 Максимальная цена\n"
        "🔹 Минимальная цена\n"
    )
    
    # Создаем кнопку для возврата в меню базы знаний
    inline_keyboard = types.InlineKeyboardMarkup()
    back_button = types.InlineKeyboardButton(text='◀️ Назад к базе знаний', callback_data='back_to_knowledge_base')
    inline_keyboard.add(back_button)
    
    send_or_edit_message(chat_id, text, reply_markup=inline_keyboard)