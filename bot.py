'''
import json
import telebot
import creds
from methods import get_share_figi_by_ticker, get_share_info_by_ticker, get_price_change_in_current_interval, get_last_average_price
from constants import FIRST_ALERT, SECOND_ALERT, THIRD_ALERT, FOURTH_ALERT

# Токен и id чата
TOKEN = creds.BOT_TOKEN
CHAT_ID = creds.CHAT_ID

# Создание бота
bot = telebot.TeleBot(TOKEN)

# Загрузка тикеров из файла
with open('tickers.json') as f:
    tickers = json.load(f)

# Основная логика
def send_alerts():
    for ticker in tickers:
        figi = get_share_figi_by_ticker(ticker['ticker'])
        if figi is None:
            continue
        info = get_share_info_by_ticker(ticker['ticker'])
        price_change, price_change_percent, max_price, min_price, close_price = get_price_change_in_current_interval(figi)

        if price_change is not None:
            alert_level = ""
            alert_emoji = ""
            if FIRST_ALERT > price_change_percent > SECOND_ALERT:
                alert_level = "FIRST_ALERT"
                alert_emoji = "⚠️"
            elif SECOND_ALERT > price_change_percent > THIRD_ALERT:
                alert_level = "SECOND_ALERT"
                alert_emoji = "🚨"
            elif THIRD_ALERT > price_change_percent > FOURTH_ALERT:
                alert_level = "THIRD_ALERT"
                alert_emoji = "🔴"
            elif price_change_percent < FOURTH_ALERT:
                alert_level = "FOURTH_ALERT"
                alert_emoji = "🚨🚨"

            bot.send_message(CHAT_ID, f"""
        {alert_emoji} {alert_level} {info['name']} ({info['ticker']})
        -------------------------
        Цена изменилась на: {price_change:.2f} руб.
        Процент изменения: {price_change_percent:.2f}%
        Средняя последняя цена: {close_price:.2f}
        """)
        else:
            continue



# Запуск бота
send_alerts()
print("Рассылка завершена")
bot.polling()
'''

from datetime import datetime, timedelta
import telebot
import sqlite3
from alligator_strategy import calculate_alligator_strategy
import credentials
from db import get_alligator, get_config, get_sma, get_strategy, get_t_token, get_tpsl, insert_ticker, get_all_tickers, delete_ticker, delete_all_tickers, update_config_collapse, update_signal_alligator, update_signal_rsi, update_signal_sma, update_signal_tpsl, get_rsi, update_strategy
import db
from helpers import calculate_profit, cancel_existing_order
from methods import create_df, get_historic_candles, get_portfolio, get_figi_by_ticker, get_info_by_ticker, get_price_change_in_current_interval, get_instrument_from_portfolio_by_ticker
from telebot import types
from tinkoff.invest import CandleInterval
from apscheduler.schedulers.background import BackgroundScheduler
from orders import place_order
from rsi_strategy import calculate_rsi, check_rsi_signal
from sma_strategy import calculate_sma_strategy

# Создаем экземпляр бота
bot = telebot.TeleBot(credentials.BOT_TOKEN)

# Подключаемся к базе данных
conn = sqlite3.connect('database.db')
cursor = conn.cursor()

# Обработчик команды /start
@bot.message_handler(commands=['start'])
def start(message):
    chat_id = message.chat.id
    print(chat_id)
    token = get_t_token(chat_id)
    if token is None:
        bot.send_message(message.chat.id, 'Вы не зарегистрированы в системе')
    else:
        keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
        portfolio_button = types.KeyboardButton('Получить портфолио')
        ticker_add_button = types.KeyboardButton('Добавить тикер')
        tickers_get_button = types.KeyboardButton('Получить мои тикеры')
        ticker_delete_button = types.KeyboardButton('Удалить тикер')
        tickers_delete_all_button = types.KeyboardButton('Удалить мои тикеры')
        receive_market_collapse_button = types.KeyboardButton('Получить обвал рынка по тикерам')
        receive_market_update_button = types.KeyboardButton('Получить рост рынка по тикерам')
        all_market_status_button = types.KeyboardButton('Получить изменение состояния рынка по тикерам')
        subscribe_to_collapse_update_button = types.KeyboardButton('Подписаться на обновления падений рынка')
        unsubscribe_to_collapse_update_button = types.KeyboardButton('Отписаться от обновления падений рынка')
        subscribe_to_market_update_button = types.KeyboardButton('Подписаться на обновления рынка')
        unsubscribe_to_market_update_button = types.KeyboardButton('Отписаться от обновления рынка')

        strategies_button = types.KeyboardButton('Стратегии')


        
        keyboard.row(portfolio_button, tickers_get_button, receive_market_collapse_button)

        keyboard.row(ticker_add_button, ticker_delete_button, tickers_delete_all_button)

        keyboard.row(subscribe_to_collapse_update_button, unsubscribe_to_collapse_update_button)

        keyboard.row(subscribe_to_market_update_button, unsubscribe_to_market_update_button, receive_market_update_button)

        keyboard.row(all_market_status_button, strategies_button)
        
        bot.send_message(message.chat.id, 'Добро пожаловать!', reply_markup=keyboard)

@bot.message_handler(func=lambda message: message.text == 'Получить портфолио')
def get_portfolio_handler(message):
    chat_id = message.chat.id
    token = get_t_token(chat_id)
    if token is not None:
        portfolio = get_portfolio(token)

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
                f"\nНазвание: {position['name']}\n"
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


@bot.message_handler(func=lambda message: message.text == 'Добавить тикер')
def add_ticker_handler(message):
    chat_id = message.chat.id
    token = get_t_token(chat_id)
    if token is not None:
        bot.send_message(chat_id, 'Пожалуйста, введите тикер')
        bot.register_next_step_handler(message, add_ticker_step)

def add_ticker_step(message):
    ticker = message.text.upper()
    chat_id = message.chat.id
    figi = get_figi_by_ticker(ticker)  
    if figi is None:
        bot.send_message(message.chat.id, 'Не удалось найти информацию по данному инструменту')
    else:
        result = insert_ticker(chat_id, ticker)
        bot.send_message(message.chat.id, result)

@bot.message_handler(func=lambda message: message.text == 'Получить мои тикеры')
def add_ticker_handler(message):
    chat_id = message.chat.id
    token = get_t_token(chat_id)
    if token is not None:
        tickers = get_all_tickers(chat_id)

        if not tickers:
            bot.send_message(chat_id, 'У вас нет активных тикеров')
        else:
            text = "Ваши тикеры:\n"
            for ticker in tickers:
                text += f"{ticker[0]}\n"
            bot.send_message(chat_id, text)

@bot.message_handler(func=lambda message: message.text == 'Удалить мои тикеры')
def add_ticker_handler(message):
    chat_id = message.chat.id
    token = get_t_token(chat_id)
    if token is not None:
        delete_all_tickers(chat_id)
        bot.send_message(chat_id, "Все тикеры были удалены")


@bot.message_handler(func=lambda message: message.text == 'Удалить тикер')
def delete_ticker_handler(message):
    chat_id = message.chat.id
    token = get_t_token(chat_id)
    if token is not None:
        tickers = get_all_tickers(chat_id)
        if not tickers:
            bot.send_message(chat_id, 'У вас нет активных тикеров')
        else:
            inline_keyboard = types.InlineKeyboardMarkup()
            for ticker in tickers:
                button = types.InlineKeyboardButton(text=str(ticker[0]), callback_data=f'ticker_{ticker[0]}')
                inline_keyboard.add(button)
            bot.send_message(chat_id, 'Выберите тикер для удаления', reply_markup=inline_keyboard)

# Обработчик для callback удаления тикера
@bot.callback_query_handler(func=lambda call: call.data.startswith('ticker_'))
def delete_ticker_step(call):
    ticker = call.data.replace('ticker_', '')
    delete_ticker(call.message.chat.id, ticker)
    bot.send_message(call.message.chat.id, f'Тикер "{ticker}" успешно удален')

