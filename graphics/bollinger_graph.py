import matplotlib
matplotlib.use('Agg')

import matplotlib.pyplot as plt
import os
from bot.bot import bot
import store.store as store

def plot_bollinger(chat_id, df):
    """
    Функция для построения графика цены с полосами Боллинджера и отправки его в Telegram.
    
    :param chat_id: Идентификатор чата в Telegram, куда нужно отправить график.
    :param df: DataFrame с колонками 'time' и 'close' для построения графика цены.
    """

    lower_band = store.lower_band
    middle_band = store.middle_band
    upper_band = store.upper_band

    fig, ax = plt.subplots(figsize=(14, 8))

    # График цены закрытия
    ax.plot(df['time'], df['close'], label='Close Price', color='blue')
    
    # Полосы Боллинджера
    ax.plot(df['time'], middle_band, label='Middle Band', color='orange')
    ax.plot(df['time'], upper_band, label='Upper Band', color='green')
    ax.plot(df['time'], lower_band, label='Lower Band', color='red')

    # Настройка легенды и заголовков
    ax.set_title('Bollinger Bands')
    ax.set_xlabel('Date')
    ax.set_ylabel('Price')
    ax.legend(loc='upper left')

    # Сохраняем график во временный файл
    file_path = 'bollinger_chart.png'
    plt.savefig(file_path)
    plt.close(fig)

    # Отправляем файл в Telegram
    with open(file_path, 'rb') as photo:
        bot.send_photo(chat_id, photo)

    # Удаляем временный файл после отправки
    os.remove(file_path)
