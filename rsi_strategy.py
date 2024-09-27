import numpy as np
from tinkoff.invest import HistoricCandle
from methods import create_df

'''
Общий алгоритм расчета RSI для периода N выглядит следующим образом:

Берутся цены закрытия за выбранный период, включая текущий день.
Определяются дни, в которые цена закрытия была выше, чем открытие следующего дня.
Вычисляется совокупная абсолютная величина этих приростов и делится на N, в результате чего получается средняя величина прироста (во многих случаях это экспоненциальное скользящее среднее).
Определяются дни, когда цена закрытия была ниже, чем последующая цена открытия.
Аналогично приросту вычисляется средняя величина падения.
В результате деления среднего прироста на среднее падение, получаем относительную силу (RS), которая станет основой индикатора.
На основании RS вычисляется индекс относительной силы: RSI = 100 – 100 / (RS + 1).
'''

def ema(prices, length):
    if len(prices) < length:
        return None

    ema_values = np.zeros(len(prices))
    initial_sma = np.mean(prices[:length])
    ema_values[length - 1] = initial_sma
    k = 2 / (length + 1)

    for i in range(length, len(prices)):
        ema_values[i] = (prices[i] * k) + (ema_values[i - 1] * (1 - k))

    return ema_values

def calculate_rsi(data, period):
    period = int(period)
    candles = data.candles  # Извлекаем список свечей из объекта ответа

    df = create_df(candles)

    close_prices = df['close'].values

    if len(close_prices) < period:
        return None

    deltas = np.diff(close_prices)

    gains = np.where(deltas > 0, deltas, 0)
    losses = np.where(deltas < 0, -deltas, 0)

    avg_gain = ema(gains, period)
    avg_loss = ema(losses, period)

    if avg_gain is None or avg_loss is None:
        return None

    if avg_loss[-1] == 0:
        return 100

    rs = avg_gain[-1] / avg_loss[-1]
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
