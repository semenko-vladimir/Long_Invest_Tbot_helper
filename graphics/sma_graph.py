import matplotlib
matplotlib.use('Agg')

import matplotlib.pyplot as plt
import os
from bot.bot import bot
import store.store as store

def plot_sma(chat_id, df):
    """
    Функция для построения графика цены и сигналов SMA, и отправки его в Telegram.

    :param chat_id: Идентификатор чата в Telegram, куда нужно отправить график.
    :param df: DataFrame с колонками 'date' и 'close' для построения графика цены.
    :param fast_sma: Массив значений быстрой SMA.
    :param slow_sma: Массив значений медленной SMA.
    """

    fast_sma = store.fast_sma
    slow_sma = store.slow_sma

    fig, ax = plt.subplots(figsize=(14, 7))

    # График цены
    ax.plot(df['time'], df['close'], label='Close Price', color='blue')
    ax.set_title('Stock Close Price with SMA')
    ax.set_ylabel('Price')

    # График быстрой SMA
    ax.plot(df['time'], fast_sma, label='Fast SMA', color='orange', linestyle='--')

    # График медленной SMA
    ax.plot(df['time'], slow_sma, label='Slow SMA', color='green', linestyle='--')

    # Легенда и подписи
    ax.legend(loc='upper left')
    ax.set_xlabel('Date')
    ax.set_ylabel('Price')
    
    # Сохранение графика во временный файл
    file_path = 'sma_chart.png'
    plt.savefig(file_path)
    plt.close(fig)  # Закрываем график, чтобы освободить ресурсы

    # Отправляем файл в Telegram
    with open(file_path, 'rb') as photo:
        bot.send_photo(chat_id, photo)

    # Удаляем файл после отправки (необязательно)
    os.remove(file_path)
