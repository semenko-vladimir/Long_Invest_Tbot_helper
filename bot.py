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
import credentials
from db import get_config, get_t_token, get_tpsl, insert_ticker, get_all_tickers, delete_ticker, delete_all_tickers, update_config_collapse, update_tpsl
import db
from methods import get_portfolio, get_figi_by_ticker, get_info_by_ticker, get_price_change_in_current_interval
from telebot import types
from tinkoff.invest import CandleInterval
from apscheduler.schedulers.background import BackgroundScheduler

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
        take_profit_stop_loss_button = types.KeyboardButton('Take Profit/Stop Loss')


        
        keyboard.row(portfolio_button, tickers_get_button, receive_market_collapse_button)

        keyboard.row(ticker_add_button, ticker_delete_button, tickers_delete_all_button)

        keyboard.row(subscribe_to_collapse_update_button, unsubscribe_to_collapse_update_button)

        keyboard.row(subscribe_to_market_update_button, unsubscribe_to_market_update_button, receive_market_update_button)

        keyboard.row(all_market_status_button, take_profit_stop_loss_button)
        
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
tpsl_shedulers = {}

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

def configure_scheduler():

    chat_id = None
    
    collapse_updates = None
    collapse_updates_time = None
    market_updates = None
    market_updates_time = None

    config_data = get_config()

    if config_data is None:
        return

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
    trigger = None
    time = None


    tpsl_data = get_tpsl()

    if tpsl_data is None:
        return

    for row in tpsl_data:
        chat_id = row[1]
        trigger = row[2]
        time = row[3]

        if chat_id not in tpsl_shedulers and trigger:
            scheduler = BackgroundScheduler()
            tpsl_shedulers[chat_id] = scheduler
            scheduler.start()

            scheduler = tpsl_shedulers[chat_id]

            scheduler.add_job(tpsl_run, 'interval', minutes=int(time), args=(chat_id,))

            



# <=============================================================================>


@bot.message_handler(func=lambda message: message.text == 'Take Profit/Stop Loss')
def add_ticker_handler(message):
    chat_id = message.chat.id
    inline_keyboard = types.InlineKeyboardMarkup()
    buttons = [
        types.InlineKeyboardButton(text='Подключить Take Profit/Stop Loss', callback_data='connect_tp_sl'),
        types.InlineKeyboardButton(text='Отключить Take Profit/Stop Loss', callback_data='disconnect_tp_sl'),
    ]
    inline_keyboard.add(*buttons)
    bot.send_message(chat_id, 'Выберите опцию', reply_markup=inline_keyboard)


user_data = {}

@bot.callback_query_handler(func=lambda call: call.data == 'connect_tp_sl')
def connect_tp_sl(call):
    chat_id = call.message.chat.id
    data = get_tpsl()
    for row in data:
        trigger_chat_id = row[1]
        trigger = row[2]
        if trigger and chat_id == trigger_chat_id:
            bot.send_message(chat_id, 'У вас уже подключены Take Profit/Stop Loss')
            return
    user_data[chat_id] = {}
    bot.send_message(chat_id, 'Введите значение для Take Profit')
    bot.register_next_step_handler_by_chat_id(chat_id, get_tp_value)


def get_tp_value(message):
    chat_id = message.chat.id
    tp_value = message.text
    user_data[chat_id]['tp_value'] = tp_value
    bot.send_message(chat_id, 'Введите значение для Stop Loss')
    bot.register_next_step_handler_by_chat_id(chat_id, get_sl_value)


def get_sl_value(message):
    chat_id = message.chat.id
    sl_value = message.text
    user_data[chat_id]['sl_value'] = sl_value

    # Вместо использования next_step_handler, сразу выводим клавиатуру для интервала
    inline_keyboard = types.InlineKeyboardMarkup()
    buttons = [
        types.InlineKeyboardButton(text='1 минута', callback_data='1'),
        types.InlineKeyboardButton(text='5 минут', callback_data='5'),
        types.InlineKeyboardButton(text='10 минут', callback_data='10'),
    ]
    inline_keyboard.add(*buttons)
    bot.send_message(chat_id, 'Выберите интервал', reply_markup=inline_keyboard)


