import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from mplfinance.original_flavor import candlestick_ohlc
import os
import pandas as pd
from app.client.bot.bot import bot
import app.client.store.store as store

def plot_alligator(chat_id, df):
    """
    Функция для построения свечного графика средней цены с линиями Аллигатора и отправки его в Telegram.
    
    :param chat_id: Идентификатор чата в Telegram, куда нужно отправить график.
    :param df: DataFrame с колонками 'time', 'open', 'high', 'low', 'close' для построения свечного графика.
    """

    jaw_sma = store.jaw_sma
    teeth_sma = store.teeth_sma
    lips_sma = store.lips_sma

    # Рассчитываем среднюю цену
    avg_prices = (df['high'] + df['low']) / 2

    # Конвертация столбца 'time' в формат для matplotlib
    df['time'] = pd.to_datetime(df['time'])
    df['time'] = df['time'].map(mdates.date2num)

    # Создаем список данных для candlestick_ohlc
    ohlc = df[['time', 'open', 'high', 'low', 'close']].values

    # Построение графика
    fig, ax = plt.subplots(figsize=(14, 8))

    # Свечной график
    candlestick_ohlc(ax, ohlc, width=0.8, colorup='green', colordown='red')

    # Линии Аллигатора
    ax.plot(df['time'], jaw_sma, label='Jaw (SMA)', color='blue', linewidth=1.5)
    ax.plot(df['time'], teeth_sma, label='Teeth (SMA)', color='red', linewidth=1.5)
    ax.plot(df['time'], lips_sma, label='Lips (SMA)', color='green', linewidth=1.5)
    
    ax.set_title('Alligator Indicator with Candlesticks')
    ax.set_xlabel('Date')
    ax.set_ylabel('Price')
    ax.legend(loc='upper left')

    # Форматирование дат на оси X
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d'))
    fig.autofmt_xdate()

    # Сохраняем график во временный файл
    file_path = 'alligator_candlestick_chart.png'
    plt.savefig(file_path)
    plt.close(fig)

    # Отправляем файл в Telegram
    with open(file_path, 'rb') as photo:
        bot.send_photo(chat_id, photo)

    # Удаляем временный файл после отправки
    os.remove(file_path)
