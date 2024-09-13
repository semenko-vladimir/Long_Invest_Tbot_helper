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

import telebot
import sqlite3
import credentials
from db import get_t_token
from methods import get_portfolio
from telebot import types
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
        keyboard.add(portfolio_button)
        bot.send_message(message.chat.id, 'Добро пожаловать!', reply_markup=keyboard)

@bot.message_handler(func=lambda message: message.text == 'Получить портфолио')
def get_portfolio_handler(message):
    chat_id = message.chat.id
    token = get_t_token(chat_id)
    if token is not None:
        portfolio = get_portfolio(token)
        text = (
            f"Общая стоимость акций: {portfolio['total_amount_shares']} руб.\n"
            f"Общая стоимость облигаций: {portfolio['total_amount_bonds']} руб.\n"
            f"Общая стоимость фондов: {portfolio['total_amount_etf']} руб.\n"
            f"Общая стоимость валют: {portfolio['total_amount_currencies']} руб.\n"
            f"Ожидаемая доходность: {portfolio['expected_yield']} %\n"
            f"Общая стоимость портфеля: {portfolio['total_amount_portfolio']} руб.\n"
        )
        bot.send_message(chat_id, text)
        

# Запускаем бота
bot.polling()