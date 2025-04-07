from app.client.bot.bot import bot
from telebot import types
from app.client.handlers.utils.message_utils import send_or_edit_message


@bot.callback_query_handler(func=lambda call: call.data == 'base_portfolio')
def base_portfolio_handler(call):
    """
    Обработчик для раздела базы знаний о портфолио.
    """
    chat_id = call.message.chat.id
    
    text = [
        f'📊 *РАЗДЕЛ: ПОРТФОЛИО*\n\n'
        f'Раздел "Получить портфолио" представляет собой получение вашего портфолио.\n',
        
        f'\nЗдесь вы можете получить состояние вашего счета и все активные инструменты портфеля.\n',

        f'\nПосле нажатия на кнопку вы получите полную информацию о вашем портфеле, включая:\n',
        
        f'💹 Общую стоимость акций, облигаций, фондов и валют.\n'
        f'📈 Ожидаемую доходность.\n'
        f'📊 Полный список ваших активов с деталями, такими как тикер, тип, количество и текущая цена.\n'
        
        f'\nЭта информация поможет вам лучше понять состояние ваших инвестиций и принимать более обоснованные решения.\n'
    ]

    # Создаем кнопку для возврата в меню базы знаний
    inline_keyboard = types.InlineKeyboardMarkup()
    back_button = types.InlineKeyboardButton(text='◀️ Назад к базе знаний', callback_data='back_to_knowledge_base')
    inline_keyboard.add(back_button)
    
    send_or_edit_message(chat_id, ''.join(text), reply_markup=inline_keyboard)