# Обработчик для получения обвала рынка по тикерам
@bot.message_handler(func=lambda message: message.text == 'Получить обвал рынка по тикерам')
# TODO: Refactor this function
def add_ticker_handler(message):
    chat_id = message.chat.id
    token = get_t_token(chat_id)
    if token is not None:
        tickers = get_all_tickers(chat_id)

        if not tickers:
            bot.send_message(chat_id, 'У вас нет активных тикеров')
        else:
            inline_keyboard = types.InlineKeyboardMarkup()
            buttons = [
                types.InlineKeyboardButton(text='10 минут', callback_data='interval_10 минут'),
                types.InlineKeyboardButton(text='час', callback_data='interval_час'),
                types.InlineKeyboardButton(text='день', callback_data='interval_день'),
                types.InlineKeyboardButton(text='неделя', callback_data='interval_неделя'),
                types.InlineKeyboardButton(text='месяц', callback_data='interval_месяц'),
                types.InlineKeyboardButton(text='год', callback_data='interval_год')
            ]
            inline_keyboard.add(*buttons)
            bot.send_message(chat_id, 'Выберите интервал', reply_markup=inline_keyboard)

# Обработчик для callback выбора интервала
@bot.callback_query_handler(func=lambda call: call.data.startswith('interval_'))
def interval_handler(call):
    interval = call.data.replace('interval_', '')
    inline_keyboard = types.InlineKeyboardMarkup()
    buttons = [
        types.InlineKeyboardButton(text='до 2%', callback_data=f'percent_до 2%_{interval}'),
        types.InlineKeyboardButton(text='от 2% до 5%', callback_data=f'percent_от 2% до 5%_{interval}'),
        types.InlineKeyboardButton(text='от 5% до 10%', callback_data=f'percent_от 5% до 10%_{interval}'),
        types.InlineKeyboardButton(text='от 10% до 20%', callback_data=f'percent_от 10% до 20%_{interval}'),
        types.InlineKeyboardButton(text='более 20%', callback_data=f'percent_более 20%_{interval}'),
        types.InlineKeyboardButton(text='Общий обвал', callback_data=f'percent_до 100%_{interval}'),
    ]
    inline_keyboard.add(*buttons)
    bot.send_message(call.message.chat.id, 'Выберите процент', reply_markup=inline_keyboard)

# Обработчик для callback выбора процента
@bot.callback_query_handler(func=lambda call: call.data.startswith('percent_'))
# TODO: Refactor this function
def percent_handler(call):
    data = call.data.split('_')
    percent = data[1]
    interval = data[2]

    # Логика для получения данных о тикерах
    chat_id = call.message.chat.id
    tickers = get_all_tickers(chat_id)
    
    for ticker in tickers:
        info = get_info_by_ticker(str(ticker[0]))
        figi = info['figi'].values[0:1][0]
        name = info['name'].values[0:1][0]
        type_of = info['type'].values[0:1][0]

        if interval == '10 минут':
            start_time = datetime.now() - timedelta(minutes=10)
            candle_interval = CandleInterval.CANDLE_INTERVAL_1_MIN
        elif interval == 'час':
            start_time = datetime.now() - timedelta(hours=1)
            candle_interval = CandleInterval.CANDLE_INTERVAL_1_MIN
        elif interval == 'день':
            start_time = datetime.now().replace(hour=10, minute=0, second=0)
            candle_interval = CandleInterval.CANDLE_INTERVAL_10_MIN
        elif interval == 'неделя':
            start_time = datetime.now() - timedelta(weeks=1)
            candle_interval = CandleInterval.CANDLE_INTERVAL_DAY
        elif interval == 'месяц':
            start_time = datetime.now() - timedelta(days=30)
            candle_interval = CandleInterval.CANDLE_INTERVAL_WEEK
        elif interval == 'год':
            start_time = datetime.now() - timedelta(days=365)
            candle_interval = CandleInterval.CANDLE_INTERVAL_MONTH

        end_time = datetime.now()
        price_change, price_change_percent, max_price, min_price, close_price = get_price_change_in_current_interval(figi, start_time, end_time, candle_interval)

        # Проверка процента изменения цены
        if percent == 'до 100%' and price_change_percent < -0.01:
            bot.send_message(chat_id, f'Название: {name}\n Тип: {type_of}\n Тикер: {ticker}\n Изменение цены: {round(price_change_percent, 2)}% \n Цена закрытия последней свечи: {close_price} \n Максимальная цена: {max_price} \n Минимальная цена: {min_price}')
        if percent == 'до 2%' and 0 > price_change_percent > -2:
            bot.send_message(chat_id, f'Название: {name}\n Тип: {type_of}\n Тикер: {ticker}\n Изменение цены: {round(price_change_percent, 2)}% \n Цена закрытия последней свечи: {close_price} \n Максимальная цена: {max_price} \n Минимальная цена: {min_price}')
        elif percent == 'от 2% до 5%' and -2 >= price_change_percent >= -5:
            bot.send_message(chat_id, f'Название: {name}\n Тип: {type_of}\n Тикер: {ticker}\n Изменение цены: {round(price_change_percent, 2)}% \n Цена закрытия последней свечи: {close_price} \n Максимальная цена: {max_price} \n Минимальная цена: {min_price}')
        elif percent == 'от 5% до 10%' and -5 >= price_change_percent >= -10:
            bot.send_message(chat_id, f'Название: {name}\n Тип: {type_of}\n Тикер: {ticker}\n Изменение цены: {round(price_change_percent, 2)}% \n Цена закрытия последней свечи: {close_price} \n Максимальная цена: {max_price} \n Минимальная цена: {min_price}')
        elif percent == 'от 10% до 20%' and -10 >= price_change_percent >= -20:
            bot.send_message(chat_id, f'Название: {name}\n Тип: {type_of}\n Тикер: {ticker}\n Изменение цены: {round(price_change_percent, 2)}% \n Цена закрытия последней свечи: {close_price} \n Максимальная цена: {max_price} \n Минимальная цена: {min_price}')
        elif percent == 'более 20%' and price_change_percent <= -20:
            bot.send_message(chat_id, f'Название: {name}\n Тип: {type_of}\n Тикер: {ticker}\n Изменение цены: {round(price_change_percent, 2)}% \n Цена закрытия последней свечи: {close_price} \n Максимальная цена: {max_price} \n Минимальная цена: {min_price}')



# <==============================================================================================================================>

# Обработчик для получения роста рынка по тикерам
@bot.message_handler(func=lambda message: message.text == 'Получить рост рынка по тикерам')
# TODO: Refactor this function
def add_ticker_handler(message):
    chat_id = message.chat.id
    token = get_t_token(chat_id)
    if token is not None:
        tickers = get_all_tickers(chat_id)

        if not tickers:
            bot.send_message(chat_id, 'У вас нет активных тикеров')
        else:
            inline_keyboard = types.InlineKeyboardMarkup()
            buttons = [
                types.InlineKeyboardButton(text='10 минут', callback_data='intervalu_10 минут'),
                types.InlineKeyboardButton(text='час', callback_data='intervalu_час'),
                types.InlineKeyboardButton(text='день', callback_data='intervalu_день'),
                types.InlineKeyboardButton(text='неделя', callback_data='intervalu_неделя'),
                types.InlineKeyboardButton(text='месяц', callback_data='intervalu_месяц'),
                types.InlineKeyboardButton(text='год', callback_data='intervalu_год')
            ]
            inline_keyboard.add(*buttons)
            bot.send_message(chat_id, 'Выберите интервал', reply_markup=inline_keyboard)

