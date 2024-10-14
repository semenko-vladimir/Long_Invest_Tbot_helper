import matplotlib
matplotlib.use('Agg')

import matplotlib.pyplot as plt
import os
from bot.bot import bot

import store.store as store

def plot_alligator(chat_id, df):
    """
    Функция для построения графика средней цены и индикатора Аллигатор и отправки его в Telegram.
    
    :param chat_id: Идентификатор чата в Telegram, куда нужно отправить график.
    :param df: DataFrame с колонками 'time', 'high', 'low' для построения графика средней цены.
    :param jaw_sma: Массив значений SMA для линии челюстей.
    :param teeth_sma: Массив значений SMA для линии зубов.
    :param lips_sma: Массив значений SMA для линии губ.
    """

    jaw_sma = store.jaw_sma
    teeth_sma = store.teeth_sma
    lips_sma = store.lips_sma

    # Рассчитываем среднюю цену
    avg_prices = (df['high'].values + df['low'].values) / 2

    # Построение графика
    fig, ax = plt.subplots(figsize=(14, 8))
    
    # Средняя цена
    ax.plot(df['time'], avg_prices, label='Average Price', color='black')
    
    # Линии Аллигатора
    ax.plot(df['time'], jaw_sma, label='Jaw (SMA)', color='blue')
    ax.plot(df['time'], teeth_sma, label='Teeth (SMA)', color='red')
    ax.plot(df['time'], lips_sma, label='Lips (SMA)', color='green')
    
    ax.set_title('Alligator Indicator')
    ax.set_xlabel('Date')
    ax.set_ylabel('Price')
    ax.legend(loc='upper left')

    # Сохраняем график во временный файл
    file_path = 'alligator_chart.png'
    plt.savefig(file_path)
    plt.close(fig)

    # Отправляем файл в Telegram
    with open(file_path, 'rb') as photo:
        bot.send_photo(chat_id, photo)

    # Удаляем файл после отправки
    os.remove(file_path)
