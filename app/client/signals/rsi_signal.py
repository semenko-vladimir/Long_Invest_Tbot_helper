import numpy as np
from tinkoff.invest import HistoricCandle
from app.client.utils.helpers import create_df
import app.client.store.store as store
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

import numpy as np
import pandas as pd
import ta
from tinkoff.invest import HistoricCandle
from app.client.utils.helpers import create_df

def ema(prices, length):
    if len(prices) < length:
        return None

    # Преобразуем в Series для удобства
    prices_series = pd.Series(prices)

    # Рассчитываем EMA с помощью ta
    ema_values = ta.trend.ema_indicator(prices_series, window=length, fillna=True)

    return ema_values.to_numpy()

def calculate_rsi(data, period):

    """
    Вычисляет Relative Strength Index (RSI) для списка свечей, полученных из HistoricCandle.

    :param data: объект HistoricCandle, содержащий список свечей
    :param period: период, для которого нужно вычислить RSI
    :return: последнее значение RSI или None, если список свечей имеет длину меньше period
    """
    period = int(period)
    candles = data.candles  # Извлекаем список свечей из объекта ответа

    df = create_df(candles)

    close_prices = df['close'].values

    if len(close_prices) < period:
        return None
    
    rsi_values = ta.momentum.rsi(pd.Series(close_prices), window=period, fillna=True)
    store.rsi_values = rsi_values

    if not rsi_values.empty:
        last_rsi = rsi_values.iloc[-1]
    else:
        last_rsi = None

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

    print(f"RSI: {rsi} | Last RSI: {last_rsi}")
    return last_rsi

def check_rsi_signal(rsi_value, low_level, high_level, profit):
    """
    Проверяет сигнал RSI для определения действия торговли.

    :param rsi_value: текущее значение RSI
    :param low_level: уровень перепроданности для сигнала на покупку
    :param high_level: уровень перекупленности для сигнала на продажу
    :param profit: текущая прибыль, используется для подтверждения сигнала на продажу
    :return: 'buy', если RSI ниже уровня перепроданности;
             'sell', если RSI выше уровня перекупленности и есть прибыль;
             'hold', если ни одно из условий не выполнено
    """

    # Проверяем пересечение уровня перепроданности (сигнал на покупку)
    if rsi_value < low_level:
        return 'buy'
    
    # Проверяем пересечение уровня перекупленности (сигнал на продажу)
    if rsi_value > high_level and profit > 0:
        return 'sell'
    
    return 'hold'

