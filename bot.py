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
from db import get_t_token, insert_ticker, get_all_tickers, delete_ticker, delete_all_tickers
from methods import get_portfolio, get_figi_by_ticker
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
        ticker_add_button = types.KeyboardButton('Добавить тикер')
        tickers_get_button = types.KeyboardButton('Получить мои тикеры')
        ticker_delete_button = types.KeyboardButton('Удалить тикер')
        tickers_delete_all_button = types.KeyboardButton('Удалить мои тикеры')
        
        keyboard.row(portfolio_button, tickers_get_button)
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
            buttons = []
            for ticker in tickers:
                t = ticker[0]
                button = types.InlineKeyboardButton(text=str(ticker[0]), callback_data=str(ticker[0]))
                buttons.append([button])
            inline_keyboard.keyboard = buttons
            bot.send_message(chat_id, 'Выберите тикер', reply_markup=inline_keyboard)

@bot.callback_query_handler(func=lambda call: True)
def delete_ticker_step(call):
    ticker = call.data
    delete_ticker(call.message.chat.id, ticker)
    bot.send_message(call.message.chat.id, f'Тикер "{ticker}" успешно удален')


# Запускаем бота
bot.polling()