from bot.bot import bot
from db.db import db_get_figi, get_all_tickers, get_alligator, get_bollinger, get_gpt, get_macd, get_rsi, get_sandbox_token, get_sandbox_trigger, get_sma, get_ema, get_strategy, get_t_token, get_tpsl, new_buy, new_margin
from utils.helpers import calculate_profit, format_date
from orders.orders import cancel_existing_order, check_orders, place_order
from log.logger import setup_logger
from utils.helpers import cast_money, create_df
from utils.methods import get_current_price, get_historic_candles, get_instrument_from_portfolio_by_ticker
from tinkoff.invest import Client, CandleInterval
from datetime import datetime, timedelta


from signals.alligator_signal import calculate_alligator_strategy
from signals.bollinger_signal import calculate_bollinger_strategy
from signals.gpt_signal import calculate_gpt_strategy
from signals.lstm_signal import calculate_lstm_strategy
from signals.macd_signal import calculate_macd_strategy
from signals.rsi_signal import calculate_rsi, check_rsi_signal
from signals.sma_signal import calculate_sma_strategy
from signals.ema_signal import calculate_ema_strategy

logger = setup_logger(__name__)

def strategy_run(chat_id):

    token = None
    sandbox_method = False

    sandbox_trigger = get_sandbox_trigger(chat_id)

    if sandbox_trigger:
        token = get_sandbox_token(chat_id)
        sandbox_method = True

    else:
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
            ema = None
            alligator = None  
            gpt = None
            lstm = None
            bollinger = None
            macd = None
            time = None
            auto_market = None
            quantity = None
            joint = None

            strategy_data = get_strategy()

            for row in strategy_data:

                tpsl = row[2]
                rsi = row[3]
                sma = row[4]
                ema = row[5]
                alligator = row[6]  # Получаем значение для Аллигатора
                gpt = row[7]
                lstm = row[8]
                bollinger = row[9]
                macd = row[10]
                time = row[11]
                auto_market = row[12]
                quantity = row[13]
                joint = row[14]

            for ticker in tickers:

                print(ticker[0])

                current_profit = None

                rsi_signal = None
                tpsl_signal = None
                sma_signal = None
                ema_signal = None
                alligator_signal = None  # Добавляем переменную для сигнала Аллигатора
                gpt_signal = None
                lstm_signal = None
                bollinger_signal = None
                macd_signal = None

                figi = db_get_figi(chat_id, ticker[0])

                # Смотрим, есть ли актив в портфеле
                position = get_instrument_from_portfolio_by_ticker(token, figi, ticker[0], sandbox_method)

                if position is not None:

                    average_position_price = position['average_position_price']
                    #current_price_one = position['current_price_one']

                    with Client(token) as client:
                        current_price_sell, _ = get_current_price(figi, client, 'fast')

                    brokerFee = 0.3

                    current_profit = calculate_profit(average_position_price, cast_money(current_price_sell), brokerFee)

                else:

                    current_profit = 0


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
                        logger.info("NOT enough candles for the RSI signal")
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
                        logger.info(f"NOT enough candles for the SMA signal {ticker[0]}")
                        print("MINIMUM")

                    else:
                        # Расчет SMA
                        sma_signal = calculate_sma_strategy(candles, fastLength, slowLength, current_profit)

                
                # Проверяем sma
                if ema == 1:

                    fastLength = None
                    slowLength = None

                    ema_data = get_ema(chat_id)

                    for row in ema_data:

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
                        logger.info(f"NOT enough candles for the EMA signal {ticker[0]}")
                        print("MINIMUM")

                    else:
                        # Расчет EMA
                        ema_signal = calculate_ema_strategy(candles, fastLength, slowLength, current_profit)


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
                        logger.info("NOT enough candles for the Alligator signal")
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

                if gpt == 1:

                    gpt_text = None

                    gpt_data = get_gpt(chat_id)

                    for row in gpt_data:
                        gpt_text = row[2]

                    gpt_signal = calculate_gpt_strategy(gpt_text, current_profit, ticker[0])

                if lstm == 1:

                    start_time = None
                    candle_interval = None
                    time = int(time)

                    CANDLE_CONSTANT = 60
                    
                    start_time = datetime.now() - timedelta(minutes=time+CANDLE_CONSTANT)
                    candle_interval = CandleInterval.CANDLE_INTERVAL_1_MIN
                    end_time = datetime.now()

                    # Получение свечей за указанный период
                    candles = get_historic_candles(figi, start_time, end_time, candle_interval)

                    # if len(create_df(candles.candles)["close"].values) < time+CANDLE_CONSTANT:
                    #     logger.info("NOT enough candles for the SMA signal")
                    #     print("MINIMUM")
                    
                    # else:
                    # Расчет LSTM
                    lstm_signal = calculate_lstm_strategy(candles, figi, current_profit)

                if bollinger == 1:

                    bollinger_period = None
                    bollinger_std = None
                    type_ma = None

                    bollinger_data = get_bollinger(chat_id)

                    for row in bollinger_data:
                        bollinger_period = row[2]
                        bollinger_std = row[3]
                        type_ma = row[4]

                    
                    start_time = None
                    candle_interval = None
                    time = int(time)

                    CANDLE_CONSTANT = 1
                    
                    start_time = datetime.now() - timedelta(minutes=bollinger_period+CANDLE_CONSTANT)
                    candle_interval = CandleInterval.CANDLE_INTERVAL_1_MIN
                    end_time = datetime.now()

                    # Получение свечей за указанный период
                    candles = get_historic_candles(figi, start_time, end_time, candle_interval)

                    if len(create_df(candles.candles)["close"].values) < bollinger_period+CANDLE_CONSTANT:
                        logger.info("NOT enough candles for the Bollinger signal")
                        print("MINIMUM")

                    else:
                        # Расчет Bollinger
                        bollinger_signal = calculate_bollinger_strategy(candles, bollinger_period, bollinger_std, type_ma, current_profit)

                
                if macd == 1:

                    macd_fast = None
                    macd_slow = None
                    macd_signal_length = None

                    macd_data = get_macd(chat_id)

                    for row in macd_data:

                        macd_fast = row[2]
                        macd_slow = row[3]
                        macd_signal_length = row[4]

                    
                    start_time = None
                    candle_interval = None
                    time = int(time)

                    CANDLE_CONSTANT = 1
                    
                    start_time = datetime.now() - timedelta(minutes=max(macd_fast, macd_slow, macd_signal_length)+CANDLE_CONSTANT)
                    candle_interval = CandleInterval.CANDLE_INTERVAL_1_MIN

                    end_time = datetime.now()

                    # Получение свечей за указанный период
                    candles = get_historic_candles(figi, start_time, end_time, candle_interval)

                    if len(create_df(candles.candles)["high"].values) < max(macd_fast, macd_slow, macd_signal_length)+CANDLE_CONSTANT:
                        logger.info("NOT enough candles for the MACD signal")
                        print("MINIMUM")

                    else:

                        # Расчет MACD
                        macd_signal = calculate_macd_strategy(candles, macd_fast, macd_slow, macd_signal_length, current_profit)


                buy_signals = [
                    rsi_signal == "buy",
                    sma_signal == "buy",
                    ema_signal == "buy",
                    alligator_signal == "buy",
                    tpsl_signal == "buy",
                    gpt_signal == "buy",
                    lstm_signal == "buy",
                    bollinger_signal == "buy",
                    macd_signal == "buy"
                ]
                sell_signals = [
                    rsi_signal == "sell",
                    sma_signal == "sell",
                    ema_signal == "sell",
                    alligator_signal == "sell",
                    tpsl_signal == "sell",
                    gpt_signal == "sell",
                    lstm_signal == "sell",
                    bollinger_signal == "sell",
                    macd_signal == "sell"
                ]

                # Логика для объединения сигналов
                buy_condition = all(buy_signals) if joint else any(buy_signals)
                sell_condition = all(sell_signals) if joint else any(sell_signals)

                signal_text = ""

                if buy_condition:
                    if rsi_signal == "buy": signal_text += "RSI "
                    if sma_signal == "buy": signal_text += "SMA "
                    if ema_signal == "buy": signal_text += "EMA "
                    if alligator_signal == "buy": signal_text += "Alligator "
                    if tpsl_signal == "buy": signal_text += "TPSL "
                    if gpt_signal == "buy": signal_text += "GPT "
                    if lstm_signal == "buy": signal_text += "LSTM "
                    if bollinger_signal == "buy": signal_text += "Bollinger "
                    if macd_signal == "buy": signal_text += "MACD "

                    if auto_market:
                        # Автоматическая покупка
                        cancel_existing_order(token, figi, sandbox_method)
                        place_order(token, figi, quantity, 'buy', sandbox_method, ticker[0], 0, signal_text, chat_id)
                        check_orders(token, chat_id, sandbox_method)
                    else:
                        # Рекомендация на покупку
                        logger.info(f"Recommended to purchase {ticker[0]} on the signal {signal_text}")
                        bot.send_message(chat_id, f"Рекомендуется покупка {ticker[0]} по сигналу {signal_text}")

                elif sell_condition:
                    if rsi_signal == "sell": signal_text += "RSI "
                    if sma_signal == "sell": signal_text += "SMA "
                    if ema_signal == "sell": signal_text += "EMA "
                    if alligator_signal == "sell": signal_text += "Alligator "
                    if tpsl_signal == "sell":
                        signal_text += "TPSL "
                    if gpt_signal == "sell": signal_text += "GPT "
                    if lstm_signal == "sell": signal_text += "LSTM "
                    if bollinger_signal == "sell": signal_text += "Bollinger "
                    if macd_signal == "sell": signal_text += "MACD "

                    if auto_market:
                        # Автоматическая продажа
                        # Отмена заявки по бумаге, если она существует
                        cancel_existing_order(token, figi, sandbox_method)
                        # Размещение заявки
                        place_order(token, figi, quantity, 'sell', sandbox_method, ticker[0], round(current_profit, 2), signal_text, chat_id)
                        # Проверка заявок
                        check_orders(token, chat_id, sandbox_method)
                    else:
                        # Рекомендация на продажу
                        logger.info(f"Recommended to sell {ticker[0]} on the signal {signal_text}")
                        bot.send_message(chat_id, f"Рекомендуется продажа {ticker[0]} по сигналу {signal_text}")


                    # elif rsi_signal == "hold" or sma_signal == "hold" or alligator_signal == "hold" or tpsl_signal == "hold":
                    #     signal_text = ""
                    #     if rsi_signal == "hold":
                    #         signal_text += "RSI "
                    #     if sma_signal == "hold":
                    #         signal_text += "SMA "
                    #     if alligator_signal == "hold":
                    #         signal_text += "Alligator "
                    #     if tpsl_signal == "hold":
                    #         signal_text += "TPSL "
                    #     bot.send_message(chat_id, f"Держим {ticker[0]} по сигналу {signal_text}")
