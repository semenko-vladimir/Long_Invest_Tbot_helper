from app.client.api.config_client import ConfigApiClient
from app.client.api.instruments_client import InstrumentsApiClient
from app.client.api.signals_client import SignalsApiClient
from app.client.api.strategy_client import StrategyApiClient
from app.client.bot.bot import bot
from app.client.utils.helpers import calculate_profit, format_date, cast_money, create_df
from app.client.orders.orders import cancel_existing_order, check_orders, place_order
from app.client.log.logger import setup_logger
from app.client.utils.methods import get_current_price, get_historic_candles, get_instrument_from_portfolio_by_ticker
from tinkoff.invest import Client, CandleInterval
from datetime import datetime, timedelta
from dotenv import load_dotenv
import os

from app.client.signals.alligator_signal import calculate_alligator_strategy
from app.client.signals.bollinger_signal import calculate_bollinger_strategy
from app.client.signals.gpt_signal import calculate_gpt_strategy
from app.client.signals.lstm_signal import calculate_lstm_strategy
from app.client.signals.macd_signal import calculate_macd_strategy
from app.client.signals.rsi_signal import calculate_rsi, check_rsi_signal
from app.client.signals.sma_signal import calculate_sma_strategy
from app.client.signals.ema_signal import calculate_ema_strategy

signals_client = SignalsApiClient()
strategy_client = StrategyApiClient()
instruments_client = InstrumentsApiClient()
config_client = ConfigApiClient()

logger = setup_logger(__name__)

load_dotenv()
BROKER_FEE = os.getenv('BROKER_FEE')

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

def get_token_and_sandbox_method():
    """
    Получает токен и флаг использования песочницы.
    
    Returns:
        tuple: (token, sandbox_method)
    """
    tokens = get_tokens()
    
    try:
        sandbox_trigger = config_client.get_sandbox_trigger()
        
        if sandbox_trigger:
            return tokens["sandbox_token"], True
        else:
            return tokens["token"], False
    except Exception as e:
        logger.error(f"Error getting sandbox_trigger: {str(e)}, using default token")
        return tokens["token"], False

def get_current_profit(token, figi, ticker, sandbox_method):
    """
    Рассчитывает текущую прибыль для инструмента.
    
    Args:
        token: Токен API
        figi: FIGI инструмента
        ticker: Тикер инструмента
        sandbox_method: Флаг использования песочницы
        
    Returns:
        float: Текущая прибыль
    """
    position = get_instrument_from_portfolio_by_ticker(token, figi, ticker, sandbox_method)
    
    if position is not None:
        average_position_price = position['average_position_price']
        
        with Client(token) as client:
            current_price_sell, _ = get_current_price(figi, client, 'fast')
        
        return calculate_profit(average_position_price, cast_money(current_price_sell), BROKER_FEE)
    
    return 0

def get_candles_for_signal(figi, signal_type, settings, strategy_time):
    """
    Получает свечи для указанного сигнала.
    
    Args:
        figi: FIGI инструмента
        signal_type: Тип сигнала
        settings: Настройки сигнала
        strategy_time: Время стратегии
        
    Returns:
        tuple: (candles, success)
    """
    token, sandbox_method = get_token_and_sandbox_method()
    
    # Определяем интервал свечей в зависимости от типа сигнала
    interval = CandleInterval.CANDLE_INTERVAL_1_MIN
    
    # Определяем количество свечей в зависимости от типа сигнала
    if signal_type == 'rsi':
        candle_count = settings['period'] * 3
    elif signal_type == 'sma' or signal_type == 'ema':
        candle_count = max(settings['fastLength'], settings['slowLength']) * 3
    elif signal_type == 'alligator':
        candle_count = max(settings['jaw_period'], settings['teeth_period'], settings['lips_period']) * 3
    elif signal_type == 'lstm':
        candle_count = 100  # Для LSTM нужно больше данных
    elif signal_type == 'bollinger':
        candle_count = settings['period'] * 3
    elif signal_type == 'macd':
        candle_count = max(settings['fastLength'], settings['slowLength'], settings['signalLength']) * 3
    else:
        candle_count = 100  # По умолчанию
    
    # Определяем временной интервал для получения свечей
    end_time = datetime.now()
    start_time = end_time - timedelta(minutes=candle_count)
    
    # Получаем свечи
    with Client(token) as client:
        market_data = client.market_data
        try:
            data = market_data.get_candles(
                figi=figi,
                from_=start_time,
                to=end_time,
                interval=interval
            )
            return data, True
        except Exception as e:
            logger.error(f"Error getting candles for {figi}: {str(e)}")
            return None, False

