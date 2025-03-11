from app.client.bot.bot import bot
from app.backend.api_client import ApiClient
from app.client.utils.methods import get_portfolio
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


@bot.message_handler(func=lambda message: message.text == 'Получить портфолио')
def get_portfolio_handler(message):
    """
    Обработчик для получения информации о портфолио.
    
    Отображает информацию о портфолио пользователя.
    """
    chat_id = message.chat.id
    
    try:
        # Получаем токен из переменных окружения
        tokens = get_tokens()
        token = tokens["token"]
        
        if not token:
            bot.send_message(chat_id, "Токен не найден. Пожалуйста, проверьте настройки.")
            return
        
        # Получаем информацию о портфолио
        portfolio = get_portfolio(token)
        
        if not portfolio:
            bot.send_message(chat_id, "Не удалось получить информацию о портфолио.")
            return
        
        positions = portfolio['positions']
        
        # Формируем текст сообщения с общей информацией о портфолио
        text = (
            f"Общая стоимость акций: {portfolio['total_amount_shares']} руб.\n"
            f"Общая стоимость облигаций: {portfolio['total_amount_bonds']} руб.\n"
            f"Общая стоимость фондов: {portfolio['total_amount_etf']} руб.\n"
            f"Общая стоимость валют: {portfolio['total_amount_currencies']} руб.\n"
            f"Ожидаемая доходность: {portfolio['expected_yield']} %\n"
            f"Общая стоимость портфеля: {portfolio['total_amount_portfolio']} руб.\n"
        )
        
        # Добавляем информацию о каждой позиции в портфолио
        for position in positions:
            text += (
                f"\nТикер: {position['ticker']}\n"
                f"Figi: {position['figi']}\n"
                f"Тип: {position['type']}\n"
                f"Количество: {position['quantity']}\n"
                f"Средневзвешенная цена: {position['average_position_price']}\n"
                f"Ожидаемая доходность: {position['expected_yield']}\n"
                f"Текущая цена: {position['current_price']}\n"
                f"Состояние: {position['blocked']}\n"
            )
        
        bot.send_message(chat_id, text)
    
    except Exception as e:
        bot.send_message(chat_id, f"Ошибка при получении портфолио: {str(e)}")
