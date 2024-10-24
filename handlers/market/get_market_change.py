from datetime import datetime, timedelta
from bot.bot import bot
from telebot import types
from db.db import get_all_tickers, get_t_token
from utils.methods import get_info_by_ticker, get_price_change_in_current_interval
from tinkoff.invest import CandleInterval

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
    chat_id = call.message.chat.id
    token = get_t_token(chat_id)

    if token:
        tickers = get_all_tickers(chat_id)

        if not tickers:
            bot.send_message(chat_id, 'У вас нет активных тикеров')
        else:
            show_interval_selection(chat_id)
    else:
        bot.send_message(chat_id, "Токен не найден. Пожалуйста, авторизуйтесь.")


def show_interval_selection(chat_id):
    """Отображает кнопки для выбора интервала времени."""
    inline_keyboard = types.InlineKeyboardMarkup()
    intervals = ['10 минут', 'час', 'день', 'неделя', 'месяц', 'год']
    buttons = [types.InlineKeyboardButton(text=interval, callback_data=f'intervals_{interval}') for interval in intervals]
    inline_keyboard.add(*buttons)
    bot.send_message(chat_id, 'Выберите интервал', reply_markup=inline_keyboard)


@bot.callback_query_handler(func=lambda call: call.data.startswith('intervals_'))
def percent_handler(call):
    """Обрабатывает выбор интервала и выводит информацию по тикерам."""
    chat_id = call.message.chat.id
    interval = call.data.split('_')[1]
    tickers = get_all_tickers(chat_id)

    if tickers:
        for ticker in tickers:
            process_ticker_data(chat_id, ticker, interval)
    else:
        bot.send_message(chat_id, "У вас нет активных тикеров.")


def process_ticker_data(chat_id, ticker, interval):
    """Получает данные по тикеру и отправляет результат пользователю."""
    info = get_info_by_ticker(ticker[0])
    if info is None:
        bot.send_message(chat_id, f'Не удалось найти информацию для тикера {ticker[0]}')
        return

    figi, name, type_of = extract_ticker_info(info)
    start_time, candle_interval = get_time_interval(interval)

    if start_time is None:
        bot.send_message(chat_id, 'Неправильный интервал времени.')
        return

    end_time = datetime.now()
    price_change, price_change_percent, max_price, min_price, close_price = get_price_change_in_current_interval(
        figi, start_time, end_time, candle_interval
    )

    send_ticker_summary(chat_id, name, type_of, ticker[0], price_change_percent, close_price, max_price, min_price)


def extract_ticker_info(info):
    """Извлекает основные данные о тикере из полученной информации."""
    figi = info['figi'].values[0:1][0]
    name = info['name'].values[0:1][0]
    type_of = info['type'].values[0:1][0]
    return figi, name, type_of


def get_time_interval(interval):
    """Получает начальное время и интервал свечи для выбранного периода."""
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
    """Отправляет пользователю информацию о тикере."""
    text = (
        f'Название: {name}\n'
        f'Тип: {type_of}\n'
        f'Тикер: {ticker}\n'
        f'Изменение цены: {round(price_change_percent, 2)}%\n'
        f'Цена закрытия последней свечи: {close_price}\n'
        f'Максимальная цена: {max_price}\n'
        f'Минимальная цена: {min_price}\n'
    )
    bot.send_message(chat_id, text)
