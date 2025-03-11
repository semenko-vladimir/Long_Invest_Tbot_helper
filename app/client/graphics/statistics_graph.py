import matplotlib
matplotlib.use('Agg')

import matplotlib.pyplot as plt
import pandas as pd
import os
import seaborn as sns
from datetime import datetime
import pytz
from app.client.bot.bot import bot

def statistics_graph(buy, margin, chat_id):
    """
    Функция для формирования статистики по покупкам и продажам.
    
    Args:
        buy (list): Список покупок.
        margin (list): Список продаж.
        chat_id (int): Id чата, в который будет отправлена статистика.
    """
    if len(buy) > 0:
        # Преобразуем данные в DataFrame для удобства работы
        buy_df = pd.DataFrame(buy, columns=['id', 'price', 'ticker', 'signal', 'time', 'chat_id'])
        buy_df['time'] = pd.to_datetime(buy_df['time'], format='%d-%m-%Y %H:%M')

        # 1. Гистограмма покупок тикеров
        plt.figure(figsize=(14, 9))
        if buy_df['ticker'].nunique() > 1:
            sns.countplot(data=buy_df, x='ticker', palette='Blues')
        else:
            sns.countplot(data=buy_df, x='ticker', palette='Blues', width=0.1)
        plt.title('Количество покупок по тикерам')
        plt.xlabel('Тикер', labelpad=20)
        plt.ylabel('Количество покупок', labelpad=20)
        plt.xticks(rotation=0, ha='center', va='top')  
        plt.gca().tick_params(axis='x', pad=10)
        plt.subplots_adjust(bottom=0.2)  
        file_path = 'buy_ticker_histogram.png'
        plt.savefig(file_path)
        plt.close()
        with open(file_path, 'rb') as photo:
            bot.send_photo(chat_id, photo)
        os.remove(file_path)

        # 2. Гистограмма покупок по сигналам
        plt.figure(figsize=(14, 9))
        signals = buy_df['signal']
        if signals.nunique() > 1:
            sns.countplot(x=signals, palette='Greens')
        else:
            sns.countplot(x=signals, palette='Greens', width=0.1)
        plt.title('Количество покупок по сигналам')
        plt.xlabel('Сигнал', labelpad=20)
        plt.ylabel('Количество покупок', labelpad=20)
        plt.xticks(rotation=0, ha='center', va='top')  
        plt.gca().tick_params(axis='x', pad=10)
        plt.subplots_adjust(bottom=0.2)  
        file_path = 'buy_signal_histogram.png'
        plt.savefig(file_path)
        plt.close()
        with open(file_path, 'rb') as photo:
            bot.send_photo(chat_id, photo)
        os.remove(file_path)

        # 3. Линейный график покупок по дням или часам
        buy_per_day = buy_df.groupby(buy_df['time'].dt.strftime('%d-%m-%Y')).size()

        plt.figure(figsize=(14, 9))
        if len(buy_per_day) > 1:
            buy_per_day.plot(kind='line', marker='o', color='orange')
            plt.title('Количество покупок по дням')
            plt.xlabel('Дата', labelpad=20)
            plt.ylabel('Количество покупок', labelpad=20)
            plt.xticks(rotation=0, ha='center', va='top')  
            plt.gca().tick_params(axis='x', pad=10)
            plt.subplots_adjust(bottom=0.2)  
        else:
            buy_per_hour = buy_df.groupby(buy_df['time'].dt.strftime('%H:%M')).size()
            buy_per_hour.plot(kind='bar', color='orange', width=0.1)
            plt.title('Количество покупок по часам')
            plt.xlabel('Время', labelpad=20)
            plt.ylabel('Количество покупок', labelpad=20)
            plt.xticks(rotation=0, ha='center', va='top')  
            plt.gca().tick_params(axis='x', pad=10)
            plt.subplots_adjust(bottom=0.2)  

        plt.xticks(rotation=0, ha='center', va='top')  
        plt.gca().tick_params(axis='x', pad=10)
        plt.subplots_adjust(bottom=0.2)  
        file_path = 'buy_time_graph.png'
        plt.savefig(file_path)
        plt.close()
        with open(file_path, 'rb') as photo:
            bot.send_photo(chat_id, photo)
        os.remove(file_path)

        # 4. Общая сумма покупок
        total_buy_amount = buy_df['price'].sum()
        bot.send_message(chat_id, f"Общая сумма покупок: {total_buy_amount} руб.")

    if len(margin) > 0:
        margin_df = pd.DataFrame(margin, columns=['id', 'margin', 'ticker', 'signal', 'time', 'chat_id'])
        margin_df['time'] = pd.to_datetime(margin_df['time'], format='%d-%m-%Y %H:%M')

        # 5. Круговой график маржи
        positive_margin = margin_df[margin_df['margin'] > 0].shape[0]
        negative_margin = margin_df[margin_df['margin'] < 0].shape[0]
        data = [positive_margin, negative_margin]
        labels = ['Положительная маржа', 'Отрицательная маржа']
        
        plt.figure(figsize=(12, 7))
        plt.pie([v for v in data if v > 0], labels=[l for v, l in zip(data, labels) if v > 0], 
                autopct='%1.1f%%', colors=['orange', 'deepskyblue'])
        plt.title('Соотношение положительной и отрицательной маржи')
        file_path = 'margin_pie_chart.png'
        plt.savefig(file_path)
        plt.close()
        with open(file_path, 'rb') as photo:
            bot.send_photo(chat_id, photo)
        os.remove(file_path)

        # 6. Гистограмма маржи по тикерам (вверх положительная, вниз отрицательная)
        margin_df_ticker = margin_df.copy()
        margin_df_ticker['margin_type'] = ['Положительная' if m > 0 else 'Отрицательная' for m in margin_df_ticker['margin']]
        margin_ticker = margin_df_ticker.pivot_table(index='ticker', columns='margin_type', aggfunc='size', fill_value=0)

        # Проверяем, какие столбцы есть в margin_ticker и переименовываем их
        columns_mapping = {}
        if 'Положительная' in margin_ticker.columns:
            columns_mapping['Положительная'] = 'Положительная'
        if 'Отрицательная' in margin_ticker.columns:
            columns_mapping['Отрицательная'] = 'Отрицательная'

        margin_ticker = margin_ticker[list(columns_mapping.keys())]  # Убираем столбцы, которых нет

        # Преобразуем в формат long для Seaborn
        margin_ticker_long = margin_ticker.reset_index().melt(id_vars='ticker', var_name='margin_type', value_name='count')

        # Построение графика
        plt.figure(figsize=(20, 12))
        # Отдельно создаем массив для отрицательных значений
        negative_counts = margin_ticker_long[margin_ticker_long['margin_type'] == 'Отрицательная']['count'] if 'Отрицательная' in margin_ticker_long['margin_type'].values else []
        positive_counts = margin_ticker_long[margin_ticker_long['margin_type'] == 'Положительная']['count'] if 'Положительная' in margin_ticker_long['margin_type'].values else []

        # Устанавливаем ширину баров
        bar_width = 0.1
        x = range(len(margin_ticker_long['ticker'].unique()))

        # Определяем количество уникальных тикеров
        num_tickers = len(margin_ticker_long['ticker'].unique())

        # Рисуем положительные бары, если они существуют
        if len(positive_counts) > 0:
            plt.bar(x, positive_counts, width=bar_width, color='green', label='Положительная', align='center')

        # Рисуем отрицательные бары, если они существуют, с отрицательным значением для направления вниз
        if len(negative_counts) > 0:
            plt.bar(x, -negative_counts, width=bar_width, color='red', label='Отрицательная', align='center')

        # Настройка меток и заголовка
        plt.title('Количество продаж по тикерам')
        plt.xlabel('Тикер', labelpad=20)  # Уменьшите значение labelpad для уменьшения расстояния
        plt.ylabel('Количество продаж')
        plt.xticks(x, margin_ticker_long['ticker'].unique(), rotation=0)
        plt.axhline(0, color='black', linewidth=0.8)  # Линия по оси Y на нуле
        plt.legend()

        # Устанавливаем границы оси X, чтобы ограничить ширину графика
        plt.xlim(-0.5, num_tickers - 0.5)

        file_path = 'margin_ticker_histogram.png'
        plt.savefig(file_path)
        plt.close()
        with open(file_path, 'rb') as photo:
            bot.send_photo(chat_id, photo)
        os.remove(file_path)

        # 7. Гистограмма маржи по сигналам
        margin_df['margin_type'] = ['Положительная' if m > 0 else 'Отрицательная' for m in margin_df['margin']]
        margin_signal = margin_df.pivot_table(index='signal', columns='margin_type', aggfunc='size', fill_value=0)

        # Проверяем, какие столбцы есть в margin_signal и переименовываем их
        columns_mapping = {}
        if 'Положительная' in margin_signal.columns:
            columns_mapping['Положительная'] = 'Положительная'
        if 'Отрицательная' in margin_signal.columns:
            columns_mapping['Отрицательная'] = 'Отрицательная'

        margin_signal = margin_signal[list(columns_mapping.keys())]  # Убираем столбцы, которых нет

        # Преобразуем в формат long для Seaborn
        margin_signal_grouped_long = margin_signal.reset_index().melt(id_vars='signal', var_name='margin_type', value_name='count')

        plt.figure(figsize=(20, 12))
        # Отдельно создаем массив для отрицательных значений
        negative_signal_counts = margin_signal_grouped_long[margin_signal_grouped_long['margin_type'] == 'Отрицательная']['count'] if 'Отрицательная' in margin_signal_grouped_long['margin_type'].values else []
        positive_signal_counts = margin_signal_grouped_long[margin_signal_grouped_long['margin_type'] == 'Положительная']['count'] if 'Положительная' in margin_signal_grouped_long['margin_type'].values else []

        # Устанавливаем ширину баров
        bar_width = 0.1
        x = range(len(margin_signal_grouped_long['signal'].unique()))

        # Определяем, сколько уникальных значений сигнала
        num_signals = len(margin_signal_grouped_long['signal'].unique())

        # Рисуем положительные бары, если они существуют
        if len(positive_signal_counts) > 0:
            plt.bar(x, positive_signal_counts, width=bar_width, color='green', label='Положительная', align='center')

        # Рисуем отрицательные бары, если они существуют, с отрицательным значением для направления вниз
        if len(negative_signal_counts) > 0:
            plt.bar(x, -negative_signal_counts, width=bar_width, color='red', label='Отрицательная', align='center')

        # Настройка меток и заголовка
        plt.title('Количество продаж по сигналам')
        plt.xlabel('Сигнал', labelpad=20)  # Уменьшите значение labelpad для уменьшения расстояния
        plt.ylabel('Количество продаж')
        plt.xticks(x, margin_signal_grouped_long['signal'].unique(), rotation=0)
        plt.axhline(0, color='black', linewidth=0.8)  # Линия по оси Y на нуле
        plt.legend()

        # Устанавливаем границы оси X, чтобы ограничить ширину графика
        plt.xlim(-0.5, num_signals - 0.5)

        file_path = 'margin_signal_histogram.png'
        plt.savefig(file_path)
        plt.close()
        with open(file_path, 'rb') as photo:
            bot.send_photo(chat_id, photo)
        os.remove(file_path)

        # 8. Линейный график продаж по дням или часам
        margin_per_day = margin_df.groupby(margin_df['time'].dt.strftime('%d-%m-%Y')).size()
        plt.figure(figsize=(14, 9))
        if len(margin_per_day) > 1:
            margin_per_day.plot(kind='line', marker='o', color='purple')
            plt.title('Количество продаж по дням')
            plt.xlabel('Дата', labelpad=20)
            plt.ylabel('Количество продаж', labelpad=20)
            plt.xticks(rotation=0, ha='center', va='top')  
            plt.gca().tick_params(axis='x', pad=10)
            plt.subplots_adjust(bottom=0.2)  
        else:
            margin_per_hour = margin_df.groupby(margin_df['time'].dt.strftime('%H:%M')).size()
            margin_per_hour.plot(kind='bar', color='purple', width=0.1)
            plt.title('Количество продаж по часам')
            plt.xlabel('Время', labelpad=20)
            plt.ylabel('Количество продаж', labelpad=20)
            plt.xticks(rotation=0, ha='center', va='top')  
        plt.gca().tick_params(axis='x', pad=10)
        plt.subplots_adjust(bottom=0.2)  
        plt.xticks(rotation=0)
        file_path = 'sell_time_graph.png'
        plt.savefig(file_path)
        plt.close()
        with open(file_path, 'rb') as photo:
            bot.send_photo(chat_id, photo)
        os.remove(file_path)

        # 9. Общая сумма маржи
        total_margin_percent = margin_df['margin'].sum()
        bot.send_message(chat_id, f"Общая сумма маржи: {total_margin_percent}%")
