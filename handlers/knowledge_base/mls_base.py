from db.db import get_t_token
from bot.bot import bot


@bot.callback_query_handler(func=lambda call: call.data == 'base_mls')
def base_mls_handler(call):
    chat_id = call.message.chat.id
    token = get_t_token(chat_id)
    if token is not None:
        text = [
            f'Раздел "Middle/Long сигналы" позволяет вам получить сигнал и его визуальное представление.\n',
                       
            f'\nВы можете выбрать временной промежуток, инструмент и сигнал.\n',

            f'\nБолее подробную информацию о сигналах смотрите в разделе "Сигналы и их настройка".\n'
        ]



        bot.send_message(chat_id=chat_id, text='\n'.join(text))