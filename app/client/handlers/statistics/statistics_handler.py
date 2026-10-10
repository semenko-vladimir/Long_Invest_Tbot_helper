from app.client.bot.bot import bot
from telebot import types
from app.client.handlers.user_context import get_telegram_services_or_notify
from app.client.handlers.statistics.calculate_statistics import calculate_statistics
from app.client.handlers.utils.message_utils import send_or_edit_message
from app.services.stock_market import MOSCOW, utc, instrument_key, delta, StockMarketService
from app.services.portfolio import money, percent, signed_money

@bot.message_handler(func=lambda message: message.text in {'Stats', 'Statistics', 'Статистика'})
def statistics_handler(message):
    """
    Основной обработчик для раздела "Статистика".
    
    Отображает меню с доступными опциями для работы со статистикой.
    """
    send_current_statistics(message.chat.id)


def format_current_statistics(view):
    lines = ["📊 Портфель и рынок", f"Стоимость счетов: {money(view.total_value) if view.total_value is not None else 'недоступна'}",
             f"Нереализованная прибыль позиций: {signed_money(view.unrealized_pnl) if view.total_value is not None else 'недоступна'}"]
    if view.partial:
        lines.append("⚠️ Есть устаревшие или недоступные данные; итог включает последний успешный снимок доступных счетов.")
    if view.error:
        lines.append(view.error)
    index = view.index
    if index:
        lines.append(f"\nIMOEX: {index['price']:.2f} · за день {percent(index.get('change_pct'))}")
        lines.append(f"Данные индекса: {index.get('as_of_date') or 'дата не установлена'}; MOEX ISS, возможна задержка.")
        if index.get("fetched_at"):
            from datetime import datetime, timedelta
            fetched = utc(datetime.fromisoformat(index["fetched_at"]))
            lines.append(f"Индекс получен: {fetched.astimezone(MOSCOW):%d.%m %H:%M} МСК"
                         + (" · кэш устарел" if utc() - fetched > timedelta(minutes=6) else ""))
    else:
        lines.append("\nIMOEX: данные недоступны.")
    for account in view.accounts:
        label = money(account.total_value) if account.total_value is not None else "недоступно"
        lines.append(f"\n{account.account.account_name}: {label}")
        if account.captured_at:
            lines.append(f"Снимок: {utc(account.captured_at).astimezone(MOSCOW):%d.%m %H:%M} МСК" + (" · устарел" if account.stale else ""))
        for position in account.positions:
            quote = view.quotes.get(instrument_key(position), {}) if position.instrument_uid or position.figi else {}
            quote_fresh = StockMarketService.quote_is_current(quote, utc())
            weight = position.market_value / account.total_value * 100 if account.total_value else None
            weight_label = f"{weight:.2f}%" if weight is not None else "недоступна"
            lines.append(f"• {position.ticker}: {position.current_price_display} · доля {weight_label}\n"
                         f"  Прибыль {position.pnl_display} ({position.return_display}); цена за день {percent(delta(quote.get('price'), quote.get('previous_close'))) if quote_fresh else 'нет свежей котировки'}")
            if quote_fresh and quote.get("time"):
                from datetime import datetime
                lines.append(f"  Последняя сделка: {utc(datetime.fromisoformat(quote['time'])).astimezone(MOSCOW):%d.%m %H:%M} МСК.")
    lines.extend(["", "Движение цен за день не является доходностью счёта с учётом пополнений и сделок.",
                  "Фоновое обновление — каждые 5 минут во время торгов, без рассылки."])
    return "\n".join(lines)


def send_current_statistics(chat_id):
    services = get_telegram_services_or_notify(chat_id)
    if services is None:
        return
    try:
        view = services.statistics_service.get_current_view()
        text = format_current_statistics(view)
        keyboard = types.InlineKeyboardMarkup()
        keyboard.add(types.InlineKeyboardButton("Обновить", callback_data="stat_current"))
        keyboard.add(types.InlineKeyboardButton("История локальных сделок", callback_data="stat_full"),
                     types.InlineKeyboardButton("История за период", callback_data="stat_interval"))
        from app.client.handlers.stocks.stock_handler import send_long_text
        send_long_text(chat_id, text, keyboard)
    except Exception:
        bot.send_message(chat_id, "Не удалось получить статистику. Повторите обновление позже.")


@bot.callback_query_handler(func=lambda call: call.data == 'stat_current')
def current_statistics_callback(call):
    bot.answer_callback_query(call.id)
    send_current_statistics(call.message.chat.id)


@bot.callback_query_handler(func=lambda call: call.data == 'stat_interval')
def stat_interval_handler(call):
    """
    Обработчик для выбора интервала статистики.
    
    Запрашивает у пользователя количество дней для расчета статистики.
    """
    chat_id = call.message.chat.id
    
    try:
        msg = send_or_edit_message(chat_id, "*Interval*\n\nEnter the number of days to include (1 to 365):")
        bot.register_next_step_handler(msg, validate_days)
    
    except Exception as e:
        send_or_edit_message(chat_id, f"*Interval error*\n\n`{str(e)}`")


def validate_days(message):
    """
    Обработчик для валидации количества дней.
    
    Проверяет, что введенное значение является целым числом от 1 до 365.
    """
    chat_id = message.chat.id
    
    try:
        days = int(message.text)
        
        if 1 <= days <= 365:
            days = str(days)
            services = get_telegram_services_or_notify(chat_id)
            if services is None:
                return
            send_or_edit_message(chat_id, f"*Processing*\n\nCalculating statistics for the last {days} days...")
            calculate_statistics(days, chat_id, services.statistics_service)
        else:
            msg = send_or_edit_message(chat_id, "*Input error*\n\nEnter a value from 1 to 365:")
            bot.register_next_step_handler(msg, validate_days)
    
    except ValueError:
        msg = send_or_edit_message(chat_id, "*Input error*\n\nEnter an integer:")
        bot.register_next_step_handler(msg, validate_days)
    
    except Exception as e:
        send_or_edit_message(chat_id, f"*Input processing error*\n\n`{str(e)}`")


@bot.callback_query_handler(func=lambda call: call.data == 'stat_full')
def stat_full_handler(call):
    """
    Обработчик для получения общей статистики.
    
    Вызывает функцию расчета статистики с параметром 'full'.
    """
    chat_id = call.message.chat.id
    
    try:
        services = get_telegram_services_or_notify(chat_id)
        if services is None:
            return
        send_or_edit_message(chat_id, "*Processing*\n\nCalculating full statistics...")
        calculate_statistics('full', chat_id, services.statistics_service)
    
    except Exception as e:
        send_or_edit_message(chat_id, f"*Statistics error*\n\n`{str(e)}`")
