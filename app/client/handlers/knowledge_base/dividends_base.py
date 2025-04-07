from app.client.bot.bot import bot
from telebot import types
from app.client.handlers.utils.message_utils import send_or_edit_message


@bot.callback_query_handler(func=lambda call: call.data == 'base_dividends')
def base_dividends_handler(call):
    """
    Обработчик для раздела базы знаний о дивидендах.
    """
    chat_id = call.message.chat.id
    
    text = (
        "💰 *РАЗДЕЛ: ДИВИДЕНДЫ*\n\n"
        "Дивиденды — это часть прибыли компании, распределяемая между акционерами.\n\n"
        "*Основная информация:*\n"
        "🔹 Дивидендный календарь - ключевые даты выплат и закрытия реестров\n"
        "🔹 Размеры выплат - суммы и периодичность дивидендных выплат\n"
        "🔹 Дивидендная доходность - процентное соотношение дивиденда к цене акции\n"
        "🔹 Дата фиксации реестра - последний день для включения в список получателей\n"
        "🔹 Последний день покупки - deadline для приобретения акций с дивидендами\n\n"
        "💡 *Совет:* Для стабильного пассивного дохода создайте портфель из компаний с историей регулярных выплат."
    )
    
    # Создаем кнопку для возврата в меню базы знаний
    inline_keyboard = types.InlineKeyboardMarkup()
    back_button = types.InlineKeyboardButton(text='◀️ Назад к базе знаний', callback_data='back_to_knowledge_base')
    inline_keyboard.add(back_button)
    
    send_or_edit_message(chat_id, text, reply_markup=inline_keyboard)