from app.client.bot.bot import bot
from telebot import types
from app.client.handlers.utils.message_utils import send_or_edit_message


@bot.callback_query_handler(func=lambda call: call.data == 'base_notifications')
def base_notifications_handler(call):
    """
    Обработчик для раздела базы знаний об уведомлениях.
    """
    chat_id = call.message.chat.id
    
    text = [
        f'🔔 *РАЗДЕЛ: УВЕДОМЛЕНИЯ*\n\n'
        f'Раздел "Уведомления" позволяет вам подписаться на уведомления изменения цен по вашим инструментам.\n',
        
        f'\nВы можете получать уведомления падений цен ваших инструментов или изменения цен ваших инструментов.\n'
        f'\n Также вы можете отписаться от выбранной категории уведомлений.\n'
        f'\n При подписке на одну категорию уведомлений, вы будете автоматически отписаны от другой категории.\n',
        
        f'Вы можете настроить время получения уведомлений.\n',

        f'\n*При получении уведомлений вам будет предоставлена следующая информация:*\n'
        f'🔹 Название инструмента\n'
        f'🔹 Тип инструмента\n'
        f'🔹 Тикер инструмента\n'
        f'🔹 Изменение цены за выбранный период в %\n'
        f'🔹 Цена закрытия последней свечи\n'
        f'🔹 Максимальная цена\n'
        f'🔹 Минимальная цена\n'
    ]

    # Создаем кнопку для возврата в меню базы знаний
    inline_keyboard = types.InlineKeyboardMarkup()
    back_button = types.InlineKeyboardButton(text='◀️ Назад к базе знаний', callback_data='back_to_knowledge_base')
    inline_keyboard.add(back_button)
    
    send_or_edit_message(chat_id, ''.join(text), reply_markup=inline_keyboard)