def get_signal_settings(signal_type):
    """
    Получает настройки для указанного типа сигнала.
    
    Args:
        signal_type: Тип сигнала
        
    Returns:
        dict: Настройки сигнала или None, если настройки не найдены
    """
    try:
        if signal_type == 'tpsl':
            settings = signals_client.get_signal_tpsl()
            if not settings:
                return None
            return {
                'takeProfit': settings.get('take_profit'),
                'stopLoss': settings.get('stop_loss')
            }
        
        elif signal_type == 'rsi':
            settings = signals_client.get_signal_rsi()
            if not settings:
                return None
            return {
                'period': settings.get('period'),
                'highLevel': settings.get('hightLevel'),
                'lowLevel': settings.get('lowLevel')
            }
        
        elif signal_type == 'sma':
            settings = signals_client.get_signal_sma()
            if not settings:
                return None
            return {
                'fastLength': settings.get('fastLength'),
                'slowLength': settings.get('slowLength')
            }
        
        elif signal_type == 'ema':
            settings = signals_client.get_signal_ema()
            if not settings:
                return None
            return {
                'fastLength': settings.get('fastLength'),
                'slowLength': settings.get('slowLength')
            }
        
        elif signal_type == 'alligator':
            settings = signals_client.get_signal_alligator()
            if not settings:
                return None
            return {
                'jaw_period': settings.get('jaw_period'),
                'jaw_shift': settings.get('jaw_shift'),
                'teeth_period': settings.get('teeth_period'),
                'teeth_shift': settings.get('teeth_shift'),
                'lips_period': settings.get('lips_period'),
                'lips_shift': settings.get('lips_shift')
            }
        
        elif signal_type == 'gpt':
            settings = signals_client.get_signal_gpt()
            if not settings:
                return None
            return {
                'text': settings.get('text')
            }
        
        elif signal_type == 'bollinger':
            settings = signals_client.get_signal_bollinger()
            if not settings:
                return None
            return {
                'period': settings.get('period'),
                'deviation': settings.get('deviation'),
                'type_ma': settings.get('type_ma')
            }
        
        elif signal_type == 'macd':
            settings = signals_client.get_signal_macd()
            if not settings:
                return None
            return {
                'fastLength': settings.get('fastLength'),
                'slowLength': settings.get('slowLength'),
                'signalLength': settings.get('signalLength')
            }
    
    except Exception as e:
        logger.error(f"Error getting settings for signal {signal_type}: {str(e)}")
    
    return None