# Обработчик для callback выбора интервала
@bot.callback_query_handler(func=lambda call: call.data.startswith('intervalu_'))
def interval_handler(call):
    interval = call.data.replace('intervalu_', '')
    inline_keyboard = types.InlineKeyboardMarkup()
    buttons = [
        types.InlineKeyboardButton(text='до 2%', callback_data=f'percentu_до 2%_{interval}'),
        types.InlineKeyboardButton(text='от 2% до 5%', callback_data=f'percentu_от 2% до 5%_{interval}'),
        types.InlineKeyboardButton(text='от 5% до 10%', callback_data=f'percentu_от 5% до 10%_{interval}'),
        types.InlineKeyboardButton(text='от 10% до 20%', callback_data=f'percentu_от 10% до 20%_{interval}'),
        types.InlineKeyboardButton(text='более 20%', callback_data=f'percentu_более 20%_{interval}'),
        types.InlineKeyboardButton(text='Общее состояние', callback_data=f'percentu_до 100%_{interval}'),
    ]
    inline_keyboard.add(*buttons)
    bot.send_message(call.message.chat.id, 'Выберите процент', reply_markup=inline_keyboard)

# Обработчик для callback выбора процента
@bot.callback_query_handler(func=lambda call: call.data.startswith('percentu_'))
# TODO: Refactor this function
def percent_handler(call):
    data = call.data.split('_')
    percent = data[1]
    interval = data[2]

    # Логика для получения данных о тикерах
    chat_id = call.message.chat.id
    tickers = get_all_tickers(chat_id)
    
    for ticker in tickers:
        info = get_info_by_ticker(str(ticker[0]))
        figi = info['figi'].values[0:1][0]
        name = info['name'].values[0:1][0]
        type_of = info['type'].values[0:1][0]

        if interval == '10 минут':
            start_time = datetime.now() - timedelta(minutes=10)
            candle_interval = CandleInterval.CANDLE_INTERVAL_1_MIN
        elif interval == 'час':
            start_time = datetime.now() - timedelta(hours=1)
            candle_interval = CandleInterval.CANDLE_INTERVAL_1_MIN
        elif interval == 'день':
            start_time = datetime.now().replace(hour=10, minute=0, second=0)
            candle_interval = CandleInterval.CANDLE_INTERVAL_10_MIN
        elif interval == 'неделя':
            start_time = datetime.now() - timedelta(weeks=1)
            candle_interval = CandleInterval.CANDLE_INTERVAL_DAY
        elif interval == 'месяц':
            start_time = datetime.now() - timedelta(days=30)
            candle_interval = CandleInterval.CANDLE_INTERVAL_WEEK
        elif interval == 'год':
            start_time = datetime.now() - timedelta(days=365)
            candle_interval = CandleInterval.CANDLE_INTERVAL_MONTH

        end_time = datetime.now()
        price_change, price_change_percent, max_price, min_price, close_price = get_price_change_in_current_interval(figi, start_time, end_time, candle_interval)

        # Проверка процента изменения цены
        if percent == 'до 100%' and price_change_percent > 0.01:
            bot.send_message(chat_id, f'Название: {name}\n Тип: {type_of}\n Тикер: {ticker}\n Изменение цены: {round(price_change_percent, 2)}% \n Цена закрытия последней свечи: {close_price} \n Максимальная цена: {max_price} \n Минимальная цена: {min_price}')
        if percent == 'до 2%' and 0 < price_change_percent < 2:
            bot.send_message(chat_id, f'Название: {name}\n Тип: {type_of}\n Тикер: {ticker}\n Изменение цены: {round(price_change_percent, 2)}% \n Цена закрытия последней свечи: {close_price} \n Максимальная цена: {max_price} \n Минимальная цена: {min_price}')
        elif percent == 'от 2% до 5%' and 2 <= price_change_percent <= 5:
            bot.send_message(chat_id, f'Название: {name}\n Тип: {type_of}\n Тикер: {ticker}\n Изменение цены: {round(price_change_percent, 2)}% \n Цена закрытия последней свечи: {close_price} \n Максимальная цена: {max_price} \n Минимальная цена: {min_price}')
        elif percent == 'от 5% до 10%' and 5 <= price_change_percent <= 10:
            bot.send_message(chat_id, f'Название: {name}\n Тип: {type_of}\n Тикер: {ticker}\n Изменение цены: {round(price_change_percent, 2)}% \n Цена закрытия последней свечи: {close_price} \n Максимальная цена: {max_price} \n Минимальная цена: {min_price}')
        elif percent == 'от 10% до 20%' and 10 <= price_change_percent <= 20:
            bot.send_message(chat_id, f'Название: {name}\n Тип: {type_of}\n Тикер: {ticker}\n Изменение цены: {round(price_change_percent, 2)}% \n Цена закрытия последней свечи: {close_price} \n Максимальная цена: {max_price} \n Минимальная цена: {min_price}')
        elif percent == 'более 20%' and price_change_percent >= 20:
            bot.send_message(chat_id, f'Название: {name}\n Тип: {type_of}\n Тикер: {ticker}\n Изменение цены: {round(price_change_percent, 2)}% \n Цена закрытия последней свечи: {close_price} \n Максимальная цена: {max_price} \n Минимальная цена: {min_price}')


# <==============================================================================================================================>

# Обработчик для получения изменеия состояния рынка по тикерам
@bot.message_handler(func=lambda message: message.text == 'Получить изменение состояния рынка по тикерам')
# TODO: Refactor this function
def add_ticker_handler(message):
    chat_id = message.chat.id
    token = get_t_token(chat_id)
    if token is not None:
        tickers = get_all_tickers(chat_id)

        if not tickers:
            bot.send_message(chat_id, 'У вас нет активных тикеров')
        else:
            inline_keyboard = types.InlineKeyboardMarkup()
            buttons = [
                types.InlineKeyboardButton(text='10 минут', callback_data='intervals_10 минут'),
                types.InlineKeyboardButton(text='час', callback_data='intervals_час'),
                types.InlineKeyboardButton(text='день', callback_data='intervals_день'),
                types.InlineKeyboardButton(text='неделя', callback_data='intervals_неделя'),
                types.InlineKeyboardButton(text='месяц', callback_data='intervals_месяц'),
                types.InlineKeyboardButton(text='год', callback_data='intervals_год')
            ]
            inline_keyboard.add(*buttons)
            bot.send_message(chat_id, 'Выберите интервал', reply_markup=inline_keyboard)


# Обработчик для callback выбора процента
@bot.callback_query_handler(func=lambda call: call.data.startswith('intervals_'))
# TODO: Refactor this function
def percent_handler(call):
    data = call.data.split('_')
    interval = data[1]

    # Логика для получения данных о тикерах
    chat_id = call.message.chat.id
    tickers = get_all_tickers(chat_id)
    
    for ticker in tickers:
        info = get_info_by_ticker(str(ticker[0]))
        figi = info['figi'].values[0:1][0]
        name = info['name'].values[0:1][0]
        type_of = info['type'].values[0:1][0]

        if interval == '10 минут':
            start_time = datetime.now() - timedelta(minutes=10)
            candle_interval = CandleInterval.CANDLE_INTERVAL_1_MIN
        elif interval == 'час':
            start_time = datetime.now() - timedelta(hours=1)
            candle_interval = CandleInterval.CANDLE_INTERVAL_1_MIN
        elif interval == 'день':
            start_time = datetime.now().replace(hour=10, minute=0, second=0)
            candle_interval = CandleInterval.CANDLE_INTERVAL_10_MIN
        elif interval == 'неделя':
            start_time = datetime.now() - timedelta(weeks=1)
            candle_interval = CandleInterval.CANDLE_INTERVAL_DAY
        elif interval == 'месяц':
            start_time = datetime.now() - timedelta(days=30)
            candle_interval = CandleInterval.CANDLE_INTERVAL_WEEK
        elif interval == 'год':
            start_time = datetime.now() - timedelta(days=365)
            candle_interval = CandleInterval.CANDLE_INTERVAL_MONTH

        end_time = datetime.now()
        price_change, price_change_percent, max_price, min_price, close_price = get_price_change_in_current_interval(figi, start_time, end_time, candle_interval)

        bot.send_message(chat_id, f'Название: {name}\n Тип: {type_of}\n Тикер: {ticker}\n Изменение цены: {round(price_change_percent, 2)}% \n Цена закрытия последней свечи: {close_price} \n Максимальная цена: {max_price} \n Минимальная цена: {min_price}')
        



chat_schedulers = {}


