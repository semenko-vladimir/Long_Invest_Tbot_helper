from app.client.api.instruments_client import InstrumentsApiClient
from app.client.bot.bot import bot
from app.client.handlers.utils.message_utils import send_or_edit_message, last_messages
from app.client.utils.methods import get_dividends_data
from dotenv import load_dotenv
import os

instruments_client = InstrumentsApiClient()

# Функция для получения токенов из переменных окружения
def get_tokens():
    """
    Получает токены из переменных окружения.
    
    Returns:
        dict: Словарь с токенами
    """
    load_dotenv()
    return {
        "token": os.getenv('TOKEN'),
        "sandbox_token": os.getenv('SANDBOX_TOKEN')
    }


# Функция для остановки обработчика дивидендов
def stop_dividends_handler(chat_id):
    """
    Останавливает обработчик дивидендов для указанного чата.
    
    Args:
        chat_id: ID чата
    """
    if chat_id in last_messages:
        del last_messages[chat_id]


@bot.message_handler(func=lambda message: message.text == 'Дивиденды')
def dividends_handler(message):
    """
    Обработчик для получения информации о дивидендах.
    
    Запрашивает у пользователя период окончания для поиска дивидендов.
    """
    chat_id = message.chat.id
    
    try:
        # Получаем токен из переменных окружения
        tokens = get_tokens()
        token = tokens["token"]
        
        if not token:
            # Отправляем сообщение об ошибке
            msg = bot.send_message(
                chat_id=chat_id,
                text="❌ *Токен не найден*\nПожалуйста, проверьте настройки.",
                parse_mode='Markdown'
            )
            last_messages[chat_id] = msg.message_id
            return
        
        # Отправляем новое сообщение для запроса периода
        msg = bot.send_message(
            chat_id=chat_id,
            text="📅 *Дивиденды*\n\nВведите период окончания (в днях):",
            parse_mode='Markdown'
        )
        
        # Сохраняем ID сообщения для последующего редактирования
        last_messages[chat_id] = msg.message_id
        
        bot.register_next_step_handler(msg, handle_dividends_period, token)
    
    except Exception as e:
        msg = bot.send_message(
            chat_id=chat_id,
            text=f"❌ *Ошибка при получении токена*\n`{str(e)}`",
            parse_mode='Markdown'
        )
        last_messages[chat_id] = msg.message_id


def handle_dividends_period(message, token):
    """
    Обработчик для получения периода окончания.
    
    Получает период окончания и генерирует отчет о дивидендах.
    
    Args:
        message: Сообщение пользователя
        token: Токен API
    """
    chat_id = message.chat.id
    
    try:
        period = int(message.text)
        
        # Отправляем сообщение о начале обработки
        send_or_edit_message(chat_id, "⏳ *Обработка запроса*\nПолучаем информацию о дивидендах...")
        
        # Получаем список всех инструментов
        instruments = instruments_client.get_all_instruments()
        
        if not instruments:
            send_or_edit_message(chat_id, "📊 *Информация о дивидендах*\n\n❌ У вас нет активных инструментов.")
            return
        
        dividends_text = generate_dividends_report(token, period, instruments)
        send_or_edit_message(chat_id, dividends_text)
    
    except ValueError:
        msg = send_or_edit_message(chat_id, "❌ *Некорректный ввод*\n\nВведите числовое значение для периода:")
        bot.register_next_step_handler(msg, handle_dividends_period, token)
    
    except Exception as e:
        send_or_edit_message(chat_id, f"❌ *Ошибка при обработке периода*\n`{str(e)}`")


def generate_dividends_report(token, period, instruments):
    """
    Генерирует отчет о дивидендах.
    
    Args:
        token: Токен API
        period: Период окончания в днях
        instruments: Список инструментов
        
    Returns:
        str: Текст отчета о дивидендах
    """
    report_text = '📊 *ИНФОРМАЦИЯ О ДИВИДЕНДАХ*\n\n'
    
    try:
        found_dividends = False
        
        for instrument in instruments:
            ticker = instrument.get('ticker')
            figi = instrument.get('figi')
            
            dividend_data = get_dividends_data(token, period, figi)
            
            if dividend_data:
                found_dividends = True
                report_text += format_dividend_data(ticker, dividend_data)
        
        if not found_dividends:
            return '📊 *ИНФОРМАЦИЯ О ДИВИДЕНДАХ*\n\n❌ Дивиденды за выбранный период не найдены'
        
        return report_text
    
    except Exception as e:
        return f"❌ *Ошибка при генерации отчета о дивидендах*\n`{str(e)}`"


def format_dividend_data(ticker, data):
    """
    Форматирует данные о дивидендах.
    
    Args:
        ticker: Тикер инструмента
        data: Данные о дивидендах
        
    Returns:
        str: Отформатированный текст о дивидендах
    """
    return (
        f'\n🔸 *Тикер: {ticker}*\n'
        f'💰 Дивиденд: `{data["dividend_net"]} руб.`\n'
        f'📅 Дата выплат: `{data["payment_date"]}`\n'
        f'📣 Дата объявления: `{data["declared_date"]}`\n'
        f'🛒 Последний день покупки: `{data["last_buy_date"]}`\n'
        f'📝 Дата фиксации реестра: `{data["record_date"]}`\n'
        f'📈 Доходность: `{data["yield_value"]}%`\n'
    )