def process_signal(signal_type, token, figi, ticker, sandbox_method, strategy_time):
    """
    Обрабатывает сигнал указанного типа.
    
    Args:
        signal_type: Тип сигнала
        token: Токен API
        figi: FIGI инструмента
        ticker: Тикер инструмента
        sandbox_method: Флаг использования песочницы
        strategy_time: Время стратегии
        
    Returns:
        str: Сигнал (buy, sell, hold) или None, если сигнал не может быть обработан
    """
    current_profit = get_current_profit(token, figi, ticker, sandbox_method)
    
    if signal_type == 'tpsl':
        settings = get_signal_settings('tpsl')
        if not settings:
            return None
        
        if current_profit > settings['takeProfit'] or current_profit < -settings['stopLoss']:
            return "sell"
        else:
            return "hold"
    
    if signal_type == 'gpt':
        settings = get_signal_settings('gpt')
        if not settings:
            return None
        
        return calculate_gpt_strategy(settings['text'], current_profit, ticker)
    
    # Для остальных сигналов нужны свечи
    settings = get_signal_settings(signal_type)
    if not settings:
        return None
    
    candles, success = get_candles_for_signal(figi, signal_type, settings, strategy_time)
    if not success:
        return None
    
    if signal_type == 'rsi':
        rsi_value = calculate_rsi(candles, settings['period'])
        if rsi_value is None:
            return None
        return check_rsi_signal(rsi_value, settings['lowLevel'], settings['highLevel'], current_profit)
    
    elif signal_type == 'sma':
        return calculate_sma_strategy(candles, settings['fastLength'], settings['slowLength'], current_profit)
    
    elif signal_type == 'ema':
        return calculate_ema_strategy(candles, settings['fastLength'], settings['slowLength'], current_profit)
    
    elif signal_type == 'alligator':
        return calculate_alligator_strategy(
            candles, 
            settings['jaw_period'], 
            settings['jaw_shift'], 
            settings['teeth_period'], 
            settings['teeth_shift'],
            settings['lips_period'], 
            settings['lips_shift'], 
            current_profit
        )
    
    elif signal_type == 'lstm':
        return calculate_lstm_strategy(candles, figi, current_profit)
    
    elif signal_type == 'bollinger':
        return calculate_bollinger_strategy(
            candles, 
            settings['period'], 
            settings['deviation'], 
            settings['type_ma'], 
            current_profit
        )
    
    elif signal_type == 'macd':
        return calculate_macd_strategy(
            candles, 
            settings['fastLength'], 
            settings['slowLength'], 
            settings['signalLength'], 
            current_profit
        )
    
    return None

def get_strategy_config():
    """
    Получает конфигурацию стратегии.
    
    Returns:
        dict: Конфигурация стратегии или None, если конфигурация не найдена
    """
    try:
        # Получаем настройки сигналов стратегии
        signals = strategy_client.get_strategy_signals()
        if not signals:
            logger.error("Strategy signals not found")
            return None
        
        # Получаем общие настройки стратегии
        settings = strategy_client.get_strategy_settings()
        if not settings:
            logger.error("Strategy settings not found")
            return None
        
        return {
            'tpsl_trigger': signals.get('tpls_trigger', False),
            'rsi_trigger': signals.get('rsi_trigger', False),
            'sma_trigger': signals.get('sma_trigger', False),
            'ema_trigger': signals.get('ema_trigger', False),
            'alligator_trigger': signals.get('alligator_trigger', False),
            'gpt_trigger': signals.get('gpt_trigger', False),
            'lstm_trigger': signals.get('lstm_trigger', False),
            'bollinger_trigger': signals.get('bollinger_trigger', False),
            'macd_trigger': signals.get('macd_trigger', False),
            'joint': signals.get('joint', False),
            'time': settings.get('time', '5'),
            'auto_market': settings.get('auto_market', False),
            'quantity': settings.get('quantity', 1)
        }
    
    except Exception as e:
        logger.error(f"Error getting strategy configuration: {str(e)}")
        return None

