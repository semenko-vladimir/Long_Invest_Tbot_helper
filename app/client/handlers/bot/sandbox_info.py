from telebot import types
from app.client.bot.bot import bot
from app.backend.api_client import ApiClient
from tinkoff.invest import Client, RequestError
from tinkoff.invest.services import SandboxService
from app.client.utils.helpers import to_money_value
from app.client.utils.methods import get_sandbox_portfolio
from tinkoff.invest import MoneyValue
from dotenv import load_dotenv
import os

# Создаем экземпляр API-клиента
api_client = ApiClient()

# Функция для получения токенов из переменных окружения
def get_tokens():
    """
    Получает токены из переменных окружения.
    
    Returns:
        dict: Словарь с токенами
    """
    load_dotenv()
    return {
        "token": os.getenv('TOKEN'),
        "sandbox_token": os.getenv('SANDBOX_TOKEN')
    }


@bot.callback_query_handler(func=lambda call: call.data == 'sandbox_info')
def sandbox_info_handler(call):
    """
    Обработчик для получения информации о песочнице.
    
    Отображает меню с опциями для работы с песочницей.
    """
    chat_id = call.message.chat.id
    tokens = get_tokens()
    
    if not tokens["sandbox_token"]:
        bot.send_message(chat_id, 'У вас нет открытого счета в песочнице')
        return
    
    inline_keyboard = types.InlineKeyboardMarkup()
    buttons = [
        types.InlineKeyboardButton(text='Получить портфолио песочницы', callback_data='get_sandbox'),
        types.InlineKeyboardButton(text='Пополнить баланс', callback_data='set_sandbox_balance'),
    ]
    
    for button in buttons:
        inline_keyboard.add(button)
    
    bot.send_message(chat_id, 'Выберите опцию', reply_markup=inline_keyboard)


@bot.callback_query_handler(func=lambda call: call.data == 'set_sandbox_balance')
def set_sandbox_balance(call):
    """
    Обработчик для пополнения баланса в песочнице.
    
    Запрашивает у пользователя сумму для пополнения.
    """
    chat_id = call.message.chat.id
    tokens = get_tokens()
    
    if not tokens["sandbox_token"]:
        bot.send_message(chat_id, 'У вас нет открытого счета в песочнице')
        return
    
    bot.send_message(chat_id, 'Введите сумму для пополнения баланса')
    bot.register_next_step_handler(call.message, set_sandbox_balance_2)


def set_sandbox_balance_2(message):
    """
    Обработчик для получения суммы пополнения баланса в песочнице.
    
    Пополняет баланс в песочнице на указанную сумму.
    """
    chat_id = message.chat.id
    tokens = get_tokens()
    
    if not tokens["sandbox_token"]:
        bot.send_message(chat_id, 'У вас нет открытого счета в песочнице')
        return
    
    # Проверка на ввод числа
    try:
        money_value = int(message.text)
        
        with Client(tokens["sandbox_token"]) as client:
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
    
    except Exception as e:
        bot.send_message(chat_id, f"Ошибка при пополнении баланса: {str(e)}")


@bot.callback_query_handler(func=lambda call: call.data == 'get_sandbox')
def get_sandbox(call):
    """
    Обработчик для получения информации о портфолио в песочнице.
    
    Отображает информацию о портфолио в песочнице.
    """
    chat_id = call.message.chat.id
    tokens = get_tokens()
    
    if not tokens["sandbox_token"]:
        bot.send_message(chat_id, 'У вас нет открытого счета в песочнице')
        return
    
    try:
        portfolio = get_sandbox_portfolio(tokens["sandbox_token"])

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
                f"\nТикер: {position['ticker']}\n"
                f"Figi: {position['figi']}\n"
                f"Тип: {position['type']}\n"
                f"Количество: {position['quantity']}\n"
                f"Средневзвешенная цена: {position['average_position_price']}\n"
                f"Ожидаемая доходность: {position['expected_yield']}\n"
                f"Текущая цена: {position['current_price']}\n"
                f"Состояние: {position['blocked']}\n"
            )
        
        bot.send_message(chat_id, text)
    
    except Exception as e:
        bot.send_message(chat_id, f"Ошибка при получении портфолио: {str(e)}")