def send_price_change_notification_collapse(figi, start_time, end_time, candle_interval, bot, chat_id, name, type_of, ticker):
    price_change, price_change_percent, max_price, min_price, close_price = get_price_change_in_current_interval(figi, start_time, end_time, candle_interval)
    if price_change_percent < -0.001:
        bot.send_message(chat_id, f'Название: {name}\n Тип: {type_of}\n Тикер: {ticker}\n Изменение цены: {round(price_change_percent, 2)}% \n Цена закрытия последней свечи: {close_price} \n Максимальная цена: {max_price} \n Минимальная цена: {min_price}')

def send_price_change_notification_market_updates(figi, start_time, end_time, candle_interval, bot, chat_id, name, type_of, ticker):
    price_change, price_change_percent, max_price, min_price, close_price = get_price_change_in_current_interval(figi, start_time, end_time, candle_interval)
    bot.send_message(chat_id, f'Название: {name}\n Тип: {type_of}\n Тикер: {ticker}\n Изменение цены: {round(price_change_percent, 2)}% \n Цена закрытия последней свечи: {close_price} \n Максимальная цена: {max_price} \n Минимальная цена: {min_price}')


# Функция для подписки на обновления падений рынка
@bot.message_handler(func=lambda message: message.text == 'Подписаться на обновления падений рынка')
# TODO: Refactor this function
def add_ticker_handler(message):

    config_data = get_config()

    for row in config_data:
        chat_id = row[1]
        collapse_updates = row[2]

        if collapse_updates and message.chat.id == chat_id:
            bot.send_message(message.chat.id, 'Вы уже подписаны на обновления падений рынка')
            return

    bot.send_message(message.chat.id, 'Вы автоматически будете отписаны от обновлений рынка')
    chat_id = message.chat.id
    token = get_t_token(chat_id)
    if token is not None:
        tickers = get_all_tickers(chat_id)

        if not tickers:
            bot.send_message(chat_id, 'У вас нет активных тикеров')
        else:
            inline_keyboard = types.InlineKeyboardMarkup()
            buttons = [
                types.InlineKeyboardButton(text='10 минут', callback_data='ucinterval_10 минут'),
                types.InlineKeyboardButton(text='пол часа', callback_data='ucinterval_пол_часа'),
                types.InlineKeyboardButton(text='час', callback_data='ucinterval_час'),
            ]
            inline_keyboard.add(*buttons)
            bot.send_message(chat_id, 'Выберите интервал для получения обновлений', reply_markup=inline_keyboard)

@bot.callback_query_handler(func=lambda call: call.data.startswith('ucinterval_'))
def percent_handler(call):
    data = call.data.split('_')
    interval = data[1]
    chat_id = call.message.chat.id

    if chat_id in chat_schedulers:
        scheduler = chat_schedulers[chat_id]
        scheduler.shutdown()
        del chat_schedulers[chat_id]

    time = 0

    if interval == '10 минут':
        time = 10
    elif interval == 'пол часа':
        time = 30
    elif interval == 'час':
        time = 60


    update_config_collapse(chat_id, time, True, 0, False)
    print("РАБОТАЮТ ПАДЕНИЯ РЫНКА")
    configure_scheduler()


@bot.message_handler(func=lambda message: message.text == 'Отписаться от обновления падений рынка')
def remove_ticker_handler(message):
    chat_id = message.chat.id
    update_config_collapse(chat_id, 0, False, 0, False)
    if chat_id in chat_schedulers:
        scheduler = chat_schedulers[chat_id]
        scheduler.shutdown()
        del chat_schedulers[chat_id]
        bot.send_message(chat_id, 'Вы отписались от обновлений')
    else:
        bot.send_message(chat_id, 'Вы не подписаны на обновления')


@bot.message_handler(func=lambda message: message.text == 'Отписаться от обновления рынка')
def remove_ticker_handler(message):
    chat_id = message.chat.id
    update_config_collapse(chat_id, 0, False, 0, False)
    if chat_id in chat_schedulers:
        scheduler = chat_schedulers[chat_id]
        scheduler.shutdown()
        del chat_schedulers[chat_id]
        bot.send_message(chat_id, 'Вы отписались от обновлений')
    else:
        bot.send_message(chat_id, 'Вы не подписаны на обновления')


# <==============================================================================================>

# Функция для подписки на обновления рынка
@bot.message_handler(func=lambda message: message.text == 'Подписаться на обновления рынка')
# TODO: Refactor this function
def add_ticker_handler(message):

    config_data = get_config()

    for row in config_data:
        chat_id = row[1]
        market_updates = row[4]

        if market_updates and message.chat.id == chat_id:
            bot.send_message(message.chat.id, 'Вы уже подписаны на обновления рынка')
            return

    bot.send_message(message.chat.id, 'Вы автоматически будете отписаны от обновлений падений рынка')
    chat_id = message.chat.id
    token = get_t_token(chat_id)
    if token is not None:
        tickers = get_all_tickers(chat_id)

        if not tickers:
            bot.send_message(chat_id, 'У вас нет активных тикеров')
        else:
            inline_keyboard = types.InlineKeyboardMarkup()
            buttons = [
                types.InlineKeyboardButton(text='10 минут', callback_data='uinterval_10 минут'),
                types.InlineKeyboardButton(text='пол часа', callback_data='uinterval_пол_часа'),
                types.InlineKeyboardButton(text='час', callback_data='uinterval_час'),
            ]
            inline_keyboard.add(*buttons)
            bot.send_message(chat_id, 'Выберите интервал для получения обновлений', reply_markup=inline_keyboard)

@bot.callback_query_handler(func=lambda call: call.data.startswith('uinterval_'))
def percent_handler(call):
    data = call.data.split('_')
    interval = data[1]
    chat_id = call.message.chat.id

    if chat_id in chat_schedulers:
        scheduler = chat_schedulers[chat_id]
        scheduler.shutdown()
        del chat_schedulers[chat_id]

    time = 0

    if interval == '10 минут':
        time = 10
    elif interval == 'пол часа':
        time = 30
    elif interval == 'час':
        time = 60


    update_config_collapse(chat_id, 0, False, time, True)
    print("РАБОТАЮТ ОБНОВЛЕНИЯ РЫНКА")
    configure_scheduler()

# Глобальные переменные для сохранения состояния стратегии
strategy_shedulers = {}

