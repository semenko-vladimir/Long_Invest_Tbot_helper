from app.client.bot.bot import bot
from app.client.handlers.user_context import get_telegram_services_or_notify
from app.client.handlers.utils.message_utils import send_or_edit_message, last_messages


# Функция для остановки обработчика дивидендов
def stop_dividends_handler(chat_id):
    """
    Останавливает обработчик дивидендов для указанного чата.
    
    Args:
        chat_id: ID чата
    """
    if chat_id in last_messages:
        del last_messages[chat_id]


@bot.message_handler(func=lambda message: message.text in {'Dividends', 'Дивиденды'})
def dividends_handler(message):
    """
    Обработчик для получения информации о дивидендах.
    
    Запрашивает у пользователя период окончания для поиска дивидендов.
    """
    chat_id = message.chat.id
    
    try:
        services = get_telegram_services_or_notify(chat_id)
        if services is None:
            return
        
        # Отправляем новое сообщение для запроса периода
        msg = bot.send_message(
            chat_id=chat_id,
            text="📅 *Дивиденды*\n\nВведите период окончания (в днях):",
            parse_mode='Markdown'
        )
        
        # Сохраняем ID сообщения для последующего редактирования
        last_messages[chat_id] = msg.message_id
        
        bot.register_next_step_handler(msg, handle_dividends_period, services.dividends_service)
    
    except Exception as e:
        msg = bot.send_message(
            chat_id=chat_id,
            text=f"❌ *Ошибка при подготовке дивидендов*\n`{str(e)}`",
            parse_mode='Markdown'
        )
        last_messages[chat_id] = msg.message_id


def handle_dividends_period(message, dividends_service):
    """
    Обработчик для получения периода окончания.
    
    Получает период окончания и генерирует отчет о дивидендах.
    
    Args:
        message: Сообщение пользователя
        dividends_service: Сервис дивидендов активного пользователя
    """
    chat_id = message.chat.id
    
    try:
        period = int(message.text)
        
        # Отправляем сообщение о начале обработки
        send_or_edit_message(chat_id, "⏳ *Обработка запроса*\nПолучаем информацию о дивидендах...")
        
        dividends_view = dividends_service.get_dividends_view(period)
        send_or_edit_message(chat_id, generate_dividends_report(dividends_view))
    
    except ValueError:
        msg = send_or_edit_message(chat_id, "❌ *Некорректный ввод*\n\nВведите числовое значение для периода:")
        bot.register_next_step_handler(msg, handle_dividends_period, dividends_service)
    
    except Exception as e:
        send_or_edit_message(chat_id, f"❌ *Ошибка при обработке периода*\n`{str(e)}`")


def generate_dividends_report(dividends_view):
    """
    Генерирует отчет о дивидендах.
    
    Args:
        dividends_view: Представление дивидендов
        
    Returns:
        str: Текст отчета о дивидендах
    """
    report_text = '📊 *ИНФОРМАЦИЯ О ДИВИДЕНДАХ*\n\n'

    if dividends_view.error:
        return f"{report_text}❌ {dividends_view.error}"

    if dividends_view.empty_watchlist:
        return f"{report_text}❌ У вас нет активных инструментов."

    found_dividends = False
    for item in dividends_view.items:
        if item.has_data:
            found_dividends = True
            report_text += format_dividend_data(item)

    if not found_dividends:
        return f"{report_text}❌ Дивиденды за выбранный период не найдены"

    return report_text


def format_dividend_data(item):
    """
    Форматирует данные о дивидендах.
    
    Args:
        item: Данные о дивидендах
        
    Returns:
        str: Отформатированный текст о дивидендах
    """
    return (
        f'\n🔸 *Тикер: {item.ticker}*\n'
        f'💰 Дивиденд: `{item.expected_dividend}`\n'
        f'📅 Дата выплат: `{item.next_dividend_date}`\n'
        f'🛒 Последний день покупки: `{item.last_buy_date}`\n'
        f'📝 Дата фиксации реестра: `{item.record_date}`\n'
        f'📈 Доходность: `{item.estimated_yield}`\n'
    )
