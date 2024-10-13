from db.db import get_sandbox_token, get_t_token
from telebot import types
from bot.bot import bot
from tinkoff.invest import Client, RequestError
from tinkoff.invest.services import SandboxService
from utils.helpers import to_money_value
from utils.methods import get_sandbox_portfolio
from tinkoff.invest import MoneyValue


@bot.callback_query_handler(func=lambda call: call.data == 'sandbox_info')
def sandbox_info_handler(call):
    chat_id = call.message.chat.id
    token = get_t_token(chat_id)
    if token is not None:

        sandbox_token = get_sandbox_token(chat_id)
        if sandbox_token is None:
            bot.send_message(chat_id, 'У вас нет открытого счета в песочнице')
            return
        
        else:

            inline_keyboard = types.InlineKeyboardMarkup()
            buttons = [
                types.InlineKeyboardButton(text='Получить портфолио песочницы', callback_data='get_sandbox'),
                types.InlineKeyboardButton(text='Пополнить баланс', callback_data='set_sandbox_balance'),
            ]
            inline_keyboard.add(*buttons)
            bot.send_message(chat_id, 'Выберите опцию', reply_markup=inline_keyboard)


@bot.callback_query_handler(func=lambda call: call.data == 'set_sandbox_balance')
def set_sandbox_balance(call):
    chat_id = call.message.chat.id
    token = get_t_token(chat_id)
    if token is not None:

        sandbox_token = get_sandbox_token(chat_id)

        if sandbox_token is None:
            bot.send_message(chat_id, 'У вас нет открытого счета в песочнице')
            return
        
        else:

            bot.send_message(chat_id, 'Введите сумму для пополнения баланса')
            bot.register_next_step_handler(call.message, set_sandbox_balance_2)


def set_sandbox_balance_2(message):
    chat_id = message.chat.id
    token = get_t_token(chat_id)
    if token is not None:

        sandbox_token = get_sandbox_token(chat_id)

        if sandbox_token is None:
            bot.send_message(chat_id, 'У вас нет открытого счета в песочнице')
            return
        
        else:

            # Проверка на ввод числа
            try:
                money_value = int(message.text)
                
                with Client(token) as client:
                    sb: SandboxService = client.sandbox

                    accounts = sb.get_sandbox_accounts()
                    account_id = accounts.accounts[0].id

                    units, nano = to_money_value(money_value)

                    sb.sandbox_pay_in(
                        account_id=account_id,
                        amount=MoneyValue(units=units, nano=nano, currency='rub'),
                    )

                    bot.send_message(chat_id, f'Баланс пополнен на {money_value} руб.')
                    


            except ValueError:
                msg = bot.send_message(chat_id, "Пожалуйста, введите корректное количество (целое число):")
                bot.register_next_step_handler(msg, set_sandbox_balance_2)
                return
            

@bot.callback_query_handler(func=lambda call: call.data == 'get_sandbox')
def get_sandbox(call):
    chat_id = call.message.chat.id
    token = get_t_token(chat_id)
    if token is not None:

        sandbox_token = get_sandbox_token(chat_id)

        portfolio = get_sandbox_portfolio(sandbox_token)

        positions = portfolio['positions']

        text = (
            f"Общая стоимость акций: {portfolio['total_amount_shares']} руб.\n"
            f"Общая стоимость облигаций: {portfolio['total_amount_bonds']} руб.\n"
            f"Общая стоимость фондов: {portfolio['total_amount_etf']} руб.\n"
            f"Общая стоимость валют: {portfolio['total_amount_currencies']} руб.\n"
            f"Ожидаемая доходность: {portfolio['expected_yield']} %\n"
            f"Общая стоимость портфеля: {portfolio['total_amount_portfolio']} руб.\n"
        )

        for position in positions:
            text += (
                f"Тикер: {position['ticker']}\n"
                f"Figi: {position['figi']}\n"
                f"Тип: {position['type']}\n"
                f"Количество: {position['quantity']}\n"
                f"Средневзвешенная цена: {position['average_position_price']}\n"
                f"Ожидаемая доходность: {position['expected_yield']}\n"
                f"Текущая цена: {position['current_price']}\n"
                f"Состояние: {position['blocked']}\n"
            )


        
        bot.send_message(chat_id, text)