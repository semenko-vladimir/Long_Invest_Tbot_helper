from telebot import types
from app.client.api.config_client import ConfigApiClient
from app.client.bot.bot import bot
from tinkoff.invest import Client
from tinkoff.invest.services import SandboxService
from dotenv import load_dotenv
import os

config_client = ConfigApiClient()

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


@bot.callback_query_handler(func=lambda call: call.data == 'account_selection')
def get_account_handler(call):
    """
    Обработчик для выбора типа счета.
    
    Отображает меню с выбором между боевым счетом и песочницей.
    """
    chat_id = call.message.chat.id
    
    inline_keyboard = types.InlineKeyboardMarkup()
    buttons = [
        types.InlineKeyboardButton(text='Боевой счет', callback_data='real_account'),
        types.InlineKeyboardButton(text='Песочница', callback_data='sandbox_account'),
    ]
    
    for button in buttons:
        inline_keyboard.add(button)
    
    bot.send_message(chat_id, 'Выберите счет:', reply_markup=inline_keyboard)


@bot.callback_query_handler(func=lambda call: call.data == 'real_account')
def real_account(call):
    """
    Обработчик для выбора боевого счета.
    
    Устанавливает флаг sandbox_trigger в False.
    """
    chat_id = call.message.chat.id
    
    try:
        # Используем API-клиент для установки флага sandbox_trigger
        config_client.set_sandbox_trigger(False)
        bot.send_message(chat_id, 'Вы выбрали боевой счет')
    
    except Exception as e:
        bot.send_message(chat_id, f"Ошибка при выборе боевого счета: {str(e)}")


@bot.callback_query_handler(func=lambda call: call.data == 'sandbox_account')
def sandbox_account(call):
    """
    Обработчик для выбора песочницы.
    
    Устанавливает флаг sandbox_trigger в True и проверяет/создает счет в песочнице.
    """
    chat_id = call.message.chat.id
    tokens = get_tokens()
    
    try:
        # Используем API-клиент для установки флага sandbox_trigger
        config_client.set_sandbox_trigger(True)

        # Работа с песочницей Tinkoff API
        with Client(tokens["sandbox_token"]) as client:
            sb: SandboxService = client.sandbox

            r = sb.get_sandbox_accounts().accounts

            if len(r) > 0:
                bot.send_message(chat_id, 'Вы выбрали песочницу.')
            else:
                sb.open_sandbox_account()
                bot.send_message(chat_id, 'Создан новый счет в песочнице. Выбрана песочница.')
    
    except Exception as e:
        bot.send_message(chat_id, f"Ошибка при выборе песочницы: {str(e)}")
