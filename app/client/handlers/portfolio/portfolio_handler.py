from app.client.bot.bot import bot
from app.client.utils.methods import get_portfolio
from dotenv import load_dotenv
import os

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


# Добавим словарь с эмодзи
EMOJIS = {
    'portfolio': '💼',
    'stocks': '📈',
    'bonds': '📊',
    'etf': '📉',
    'currency': '💵',
    'yield': '💰',
    'total': '💎',
    'ticker': '🔖',
    'type': '📋',
    'quantity': '🔢',
    'avg_price': '⚖️',
    'current': '💱',
    'state': '🔒',
    'warning': '⚠️',
    'error': '❌',
    'info': 'ℹ️'
}

def format_money(amount):
    """Форматирует денежную сумму"""
    return f"{float(amount):,.2f}₽".replace(',', ' ')

@bot.message_handler(func=lambda message: message.text == 'Получить портфолио')
def get_portfolio_handler(message):
    chat_id = message.chat.id
    
    try:
        tokens = get_tokens()
        token = tokens["token"]
        
        if not token:
            bot.send_message(
                chat_id,
                f"{EMOJIS['error']} *Токен не найден*\nПожалуйста, проверьте настройки.",
                parse_mode='Markdown'
            )
            return
        
        portfolio = get_portfolio(token)
        
        if not portfolio:
            bot.send_message(
                chat_id,
                f"{EMOJIS['warning']} *Не удалось получить информацию о портфолио*",
                parse_mode='Markdown'
            )
            return
        
        # Форматируем основную информацию о портфолио
        portfolio_summary = (
            f"{EMOJIS['portfolio']} *СОСТОЯНИЕ ПОРТФЕЛЯ*\n"
            f"{EMOJIS['stocks']} Акции: {format_money(portfolio['total_amount_shares'])}\n"
            f"{EMOJIS['bonds']} Облигации: {format_money(portfolio['total_amount_bonds'])}\n"
            f"{EMOJIS['etf']} Фонды: {format_money(portfolio['total_amount_etf'])}\n"
            f"{EMOJIS['currency']} Валюты: {format_money(portfolio['total_amount_currencies'])}\n"
            f"{EMOJIS['yield']} Доходность: {portfolio['expected_yield']}%\n"
            f"{EMOJIS['total']} *Общая стоимость: {format_money(portfolio['total_amount_portfolio'])}*\n\n"
        )

        # Форматируем информацию о позициях
        positions_info = f"{EMOJIS['info']} *ПОЗИЦИИ В ПОРТФЕЛЕ:*\n\n"
        
        for position in portfolio['positions']:
            positions_info += (
                f"{EMOJIS['ticker']} *{position['ticker']}*\n"
                f"├─ {EMOJIS['type']} Тип: {position['type']}\n"
                f"├─ {EMOJIS['quantity']} Количество: {position['quantity']}\n"
                f"├─ {EMOJIS['avg_price']} Ср. цена: {format_money(position['average_position_price'])}\n"
                f"├─ {EMOJIS['current']} Текущая: {format_money(position['current_price'])}\n"
                f"├─ {EMOJIS['yield']} Доходность: {position['expected_yield']}руб.\n"
                f"└─ {EMOJIS['state']} Статус: {position['blocked']}\n\n"
            )

        # Отправляем сообщения отдельно для лучшей читаемости
        bot.send_message(chat_id, portfolio_summary, parse_mode='Markdown')
        bot.send_message(chat_id, positions_info, parse_mode='Markdown')
    
    except Exception as e:
        bot.send_message(
            chat_id,
            f"{EMOJIS['error']} *Ошибка при получении портфолио:*\n`{str(e)}`",
            parse_mode='Markdown'
        )
