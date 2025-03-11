from app.client.bot.bot import bot
from app.backend.api_client import ApiClient
from app.client.utils.methods import get_dividends_data
from dotenv import load_dotenv
import os

# Создаем экземпляр API-клиента
api_client = ApiClient()

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
            bot.send_message(chat_id, "Токен не найден. Пожалуйста, проверьте настройки.")
            return
        
        msg = bot.send_message(chat_id, "Введите период окончания (в днях):")
        bot.register_next_step_handler(msg, handle_dividends_period, token)
    
    except Exception as e:
        bot.send_message(chat_id, f"Ошибка при получении токена: {str(e)}")


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
        
        # Получаем список всех инструментов
        instruments = api_client.get_all_instruments()
        
        if not instruments:
            bot.send_message(chat_id, "У вас нет активных инструментов.")
            return
        
        dividends_text = generate_dividends_report(token, period, instruments)
        bot.send_message(chat_id, dividends_text)
    
    except ValueError:
        msg = bot.send_message(chat_id, "Некорректный ввод. Введите числовое значение для периода:")
        bot.register_next_step_handler(msg, handle_dividends_period, token)
    
    except Exception as e:
        bot.send_message(chat_id, f"Ошибка при обработке периода: {str(e)}")


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
    report_text = 'Дивиденды:\n'
    
    try:
        for instrument in instruments:
            ticker = instrument.get('ticker')
            figi = instrument.get('figi')
            
            dividend_data = get_dividends_data(token, period, figi)
            
            if dividend_data:
                report_text += format_dividend_data(ticker, dividend_data)
        
        if report_text == 'Дивиденды:\n':
            return 'Дивиденды за выбранный период не найдены'
        
        return report_text
    
    except Exception as e:
        return f"Ошибка при генерации отчета о дивидендах: {str(e)}"


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
        f'\nТикер: {ticker}\n'
        f'Величина дивидента на 1 ценную бумагу (включая валюту): {data["dividend_net"]} руб.\n'
        f'Дата фактических выплат: {data["payment_date"]}\n'
        f'Дата объявления дивидендов: {data["declared_date"]}\n'
        f'Последний день (включительно) покупки для получения выплаты: {data["last_buy_date"]}\n'
        f'Дата фиксации реестра: {data["record_date"]}\n'
        f'Величина доходности: {data["yield_value"]}%\n'
    )
