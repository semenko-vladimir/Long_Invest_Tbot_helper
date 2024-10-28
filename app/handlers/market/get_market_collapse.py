from datetime import datetime, timedelta
from bot.bot import bot
from telebot import types
from db.db import get_all_tickers, get_t_token
from utils.methods import get_info_by_ticker, get_price_change_in_current_interval
from tinkoff.invest import CandleInterval

INTERVAL_MAPPING = {
    '10 минут': (timedelta(minutes=10), CandleInterval.CANDLE_INTERVAL_1_MIN),
    'час': (timedelta(hours=1), CandleInterval.CANDLE_INTERVAL_1_MIN),
    'неделя': (timedelta(weeks=1), CandleInterval.CANDLE_INTERVAL_DAY),
    'месяц': (timedelta(days=30), CandleInterval.CANDLE_INTERVAL_WEEK),
    'год': (timedelta(days=365), CandleInterval.CANDLE_INTERVAL_MONTH)
}

PERCENT_RANGES = {
    'до 2%': (0, -2),
    'от 2% до 5%': (-2, -5),
    'от 5% до 10%': (-5, -10),
    'от 10% до 20%': (-10, -20),
    'более 20%': (-20, -100),  
    'до 100%': (-0.01, -100)
}

@bot.callback_query_handler(func=lambda call: call.data == 'get_market_collapse')
def get_market_collapse_handler(call):
    chat_id = call.message.chat.id
    token = get_t_token(chat_id)
    if token is not None:
        tickers = get_all_tickers(chat_id)
        if not tickers:
            bot.send_message(chat_id, 'У вас нет активных тикеров')
        else:
            inline_keyboard = types.InlineKeyboardMarkup()
            buttons = [
                types.InlineKeyboardButton(text='10 минут', callback_data='intervalcollapse_10 минут'),
                types.InlineKeyboardButton(text='час', callback_data='intervalcollapse_час'),
                types.InlineKeyboardButton(text='день', callback_data='intervalcollapse_день'),
                types.InlineKeyboardButton(text='неделя', callback_data='intervalcollapse_неделя'),
                types.InlineKeyboardButton(text='месяц', callback_data='intervalcollapse_месяц'),
                types.InlineKeyboardButton(text='год', callback_data='intervalcollapse_год')
            ]
            inline_keyboard.add(*buttons)
            bot.send_message(chat_id, 'Выберите интервал', reply_markup=inline_keyboard)

@bot.callback_query_handler(func=lambda call: call.data.startswith('intervalcollapse_'))
def interval_handler(call):
    interval = call.data.replace('intervalcollapse_', '')
    inline_keyboard = types.InlineKeyboardMarkup()
    buttons = [
        types.InlineKeyboardButton(text='до 2%', callback_data=f'percentcollapse_до 2%_{interval}'),
        types.InlineKeyboardButton(text='от 2% до 5%', callback_data=f'percentcollapse_от 2% до 5%_{interval}'),
        types.InlineKeyboardButton(text='от 5% до 10%', callback_data=f'percentcollapse_от 5% до 10%_{interval}'),
        types.InlineKeyboardButton(text='от 10% до 20%', callback_data=f'percentcollapse_от 10% до 20%_{interval}'),
        types.InlineKeyboardButton(text='более 20%', callback_data=f'percentcollapse_более 20%_{interval}'),
        types.InlineKeyboardButton(text='Общий обвал', callback_data=f'percentcollapse_до 100%_{interval}'),
    ]
    inline_keyboard.add(*buttons)
    bot.send_message(call.message.chat.id, 'Выберите процент', reply_markup=inline_keyboard)

@bot.callback_query_handler(func=lambda call: call.data.startswith('percentcollapse_'))
def percent_handler(call):
    data = call.data.split('_')
    percent_range = data[1]
    interval = data[2]

    # Получаем начальное время и интервал свечи
    start_time, candle_interval = get_time_interval(interval)
    if start_time is None:
        bot.send_message(call.message.chat.id, 'Некорректный интервал')
        return

    chat_id = call.message.chat.id
    tickers = get_all_tickers(chat_id)

    for ticker in tickers:
        info = get_info_by_ticker(str(ticker[0]))
        figi = info['figi'].values[0:1][0]
        name = info['name'].values[0:1][0]
        type_of = info['type'].values[0:1][0]

        # Получаем изменение цены за выбранный интервал
        end_time = datetime.now()
        price_change, price_change_percent, max_price, min_price, close_price = get_price_change_in_current_interval(
            figi, start_time, end_time, candle_interval)

        # Проверяем изменение цены в зависимости от выбранного процента
        low, high = PERCENT_RANGES[percent_range]
        if high < price_change_percent <= low:
            bot.send_message(chat_id, f'Название: {name}\n Тип: {type_of}\n Тикер: {ticker}\n'
                                      f'Изменение цены: {round(price_change_percent, 2)}% \n'
                                      f'Цена закрытия последней свечи: {close_price} \n'
                                      f'Максимальная цена: {max_price} \n Минимальная цена: {min_price}')

# Вспомогательная функция для получения интервала
def get_time_interval(interval):
    if interval == 'день':
        start_time = datetime.now().replace(hour=10, minute=0, second=0)
        candle_interval = CandleInterval.CANDLE_INTERVAL_10_MIN
    else:
        timedelta_value, candle_interval = INTERVAL_MAPPING.get(interval, (None, None))
        if timedelta_value:
            start_time = datetime.now() - timedelta_value
        else:
            start_time, candle_interval = None, None
    return start_time, candle_interval
