from db.db import get_sandbox_token, get_t_token, update_sandbox_trigger
from telebot import types
from bot.bot import bot


@bot.callback_query_handler(func=lambda call: call.data == 'account_selection')
def get_account_handler(call):
    chat_id = call.message.chat.id
    token = get_t_token(chat_id)
    if token is not None:
        inline_keyboard = types.InlineKeyboardMarkup()
        buttons = [
            types.InlineKeyboardButton(text='Боевой счет', callback_data='real_account'),
            types.InlineKeyboardButton(text='Песочница', callback_data='sandbox_account'),
        ]
        inline_keyboard.add(*buttons)
        bot.send_message(chat_id, 'Выберите счет:', reply_markup=inline_keyboard)


@bot.callback_query_handler(func=lambda call: call.data == 'real_account')
def real_account(call):
    chat_id = call.message.chat.id
    token = get_t_token(chat_id)
    if token is not None:
        update_sandbox_trigger(chat_id, 0)
        bot.send_message(chat_id, 'Вы выбрали боевой счет')

from tinkoff.invest import Client
from tinkoff.invest.services import SandboxService

@bot.callback_query_handler(func=lambda call: call.data == 'sandbox_account')
def sandbox_account(call):
    chat_id = call.message.chat.id
    token = get_t_token(chat_id)
    if token is not None:
        update_sandbox_trigger(chat_id, 1)

        sandbox_token = get_sandbox_token(chat_id)

        with Client(sandbox_token) as client:
            sb: SandboxService = client.sandbox

            r = sb.get_sandbox_accounts().accounts

            if len(r) > 0:
                bot.send_message(chat_id, 'Вы выбрали песочницу.')
            else:
                sb.open_sandbox_account()
                bot.send_message(chat_id, 'Создан новый счет в песочнице. Выбрана песочница.')
        