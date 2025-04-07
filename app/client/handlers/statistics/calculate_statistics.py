from datetime import datetime, timedelta
import pytz
from app.client.api.trading_client import TradingApiClient
from app.client.bot.bot import bot
from app.client.graphics.statistics_graph import statistics_graph
from app.client.handlers.utils.message_utils import send_or_edit_message

trading_client = TradingApiClient()

def filter_data_by_days(data, days):
    """
    Фильтрует данные по интервалу времени.
    
    Args:
        data: Список данных для фильтрации
        days: Количество дней для фильтрации
        
    Returns:
        list: Отфильтрованные данные
    """
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


def calculate_statistics(days, chat_id):
    """
    Основная функция для расчета статистики.
    
    Получает данные о покупках и прибыли, фильтрует их по интервалу времени и отображает график.
    
    Args:
        days: Количество дней для расчета статистики или 'full' для полной статистики
        chat_id: ID чата
    """
    try:
        # Отправляем сообщение о начале обработки
        send_or_edit_message(chat_id, "⏳ *Обработка запроса*\n\nРассчитываем статистику торговли...")
        
        # Получаем данные о покупках и прибыли через API-клиент
        buy = trading_client.get_buys()
        margin = trading_client.get_margins()
        
        if not buy and not margin:
            send_or_edit_message(chat_id, "ℹ️ *Информация*\n\nНет данных для вывода статистики.")
            return
        
        # Если указан интервал, фильтруем данные
        if days != 'full':
            days = int(days)  # Преобразуем days в целое число для использования в фильтрации
            buy = filter_data_by_days(buy, days)
            margin = filter_data_by_days(margin, days)
        
        # Проверяем, остались ли данные после фильтрации
        if not buy and not margin:
            send_or_edit_message(chat_id, f"ℹ️ *Информация*\n\nНет данных за последние `{days}` дней.")
            return
        
        # Отправляем сообщение о построении графика
        send_or_edit_message(chat_id, "📊 *Построение графика*\n\nГенерируем визуальное представление статистики...")
        
        # Отображаем график статистики
        statistics_graph(buy, margin, chat_id)
    
    except Exception as e:
        send_or_edit_message(chat_id, f"❌ *Ошибка при расчете статистики*\n\n`{str(e)}`")