def configure_scheduler():

    chat_id = None
    
    collapse_updates = None
    collapse_updates_time = None
    market_updates = None
    market_updates_time = None

    config_data = get_config()

    if config_data is not None:


        for row in config_data:
            chat_id = row[1]
            collapse_updates = row[2]
            collapse_updates_time = row[3]
            market_updates = row[4]
            market_updates_time = row[5]

            # if chat_id in chat_schedulers:
            #     bot.send_message(chat_id, 'Вы уже подписаны на обновления')

            if chat_id not in chat_schedulers and chat_id is not None and collapse_updates:
                scheduler = BackgroundScheduler()
                chat_schedulers[chat_id] = scheduler
                scheduler.start()

                scheduler = chat_schedulers[chat_id]

                tickers = get_all_tickers(chat_id)

                if not tickers:
                    bot.send_message(chat_id, 'У вас нет активных тикеров')
                else:
                    for ticker in tickers:
                        info = get_info_by_ticker(str(ticker[0]))
                        figi = info['figi'].values[0:1][0]
                        name = info['name'].values[0:1][0]
                        type_of = info['type'].values[0:1][0]
                        ticker = ticker[0]

                        if collapse_updates_time == 10:
                            start_time = datetime.now() - timedelta(minutes=10)
                            candle_interval = CandleInterval.CANDLE_INTERVAL_1_MIN
                        elif collapse_updates_time == 30:
                            start_time = datetime.now() - timedelta(minutes=30)
                            candle_interval = CandleInterval.CANDLE_INTERVAL_1_MIN
                        elif collapse_updates_time == 60:
                            start_time = datetime.now() - timedelta(hours=1)
                            candle_interval = CandleInterval.CANDLE_INTERVAL_1_MIN

                        end_time = datetime.now()
                        # Настраиваем задания планировщика
                        scheduler.add_job(send_price_change_notification_collapse, 'interval', minutes=collapse_updates_time, args=(figi, start_time, end_time, candle_interval, bot, chat_id, name, type_of, ticker))


            if chat_id not in chat_schedulers and chat_id is not None and market_updates:
                scheduler = BackgroundScheduler()
                chat_schedulers[chat_id] = scheduler
                scheduler.start()

                scheduler = chat_schedulers[chat_id]

                tickers = get_all_tickers(chat_id)

                if not tickers:
                    bot.send_message(chat_id, 'У вас нет активных тикеров')
                else:
                    for ticker in tickers:
                        info = get_info_by_ticker(str(ticker[0]))
                        figi = info['figi'].values[0:1][0]
                        name = info['name'].values[0:1][0]
                        type_of = info['type'].values[0:1][0]
                        ticker = ticker[0]

                        if market_updates_time == 10:
                            start_time = datetime.now() - timedelta(minutes=10)
                            candle_interval = CandleInterval.CANDLE_INTERVAL_1_MIN
                        elif market_updates_time == 30:
                            start_time = datetime.now() - timedelta(minutes=30)
                            candle_interval = CandleInterval.CANDLE_INTERVAL_1_MIN
                        elif market_updates_time == 60:
                            start_time = datetime.now() - timedelta(hours=1)
                            candle_interval = CandleInterval.CANDLE_INTERVAL_1_MIN

                        end_time = datetime.now()
                        # Настраиваем задания планировщика
                        scheduler.add_job(send_price_change_notification_market_updates, 'interval', minutes=market_updates_time, args=(figi, start_time, end_time, candle_interval, bot, chat_id, name, type_of, ticker))

    
    chat_id = None
    time = None

    strategy_data = get_strategy()
    
    for row in strategy_data:
        chat_id = row[1]
        tpsl = row[2]
        rsi = row[3]
        sma = row[4]
        alligator = row[5]
        time = row[6]
        autom = row[7]
        quantity = row[8]

        if tpsl == 0 and rsi == 0 and sma == 0 and alligator == 0:
            return
        
        if chat_id not in strategy_shedulers and chat_id is not None:
            scheduler = BackgroundScheduler()
            strategy_shedulers[chat_id] = scheduler
            scheduler.start()

            scheduler = strategy_shedulers[chat_id]

            scheduler.add_job(strategy_run, 'interval', minutes=int(time), args=(chat_id,))
            print("Стратегия добавлена в планировщик")



# <=============================================================================================>

# Словарь для хранения промежуточных данных сигналов
user_rsi_data = {}
user_sma_data = {}
user_tpsl_data = {}
user_alligator_data = {}

@bot.message_handler(func=lambda message: message.text == 'Стратегии')
def show_strategies(message):
    chat_id = message.chat.id
    token = get_t_token(chat_id)
    if token is not None:
        inline_keyboard = types.InlineKeyboardMarkup()
        buttons = [
            types.InlineKeyboardButton(text='Настроить сигналы', callback_data='signals_set'),
            types.InlineKeyboardButton(text='Настроить стратегию', callback_data='strategy_set'),
            types.InlineKeyboardButton(text='Отключить стратегию', callback_data='strategy_remove'),
        ]
        inline_keyboard.add(*buttons)
        bot.send_message(chat_id, 'Выберите опцию', reply_markup=inline_keyboard)


@bot.callback_query_handler(func=lambda call: call.data == 'signals_set')
def show_signals(call):
    chat_id = call.message.chat.id
    token = get_t_token(chat_id)
    if token is not None:
        inline_keyboard = types.InlineKeyboardMarkup()
        buttons = [
            types.InlineKeyboardButton(text='Take Profit/Stop Loss', callback_data='signal_tpsl'),
            types.InlineKeyboardButton(text='RSI', callback_data='signal_rsi'),
            types.InlineKeyboardButton(text='SMA', callback_data='signal_sma'),
            types.InlineKeyboardButton(text='Alligator', callback_data='signal_alligator'),
        ]
        inline_keyboard.add(*buttons)
        bot.send_message(chat_id, 'Выберите сигнал для настройки', reply_markup=inline_keyboard)



# <==================== ОБРАБОТЧИКИ НАСТРОЙКИ СТРАТЕГИИ ====================>

selected_signals = {}
available_signals = ['RSI', 'SMA', 'Take Profit/Stop Loss', 'Alligator']
tpsl_trigger = False
rsi_trigger = False
sma_trigger = False
alligator_trigger = False
time = None
auto_market = None
quantity = None

@bot.callback_query_handler(func=lambda call: call.data == 'strategy_set')
def show_signals(call):
    chat_id = call.message.chat.id
    token = get_t_token(chat_id)
    if token is not None:
        # Генерация кнопок для выбора сигналов
        markup = types.InlineKeyboardMarkup(row_width=2)
        buttons = [types.InlineKeyboardButton(signal, callback_data=f'select_{signal.lower()}') for signal in available_signals]
        buttons.append(types.InlineKeyboardButton('Ок', callback_data='ok'))
        buttons.append(types.InlineKeyboardButton('Отмена', callback_data='cancel'))
        markup.add(*buttons)

        bot.send_message(chat_id, "Выберите, какие сигналы подключить к стратегии:", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data == 'strategy_remove')
def remove_strategy(call):
    global selected_signals, tpsl_trigger, rsi_trigger, sma_trigger, alligator_trigger, time, auto_market, quantity
    chat_id = call.message.chat.id
    token = get_t_token(chat_id)
    if token is not None:

        if chat_id in strategy_shedulers:
            scheduler = strategy_shedulers[chat_id]
            scheduler.shutdown()
            del strategy_shedulers[chat_id]

        update_strategy(chat_id, 0, 0, 0, 0, 0, False, 0)
        
        selected_signals = {}
        tpsl_trigger = False
        rsi_trigger = False
        sma_trigger = False
        alligator_trigger = False
        time = None
        auto_market = None
        quantity = None

        bot.send_message(chat_id, "Стратегия отключена.")



# Обработчик выбора сигнала
@bot.callback_query_handler(func=lambda call: call.data.startswith('select_'))
def select_signal(call):
    global selected_signals, tpsl_trigger, rsi_trigger, sma_trigger, alligator_trigger
    chat_id = call.message.chat.id
    signal = call.data.split('_')[1].upper()

    # Проверяем, не выбран ли сигнал уже
    if selected_signals.get(signal):
        bot.send_message(chat_id, f"Сигнал {signal} уже выбран.")
        return

    # Проверяем, что все поля для сигнала заполнены
    if signal == 'RSI':
        if get_rsi(chat_id)[2:] == [None, None]:  
            bot.send_message(chat_id, "Сигнал RSI не настроен.")
        else:
            selected_signals[signal] = True
            rsi_trigger = True
            bot.send_message(chat_id, f"Сигнал {signal} добавлен.")
    elif signal == 'SMA':
        if get_sma(chat_id)[2:] == [None, None]:
            bot.send_message(chat_id, "Сигнал SMA не настроен.")
        else:
            selected_signals[signal] = True
            sma_trigger = True
            bot.send_message(chat_id, f"Сигнал {signal} добавлен.")
    elif signal == 'TAKE PROFIT/STOP LOSS':
        if get_tpsl(chat_id)[2:] == [None, None]:
            bot.send_message(chat_id, "Сигнал Take Profit/Stop Loss не настроен.")
        else:
            selected_signals[signal] = True
            tpsl_trigger = True
            bot.send_message(chat_id, f"Сигнал {signal} добавлен.")
    elif signal == 'ALLIGATOR':
        if get_alligator(chat_id)[2:] == [None, None]:
            bot.send_message(chat_id, "Сигнал Alligator не настроен.")
        else:
            selected_signals[signal] = True
            alligator_trigger = True
            bot.send_message(chat_id, f"Сигнал {signal} добавлен.")

    # Повторно выводим кнопки для выбора сигналов
    show_signals(call)
        

