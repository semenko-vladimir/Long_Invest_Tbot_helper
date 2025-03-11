import numpy as np
from app.client.utils.helpers import create_df
import pandas as pd
import ta
import app.client.store.store as store


'''
Алгоритм расчета SMA (простого скользящего среднего) для периода N выглядит следующим образом:

1. Берутся цены закрытия за выбранный период.
2. Для каждого дня берется среднее арифметическое цен закрытия за период N.
   Формула для расчета SMA:
   SMA = (P1 + P2 + ... + Pn) / N,
   где P1, P2, ..., Pn — цены закрытия за период N.
3. Для начала периода (первые N-1 ) SMA не может быть рассчитано, поэтому добавляются значения None (или 0 при необходимости),
чтобы длина выходного массива соответствовала длине массива цен.
'''

# Функция для расчета SMA
def sma(prices, length):
    if len(prices) < length:
        return None  # Возвращаем NaN для всех значений

    # Преобразуем в Series для удобства
    prices_series = pd.Series(prices)

    # Рассчитываем SMA с помощью ta
    sma_values = ta.trend.sma_indicator(prices_series, window=length, fillna=True)

    return sma_values.to_numpy()  # Возвращаем в виде массива NumPy


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

# Функция для расчета сигнала по стратегии SMA
def calculate_sma_strategy(data, fast_length, slow_length, profit):
    """
    Вычисление сигнала по стратегии SMA.

    :param data: Данные о свечах.
    :param fast_length: Период для быстрой SMA.
    :param slow_length: Период для медленной SMA.
    :param profit: Текущая прибыль.
    :return: Торговый сигнал ('buy', 'sell', 'hold').
    """
    candles = data.candles
    df = create_df(candles)

    close_prices = df['close'].values

    # Рассчитываем быструю и медленную SMA
    fast_sma = sma(close_prices, fast_length)
    slow_sma = sma(close_prices, slow_length)

    store.fast_sma = fast_sma
    store.slow_sma = slow_sma

    # Проверяем пересечения
    if crossover(fast_sma, slow_sma):
        return 'buy'
    if crossunder(fast_sma, slow_sma) and profit > 0:
        return 'sell'

    return 'hold'
