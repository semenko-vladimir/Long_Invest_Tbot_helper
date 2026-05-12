from app.client.bot.bot import bot
from app.client.handlers.user_context import get_telegram_services_or_notify

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

@bot.message_handler(func=lambda message: message.text in {'Portfolio', 'Получить портфолио'})
def get_portfolio_handler(message):
    chat_id = message.chat.id
    
    try:
        services = get_telegram_services_or_notify(chat_id)
        if services is None:
            return

        portfolio = services.portfolio_service.get_portfolio_view()

        if portfolio.error:
            bot.send_message(
                chat_id,
                f"{EMOJIS['error']} *Ошибка портфеля*\n{portfolio.error}",
                parse_mode='Markdown'
            )
            return

        if portfolio.empty:
            bot.send_message(
                chat_id,
                f"{EMOJIS['warning']} *Портфель пуст*",
                parse_mode='Markdown'
            )
            return
        
        # Форматируем основную информацию о портфолио
        portfolio_summary = (
            f"{EMOJIS['portfolio']} *СОСТОЯНИЕ ПОРТФЕЛЯ*\n"
            f"{EMOJIS['info']} Пользователь: {services.user.display_name}\n"
            f"{EMOJIS['info']} Режим: {portfolio.mode.mode}\n"
            f"{EMOJIS['total']} *Общая стоимость: {portfolio.total_value_display}*\n\n"
        )

        # Форматируем информацию о позициях
        positions_info = f"{EMOJIS['info']} *ПОЗИЦИИ В ПОРТФЕЛЕ:*\n\n"
        
        for position in portfolio.positions:
            positions_info += (
                f"{EMOJIS['ticker']} *{position.ticker}*\n"
                f"├─ {EMOJIS['type']} Название: {position.name}\n"
                f"├─ {EMOJIS['quantity']} Количество: {position.quantity_display}\n"
                f"├─ {EMOJIS['avg_price']} Ср. цена: {position.average_price_display}\n"
                f"├─ {EMOJIS['current']} Текущая: {position.current_price_display}\n"
                f"└─ {EMOJIS['yield']} Доходность: {position.pnl_display} ({position.return_display})\n\n"
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
