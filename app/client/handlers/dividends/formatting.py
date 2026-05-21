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

    if dividends_view.portfolio_error:
        report_text += f"⚠️ {dividends_view.portfolio_error}\n\n"

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
        f'📦 Текущая позиция: `{item.position_quantity_display}`\n'
        f'💰 Дивиденд на акцию: `{item.expected_dividend_per_share_display}`\n'
        f'🧮 Оценка дивиденда по позиции: `{item.expected_total_dividend_display}`\n'
        f'📅 Дата выплат: `{item.next_dividend_date}`\n'
        f'🛒 Последний день покупки: `{item.last_buy_date}`\n'
        f'📝 Дата фиксации реестра: `{item.record_date}`\n'
        f'📈 Доходность: `{item.estimated_yield}`\n'
    )
