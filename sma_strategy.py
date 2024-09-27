import numpy as np

from methods import create_df

# Функция для расчета SMA
def sma(prices, length):
    if len(prices) < length:
        return None
    sma_values = np.convolve(prices, np.ones(length), 'valid') / length
    # Добавляем None для выравнивания длины списка до длины цен
    sma_values = np.concatenate((np.full(length - 1, None), sma_values))
    return sma_values

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
    candles = data.candles
    df = create_df(candles)

    close_prices = df['close'].values

    # Рассчитываем быструю и медленную SMA
    fast_sma = sma(close_prices, fast_length)
    slow_sma = sma(close_prices, slow_length)

    # Проверяем пересечения
    if crossover(fast_sma, slow_sma):
        return 'buy'
    if crossunder(fast_sma, slow_sma) and profit > 0:
        return 'sell'

    return 'hold'