@bot.callback_query_handler(func=lambda call: call.data == 'ok')
def confirm_selection(call):
    chat_id = call.message.chat.id

    if not selected_signals:
        bot.send_message(chat_id, "Вы не выбрали ни одного сигнала.")
        return

    # Показываем выбор времени
    markup = types.InlineKeyboardMarkup(row_width=3)
    markup.add(types.InlineKeyboardButton('2 минуты', callback_data='time_2'),
               types.InlineKeyboardButton('5 минут', callback_data='time_5'),
               types.InlineKeyboardButton('10 минут', callback_data='time_10'))
    bot.send_message(chat_id, "Выберите время для стратегии:", reply_markup=markup)


@bot.callback_query_handler(func=lambda call: call.data.startswith('time_'))
def select_time(call):
    global time
    chat_id = call.message.chat.id
    time = int(call.data.split('_')[1])

    # Спрашиваем о включении автоматической торговли
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(types.InlineKeyboardButton('Да', callback_data='auto_yes'),
               types.InlineKeyboardButton('Нет', callback_data='auto_no'))
    bot.send_message(chat_id, "Включить автоматическую торговлю?", reply_markup=markup)

# Обработчик включения автоматической торговли
@bot.callback_query_handler(func=lambda call: call.data.startswith('auto_'))
def set_auto_market(call):
    global quantity, selected_signals, tpsl_trigger, rsi_trigger, sma_trigger, alligator_trigger, time, auto_market, quantity
    chat_id = call.message.chat.id
    auto_market = call.data.split('_')[1] == 'yes'

    if auto_market:
        # Спрашиваем у пользователя, сколько бумаг покупать/продавать
        msg = bot.send_message(chat_id, "Введите количество бумаг для покупки/продажи:")
        bot.register_next_step_handler(msg, set_quantity)
    else:
        # Вызов функции обновления стратегии с учетом введенного количества бумаг
        update_strategy(chat_id, tpsl_trigger, rsi_trigger, sma_trigger, alligator_trigger, time, auto_market, 0)

        # Завершение текущего планировщика и создание нового
        if chat_id in strategy_shedulers:
            scheduler = strategy_shedulers[chat_id]
            scheduler.shutdown()
            del strategy_shedulers[chat_id]

        scheduler = BackgroundScheduler()
        strategy_shedulers[chat_id] = scheduler
        scheduler.start()

        scheduler = strategy_shedulers[chat_id]
        scheduler.add_job(strategy_run, 'interval', minutes=int(time), args=(chat_id,))

        # Сброс переменных стратегии
        selected_signals = {}
        tpsl_trigger = False
        rsi_trigger = False
        sma_trigger = False
        alligator_trigger = False
        time = None
        auto_market = None
        quantity = None

        bot.send_message(chat_id, "Стратегия обновлена.")

def set_quantity(message):
    global quantity, selected_signals, tpsl_trigger, rsi_trigger, sma_trigger, alligator_trigger, time, auto_market, quantity
    chat_id = message.chat.id

    # Проверка на ввод числа
    try:
        quantity = int(message.text)
    except ValueError:
        msg = bot.send_message(chat_id, "Пожалуйста, введите корректное количество (целое число):")
        bot.register_next_step_handler(msg, set_quantity)
        return

    # Вызов функции обновления стратегии с учетом введенного количества бумаг
    update_strategy(chat_id, tpsl_trigger, rsi_trigger, sma_trigger, alligator_trigger, time, auto_market, quantity)

    # Завершение текущего планировщика и создание нового
    if chat_id in strategy_shedulers:
        scheduler = strategy_shedulers[chat_id]
        scheduler.shutdown()
        del strategy_shedulers[chat_id]

    scheduler = BackgroundScheduler()
    strategy_shedulers[chat_id] = scheduler
    scheduler.start()

    scheduler = strategy_shedulers[chat_id]
    scheduler.add_job(strategy_run, 'interval', minutes=int(time), args=(chat_id,))

    # Сброс переменных стратегии
    selected_signals = {}
    tpsl_trigger = False
    rsi_trigger = False
    sma_trigger = False
    alligator_trigger = False
    time = None
    auto_market = None
    quantity = None

    bot.send_message(chat_id, "Стратегия обновлена.")




# Обработчик кнопки "Отмена"
@bot.callback_query_handler(func=lambda call: call.data == 'cancel')
def cancel_strategy(call):
    global selected_signals, tpsl_trigger, rsi_trigger, sma_trigger, alligator_trigger, time, auto_market, quantity
    chat_id = call.message.chat.id

    # Сброс всех параметров
    selected_signals.clear()
    tpsl_trigger = None
    rsi_trigger = None
    sma_trigger = None
    alligator_trigger = None
    time = None
    auto_market = None
    quantity = None

    bot.send_message(chat_id, "Выбор стратегии отменен.")

# <==================== ОБРАБОТЧИКИ НАСТРОЙКИ СИГНАЛА RSI ====================>

from telebot import types

@bot.callback_query_handler(func=lambda call: call.data == 'signal_rsi')
def rsi_on(call):
    chat_id = call.message.chat.id
    token = get_t_token(chat_id)
    
    if token is not None:
        msg = bot.send_message(chat_id, "Введите период RSI:")
        bot.register_next_step_handler(msg, get_rsi_period)

def get_rsi_period(message):
    chat_id = message.chat.id
    try:
        period = int(message.text)
        user_rsi_data[chat_id] = {'period': period}  # Сохраняем период
        bot.send_message(chat_id, f"Вы выбрали период {period}. Теперь введите уровень перекупленности:")
        bot.register_next_step_handler(message, get_rsi_overbought)
    except ValueError:
        msg = bot.send_message(chat_id, "Некорректный ввод. Введите числовое значение для периода:")
        bot.register_next_step_handler(msg, get_rsi_period)

def get_rsi_overbought(message):
    chat_id = message.chat.id
    try:
        overbought = int(message.text)
        user_rsi_data[chat_id]['overbought'] = overbought  # Сохраняем уровень перекупленности
        bot.send_message(chat_id, f"Вы выбрали уровень перекупленности {overbought}. Теперь введите уровень перепроданности:")
        bot.register_next_step_handler(message, get_rsi_oversold)
    except ValueError:
        msg = bot.send_message(chat_id, "Некорректный ввод. Введите числовое значение для уровня перекупленности:")
        bot.register_next_step_handler(msg, get_rsi_overbought)

def get_rsi_oversold(message):
    chat_id = message.chat.id

    oversold = int(message.text)
    user_rsi_data[chat_id]['oversold'] = oversold  

    period = user_rsi_data[chat_id]['period']
    overbought = user_rsi_data[chat_id]['overbought']
    oversold = user_rsi_data[chat_id]['oversold']

    update_signal_rsi(chat_id, period, overbought, oversold)
    
    # Подтверждение настройки стратегии
    bot.send_message(chat_id, f"Стратегия RSI настроена с параметрами:\n"
                            f"Период: {period}\n"
                            f"Перекупленность: {overbought}\n"
                            f"Перепроданность: {oversold}\n")

    # Очищаем временные данные после использования
    del user_rsi_data[chat_id]
        
    
# <=====================================НАСТРОЙКА СИГНАЛА SMA===============================================>

@bot.callback_query_handler(func=lambda call: call.data == 'signal_sma')
def sma_on(call):
    chat_id = call.message.chat.id
    token = get_t_token(chat_id)
    
    if token is not None:
        msg = bot.send_message(chat_id, "Введите кол-во точек для расчета быстрого тренда:")
        bot.register_next_step_handler(msg, get_sma_fast)

def get_sma_fast(message):
    chat_id = message.chat.id
    try:
        fastLength = int(message.text)
        user_sma_data[chat_id] = {'fastLength': fastLength}  # Сохраняем период
        bot.send_message(chat_id, f"Вы выбрали кол-во точек для расчета быстрого тренда {fastLength}. Теперь введите количество точек для расчета медленного тренда:")
        bot.register_next_step_handler(message, get_sma_slow)
    except ValueError:
        msg = bot.send_message(chat_id, "Некорректный ввод. Введите числовое значение для периода:")
        bot.register_next_step_handler(msg, get_sma_fast)


