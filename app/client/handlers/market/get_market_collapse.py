from datetime import datetime, timedelta
from app.client.api.instruments_client import InstrumentsApiClient
from app.client.bot.bot import bot
from telebot import types
from app.client.utils.methods import get_info_by_ticker, get_price_change_in_current_interval
from tinkoff.invest import CandleInterval
from app.client.handlers.utils.message_utils import send_or_edit_message

instruments_client = InstrumentsApiClient()

# Маппинг интервалов на соответствующие значения
INTERVAL_MAPPING = {
    '10 минут': (timedelta(minutes=10), CandleInterval.CANDLE_INTERVAL_1_MIN),
    'час': (timedelta(hours=1), CandleInterval.CANDLE_INTERVAL_1_MIN),
    'неделя': (timedelta(weeks=1), CandleInterval.CANDLE_INTERVAL_DAY),
    'месяц': (timedelta(days=30), CandleInterval.CANDLE_INTERVAL_WEEK),
    'год': (timedelta(days=365), CandleInterval.CANDLE_INTERVAL_MONTH)
}

# Диапазоны процентов для фильтрации
PERCENT_RANGES = {
    'до 2%': (0, -2),
    'от 2% до 5%': (-2, -5),
    'от 5% до 10%': (-5, -10),
    'от 10% до 20%': (-10, -20),
    'более 20%': (-20, -100),  
    'до 100%': (-0.01, -100)
}


@bot.callback_query_handler(func=lambda call: call.data == 'get_market_collapse')
def get_market_collapse_handler(call):
    """
    Обработчик для получения информации об обвале рынка.
    
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
                types.InlineKeyboardButton(text='10 минут', callback_data='intervalcollapse_10 минут'),
                types.InlineKeyboardButton(text='час', callback_data='intervalcollapse_час'),
                types.InlineKeyboardButton(text='день', callback_data='intervalcollapse_день'),
                types.InlineKeyboardButton(text='неделя', callback_data='intervalcollapse_неделя'),
                types.InlineKeyboardButton(text='месяц', callback_data='intervalcollapse_месяц'),
                types.InlineKeyboardButton(text='год', callback_data='intervalcollapse_год')
            ]
            
            for button in buttons:
                inline_keyboard.add(button)
            
            send_or_edit_message(
                chat_id, 
                '📉 *Обвал рынка*\n\nВыберите интервал времени:', 
                reply_markup=inline_keyboard
            )
    
    except Exception as e:
        send_or_edit_message(chat_id, f"❌ *Ошибка при получении списка инструментов*\n\n`{str(e)}`")


@bot.callback_query_handler(func=lambda call: call.data.startswith('intervalcollapse_'))
def interval_handler(call):
    """
    Обработчик для выбора интервала времени.
    
    Отображает меню с выбором процентного диапазона.
    """
    chat_id = call.message.chat.id
    interval = call.data.replace('intervalcollapse_', '')
    
    try:
        inline_keyboard = types.InlineKeyboardMarkup()
        buttons = [
            types.InlineKeyboardButton(text='до 2%', callback_data=f'percentcollapse_до 2%_{interval}'),
            types.InlineKeyboardButton(text='от 2% до 5%', callback_data=f'percentcollapse_от 2% до 5%_{interval}'),
            types.InlineKeyboardButton(text='от 5% до 10%', callback_data=f'percentcollapse_от 5% до 10%_{interval}'),
            types.InlineKeyboardButton(text='от 10% до 20%', callback_data=f'percentcollapse_от 10% до 20%_{interval}'),
            types.InlineKeyboardButton(text='более 20%', callback_data=f'percentcollapse_более 20%_{interval}'),
            types.InlineKeyboardButton(text='Общий обвал', callback_data=f'percentcollapse_до 100%_{interval}'),
        ]
        
        for button in buttons:
            inline_keyboard.add(button)
        
        send_or_edit_message(
            chat_id, 
            f'📉 *Обвал рынка*\n\nВыбран интервал: `{interval}`\n\nВыберите процентный диапазон:', 
            reply_markup=inline_keyboard
        )
    
    except Exception as e:
        send_or_edit_message(chat_id, f"❌ *Ошибка при выборе интервала*\n\n`{str(e)}`")


@bot.callback_query_handler(func=lambda call: call.data.startswith('percentcollapse_'))
def percent_handler(call):
    """
    Обработчик для выбора процентного диапазона.
    
    Отображает информацию об инструментах, которые упали на выбранный процент за выбранный интервал.
    """
    chat_id = call.message.chat.id
    data = call.data.split('_')
    percent_range = data[1]
    interval = data[2]
    
    try:
        # Отправляем сообщение о начале обработки
        send_or_edit_message(
            chat_id, 
            f"⏳ *Обработка запроса*\n\nПолучаем данные об обвале рынка за интервал `{interval}` с диапазоном `{percent_range}`..."
        )
        
        # Получаем начальное время и интервал свечи
        start_time, candle_interval = get_time_interval(interval)
        if start_time is None:
            send_or_edit_message(chat_id, '❌ *Ошибка*\n\nНекорректный интервал')
            return
        
        # Получаем список всех инструментов
        instruments = instruments_client.get_all_instruments()
        
        # Проверяем каждый инструмент
        found_instruments = False
        for instrument in instruments:
            ticker = instrument.get('ticker')
            figi = instrument.get('figi')
            
            # Получаем дополнительную информацию об инструменте
            info = get_info_by_ticker(ticker)
            name = info['name'].values[0:1][0]
            type_of = info['type'].values[0:1][0]
            
            # Получаем изменение цены за выбранный интервал
            end_time = datetime.now()
            price_change, price_change_percent, max_price, min_price, close_price = get_price_change_in_current_interval(
                figi, start_time, end_time, candle_interval)
            
            # Проверяем изменение цены в зависимости от выбранного процента
            low, high = PERCENT_RANGES[percent_range]
            if high < price_change_percent <= low:
                found_instruments = True
                message_text = (
                    f'📉 *Информация об обвале инструмента*\n\n'
                    f'📌 Название: `{name}`\n'
                    f'📋 Тип: `{type_of}`\n'
                    f'🏷️ Тикер: `{ticker}`\n'
                    f'📊 Изменение цены: `{round(price_change_percent, 2)}%`\n'
                    f'💰 Цена закрытия последней свечи: `{close_price}`\n'
                    f'⬆️ Максимальная цена: `{max_price}`\n'
                    f'⬇️ Минимальная цена: `{min_price}`\n'
                )
                send_or_edit_message(chat_id, message_text)
        
        if not found_instruments:
            send_or_edit_message(
                chat_id, 
                f'ℹ️ *Информация*\n\nНе найдено инструментов с падением в диапазоне {percent_range} за интервал {interval}'
            )
    
    except Exception as e:
        send_or_edit_message(chat_id, f"❌ *Ошибка при получении данных об обвале рынка*\n\n`{str(e)}`")


# Вспомогательная функция для получения интервала
def get_time_interval(interval):
    """
    Получает начальное время и интервал свечи в зависимости от выбранного интервала.
    
    Args:
        interval: Выбранный интервал времени
        
    Returns:
        tuple: (start_time, candle_interval)
    """
    if interval == 'день':
        start_time = datetime.now().replace(hour=10, minute=0, second=0)
        candle_interval = CandleInterval.CANDLE_INTERVAL_10_MIN
    else:
        timedelta_value, candle_interval = INTERVAL_MAPPING.get(interval, (None, None))
        if timedelta_value:
            start_time = datetime.now() - timedelta_value
        else:
            start_time, candle_interval = None, None
    
    return start_time, candle_interval
