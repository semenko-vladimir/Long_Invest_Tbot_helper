from db.db import get_t_token
from bot.bot import bot


@bot.message_handler(func=lambda message: message.text == 'Middle/Long сигналы')
def mls_handler(message):
    chat_id = message.chat.id
    token = get_t_token(chat_id)

    if token is not None:
        pass