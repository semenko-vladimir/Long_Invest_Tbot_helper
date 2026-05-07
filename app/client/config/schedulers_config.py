from app.client.log.logger import setup_logger
from app.client.utils.methods import get_info_by_ticker
from app.client.store.store import market_scheduler
from app.client.bot.bot import bot
from datetime import datetime, timedelta
from tinkoff.invest import CandleInterval
from dotenv import load_dotenv
import os
from app.client.config import background_schedulers_enabled

logger = setup_logger(__name__)

# Функция для получения токенов из переменных окружения
def get_tokens():
    """
    Получает токены из переменных окружения.
    
    Returns:
        dict: Словарь с токенами
    """
    load_dotenv()
    return {
        "token": os.getenv('TOKEN'),
        "sandbox_token": os.getenv('SANDBOX_TOKEN')
    }


def configure_market_scheduler():
    """
    Настраивает планировщики для уведомлений о падениях и обновлениях рынка.

    Функция получает конфигурационные данные через API-клиент и настраивает 
    планировщики для отправки уведомлений о падениях и обновлениях рынка.
    Если активированы обновления, и нет активных инструментов, уведомление 
    об этом отправляется пользователю. 

    - Если включены обновления о падениях рынка, настраивается соответствующий 
      планировщик.
    - Если включены обновления рынка, настраивается соответствующий планировщик.
    """
    global market_scheduler
    
    try:
        from app.client.api.config_client import ConfigApiClient
        from app.client.api.instruments_client import InstrumentsApiClient

        config_client = ConfigApiClient()
        instruments_client = InstrumentsApiClient()

        # Получаем конфигурацию через API-клиент
        try:
            config_data = config_client.get_config()
        except Exception as e:
            logger.error(f"Failed to get configuration: {str(e)}")
            return
        
        if not config_data:
            logger.error("Configuration data not found")
            return
        
        # Получаем настройки уведомлений
        collapse_updates = config_data.get('collapse_updates', False)
        collapse_updates_time = config_data.get('collapse_updates_time', '60')
        market_updates = config_data.get('market_updates', False)
        market_updates_time = config_data.get('market_updates_time', '60')
        
        # Преобразуем строковые значения времени в числа
        try:
            collapse_updates_time = int(collapse_updates_time)
        except (ValueError, TypeError):
            collapse_updates_time = 60
            
        try:
            market_updates_time = int(market_updates_time)
        except (ValueError, TypeError):
            market_updates_time = 60
        
        # Получаем список всех инструментов
        try:
            instruments = instruments_client.get_all_instruments()
        except Exception as e:
            logger.error(f"Failed to get instruments: {str(e)}")
            return
        
        if not instruments:
            logger.info('Нет активных инструментов для настройки уведомлений')
            return
        
        # Получаем chat_id из переменных окружения для отправки уведомлений
        load_dotenv()
        chat_id = os.getenv('CHAT_ID')
        
        if not chat_id:
            logger.error("Chat ID is not available in environment variables")
            return
        
        # Если планировщик уже существует, останавливаем его
        if market_scheduler:
            market_scheduler.shutdown()
        
        # Создаем новый планировщик
        if collapse_updates or market_updates:
            from apscheduler.schedulers.background import BackgroundScheduler

            market_scheduler = BackgroundScheduler()
            market_scheduler.start()
            
            # Настраиваем планировщики в зависимости от настроек
            if collapse_updates:
                setup_market_jobs(market_scheduler, instruments, collapse_updates_time, chat_id, "Падения рынка")
            
            if market_updates:
                setup_market_jobs(market_scheduler, instruments, market_updates_time, chat_id, "Обновления рынка")
            
            logger.info("Планировщик уведомлений о рынке успешно настроен")
    
    except Exception as e:
        logger.error(f"Error configuring market scheduler: {str(e)}")


def setup_market_jobs(scheduler, instruments, update_time, chat_id, update_type):
    """
    Настраивает задачи для планировщика уведомлений о рынке.
    
    Args:
        scheduler: Планировщик задач
        instruments: Список инструментов, по которым нужно отправлять уведомления
        update_time: Интервал времени, с которым нужно отправлять уведомления
        chat_id: ID чата, в который нужно отправить уведомления
        update_type: Тип уведомления ('Падения рынка' или 'Обновления рынка')
    """
    try:
        from app.client.handlers.notifications.send import send_price_change_notification

        for instrument in instruments:
            ticker = instrument.get('ticker')
            figi = instrument.get('figi')
            
            # Получаем дополнительную информацию об инструменте
            info = get_info_by_ticker(ticker)
            name = info['name'].values[0:1][0]
            type_of = info['type'].values[0:1][0]
            
            # Вычисляем временной интервал
            start_time, candle_interval = calculate_start_time_and_interval(update_time)
            end_time = datetime.now()
            
            logger.info(f"{update_type} уведомления добавлены для {ticker}")
            
            # Добавляем задачу в планировщик
            scheduler.add_job(
                send_price_change_notification, 
                'interval', 
                minutes=update_time, 
                args=(figi, start_time, end_time, candle_interval, bot, chat_id, name, type_of, ticker)
            )
    
    except Exception as e:
        logger.error(f"Error setting up market jobs: {str(e)}")


def calculate_start_time_and_interval(update_time):
    """
    Вычисляет начальное время и интервал свечи для выбранного периода.
    
    Args:
        update_time: Интервал времени, с которым нужно отправлять уведомления
        
    Returns:
        tuple: (start_time, candle_interval)
    """
    start_time = datetime.now() - timedelta(minutes=update_time if update_time <= 60 else 10)
    candle_interval = CandleInterval.CANDLE_INTERVAL_1_MIN
    return start_time, candle_interval


def configure_strategy_scheduler():
    """
    Compatibility no-op for the legacy strategy scheduler.

    Strategy automation is not part of the active investor v1 runtime.
    """
    load_dotenv()
    if os.getenv("ENABLE_STRATEGY_SCHEDULER", "false").strip().lower() in {"1", "true", "yes", "on"}:
        logger.warning(
            "ENABLE_STRATEGY_SCHEDULER is ignored: legacy strategy scheduling is disabled for investor v1."
        )
    else:
        logger.info("Legacy strategy scheduling is disabled for investor v1.")


def configure_schedulers():
    """
    Настраивает все планировщики.
    
    Собирает информацию о всех чатах, настраивает планировщик для отправки 
    уведомлений о падениях рынка и для запуска стратегий.
    """
    if not background_schedulers_enabled():
        logger.info("Фоновые планировщики отключены для sandbox-first v1")
        return

    configure_market_scheduler()
    configure_strategy_scheduler()
