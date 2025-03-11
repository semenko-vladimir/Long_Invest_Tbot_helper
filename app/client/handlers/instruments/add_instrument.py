from telebot import types
from app.client.bot.bot import bot
from app.backend.api_client import ApiClient
from app.client.utils.methods import get_figi_by_ticker
import re
import requests

# Создаем экземпляр API-клиента
api_client = ApiClient()


@bot.callback_query_handler(func=lambda call: call.data == 'add_instrument')
def add_instrument_handler(call):
    """
    Обработчик для добавления нового инструмента.
    
    Запрашивает у пользователя тикер инструмента.
    """
    chat_id = call.message.chat.id
    msg = bot.send_message(chat_id, 'Введите тикер инструмента:')
    bot.register_next_step_handler(msg, process_ticker_step)


def process_ticker_step(message):
    """
    Обработчик для получения тикера инструмента.
    
    Сохраняет тикер и автоматически получает FIGI.
    """
    chat_id = message.chat.id
    ticker = message.text.strip().upper()
    
    # Проверка формата тикера
    if not re.match(r'^[A-Z0-9]+$', ticker):
        msg = bot.send_message(chat_id, 'Некорректный формат тикера. Пожалуйста, введите тикер, состоящий только из букв и цифр:')
        bot.register_next_step_handler(msg, process_ticker_step)
        return
    
    # Проверка, существует ли уже инструмент с таким тикером
    try:
        existing = api_client.get_instrument_by_ticker(ticker)
        bot.send_message(chat_id, f'Инструмент с тикером {ticker} уже существует.')
        return
    except requests.exceptions.HTTPError as e:
        # Проверяем, что ошибка именно 404 (Not Found)
        if e.response.status_code == 404:
            # Если инструмент не найден, продолжаем
            pass
        else:
            # Если другая ошибка, сообщаем пользователю
            bot.send_message(chat_id, f'Ошибка при проверке инструмента: {str(e)}')
            return
    except Exception as e:
        # Если другая ошибка, сообщаем пользователю
        bot.send_message(chat_id, f'Ошибка при проверке инструмента: {str(e)}')
        return
    
    # Автоматически получаем FIGI по тикеру
    figi = get_figi_by_ticker(ticker)
    
    if figi is None:
        bot.send_message(chat_id, f'Не удалось найти FIGI для тикера {ticker}. Проверьте правильность тикера.')
        return
    
    # Добавляем инструмент через API-клиент
    try:
        result = api_client.add_instrument(ticker, figi)
        bot.send_message(chat_id, f'Инструмент {ticker} успешно добавлен.')
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 400 and "already exists" in str(e.response.text):
            bot.send_message(chat_id, f'Инструмент с тикером {ticker} уже существует.')
        else:
            bot.send_message(chat_id, f'Ошибка при добавлении инструмента: {str(e)}')
    except Exception as e:
        bot.send_message(chat_id, f'Ошибка при добавлении инструмента: {str(e)}')
