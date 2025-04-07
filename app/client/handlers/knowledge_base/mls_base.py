from app.client.bot.bot import bot
from telebot import types
from app.client.handlers.utils.message_utils import send_or_edit_message


@bot.callback_query_handler(func=lambda call: call.data == 'base_mls')
def base_mls_handler(call):
    """
    Обработчик для раздела базы знаний о Middle/Long сигналах.
    """
    chat_id = call.message.chat.id
    
    text = [
        f'📉 *РАЗДЕЛ: MIDDLE/LONG СИГНАЛЫ (ГРАФИКИ)*\n\n'
        f'Раздел "Middle/Long сигналы(Графики)" позволяет вам получить сигнал и его визуальное представление.\n',
                    
        f'\nВы можете выбрать временной промежуток, инструмент и сигнал.\n',

        f'\nБолее подробную информацию о сигналах смотрите в разделе "Сигналы и их настройка".\n'
    ]

    # Создаем кнопку для возврата в меню базы знаний
    inline_keyboard = types.InlineKeyboardMarkup()
    back_button = types.InlineKeyboardButton(text='◀️ Назад к базе знаний', callback_data='back_to_knowledge_base')
    inline_keyboard.add(back_button)
    
    send_or_edit_message(chat_id, ''.join(text), reply_markup=inline_keyboard)