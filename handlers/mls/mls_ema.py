from datetime import datetime, timedelta
from db.db import db_get_figi, get_all_tickers, get_ema, get_t_token
from bot.bot import bot
from telebot import types
from graphics.ema_graph import plot_ema
from log.logger import setup_logger
from signals.ema_signal import calculate_ema_strategy
from store.store import mls_interval
from tinkoff.invest import CandleInterval, Client

from utils.helpers import calculate_profit, cast_money, create_df
from utils.methods import get_current_price, get_historic_candles, get_instrument_from_portfolio_by_ticker

logger = setup_logger(__name__)

@bot.callback_query_handler(func=lambda call: call.data == 'calc_mls_ema')
def mls_ema_handler(call):
    chat_id = call.message.chat.id
    token = get_t_token(chat_id)
    if token is not None:
        tickers = get_all_tickers(chat_id)

        if not tickers:
            bot.send_message(chat_id, 'У вас нет активных тикеров')
        else:
            inline_keyboard = types.InlineKeyboardMarkup()
            buttons = [
                types.InlineKeyboardButton(text='пол года', callback_data='ema_interval_6'),
                types.InlineKeyboardButton(text='год', callback_data='ema_interval_12')
            ]
            inline_keyboard.add(*buttons)
            bot.send_message(chat_id, 'Выберите интервал', reply_markup=inline_keyboard)


@bot.callback_query_handler(func=lambda call: call.data.startswith('ema_interval_'))
def interval_handler(call):
    global mls_interval
    interval = call.data.replace('ema_interval_', '')
    
    mls_interval = interval

    chat_id = call.message.chat.id
    token = get_t_token(chat_id)
    if token is not None:
        tickers = get_all_tickers(chat_id)

        if not tickers:
            bot.send_message(chat_id, 'У вас нет активных тикеров')
        else:
            inline_keyboard = types.InlineKeyboardMarkup()
            for ticker in tickers:
                button = types.InlineKeyboardButton(text=str(ticker[0]), callback_data=f'mls_ema_ticker_{ticker[0]}')
                inline_keyboard.add(button)
            bot.send_message(chat_id, 'Выберите инструмент для расчета', reply_markup=inline_keyboard)


@bot.callback_query_handler(func=lambda call: call.data.startswith('mls_ema_ticker_'))
def calculate_mls_ema(call):
    ticker = call.data.replace('mls_ema_ticker_', '')

    chat_id = call.message.chat.id
    token = get_t_token(chat_id)

    current_profit = 0

    if token is not None:

        fastLength = None
        slowLength = None

        ema_data = get_ema(chat_id)

        for row in ema_data:

            fastLength = row[2]
            slowLength = row[3]

        figi = db_get_figi(chat_id, ticker)

        # Смотрим, есть ли актив в портфеле
        position = get_instrument_from_portfolio_by_ticker(token, figi, ticker[0], False)

        if position is not None:

            average_position_price = position['average_position_price']
            #current_price_one = position['current_price_one']

            with Client(token) as client:
                current_price_sell, _ = get_current_price(figi, client, 'fast')

            brokerFee = 0.3

            current_profit = calculate_profit(average_position_price, cast_money(current_price_sell), brokerFee)

        else:

            current_profit = 0

        CANDLE_CONSTANT = 1

        if mls_interval == '6':
            start_time = datetime.now() - timedelta(days=183)
        elif mls_interval == '12':
            start_time = datetime.now() - timedelta(days=365)

        candle_interval = CandleInterval.CANDLE_INTERVAL_DAY

        end_time = datetime.now()

        candles = get_historic_candles(figi, start_time, end_time, candle_interval)
                    
        if len(create_df(candles.candles)["close"].values) < slowLength+CANDLE_CONSTANT:
            logger.info("NOT enough candles for the EMA signal")
            print("MINIMUM")
        
        else:

            ema_signal = calculate_ema_strategy(candles, fastLength, slowLength, current_profit)

            bot.send_message(chat_id, f'{ticker} - {ema_signal}')

            df = create_df(candles.candles)
            plot_ema(chat_id, df)






    


