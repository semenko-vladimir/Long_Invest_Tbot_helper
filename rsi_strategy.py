import numpy as np
from tinkoff.invest import HistoricCandle
from methods import create_df


def calculate_rsi(data, period):
    # Получаем массив свечей из ответа

    period = int(period)
    candles = data.candles  # Извлекаем список свечей из объекта ответа

    df = create_df(candles)

    # Берем цены закрытия из DataFrame
    close_prices = df['close'].values

    # Проверяем, достаточно ли данных для расчета RSI
    if len(close_prices) < period:
        raise ValueError("Недостаточно данных для расчета RSI")

    # Рассчитываем изменения цены между периодами
    deltas = np.diff(close_prices)

    # Разделяем на приросты (gain) и убытки (loss)
    gains = np.where(deltas > 0, deltas, 0)  # Только положительные изменения
    losses = np.where(deltas < 0, -deltas, 0)  # Только отрицательные изменения

    # Рассчитываем средние приросты и потери за период
    avg_gain = np.mean(gains[:period])
    avg_loss = np.mean(losses[:period])

    # Для следующего периода используем формулу скользящего среднего
    for i in range(period, len(close_prices) - 1):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period

    # Если средняя потеря равна 0, то RSI = 100
    if avg_loss == 0:
        return 100

    # Рассчитываем RS и RSI
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))

    return rsi


def check_rsi_signal(rsi_value, low_level, high_level, profit):
    # Проверяем пересечение уровня перепроданности (сигнал на покупку)
    if rsi_value < low_level:
        return 'buy'
    
    # Проверяем пересечение уровня перекупленности (сигнал на продажу)
    if rsi_value > high_level and profit > 0:
        return 'sell'
    
    return 'hold'
