import numpy as np
from app.client.utils.helpers import create_df
import pandas as pd
import ta
import app.client.store.store as store

# Функция для проверки пересечения (crossover) - снизу вверх
def crossover(source1, source2):
    if len(source1) < 2 or len(source2) < 2:
        return False
    return source1[-2] < source2[-2] and source1[-1] > source2[-1]

# Функция для проверки пересечения (crossunder) - сверху вниз
def crossunder(source1, source2):
    if len(source1) < 2 or len(source2) < 2:
        return False
    return source1[-2] > source2[-2] and source1[-1] < source2[-1]

# Функция для расчета EMA
def ema(prices, length):
    if len(prices) < length:
        return None  # Возвращаем NaN для всех значений
    
    # Преобразуем в Series для удобства
    prices_series = pd.Series(prices)
    
    # Рассчитываем EMA с помощью ta
    ema_values = ta.trend.ema_indicator(prices_series, window=length, fillna=True)
    
    return ema_values.to_numpy()  # Возвращаем в виде массива NumPy

def calculate_ema_strategy(data, fast_length, slow_length, profit):
    """
    Вычисление EMA и генерация торгового сигнала.
    
    :param data: Данные о свечах.
    :param fast_length: Период для быстрой EMA.
    :param slow_length: Период для медленной EMA.
    :param profit: Текущая прибыль.
    :return: Торговый сигнал ('buy', 'sell', 'hold').
    """
    
    candles = data.candles
    df = create_df(candles)
    
    close_prices = df['close'].values

    # Рассчитываем быструю и медленную EMA
    fast_ema = ema(close_prices, fast_length)
    slow_ema = ema(close_prices, slow_length)

    store.fast_ema = fast_ema
    store.slow_ema = slow_ema

    # Проверяем пересечения EMA
    if crossover(fast_ema, slow_ema):
        return 'buy'
    if crossunder(fast_ema, slow_ema) and profit > 0:
        return 'sell'

    return 'hold'
