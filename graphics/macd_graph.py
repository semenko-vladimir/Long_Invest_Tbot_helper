import matplotlib
matplotlib.use('Agg')

import matplotlib.pyplot as plt
import os
from bot.bot import bot
import store.store as store

def plot_macd(chat_id, df):
    """
    Функция для построения графика MACD с сигнальной линией и отправки его в Telegram.
    
    :param chat_id: Идентификатор чата в Telegram, куда нужно отправить график.
    :param df: DataFrame с колонками 'time' для оси X.
    """

    macd_line = store.macd_line
    signal_line = store.signal_line

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 10), sharex=True)

    # График цены закрытия
    ax1.plot(df['time'], df['close'], label='Close Price', color='blue')
    ax1.set_title('Price Chart')
    ax1.set_ylabel('Price')
    ax1.legend(loc='upper left')

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
    file_path = 'macd_chart.png'
    plt.savefig(file_path)
    plt.close(fig)

    # Отправляем файл в Telegram
    with open(file_path, 'rb') as photo:
        bot.send_photo(chat_id, photo)

    # Удаляем временный файл после отправки
    os.remove(file_path)