@bot.callback_query_handler(func=lambda call: call.data in ['1', '5', '10'])
def get_time(call):
    chat_id = call.message.chat.id
    time_value = call.data
    user_data[chat_id]['time_value'] = time_value

    inline_keyboard = types.InlineKeyboardMarkup()
    buttons = [
        types.InlineKeyboardButton(text='Да', callback_data='yes'),
        types.InlineKeyboardButton(text='Нет', callback_data='no'),
    ]
    inline_keyboard.add(*buttons)
    bot.send_message(chat_id, 'Включить ли автоматическую торговлю?', reply_markup=inline_keyboard)


@bot.callback_query_handler(func=lambda call: call.data in ['yes', 'no'])
def auto_trade(call):
    chat_id = call.message.chat.id
    user_data[chat_id]['call_data'] = call.data
    set_tpsl(chat_id)


def set_tpsl(chat_id):
    tp_value = user_data[chat_id]['tp_value']
    sl_value = user_data[chat_id]['sl_value']
    time_value = user_data[chat_id]['time_value']
    call_data = user_data[chat_id]['call_data']

    if call_data == 'yes':
        update_tpsl(chat_id, tp_value, sl_value, time_value, 1, 1)
    else:
        update_tpsl(chat_id, tp_value, sl_value, time_value, 0, 1)

    if chat_id not in tpsl_shedulers:
        scheduler = BackgroundScheduler()
        tpsl_shedulers[chat_id] = scheduler
        scheduler.start()
        scheduler = tpsl_shedulers[chat_id]

        scheduler.add_job(tpsl_run, 'interval', minutes=int(time_value), args=(chat_id,))

    bot.send_message(chat_id, 'Take Profit/Stop Loss успешно добавлен')




def tpsl_run(chat_id):

    text = ""
    token = get_t_token(chat_id)
    if token is not None:

        portfolio = get_portfolio(token)

        positions = portfolio['positions']

        if positions is None:
            bot.send_message(chat_id, 'Портфолио пустое')
            return
        
        tpls_data = get_tpsl()

        if tpls_data is None:
            return

        for row in tpls_data:
            auto_market = row[4]
            take_profit = row[5]
            stop_loss = row[6]

        for position in positions:

            expected_yeild = position['expected_yield']

            #Buy price
            average_position_price = position['average_position_price']

            current_price_one = position['current_price_one']
            print(current_price_one)
            quantity = position['quantity']
            ticker = position['ticker']
            brokerFee = 0.3

            comission = (average_position_price + current_price_one) * brokerFee / 100

            profit = current_price_one - average_position_price - comission

            current_profit = 100 * profit / average_position_price

            print(current_profit, ' <=>', ticker)

            if expected_yeild is None or expected_yeild == 0:
                pass
            else:

                if auto_market == 1:
                    # TODO: РЕАЛИЗОВАТЬ АВТОМАТИЧЕСКОЕ СОЗДАНИЕ ЗАЯВКИ
                    pass
                else:

                    if current_profit >= take_profit:
                        text = ""
                        text += (
                            f"TAKE_PROFIT\n\n"
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

                    elif current_profit <= -stop_loss:
                        text = ""
                        text += (
                            f"STOP_LOSS\n\n"
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

@bot.callback_query_handler(func=lambda call: call.data == 'disconnect_tp_sl')
def connect_tp_sl(call):

    chat_id = call.message.chat.id

    update_tpsl(chat_id, 0, 0, 0, 0, 0)

    if chat_id in tpsl_shedulers:
        scheduler = tpsl_shedulers[chat_id]
        scheduler.shutdown()
        del tpsl_shedulers[chat_id]
        bot.send_message(chat_id, 'Take Profit/Stop Loss отключен')
    else:
        bot.send_message(chat_id, 'Take Profit/Stop Loss не включен')


                        



            











# Настройка конфигуратора планировщика
configure_scheduler()
print("Конфигуратор успешно настроен")
# Запускаем бота
bot.polling()