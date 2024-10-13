from db.db import get_t_token, insert_instrument
from bot.bot import bot
from utils.methods import get_figi_by_ticker


@bot.callback_query_handler(func=lambda call: call.data == 'add_instrument')
def add_instrument_handler(call):
    chat_id = call.message.chat.id
    token = get_t_token(chat_id)
    if token is not None:
        bot.send_message(chat_id, 'Пожалуйста, введите тикер')
        bot.register_next_step_handler(call.message, add_ticker_step)

def add_ticker_step(message):
    ticker = message.text.upper()
    chat_id = message.chat.id
    figi = get_figi_by_ticker(ticker)
    if figi is None:
        bot.send_message(message.chat.id, 'Не удалось найти информацию по данному инструменту')
    else:
        result = insert_instrument(chat_id, ticker, figi)
        bot.send_message(message.chat.id, result)