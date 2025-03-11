import numpy as np
import pandas as pd
import ta  
from app.client.utils.helpers import create_df
from app.client.signals.sma_signal import sma
from app.client.signals.rsi_signal import ema
import app.client.store.store as store

def calculate_bollinger_strategy(data, period, stddev, ma_type, profit):
    """
    Вычисление полос Боллинджера и генерация торгового сигнала.
    
    :param prices: массив цен закрытия.
    :param period: период для скользящей средней.
    :param stddev: количество стандартных отклонений.
    :param ma_type: тип скользящей средней ('SMA' или 'EMA').
    :return: торговый сигнал ('buy', 'sell', 'hold')
    """

    candles = data.candles
    df = create_df(candles)

    close_prices = df['close'].values

    # Рассчитываем среднюю линию с помощью SMA или EMA
    if ma_type == 'SMA':
        middle_band = sma(close_prices, period)
    elif ma_type == 'EMA':
        middle_band = ema(close_prices, period)
    else:
        raise ValueError("Неверный тип скользящей средней. Допустимые значения: 'SMA', 'EMA'.")

    # Преобразуем цены в DataFrame для вычисления стандартного отклонения
    prices_series = pd.Series(close_prices)
    rolling_std = prices_series.rolling(window=period).std(ddof=0).to_numpy()

    # Проверяем, что длины массивов совпадают
    if len(middle_band) != len(rolling_std):
        raise ValueError("Длина скользящей средней и стандартного отклонения не совпадают.")

    # Вычисляем верхнюю и нижнюю полосы
    upper_band = middle_band + (rolling_std * stddev)
    lower_band = middle_band - (rolling_std * stddev)

    store.lower_band = lower_band
    store.middle_band = middle_band
    store.upper_band = upper_band

    # Получаем последнюю цену и значение полос для принятия решения
    current_price = close_prices[-1]
    current_upper_band = upper_band[-1]
    current_lower_band = lower_band[-1]
    
    # Генерация торгового сигнала
    if current_price <= current_lower_band:
        return 'buy'
    elif current_price >= current_upper_band and profit > 0:
        return 'sell'
    else:
        return 'hold'
