from db.db import get_all_tickers, get_config, get_strategy
from handlers.notifications.send import send_price_change_notification
from log.logger import setup_logger
from utils.methods import get_info_by_ticker
from store.store import chat_schedulers, strategy_shedulers
from apscheduler.schedulers.background import BackgroundScheduler
from bot.bot import bot
from datetime import datetime, timedelta
from tinkoff.invest import CandleInterval
from strategy.strategy_run import strategy_run

logger = setup_logger(__name__)

def configure_market_scheduler():
    config_data = get_config()
    
    if not config_data:
        return

    for row in config_data:
        chat_id = row[1]
        collapse_updates = row[2]
        collapse_updates_time = row[3]
        market_updates = row[4]
        market_updates_time = row[5]

        if chat_id and chat_id not in chat_schedulers:
            tickers = get_all_tickers(chat_id)
            if not tickers:
                bot.send_message(chat_id, 'У вас нет активных тикеров')
                continue

            if collapse_updates:
                setup_scheduler(chat_id, tickers, collapse_updates_time, send_price_change_notification, "Падения рынка")
            if market_updates:
                setup_scheduler(chat_id, tickers, market_updates_time, send_price_change_notification, "Обновления рынка")


def setup_scheduler(chat_id, tickers, update_time, notification_func, update_type):
    """Настройка планировщика для уведомлений"""
    scheduler = BackgroundScheduler()
    chat_schedulers[chat_id] = scheduler
    scheduler.start()

    for ticker in tickers:
        info = get_info_by_ticker(str(ticker[0]))
        figi = info['figi'].values[0:1][0]
        name = info['name'].values[0:1][0]
        type_of = info['type'].values[0:1][0]
        ticker_symbol = ticker[0]

        start_time, candle_interval = calculate_start_time_and_interval(update_time)
        end_time = datetime.now()

        print(f"{update_type} уведомления добавлены для {ticker_symbol}")
        scheduler.add_job(
            notification_func, 
            'interval', 
            minutes=update_time, 
            args=(figi, start_time, end_time, candle_interval, bot, chat_id, name, type_of, ticker_symbol)
        )


def calculate_start_time_and_interval(update_time):
    """Рассчитывает начальное время и интервал свечей на основе времени обновлений"""
    start_time = datetime.now() - timedelta(minutes=update_time if update_time <= 60 else 10)
    candle_interval = CandleInterval.CANDLE_INTERVAL_1_MIN
    return start_time, candle_interval
    

def configure_strategy_scheduler():
    strategy_data = get_strategy()
    
    for row in strategy_data:
        chat_id = row[1]
        active_strategies = {
            "tpsl": row[2],
            "rsi": row[3],
            "sma": row[4],
            "ema": row[5],
            "alligator": row[6],
            "gpt": row[7],
            "lstm": row[8],
            "bollinger": row[9],
            "macd": row[10],
        }
        time_interval = row[11]

        if not is_any_strategy_active(active_strategies):
            continue
        
        if chat_id and chat_id not in strategy_shedulers:
            setup_strategy_scheduler(chat_id, time_interval)


def is_any_strategy_active(strategies):
    """Проверяет, активна ли хотя бы одна стратегия."""
    return any(strategy == 1 for strategy in strategies.values())


def setup_strategy_scheduler(chat_id, time_interval):
    """Настраивает планировщик для запуска стратегий."""
    scheduler = BackgroundScheduler()
    strategy_shedulers[chat_id] = scheduler
    scheduler.start()

    scheduler.add_job(strategy_run, 'interval', minutes=int(time_interval), args=(chat_id,))
    logger.info(f"The strategy for chat {chat_id} has been added to the scheduler.")

def configure_schedulers():
    configure_market_scheduler()
    configure_strategy_scheduler()