def get_sma_slow(message):
    chat_id = message.chat.id
    try:
        slowLength = int(message.text)
        user_sma_data[chat_id]['slowLength'] = slowLength # Сохраняем период
        bot.send_message(chat_id, f"Вы выбрали кол-во точек для расчета медленного тренда {slowLength}.")
        fastLength = user_sma_data[chat_id]['fastLength']

        update_signal_sma(chat_id, fastLength, slowLength)

        # Подтверждение активации стратегии
        bot.send_message(chat_id, 
                                f"Стратегия SMA настроена с параметрами:\n"
                                f"Кол-во точек для расчета быстрого тренда: {fastLength}\n"
                                f"Кол-во точек для расчета медленного тренда: {slowLength}\n"
                         )


        # Очищаем временные данные после использования
        del user_sma_data[chat_id]
        
    except ValueError:
        msg = bot.send_message(chat_id, "Некорректный ввод. Введите числовое значение для периода:")
        bot.register_next_step_handler(msg, get_sma_slow)

# <=====================================НАСТРОЙКА СИГНАЛА TPSL===============================================>

@bot.callback_query_handler(func=lambda call: call.data == 'signal_tpsl')
def connect_tp_sl(call):
    chat_id = call.message.chat.id
    bot.send_message(chat_id, 'Введите значение для Take Profit')
    bot.register_next_step_handler_by_chat_id(chat_id, get_tp_value)


def get_tp_value(message):
    chat_id = message.chat.id
    tp_value = message.text
    user_tpsl_data[chat_id] = {'tp_value': tp_value}
    bot.send_message(chat_id, 'Введите значение для Stop Loss')
    bot.register_next_step_handler_by_chat_id(chat_id, get_sl_value)


def get_sl_value(message):
    chat_id = message.chat.id
    sl_value = message.text
    user_tpsl_data[chat_id]['sl_value'] = sl_value
    tp_value = user_tpsl_data[chat_id]['tp_value']

    update_signal_tpsl(chat_id, tp_value, sl_value)

    bot.send_message(chat_id, 'Take Profit/Stop Loss настроен с параметрами:\nTake Profit = ' + user_tpsl_data[chat_id]['tp_value'] + '\nStop Loss = ' + user_tpsl_data[chat_id]['sl_value'])

    del user_tpsl_data[chat_id]


# <==================== ОБРАБОТЧИКИ НАСТРОЙКИ СИГНАЛА ALLIGATOR ====================>

@bot.callback_query_handler(func=lambda call: call.data == 'signal_alligator')
def alligator_on(call):
    chat_id = call.message.chat.id
    token = get_t_token(chat_id)
    
    if token is not None:
        msg = bot.send_message(chat_id, "Введите период для челюстей (Jaw):")
        bot.register_next_step_handler(msg, get_alligator_jaw_period)

def get_alligator_jaw_period(message):
    chat_id = message.chat.id
    try:
        jaw_period = int(message.text)
        user_alligator_data[chat_id] = {'jaw_period': jaw_period}  # Сохраняем период для челюстей
        bot.send_message(chat_id, f"Вы выбрали период {jaw_period} для челюстей. Теперь введите смещение для челюстей (Jaw shift):")
        bot.register_next_step_handler(message, get_alligator_jaw_shift)
    except ValueError:
        msg = bot.send_message(chat_id, "Некорректный ввод. Введите числовое значение для периода челюстей:")
        bot.register_next_step_handler(msg, get_alligator_jaw_period)

def get_alligator_jaw_shift(message):
    chat_id = message.chat.id
    try:
        jaw_shift = int(message.text)
        user_alligator_data[chat_id]['jaw_shift'] = jaw_shift  # Сохраняем смещение для челюстей
        bot.send_message(chat_id, f"Вы выбрали смещение {jaw_shift} для челюстей. Теперь введите период для зубов (Teeth):")
        bot.register_next_step_handler(message, get_alligator_teeth_period)
    except ValueError:
        msg = bot.send_message(chat_id, "Некорректный ввод. Введите числовое значение для смещения челюстей:")
        bot.register_next_step_handler(msg, get_alligator_jaw_shift)

def get_alligator_teeth_period(message):
    chat_id = message.chat.id
    try:
        teeth_period = int(message.text)
        user_alligator_data[chat_id]['teeth_period'] = teeth_period  # Сохраняем период для зубов
        bot.send_message(chat_id, f"Вы выбрали период {teeth_period} для зубов. Теперь введите смещение для зубов (Teeth shift):")
        bot.register_next_step_handler(message, get_alligator_teeth_shift)
    except ValueError:
        msg = bot.send_message(chat_id, "Некорректный ввод. Введите числовое значение для периода зубов:")
        bot.register_next_step_handler(msg, get_alligator_teeth_period)

def get_alligator_teeth_shift(message):
    chat_id = message.chat.id
    try:
        teeth_shift = int(message.text)
        user_alligator_data[chat_id]['teeth_shift'] = teeth_shift  # Сохраняем смещение для зубов
        bot.send_message(chat_id, f"Вы выбрали смещение {teeth_shift} для зубов. Теперь введите период для губ (Lips):")
        bot.register_next_step_handler(message, get_alligator_lips_period)
    except ValueError:
        msg = bot.send_message(chat_id, "Некорректный ввод. Введите числовое значение для смещения зубов:")
        bot.register_next_step_handler(msg, get_alligator_teeth_shift)

def get_alligator_lips_period(message):
    chat_id = message.chat.id
    try:
        lips_period = int(message.text)
        user_alligator_data[chat_id]['lips_period'] = lips_period  # Сохраняем период для губ
        bot.send_message(chat_id, f"Вы выбрали период {lips_period} для губ. Теперь введите смещение для губ (Lips shift):")
        bot.register_next_step_handler(message, get_alligator_lips_shift)
    except ValueError:
        msg = bot.send_message(chat_id, "Некорректный ввод. Введите числовое значение для периода губ:")
        bot.register_next_step_handler(msg, get_alligator_lips_period)

def get_alligator_lips_shift(message):
    chat_id = message.chat.id
    try:
        lips_shift = int(message.text)
        user_alligator_data[chat_id]['lips_shift'] = lips_shift  # Сохраняем смещение для губ

        # Получаем все введённые параметры
        jaw_period = user_alligator_data[chat_id]['jaw_period']
        jaw_shift = user_alligator_data[chat_id]['jaw_shift']
        teeth_period = user_alligator_data[chat_id]['teeth_period']
        teeth_shift = user_alligator_data[chat_id]['teeth_shift']
        lips_period = user_alligator_data[chat_id]['lips_period']
        lips_shift = user_alligator_data[chat_id]['lips_shift']

        # Обновляем параметры в базе данных
        update_signal_alligator(chat_id, jaw_period, jaw_shift, teeth_period, teeth_shift, lips_period, lips_shift)
        
        # Подтверждение настройки стратегии
        bot.send_message(chat_id, f"Стратегия Аллигатор настроена с параметрами:\n"
                                  f"Челюсти - Период: {jaw_period}, Смещение: {jaw_shift}\n"
                                  f"Зубы - Период: {teeth_period}, Смещение: {teeth_shift}\n"
                                  f"Губы - Период: {lips_period}, Смещение: {lips_shift}\n")

        # Очищаем временные данные после использования
        del user_alligator_data[chat_id]
    except ValueError:
        msg = bot.send_message(chat_id, "Некорректный ввод. Введите числовое значение для смещения губ:")
        bot.register_next_step_handler(msg, get_alligator_lips_shift)


