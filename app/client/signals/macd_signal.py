import pandas as pd
import ta  
from app.client.utils.helpers import create_df
import app.client.store.store as store

def calculate_macd_strategy(data, fast_length, slow_length, signal_length, profit):
    """
    Вычисление MACD и генерация торгового сигнала.
    
    :param data: Данные о свечах.
    :param fast_length: Период для быстрой EMA.
    :param slow_length: Период для медленной EMA.
    :param signal_length: Период для сигнальной линии.
    :param profit: Текущая прибыль.
    :return: Торговый сигнал ('buy', 'sell', 'hold').
    """

    # Создаем DataFrame из данных о свечах
    candles = data.candles
    df = create_df(candles)

    # Преобразуем цены закрытия в Series
    close_prices = pd.Series(df['close'].values)

    # Рассчитываем MACD
    macd_values = ta.trend.MACD(close_prices, window_slow=slow_length, window_fast=fast_length, window_sign=signal_length)

    # Получаем линии MACD и сигнальную линию
    macd_line = macd_values.macd().values
    signal_line = ta.trend.ema_indicator(pd.Series(macd_line), window=signal_length, fillna=True).to_numpy()

    store.signal_line = signal_line
    store.macd_line = macd_line

    # Проверяем, что длины массивов совпадают
    if len(macd_line) != len(signal_line):
        raise ValueError("Длина линии MACD и сигнальной линии не совпадают.")

    # Получаем последние значения
    current_macd = macd_line[-1]
    current_signal = signal_line[-1]

    # Генерация торгового сигнала
    if current_macd > current_signal:  # Условие для покупки
        return 'buy'
    elif current_macd < current_signal and profit > 0:  # Условие для продажи
        return 'sell'
    else:
        return 'hold'
