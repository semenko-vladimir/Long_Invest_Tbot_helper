import matplotlib
matplotlib.use('Agg')

import os
import matplotlib.pyplot as plt
from bot.bot import bot
import store
import store.store as store

def plot_rsi(chat_id, df, low_level, high_level):
    """
    Функция для построения графика цены и RSI и отправки его в Telegram.
    
    :param chat_id: Идентификатор чата в Telegram, куда нужно отправить график.
    :param df: DataFrame с колонками 'date' и 'close' для построения графика цены.
    :param rsi_values: Массив или список значений RSI.
    :param low_level: Нижний уровень для сигнала перепроданности.
    :param high_level: Верхний уровень для сигнала перекупленности.
    """

    rsi_values = store.rsi_values

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 10), sharex=True)

    # График цены
    ax1.plot(df['time'], df['close'], label='Close Price', color='blue')
    ax1.set_title('Stock Close Price')
    ax1.set_ylabel('Price')
    ax1.legend(loc='upper left')

    # График RSI
    ax2.plot(df['time'], rsi_values, label='RSI', color='purple')
    ax2.axhline(y=low_level, color='red', linestyle='--', label=f'Oversold ({low_level})')
    ax2.axhline(y=high_level, color='green', linestyle='--', label=f'Overbought ({high_level})')
    ax2.set_title('Relative Strength Index (RSI)')
    ax2.set_xlabel('Date')
    ax2.set_ylabel('RSI')
    ax2.legend(loc='upper left')

    # Сохраняем график во временный файл
    file_path = 'rsi_chart.png'
    plt.savefig(file_path)
    plt.close(fig)  # Закрываем график, чтобы освободить ресурсы

    # Отправляем файл в Telegram
    with open(file_path, 'rb') as photo:
        bot.send_photo(chat_id, photo)

    # Удаляем файл после отправки (необязательно)
    os.remove(file_path)

    
