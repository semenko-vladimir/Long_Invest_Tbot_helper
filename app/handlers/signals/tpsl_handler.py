from db.db import get_t_token, update_signal_tpsl
from bot.bot import bot
from store.store import user_tpsl_data

@bot.callback_query_handler(func=lambda call: call.data == 'signal_tpsl')
def tpsl_handler(call):
    chat_id = call.message.chat.id
    bot.send_message(chat_id, 'Введите значение для Take Profit')
    bot.register_next_step_handler_by_chat_id(chat_id, get_tp_value)


def get_tp_value(message):
    chat_id = message.chat.id
    tp_value = message.text
    user_tpsl_data[chat_id] = {'tp_value': tp_value}
    bot.send_message(chat_id, 'Введите значение для Stop Loss')
    bot.register_next_step_handler_by_chat_id(chat_id, get_sl_value)


def get_sl_value(message):
    chat_id = message.chat.id
    sl_value = message.text
    user_tpsl_data[chat_id]['sl_value'] = sl_value
    tp_value = user_tpsl_data[chat_id]['tp_value']

    update_signal_tpsl(chat_id, tp_value, sl_value)

    bot.send_message(chat_id, 'Take Profit/Stop Loss настроен с параметрами:\nTake Profit = ' + user_tpsl_data[chat_id]['tp_value'] + '\nStop Loss = ' + user_tpsl_data[chat_id]['sl_value'])

    del user_tpsl_data[chat_id]