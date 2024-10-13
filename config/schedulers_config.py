from db.db import get_all_tickers, get_config, get_strategy
from handlers.notifications.send import send_price_change_notification_collapse, send_price_change_notification_market_updates
from log.logger import setup_logger
from utils.methods import get_info_by_ticker
from store.store import chat_schedulers, strategy_shedulers
from apscheduler.schedulers.background import BackgroundScheduler
from bot.bot import bot
from datetime import datetime, timedelta
from tinkoff.invest import CandleInterval
from strategy.strategy_run import strategy_run

logger = setup_logger(__name__)

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
        gpt = row[6]
        lstm = row[7]
        bollinger = row[8]
        macd = row[9]
        time = row[10]
        # autom = row[9]
        # quantity = row[10]

        if tpsl == 0 and rsi == 0 and sma == 0 and alligator == 0 and gpt == 0 and lstm == 0 and bollinger == 0 and macd == 0:
            return
        
        if chat_id not in strategy_shedulers and chat_id is not None:
            scheduler = BackgroundScheduler()
            strategy_shedulers[chat_id] = scheduler
            scheduler.start()

            scheduler = strategy_shedulers[chat_id]

            scheduler.add_job(strategy_run, 'interval', minutes=int(time), args=(chat_id,))
            #print("Стратегия добавлена в планировщик")
            logger.info("The strategy has been added to the scheduler")