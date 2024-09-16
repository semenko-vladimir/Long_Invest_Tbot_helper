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
from db import get_t_token, insert_ticker, get_all_tickers, delete_ticker, delete_all_tickers
from methods import get_portfolio, get_figi_by_ticker, get_info_by_ticker, get_price_change_in_current_interval
from telebot import types
from tinkoff.invest import CandleInterval
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
        
        keyboard.row(portfolio_button, tickers_get_button, receive_market_collapse_button)
        keyboard.row(ticker_add_button, ticker_delete_button, tickers_delete_all_button)
        
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
            start_time = datetime.utcnow() - timedelta(minutes=10)
            candle_interval = CandleInterval.CANDLE_INTERVAL_1_MIN
        elif interval == 'час':
            start_time = datetime.utcnow() - timedelta(hours=1)
            candle_interval = CandleInterval.CANDLE_INTERVAL_1_MIN
        elif interval == 'день':
            start_time = datetime.utcnow() - timedelta(days=1)
            candle_interval = CandleInterval.CANDLE_INTERVAL_10_MIN
        elif interval == 'неделя':
            start_time = datetime.utcnow() - timedelta(weeks=1)
            candle_interval = CandleInterval.CANDLE_INTERVAL_DAY
        elif interval == 'месяц':
            start_time = datetime.utcnow() - timedelta(days=30)
            candle_interval = CandleInterval.CANDLE_INTERVAL_WEEK
        elif interval == 'год':
            start_time = datetime.utcnow() - timedelta(days=365)
            candle_interval = CandleInterval.CANDLE_INTERVAL_MONTH

        end_time = datetime.utcnow()
        price_change, price_change_percent, max_price, min_price, close_price = get_price_change_in_current_interval(figi, start_time, end_time, candle_interval)

        # Проверка процента изменения цены
        if percent == 'до 100%' and price_change_percent < -0.01:
            bot.send_message(chat_id, f'Название: {name}\n Тип: {type_of}\n Тикер: {ticker}\n Изменение цены: {round(price_change_percent, 2)}% \n Текущая цена: {close_price} \n Максимальная цена: {max_price} \n Минимальная цена: {min_price}')
        if percent == 'до 2%' and 0 > price_change_percent > -2:
            bot.send_message(chat_id, f'Название: {name}\n Тип: {type_of}\n Тикер: {ticker}\n Изменение цены: {round(price_change_percent, 2)}% \n Текущая цена: {close_price} \n Максимальная цена: {max_price} \n Минимальная цена: {min_price}')
        elif percent == 'от 2% до 5%' and -2 >= price_change_percent >= -5:
            bot.send_message(chat_id, f'Название: {name}\n Тип: {type_of}\n Тикер: {ticker}\n Изменение цены: {round(price_change_percent, 2)}% \n Текущая цена: {close_price} \n Максимальная цена: {max_price} \n Минимальная цена: {min_price}')
        elif percent == 'от 5% до 10%' and -5 >= price_change_percent >= -10:
            bot.send_message(chat_id, f'Название: {name}\n Тип: {type_of}\n Тикер: {ticker}\n Изменение цены: {round(price_change_percent, 2)}% \n Текущая цена: {close_price} \n Максимальная цена: {max_price} \n Минимальная цена: {min_price}')
        elif percent == 'от 10% до 20%' and -10 >= price_change_percent >= -20:
            bot.send_message(chat_id, f'Название: {name}\n Тип: {type_of}\n Тикер: {ticker}\n Изменение цены: {round(price_change_percent, 2)}% \n Текущая цена: {close_price} \n Максимальная цена: {max_price} \n Минимальная цена: {min_price}')
        elif percent == 'более 20%' and price_change_percent <= -20:
            bot.send_message(chat_id, f'Название: {name}\n Тип: {type_of}\n Тикер: {ticker}\n Изменение цены: {round(price_change_percent, 2)}% \n Текущая цена: {close_price} \n Максимальная цена: {max_price} \n Минимальная цена: {min_price}')


# Запускаем бота
bot.polling()