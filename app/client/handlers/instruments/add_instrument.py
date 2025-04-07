from telebot import types
from app.client.api.instruments_client import InstrumentsApiClient
from app.client.bot.bot import bot
from app.client.utils.methods import get_figi_by_ticker
from app.client.handlers.utils.message_utils import send_or_edit_message
import re
import requests

instruments_client = InstrumentsApiClient()


@bot.callback_query_handler(func=lambda call: call.data == 'add_instrument')
def add_instrument_handler(call):
    """
    Обработчик для добавления нового инструмента.
    
    Запрашивает у пользователя тикер инструмента.
    """
    chat_id = call.message.chat.id
    msg = send_or_edit_message(chat_id, '➕ *Добавление инструмента*\n\nВведите тикер инструмента:')
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
        msg = send_or_edit_message(chat_id, '❌ *Некорректный формат тикера*\n\nПожалуйста, введите тикер, состоящий только из букв и цифр:')
        bot.register_next_step_handler(msg, process_ticker_step)
        return
    
    # Отправляем сообщение о начале обработки
    send_or_edit_message(chat_id, f'⏳ *Обработка запроса*\n\nПроверяем тикер `{ticker}`...')
    
    # Проверка, существует ли уже инструмент с таким тикером
    try:
        existing = instruments_client.get_instrument_by_ticker(ticker)
        send_or_edit_message(chat_id, f'ℹ️ *Информация*\n\nИнструмент с тикером `{ticker}` уже существует.')
        return
    except requests.exceptions.HTTPError as e:
        # Проверяем, что ошибка именно 404 (Not Found)
        if e.response.status_code == 404:
            # Если инструмент не найден, продолжаем
            pass
        else:
            # Если другая ошибка, сообщаем пользователю
            send_or_edit_message(chat_id, f'❌ *Ошибка при проверке инструмента*\n\n`{str(e)}`')
            return
    except Exception as e:
        # Если другая ошибка, сообщаем пользователю
        send_or_edit_message(chat_id, f'❌ *Ошибка при проверке инструмента*\n\n`{str(e)}`')
        return
    
    # Автоматически получаем FIGI по тикеру
    send_or_edit_message(chat_id, f'⏳ *Обработка запроса*\n\nПолучаем FIGI для тикера `{ticker}`...')
    figi = get_figi_by_ticker(ticker)
    
    if figi is None:
        send_or_edit_message(chat_id, f'❌ *Ошибка*\n\nНе удалось найти FIGI для тикера `{ticker}`. Проверьте правильность тикера.')
        return
    
    # Добавляем инструмент через API-клиент
    try:
        send_or_edit_message(chat_id, f'⏳ *Обработка запроса*\n\nДобавляем инструмент `{ticker}`...')
        result = instruments_client.add_instrument(ticker, figi)
        send_or_edit_message(chat_id, f'✅ *Успешно*\n\nИнструмент `{ticker}` успешно добавлен.\nFIGI: `{figi}`')
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 400 and "already exists" in str(e.response.text):
            send_or_edit_message(chat_id, f'ℹ️ *Информация*\n\nИнструмент с тикером `{ticker}` уже существует.')
        else:
            send_or_edit_message(chat_id, f'❌ *Ошибка при добавлении инструмента*\n\n`{str(e)}`')
    except Exception as e:
        send_or_edit_message(chat_id, f'❌ *Ошибка при добавлении инструмента*\n\n`{str(e)}`')