def process_ticker(ticker_name, strategy_config, token, sandbox_method, chat_id):
    """
    Обрабатывает один тикер согласно стратегии.
    
    Args:
        ticker_name: Имя тикера
        strategy_config: Конфигурация стратегии
        token: Токен API
        sandbox_method: Флаг использования песочницы
        chat_id: ID чата
    """
    logger.info(f"Processing ticker: {ticker_name}")
    
    try:
        # Получаем FIGI инструмента
        instrument = instruments_client.get_instrument_by_ticker(ticker_name)
        if not instrument:
            logger.error(f"Instrument {ticker_name} not found")
            return
        
        figi = instrument.get('figi')
        
        # Инициализируем сигналы
        signals = {}
        signal_types = [
            'rsi', 'sma', 'ema', 'alligator', 'tpsl', 
            'gpt', 'lstm', 'bollinger', 'macd'
        ]
        
        # Получаем сигналы для каждого типа
        for signal_type in signal_types:
            if strategy_config.get(f'{signal_type}_trigger', False):
                signals[signal_type] = process_signal(
                    signal_type, token, figi, ticker_name, 
                    sandbox_method, strategy_config['time']
                )
        
        # Формируем списки сигналов на покупку и продажу
        buy_signals = [signals.get(s) == "buy" for s in signal_types if signals.get(s) is not None]
        sell_signals = [signals.get(s) == "sell" for s in signal_types if signals.get(s) is not None]
        
        # Проверяем условия для покупки/продажи
        buy_condition = all(buy_signals) if strategy_config['joint'] else any(buy_signals)
        sell_condition = all(sell_signals) if strategy_config['joint'] else any(sell_signals)
        
        # Формируем текст сигнала
        signal_text = ""
        
        if buy_condition:
            for s in signal_types:
                if signals.get(s) == "buy":
                    signal_text += f"{s.upper()} "
            
            if strategy_config['auto_market']:
                # Автоматическая покупка
                cancel_existing_order(token, figi, sandbox_method)
                place_order(
                    token, figi, strategy_config['quantity'], 'buy', 
                    sandbox_method, ticker_name, 0, signal_text
                )
                check_orders(token, chat_id, sandbox_method)
            else:
                # Рекомендация на покупку
                logger.info(f"Recommended to purchase {ticker_name} on the signal {signal_text}")
                bot.send_message(chat_id, f"Рекомендуется покупка {ticker_name} по сигналу {signal_text}")
        
        elif sell_condition:
            for s in signal_types:
                if signals.get(s) == "sell":
                    signal_text += f"{s.upper()} "
            
            current_profit = get_current_profit(token, figi, ticker_name, sandbox_method)
            
            if strategy_config['auto_market']:
                # Автоматическая продажа
                cancel_existing_order(token, figi, sandbox_method)
                place_order(
                    token, figi, strategy_config['quantity'], 'sell', 
                    sandbox_method, ticker_name, round(current_profit, 2), signal_text
                )
                check_orders(token, chat_id, sandbox_method)
            else:
                # Рекомендация на продажу
                logger.info(f"Recommended to sell {ticker_name} on the signal {signal_text}")
                bot.send_message(chat_id, f"Рекомендуется продажа {ticker_name} по сигналу {signal_text}")
    
    except Exception as e:
        logger.error(f"Error processing ticker {ticker_name}: {str(e)}")

def strategy_run(chat_id=None):
    """
    Основная функция запуска стратегии.
    
    Args:
        chat_id: ID чата (опционально)
    """
    # Если chat_id не передан, пытаемся получить его из переменных окружения
    if chat_id is None:
        load_dotenv()
        chat_id = os.getenv('CHAT_ID')
    
    if not chat_id:
        logger.error("Chat ID is not available")
        return
    
    # Получаем токен и флаг использования песочницы
    token, sandbox_method = get_token_and_sandbox_method()
    
    if not token:
        logger.error("Token is not available")
        return
    
    try:
        # Получаем список всех инструментов
        instruments = instruments_client.get_all_instruments()
        
        if not instruments:
            bot.send_message(chat_id, 'У вас нет активных инструментов')
            return
        
        # Получаем настройки стратегии
        strategy_config = get_strategy_config()
        
        if not strategy_config:
            logger.error("Strategy settings are not available")
            return
            
        # Проверяем, есть ли активные сигналы
        active_strategies = [
            strategy_config.get('tpsl_trigger', False),
            strategy_config.get('rsi_trigger', False),
            strategy_config.get('sma_trigger', False),
            strategy_config.get('ema_trigger', False),
            strategy_config.get('alligator_trigger', False),
            strategy_config.get('gpt_trigger', False),
            strategy_config.get('lstm_trigger', False),
            strategy_config.get('bollinger_trigger', False),
            strategy_config.get('macd_trigger', False)
        ]
        
        # Если нет активных сигналов, выходим
        if not any(active_strategies):
            logger.info("No active strategies found, skipping strategy run")
            return
        
        # Обрабатываем каждый инструмент
        for instrument in instruments:
            ticker = instrument.get('ticker')
            process_ticker(ticker, strategy_config, token, sandbox_method, chat_id)
    
    except Exception as e:
        logger.error(f"Error running strategy: {str(e)}")
