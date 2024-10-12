from db import delete_all_instruments, get_t_token
from bot import bot

@bot.callback_query_handler(func=lambda call: call.data == 'delete_all_instruments')
def delete_all_instruments_handler(call):
    chat_id = call.message.chat.id
    token = get_t_token(chat_id)
    if token is not None:
        delete_all_instruments(chat_id)
        bot.send_message(chat_id, "Все тикеры были удалены")