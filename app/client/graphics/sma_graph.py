import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from mplfinance.original_flavor import candlestick_ohlc
import os
import pandas as pd
from app.client.bot.bot import bot
import app.client.store.store as store

def plot_sma(chat_id, df):
    """
    Функция для построения свечного графика цены и сигналов SMA, и отправки его в Telegram.

    :param chat_id: Идентификатор чата в Telegram, куда нужно отправить график.
    :param df: DataFrame с колонками 'time', 'open', 'high', 'low', 'close' для построения свечного графика цены.
    """

    fast_sma = store.fast_sma
    slow_sma = store.slow_sma

    # Конвертация столбца 'time' в формат для matplotlib
    df['time'] = pd.to_datetime(df['time'])
    df['time'] = df['time'].map(mdates.date2num)

    fig, ax = plt.subplots(figsize=(14, 7))
    ax.set_title('Stock Price with SMA')
    ax.set_xlabel('Date')
    ax.set_ylabel('Price')

    # Создаем список данных для candlestick_ohlc
    ohlc = df[['time', 'open', 'high', 'low', 'close']].values

    candlestick_ohlc(ax, ohlc, width=0.8, colorup='green', colordown='red')

    # Добавление графиков SMA
    ax.plot(df['time'], fast_sma, label='Fast SMA', color='orange', linestyle='--')
    ax.plot(df['time'], slow_sma, label='Slow SMA', color='blue', linestyle='--')

    # Форматирование дат на оси X
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d'))
    fig.autofmt_xdate()

    # Добавление легенды
    ax.legend(loc='upper left')

    # Сохранение графика во временный файл
    file_path = 'sma_candlestick_chart.png'
    plt.savefig(file_path)
    plt.close(fig)  

    with open(file_path, 'rb') as photo:
        bot.send_photo(chat_id, photo)

    os.remove(file_path)
