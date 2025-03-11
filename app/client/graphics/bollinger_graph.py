import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from mplfinance.original_flavor import candlestick_ohlc
import os
import pandas as pd
from app.client.bot.bot import bot
import app.client.store.store as store

def plot_bollinger(chat_id, df):
    """
    Функция для построения свечного графика цены с полосами Боллинджера и отправки его в Telegram.
    
    :param chat_id: Идентификатор чата в Telegram, куда нужно отправить график.
    :param df: DataFrame с колонками 'time', 'open', 'high', 'low', 'close' для построения свечного графика цены.
    """

    lower_band = store.lower_band
    middle_band = store.middle_band
    upper_band = store.upper_band

    # Конвертация столбца 'time' в формат для matplotlib
    df['time'] = pd.to_datetime(df['time'])
    df['time'] = df['time'].map(mdates.date2num)

    fig, ax = plt.subplots(figsize=(14, 8))

    # Создаем список данных для candlestick_ohlc
    ohlc = df[['time', 'open', 'high', 'low', 'close']].values

    # Свечной график цены
    candlestick_ohlc(ax, ohlc, width=0.8, colorup='green', colordown='red')

    # Полосы Боллинджера
    ax.plot(df['time'], middle_band, label='Middle Band', color='orange')
    ax.plot(df['time'], upper_band, label='Upper Band', color='green')
    ax.plot(df['time'], lower_band, label='Lower Band', color='red')

    # Настройка легенды и заголовков
    ax.set_title('Bollinger Bands with Candlesticks')
    ax.set_xlabel('Date')
    ax.set_ylabel('Price')
    ax.legend(loc='upper left')

    # Форматирование дат на оси X
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d'))
    fig.autofmt_xdate()

    # Сохраняем график во временный файл
    file_path = 'bollinger_candlestick_chart.png'
    plt.savefig(file_path)
    plt.close(fig)

    # Отправляем файл в Telegram
    with open(file_path, 'rb') as photo:
        bot.send_photo(chat_id, photo)

    # Удаляем временный файл после отправки
    os.remove(file_path)