# <=====================================ЗАПУСК СТРАТЕГИИ===============================================>
def strategy_run(chat_id):

    token = get_t_token(chat_id)
    if token is not None:

        # Получаем тикеры из базы данных
        tickers = get_all_tickers(chat_id)
        
        if not tickers:
            bot.send_message(chat_id, 'У вас нет активных тикеров')
            return
        
        else:

            tpsl = None
            rsi = None
            sma = None
            alligator = None  # Добавляем переменную для Аллигатора
            time = None
            auto_market = None
            quantity = None

            strategy_data = get_strategy()

            for row in strategy_data:

                tpsl = row[2]
                rsi = row[3]
                sma = row[4]
                alligator = row[5]  # Получаем значение для Аллигатора
                time = row[6]
                auto_market = row[7]
                quantity = row[8]

            for ticker in tickers:

                print(ticker[0])

                current_profit = None

                rsi_signal = None
                tpsl_signal = None
                sma_signal = None
                alligator_signal = None  # Добавляем переменную для сигнала Аллигатора

                figi = get_figi_by_ticker(ticker[0])

                # Смотрим, есть ли актив в портфеле
                position = get_instrument_from_portfolio_by_ticker(token, figi, ticker[0])

                if position is not None:

                    average_position_price = position['average_position_price']
                    current_price_one = position['current_price_one']
                    brokerFee = 0.3

                    current_profit = calculate_profit(average_position_price, current_price_one, brokerFee)


                # Проверяем rsi
                if rsi == 1:

                    period = None
                    lowLevel = None
                    highLevel = None

                    rsi_data = get_rsi(chat_id)

                    for row in rsi_data:

                        period = row[2]
                        highLevel = row[3]
                        lowLevel = row[4]
                    

                    start_time = None
                    candle_interval = None
                    time = int(time)

                    CANDLE_CONSTANT = 1
                    
                    start_time = datetime.now() - timedelta(minutes=period+CANDLE_CONSTANT)
                    candle_interval = CandleInterval.CANDLE_INTERVAL_1_MIN
                    

                    end_time = datetime.now()

                    # Получение свечей за указаный период
                    candles = get_historic_candles(figi, start_time, end_time, candle_interval)

                    if len(create_df(candles.candles)["close"].values) < period+CANDLE_CONSTANT:
                        print("MINIMUM")
                    
                    else:

                        # Расчет RSI
                        rsi_value = calculate_rsi(candles, period)

                        if rsi_value is None:
                            continue

                        rsi_signal = check_rsi_signal(rsi_value, lowLevel, highLevel, current_profit)


                # Проверяем sma
                if sma == 1:

                    fastLength = None
                    slowLength = None

                    sma_data = get_sma(chat_id)

                    for row in sma_data:

                        fastLength = row[2]
                        slowLength = row[3]
                    

                    start_time = None
                    candle_interval = None
                    time = int(time)

                    CANDLE_CONSTANT = 1
                    
                    start_time = datetime.now() - timedelta(minutes=slowLength+CANDLE_CONSTANT)
                    candle_interval = CandleInterval.CANDLE_INTERVAL_1_MIN
                    

                    end_time = datetime.now()

                    # Получение свечей за указаный период
                    candles = get_historic_candles(figi, start_time, end_time, candle_interval)

                    if len(create_df(candles.candles)["close"].values) < slowLength+CANDLE_CONSTANT:
                        print("MINIMUM")

                    else:
                        # Расчет SMA
                        sma_signal = calculate_sma_strategy(candles, fastLength, slowLength, current_profit)


                # Проверяем Аллигатор
                if alligator == 1:

                    jaw_period = None
                    jaw_shift = None
                    teeth_period = None
                    teeth_shift = None
                    lips_period = None
                    lips_shift = None

                    alligator_data = get_alligator(chat_id)

                    for row in alligator_data:

                        jaw_period = row[2]
                        jaw_shift = row[3]
                        teeth_period = row[4]
                        teeth_shift = row[5]
                        lips_period = row[6]
                        lips_shift = row[7]
                    

                    start_time = None
                    candle_interval = None
                    time = int(time)

                    CANDLE_CONSTANT = 1
                    
                    start_time = datetime.now() - timedelta(minutes=max(jaw_period, teeth_period, lips_period)+CANDLE_CONSTANT)
                    candle_interval = CandleInterval.CANDLE_INTERVAL_1_MIN
                    

                    end_time = datetime.now()

                    # Получение свечей за указанный период
                    candles = get_historic_candles(figi, start_time, end_time, candle_interval)

                    if len(create_df(candles.candles)["high"].values) < max(jaw_period, teeth_period, lips_period)+CANDLE_CONSTANT or len(create_df(candles.candles)["low"].values) < max(jaw_period, teeth_period, lips_period)+CANDLE_CONSTANT:
                        print("MINIMUM")

                    else:
                        # Расчет Аллигатора
                        alligator_signal = calculate_alligator_strategy(candles, jaw_period, jaw_shift, teeth_period, teeth_shift, lips_period, lips_shift, current_profit)


                # Проверяем tpsl
                if tpsl == 1:

                    takeProfit = None
                    stopLoss = None

                    tpsl_data = get_tpsl(chat_id)

                    for row in tpsl_data:

                        takeProfit = row[2]
                        stopLoss = row[3]
                    

                    if current_profit > takeProfit or current_profit < -stopLoss:

                        tpsl_signal = "sell"

                    else:

                        tpsl_signal = "hold"
                

                # Настройка автоматической торговли
                if auto_market == 1:

                    if rsi_signal == "buy" or sma_signal == "buy" or alligator_signal == "buy" or tpsl_signal == "buy":
                        signal_text = ""
                        if rsi_signal == "buy":
                            signal_text += "RSI "
                        if sma_signal == "buy":
                            signal_text += "SMA "
                        if alligator_signal == "buy":
                            signal_text += "Alligator "
                        if tpsl_signal == "buy":
                            signal_text += "TPSL "
                        
                        cancel_existing_order(token, figi)
                        place_order(token, figi, quantity, 'buy')
                        bot.send_message(chat_id, f"Автоматическая торговля. Покупка {ticker[0]} по сигналу {signal_text}")

                    elif rsi_signal == "sell" or sma_signal == "sell" or alligator_signal == "sell" or tpsl_signal == "sell":
                        signal_text = ""
                        if rsi_signal == "sell":
                            signal_text += "RSI "
                        if sma_signal == "sell":
                            signal_text += "SMA "
                        if alligator_signal == "sell":
                            signal_text += "Alligator "
                        if tpsl_signal == "sell":
                            signal_text += "TPSL "

                        cancel_existing_order(token, figi)
                        place_order(token, figi, quantity, 'sell')
                        bot.send_message(chat_id, f"Продаем {ticker[0]} по сигналу {signal_text}")
                    

                else:
                    if rsi_signal == "buy" or sma_signal == "buy" or alligator_signal == "buy" or tpsl_signal == "buy":
                        signal_text = ""
                        if rsi_signal == "buy":
                            signal_text += "RSI "
                        if sma_signal == "buy":
                            signal_text += "SMA "
                        if alligator_signal == "buy":
                            signal_text += "Alligator "
                        if tpsl_signal == "buy":
                            signal_text += "TPSL "
                        bot.send_message(chat_id, f"Покупка {ticker[0]} по сигналу {signal_text}")

                    elif rsi_signal == "sell" or sma_signal == "sell" or alligator_signal == "sell" or tpsl_signal == "sell":
                        signal_text = ""
                        if rsi_signal == "sell":
                            signal_text += "RSI "
                        if sma_signal == "sell":
                            signal_text += "SMA "
                        if alligator_signal == "sell":
                            signal_text += "Alligator "
                        if tpsl_signal == "sell":
                            signal_text += "TPSL "
                        bot.send_message(chat_id, f"Продаем {ticker[0]} по сигналу {signal_text}")

                    elif rsi_signal == "hold" or sma_signal == "hold" or alligator_signal == "hold" or tpsl_signal == "hold":
                        signal_text = ""
                        if rsi_signal == "hold":
                            signal_text += "RSI "
                        if sma_signal == "hold":
                            signal_text += "SMA "
                        if alligator_signal == "hold":
                            signal_text += "Alligator "
                        if tpsl_signal == "hold":
                            signal_text += "TPSL "
                        bot.send_message(chat_id, f"Держим {ticker[0]} по сигналу {signal_text}")


# Настройка конфигуратора планировщика
configure_scheduler()
print("Конфигуратор успешно настроен")
# Запускаем бота
bot.polling()