from datetime import datetime, timedelta
from db.db import db_get_figi, get_all_tickers, get_bollinger, get_t_token
from bot.bot import bot
from telebot import types
from graphics.bollinger_graph import plot_bollinger
from log.logger import setup_logger
from signals.bollinger_signal import calculate_bollinger_strategy
from store.store import mls_interval
from tinkoff.invest import CandleInterval, Client

from utils.helpers import calculate_profit, cast_money, create_df
from utils.methods import get_current_price, get_historic_candles, get_instrument_from_portfolio_by_ticker

logger = setup_logger(__name__)

@bot.callback_query_handler(func=lambda call: call.data == 'calc_mls_bollinger')
def mls_bollinger_handler(call):
    chat_id = call.message.chat.id
    token = get_t_token(chat_id)
    if token is not None:
        tickers = get_all_tickers(chat_id)

        if not tickers:
            bot.send_message(chat_id, 'У вас нет активных тикеров')
        else:
            inline_keyboard = types.InlineKeyboardMarkup()
            buttons = [
                types.InlineKeyboardButton(text='пол года', callback_data='bollinger_interval_6'),
                types.InlineKeyboardButton(text='год', callback_data='bollinger_interval_12')
            ]
            inline_keyboard.add(*buttons)
            bot.send_message(chat_id, 'Выберите интервал', reply_markup=inline_keyboard)


@bot.callback_query_handler(func=lambda call: call.data.startswith('bollinger_interval_'))
def interval_handler(call):
    global mls_interval
    interval = call.data.replace('bollinger_interval_', '')
    
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
                button = types.InlineKeyboardButton(text=str(ticker[0]), callback_data=f'mls_bollinger_ticker_{ticker[0]}')
                inline_keyboard.add(button)
            bot.send_message(chat_id, 'Выберите инструмент для расчета', reply_markup=inline_keyboard)


@bot.callback_query_handler(func=lambda call: call.data.startswith('mls_bollinger_ticker_'))
def calculate_mls_bollinger(call):
    ticker = call.data.replace('mls_bollinger_ticker_', '')

    chat_id = call.message.chat.id
    token = get_t_token(chat_id)

    current_profit = 0

    if token is not None:

        bollinger_period = None
        bollinger_std = None
        type_ma = None

        bollinger_data = get_bollinger(chat_id)

        for row in bollinger_data:
            bollinger_period = row[2]
            bollinger_std = row[3]
            type_ma = row[4]

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

        if len(create_df(candles.candles)["close"].values) < bollinger_period+CANDLE_CONSTANT:
            logger.info("NOT enough candles for the Bollinger signal")
            print("MINIMUM")

        else:
            # Расчет Bollinger


            bollinger_signal = calculate_bollinger_strategy(candles, bollinger_period, bollinger_std, type_ma, current_profit)
            
            if bollinger_signal != 'hold':
                bot.send_message(chat_id, f'{ticker} - {bollinger_signal}')

            df = create_df(candles.candles)
            plot_bollinger(chat_id, df)






    


