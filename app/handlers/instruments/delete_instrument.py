from db.db import delete_instrument, get_all_tickers, get_t_token
from telebot import types
from bot.bot import bot

@bot.callback_query_handler(func=lambda call: call.data == 'delete_instrument')
def delete_instrument_handler(call):
    chat_id = call.message.chat.id
    token = get_t_token(chat_id)
    if token is not None:
        tickers = get_all_tickers(chat_id)
        if not tickers:
            bot.send_message(chat_id, 'У вас нет активных тикеров')
        else:
            inline_keyboard = types.InlineKeyboardMarkup()
            for ticker in tickers:
                button = types.InlineKeyboardButton(text=str(ticker[0]), callback_data=f'ticker_{ticker[0]}')
                inline_keyboard.add(button)
            bot.send_message(chat_id, 'Выберите тикер для удаления', reply_markup=inline_keyboard)

# Обработчик для callback удаления тикера
@bot.callback_query_handler(func=lambda call: call.data.startswith('ticker_'))
def delete_ticker_step(call):
    ticker = call.data.replace('ticker_', '')
    delete_instrument(call.message.chat.id, ticker)
    bot.send_message(call.message.chat.id, f'Тикер "{ticker}" успешно удален')