from datetime import datetime, timedelta
from app.client.api.instruments_client import InstrumentsApiClient
from app.client.api.signals_client import SignalsApiClient
from app.client.bot.bot import bot
from telebot import types
from app.client.graphics.sma_graph import plot_sma
from app.client.log.logger import setup_logger
from app.client.signals.sma_signal import calculate_sma_strategy
from app.client.store.store import mls_interval
from tinkoff.invest import CandleInterval, Client
from dotenv import load_dotenv
import os
from app.client.handlers.utils.message_utils import send_or_edit_message

from app.client.utils.helpers import calculate_profit, cast_money, create_df
from app.client.utils.methods import get_current_price, get_historic_candles, get_instrument_from_portfolio_by_ticker

instruments_client = InstrumentsApiClient()
signals_client = SignalsApiClient()

logger = setup_logger(__name__)

load_dotenv()
BROKER_FEE = os.getenv('BROKER_FEE')

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


@bot.callback_query_handler(func=lambda call: call.data == 'calc_mls_sma')
def mls_sma_handler(call):
    """
    Обработчик для расчета SMA сигнала.
    
    Отображает меню с выбором интервала времени.
    """
    chat_id = call.message.chat.id
    
    try:
        # Получаем список всех инструментов
        instruments = instruments_client.get_all_instruments()
        
        if not instruments:
            send_or_edit_message(chat_id, '❌ *Ошибка*\n\nУ вас нет активных инструментов')
        else:
            inline_keyboard = types.InlineKeyboardMarkup()
            buttons = [
                types.InlineKeyboardButton(text='📅 6 месяцев', callback_data='sma_interval_6'),
                types.InlineKeyboardButton(text='📆 1 год', callback_data='sma_interval_12')
            ]
            
            for button in buttons:
                inline_keyboard.add(button)
            
            send_or_edit_message(
                chat_id, 
                '📈 *SMA График*\n\nВыберите интервал времени:', 
                reply_markup=inline_keyboard
            )
    
    except Exception as e:
        send_or_edit_message(chat_id, f"❌ *Ошибка при получении списка инструментов*\n\n`{str(e)}`")


@bot.callback_query_handler(func=lambda call: call.data.startswith('sma_interval_'))
def interval_handler(call):
    """
    Обработчик для выбора интервала времени.
    
    Сохраняет выбранный интервал и отображает меню с выбором инструмента.
    """
    global mls_interval
    chat_id = call.message.chat.id
    interval = call.data.replace('sma_interval_', '')
    
    try:
        mls_interval = interval
        interval_text = "6 месяцев" if interval == '6' else "1 год"
        
        # Получаем список всех инструментов
        instruments = instruments_client.get_all_instruments()
        
        if not instruments:
            send_or_edit_message(chat_id, '❌ *Ошибка*\n\nУ вас нет активных инструментов')
        else:
            inline_keyboard = types.InlineKeyboardMarkup()
            
            for instrument in instruments:
                ticker = instrument.get('ticker')
                button = types.InlineKeyboardButton(text=ticker, callback_data=f'mls_sma_ticker_{ticker}')
                inline_keyboard.add(button)
            
            send_or_edit_message(
                chat_id, 
                f'📈 *SMA График*\n\nВыбран интервал: `{interval_text}`\n\nВыберите инструмент для построения графика:', 
                reply_markup=inline_keyboard
            )
    
    except Exception as e:
        send_or_edit_message(chat_id, f"❌ *Ошибка при выборе интервала*\n\n`{str(e)}`")


@bot.callback_query_handler(func=lambda call: call.data.startswith('mls_sma_ticker_'))
def calculate_mls_sma(call):
    """
    Обработчик для расчета SMA сигнала для выбранного инструмента.
    
    Получает данные о свечах, рассчитывает SMA сигнал и отображает график.
    """
    chat_id = call.message.chat.id
    ticker = call.data.replace('mls_sma_ticker_', '')
    
    try:
        send_or_edit_message(chat_id, f"⏳ *Обработка запроса*\n\nРассчитываем SMA для тикера `{ticker}`...")
        
        # Получаем токен из переменных окружения
        tokens = get_tokens()
        token = tokens["token"]
        
        if not token:
            send_or_edit_message(chat_id, "❌ *Ошибка*\n\nТокен не найден. Пожалуйста, проверьте настройки.")
            return
        
        # Получаем настройки SMA
        sma_settings = signals_client.get_signal_sma()
        
        if not sma_settings:
            send_or_edit_message(chat_id, "❌ *Ошибка*\n\nНастройки SMA не найдены. Пожалуйста, настройте сигнал SMA.")
            return
        
        fastLength = sma_settings.get('fastLength')
        slowLength = sma_settings.get('slowLength')
        
        # Получаем FIGI инструмента
        instrument = instruments_client.get_instrument_by_ticker(ticker)
        if not instrument:
            send_or_edit_message(chat_id, f"❌ *Ошибка*\n\nИнструмент {ticker} не найден.")
            return
        
        figi = instrument.get('figi')
        
        # Получаем текущую прибыль
        current_profit = 0
        
        # Смотрим, есть ли актив в портфеле
        position = get_instrument_from_portfolio_by_ticker(token, figi, ticker, False)
        
        if position is not None:
            average_position_price = position['average_position_price']
            
            with Client(token) as client:
                current_price_sell, _ = get_current_price(figi, client, 'fast')
            
            current_profit = calculate_profit(average_position_price, cast_money(current_price_sell), BROKER_FEE)
        
        # Определяем временной интервал
        if mls_interval == '6':
            start_time = datetime.now() - timedelta(days=183)
        elif mls_interval == '12':
            start_time = datetime.now() - timedelta(days=365)
        else:
            send_or_edit_message(chat_id, "❌ *Ошибка*\n\nНекорректный интервал.")
            return
        
        candle_interval = CandleInterval.CANDLE_INTERVAL_DAY
        end_time = datetime.now()
        
        # Получаем исторические свечи
        candles = get_historic_candles(figi, start_time, end_time, candle_interval)
        
        if not candles or not candles.candles:
            send_or_edit_message(chat_id, "❌ *Ошибка*\n\nНе удалось получить исторические данные.")
            return
        
        # Проверяем, достаточно ли свечей для расчета
        df = create_df(candles.candles)
        if len(df["close"].values) < slowLength + 1:
            send_or_edit_message(chat_id, "❌ *Ошибка*\n\nНедостаточно свечей для расчета сигнала SMA.")
            return
        
        # Рассчитываем сигнал SMA
        sma_signal = calculate_sma_strategy(candles, fastLength, slowLength, current_profit)
        
        if sma_signal != 'hold':
            emoji = "🟢 BUY" if sma_signal == 'buy' else "🔴 SELL"
            send_or_edit_message(chat_id, f'📊 *SMA сигнал для {ticker}*: {emoji}')
        
        # Строим график SMA
        plot_sma(chat_id, df)
    
    except Exception as e:
        send_or_edit_message(chat_id, f"❌ *Ошибка при расчете SMA сигнала*\n\n`{str(e)}`")
