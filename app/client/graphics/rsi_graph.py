import matplotlib
matplotlib.use('Agg')

import os
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from mplfinance.original_flavor import candlestick_ohlc
import pandas as pd
from app.client.bot.bot import bot
import app.client.store.store as store

def plot_rsi(chat_id, df, low_level, high_level):
    """
    Функция для построения свечного графика цены и RSI и отправки его в Telegram.
    
    :param chat_id: Идентификатор чата в Telegram, куда нужно отправить график.
    :param df: DataFrame с колонками 'time', 'open', 'high', 'low', 'close' для построения графика цены.
    :param low_level: Нижний уровень для сигнала перепроданности.
    :param high_level: Верхний уровень для сигнала перекупленности.
    """

    rsi_values = store.rsi_values

    # Конвертация столбца 'time' в формат для matplotlib
    df['time'] = pd.to_datetime(df['time'])
    df['time'] = df['time'].map(mdates.date2num)

    # Создаем список данных для candlestick_ohlc
    ohlc = df[['time', 'open', 'high', 'low', 'close']].values

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 10), sharex=True)

    # Свечной график
    candlestick_ohlc(ax1, ohlc, width=0.8, colorup='green', colordown='red')
    ax1.set_title('Stock Price Chart')
    ax1.set_ylabel('Price')

    # График RSI
    ax2.plot(df['time'], rsi_values, label='RSI', color='purple')
    ax2.axhline(y=low_level, color='red', linestyle='--', label=f'Oversold ({low_level})')
    ax2.axhline(y=high_level, color='green', linestyle='--', label=f'Overbought ({high_level})')
    ax2.set_title('Relative Strength Index (RSI)')
    ax2.set_xlabel('Date')
    ax2.set_ylabel('RSI')
    ax2.legend(loc='upper left')

    # Форматирование дат на оси X
    ax1.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d'))
    fig.autofmt_xdate()

    # Сохраняем график во временный файл
    file_path = 'rsi_candlestick_chart.png'
    plt.savefig(file_path)
    plt.close(fig)  # Закрываем график, чтобы освободить ресурсы

    # Отправляем файл в Telegram
    with open(file_path, 'rb') as photo:
        bot.send_photo(chat_id, photo)

    # Удаляем файл после отправки (необязательно)
    os.remove(file_path)
