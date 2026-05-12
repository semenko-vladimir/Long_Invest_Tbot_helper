from app.client.bot.bot import bot
from app.client.handlers.user_context import get_telegram_services_or_notify
from app.client.handlers.utils.message_utils import send_or_edit_message
import re


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
    if not re.match(r'^[A-Z0-9-]+$', ticker):
        msg = send_or_edit_message(chat_id, '❌ *Некорректный формат тикера*\n\nПожалуйста, введите тикер, состоящий из букв, цифр или дефиса:')
        bot.register_next_step_handler(msg, process_ticker_step)
        return
    
    # Отправляем сообщение о начале обработки
    send_or_edit_message(chat_id, f'⏳ *Обработка запроса*\n\nПроверяем тикер `{ticker}`...')

    services = get_telegram_services_or_notify(chat_id)
    if services is None:
        return

    watchlist = services.watchlist_service.add_ticker(ticker)
    if watchlist.error:
        send_or_edit_message(chat_id, f'❌ *Ошибка при добавлении инструмента*\n\n`{watchlist.error}`')
        return

    added = next((item for item in watchlist.items if item.ticker == ticker), None)
    figi_text = f'\nFIGI: `{added.figi}`' if added else ''
    send_or_edit_message(chat_id, f'✅ *Успешно*\n\n{watchlist.notice or f"Инструмент `{ticker}` добавлен."}{figi_text}')
