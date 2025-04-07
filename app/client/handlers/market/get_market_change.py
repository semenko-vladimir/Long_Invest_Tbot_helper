from datetime import datetime, timedelta
from app.client.api.instruments_client import InstrumentsApiClient
from app.client.bot.bot import bot
from telebot import types
from app.client.utils.methods import get_info_by_ticker, get_price_change_in_current_interval
from tinkoff.invest import CandleInterval
from app.client.handlers.utils.message_utils import send_or_edit_message

instruments_client = InstrumentsApiClient()


# Интервалы времени для удобства обработки
INTERVAL_MAPPING = {
    '10 минут': (timedelta(minutes=10), CandleInterval.CANDLE_INTERVAL_1_MIN),
    'час': (timedelta(hours=1), CandleInterval.CANDLE_INTERVAL_1_MIN),
    'неделя': (timedelta(weeks=1), CandleInterval.CANDLE_INTERVAL_DAY),
    'месяц': (timedelta(days=30), CandleInterval.CANDLE_INTERVAL_WEEK),
    'год': (timedelta(days=365), CandleInterval.CANDLE_INTERVAL_MONTH)
}


@bot.callback_query_handler(func=lambda call: call.data == 'get_market_change')
def get_market_change_handler(call):
    """
    Обработчик для получения информации об изменении рынка.
    
    Проверяет наличие инструментов и отображает меню с выбором интервала времени.
    """
    chat_id = call.message.chat.id
    
    try:
        # Получаем список всех инструментов
        instruments = instruments_client.get_all_instruments()
        
        if not instruments:
            send_or_edit_message(chat_id, '❌ *Ошибка*\n\nУ вас нет активных инструментов')
        else:
            show_interval_selection(chat_id)
    
    except Exception as e:
        send_or_edit_message(chat_id, f"❌ *Ошибка при получении списка инструментов*\n\n`{str(e)}`")


def show_interval_selection(chat_id):
    """
    Отображает кнопки для выбора интервала времени.
    
    Args:
        chat_id: ID чата
    """
    try:
        inline_keyboard = types.InlineKeyboardMarkup()
        intervals = ['10 минут', 'час', 'день', 'неделя', 'месяц', 'год']
        buttons = [types.InlineKeyboardButton(text=interval, callback_data=f'intervals_{interval}') for interval in intervals]
        
        for button in buttons:
            inline_keyboard.add(button)
        
        send_or_edit_message(
            chat_id, 
            '📊 *Изменение состояния рынка*\n\nВыберите интервал времени:', 
            reply_markup=inline_keyboard
        )
    
    except Exception as e:
        send_or_edit_message(chat_id, f"❌ *Ошибка при отображении меню выбора интервала*\n\n`{str(e)}`")


@bot.callback_query_handler(func=lambda call: call.data.startswith('intervals_'))
def percent_handler(call):
    """
    Обрабатывает выбор интервала и выводит информацию по инструментам.
    
    Получает данные по каждому инструменту и отправляет результат пользователю.
    """
    chat_id = call.message.chat.id
    interval = call.data.split('_')[1]
    
    try:
        # Отправляем сообщение о начале обработки
        send_or_edit_message(chat_id, f"⏳ *Обработка запроса*\n\nПолучаем данные об изменении рынка за интервал `{interval}`...")
        
        # Получаем список всех инструментов
        instruments = instruments_client.get_all_instruments()
        
        if instruments:
            for instrument in instruments:
                ticker = instrument.get('ticker')
                process_ticker_data(chat_id, ticker, interval)
        else:
            send_or_edit_message(chat_id, "❌ *Ошибка*\n\nУ вас нет активных инструментов.")
    
    except Exception as e:
        send_or_edit_message(chat_id, f"❌ *Ошибка при обработке выбора интервала*\n\n`{str(e)}`")


def process_ticker_data(chat_id, ticker, interval):
    """
    Получает данные по тикеру и отправляет результат пользователю.
    
    Args:
        chat_id: ID чата
        ticker: Тикер инструмента
        interval: Выбранный интервал времени
    """
    try:
        info = get_info_by_ticker(ticker)
        if info is None or info.empty:
            send_or_edit_message(chat_id, f'❌ Не удалось найти информацию для тикера `{ticker}`')
            return
        
        figi, name, type_of = extract_ticker_info(info)
        start_time, candle_interval = get_time_interval(interval)
        
        if start_time is None:
            send_or_edit_message(chat_id, '❌ *Ошибка*\n\nНеправильный интервал времени.')
            return
        
        end_time = datetime.now()
        price_change, price_change_percent, max_price, min_price, close_price = get_price_change_in_current_interval(
            figi, start_time, end_time, candle_interval
        )
        
        send_ticker_summary(chat_id, name, type_of, ticker, price_change_percent, close_price, max_price, min_price)
    
    except Exception as e:
        send_or_edit_message(chat_id, f"❌ *Ошибка при обработке данных тикера {ticker}*\n\n`{str(e)}`")


def extract_ticker_info(info):
    """
    Извлекает основные данные о тикере из полученной информации.
    
    Args:
        info: Информация о тикере
        
    Returns:
        tuple: (figi, name, type_of)
    """
    figi = info['figi'].values[0:1][0]
    name = info['name'].values[0:1][0]
    type_of = info['type'].values[0:1][0]
    return figi, name, type_of


def get_time_interval(interval):
    """
    Получает начальное время и интервал свечи для выбранного периода.
    
    Args:
        interval: Выбранный интервал времени
        
    Returns:
        tuple: (start_time, candle_interval)
    """
    if interval == 'день':
        start_time = datetime.now().replace(hour=10, minute=0, second=0)
        candle_interval = CandleInterval.CANDLE_INTERVAL_10_MIN
    elif interval in INTERVAL_MAPPING:
        timedelta_value, candle_interval = INTERVAL_MAPPING[interval]
        start_time = datetime.now() - timedelta_value
    else:
        start_time, candle_interval = None, None
    
    return start_time, candle_interval


def send_ticker_summary(chat_id, name, type_of, ticker, price_change_percent, close_price, max_price, min_price):
    """
    Отправляет пользователю информацию о тикере.
    
    Args:
        chat_id: ID чата
        name: Название инструмента
        type_of: Тип инструмента
        ticker: Тикер инструмента
        price_change_percent: Процент изменения цены
        close_price: Цена закрытия последней свечи
        max_price: Максимальная цена
        min_price: Минимальная цена
    """
    # Определяем эмодзи в зависимости от процента изменения
    change_emoji = "📈" if price_change_percent > 0 else "📉"
    
    text = (
        f'{change_emoji} *Информация о {ticker}*\n\n'
        f'📌 Название: `{name}`\n'
        f'📋 Тип: `{type_of}`\n'
        f'🏷️ Тикер: `{ticker}`\n'
        f'📊 Изменение цены: `{round(price_change_percent, 2)}%`\n'
        f'💰 Цена закрытия последней свечи: `{close_price}`\n'
        f'⬆️ Максимальная цена: `{max_price}`\n'
        f'⬇️ Минимальная цена: `{min_price}`\n'
    )
    send_or_edit_message(chat_id, text)
