from datetime import datetime, timedelta
import pytz
from bot.bot import bot
from db.db import get_buy, get_margin
from graphics.statistics_graph import statistics_graph

# Функция для фильтрации по интервалу времени
def filter_data_by_days(data, days):
    # Установим текущую дату и время по московскому времени
    moscow_tz = pytz.timezone('Europe/Moscow')
    now = datetime.now(moscow_tz)
    
    # Начало сегодняшнего дня
    start_of_today = now.replace(hour=0, minute=0, second=0, microsecond=0)
    
    # Если days = 1, интервал с начала текущего дня до текущего момента
    if days == 1:
        start_time = start_of_today
    else:
        # Если days > 1, интервал с начала (days-1) дней назад до текущего момента
        start_time = start_of_today - timedelta(days=days - 1)
    
    # Отфильтруем записи, у которых время лежит между start_time и текущим моментом
    filtered_data = [
        row for row in data 
        if start_time <= datetime.strptime(row[-2], '%d-%m-%Y %H:%M').replace(tzinfo=moscow_tz) <= now
    ]

    return filtered_data


# Основная функция
def calculate_statistics(days, chat_id):
    buy = get_buy(chat_id)
    margin = get_margin(chat_id)
    
    if days != 'full':
        days = int(days)  # Преобразуем days в целое число для использования в фильтрации
        buy = filter_data_by_days(buy, days)
        margin = filter_data_by_days(margin, days)

    if len(buy) == 0 and len(margin) == 0:
        bot.send_message(chat_id, "Нет данных для вывода статистики.")
    else:
        statistics_graph(buy, margin, chat_id)