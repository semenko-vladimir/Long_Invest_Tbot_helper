import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from mplfinance.original_flavor import candlestick_ohlc
import os
import pandas as pd
from app.client.bot.bot import bot
import app.client.store.store as store

def plot_macd(chat_id, df):
    """
    Функция для построения свечного графика цены и индикатора MACD, и отправки его в Telegram.
    
    :param chat_id: Идентификатор чата в Telegram, куда нужно отправить график.
    :param df: DataFrame с колонками 'time', 'open', 'high', 'low', 'close' для построения свечного графика цены.
    """

    macd_line = store.macd_line
    signal_line = store.signal_line

    # Конвертация столбца 'time' в формат для matplotlib
    df['time'] = pd.to_datetime(df['time'])
    df['time'] = df['time'].map(mdates.date2num)

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 10), sharex=True)

    # Свечной график цены
    ohlc = df[['time', 'open', 'high', 'low', 'close']].values
    candlestick_ohlc(ax1, ohlc, width=0.8, colorup='green', colordown='red')
    
    ax1.set_title('Price Chart with Candlesticks')
    ax1.set_ylabel('Price')
    ax1.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d'))
    fig.autofmt_xdate()

    # График MACD и сигнальной линии
    ax2.plot(df['time'], macd_line, label='MACD Line', color='orange')
    ax2.plot(df['time'], signal_line, label='Signal Line', color='red')

    # Гистограмма MACD
    macd_histogram = macd_line - signal_line
    ax2.bar(df['time'], macd_histogram, label='MACD Histogram', color='green', alpha=0.5)
    
    ax2.set_title('MACD Indicator')
    ax2.set_xlabel('Date')
    ax2.set_ylabel('MACD')
    ax2.legend(loc='upper left')

    # Сохраняем график во временный файл
    file_path = 'macd_candlestick_chart.png'
    plt.savefig(file_path)
    plt.close(fig)

    # Отправляем файл в Telegram
    with open(file_path, 'rb') as photo:
        bot.send_photo(chat_id, photo)

    # Удаляем временный файл после отправки
    os.remove(file_path)
