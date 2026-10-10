"""Thin Telegram flows over explicit account/instrument contexts."""

from io import BytesIO

from telebot import types

from app.client.bot.bot import bot
from app.client.handlers.user_context import get_telegram_services_or_notify
from app.services.stock_market import MOSCOW, utc, instrument_key, delta, StockMarketService
from app.services.stock_tracking import parse_interval
from app.services.portfolio import percent


def send_long_text(chat_id, text, keyboard=None):
    chunks, current = [], ""
    for line in text.splitlines():
        for start in range(0, max(len(line), 1), 3500):
            piece = line[start:start + 3500]
            if len(current) + len(piece) + 1 > 3900:
                chunks.append(current)
                current = ""
            current += ("\n" if current else "") + piece
    chunks.append(current or "Нет данных.")
    for index, chunk in enumerate(chunks):
        bot.send_message(chat_id, chunk, reply_markup=keyboard if index == len(chunks) - 1 else None)


def stock_callback(action, account_id, key):
    data = f"stk:{action}:{account_id}:{key}"
    if len(data.encode("utf-8")) > 64:
        raise ValueError("Идентификатор позиции слишком длинный.")
    return data


def card_keyboard(account_id, key):
    keyboard = types.InlineKeyboardMarkup()
    for label, action in (("График", "graphs"), ("Заметки", "notes"), ("Слежение", "tracking"), ("Обновить", "card")):
        keyboard.add(types.InlineKeyboardButton(label, callback_data=stock_callback(action, account_id, key)))
    keyboard.add(types.InlineKeyboardButton("← К счёту", callback_data=f"portfolio:account:{account_id}"))
    return keyboard


def send_card(chat_id, services, account_id, key):
    account, position = services.stock_market_service.position(account_id, key)
    if not position:
        raise ValueError("Позиция больше не открыта на этом счёте. Заметки доступны через /notes.")
    quote = services.stock_market_service.quote(position)
    quote_fresh = StockMarketService.quote_is_current(quote, utc())
    text = (f"📌 {position.ticker} · {account.account.account_name}\nКоличество: {position.quantity_display}\n"
            f"Средняя цена: {position.average_price_display}\nТекущая цена позиции: {position.current_price_display}\n"
            f"Прибыль: {position.pnl_display} ({position.return_display})\n"
            f"Изменение цены за день: {percent(delta(quote.get('price'), quote.get('previous_close'))) if quote_fresh else 'нет свежей котировки'}")
    if account.captured_at:
        text += f"\nСнимок: {utc(account.captured_at).astimezone(MOSCOW):%d.%m %H:%M} МСК."
    if account.stale:
        text += "\n⚠️ Используется устаревший снимок: обновить счёт не удалось."
    send_long_text(chat_id, text, card_keyboard(account_id, key))


@bot.message_handler(commands=["stock"])
def stock_command(message):
    services = get_telegram_services_or_notify(message.chat.id)
    if services is None:
        return
    parts = (message.text or "").split()
    if len(parts) != 2:
        bot.send_message(message.chat.id, "Используйте /stock SBER или выберите акцию внутри счёта в портфеле.")
        return
    try:
        services.stock_market_service.refresh(force=True)
        matches = [(a, p) for a in services.stock_market_service.snapshots() for p in a.positions
                   if p.ticker.upper() == parts[1].upper() and p.quantity and (p.instrument_uid or p.figi)]
        if not matches:
            raise ValueError("Открытая позиция с таким тикером не найдена.")
        if len(matches) == 1:
            account, position = matches[0]
            send_card(message.chat.id, services, account.account.investment_account_id, instrument_key(position))
        else:
            keyboard = types.InlineKeyboardMarkup()
            for account, position in matches:
                keyboard.add(types.InlineKeyboardButton(account.account.account_name,
                    callback_data=stock_callback("card", account.account.investment_account_id, instrument_key(position))))
            bot.send_message(message.chat.id, "Выберите счёт для этой позиции:", reply_markup=keyboard)
    except ValueError as exc:
        bot.send_message(message.chat.id, str(exc))


def graph_keyboard(account_id, key):
    keyboard = types.InlineKeyboardMarkup()
    for label, period in (("День", "day"), ("Неделя", "week"), ("Месяц", "month")):
        keyboard.add(types.InlineKeyboardButton(label, callback_data=stock_callback("g_" + period, account_id, key)))
    keyboard.add(types.InlineKeyboardButton("← Карточка акции", callback_data=stock_callback("card", account_id, key)))
    return keyboard


def send_stock_chart(chat_id, services, position, account_id, key, period="month"):
    chart = services.stock_chart_service.render(position, period)
    stream = BytesIO(chart.png_bytes)
    stream.name = position.ticker + ".png"
    bot.send_photo(chat_id, stream, caption=(position.ticker + "\n" + chart.summary)[:1000],
                   reply_markup=graph_keyboard(account_id, key))


def tracking_menu(chat_id, services, account_id, key):
    current = services.stock_tracking_service.get(account_id, key)
    labels = {"active": "включено", "paused": "пауза", "disabled": "отключено"}
    text = "Слежение: " + (labels[current.status] if current else "не настроено")
    if current:
        period = {"day": "день", "week": "неделя", "month": "месяц"}[current.chart_range]
        text += f"\nКаждые {current.interval_minutes} мин; график: {period}."
        if current.error:
            text += "\nПоследняя ошибка: " + current.error
    text += "\nТекст и график во время биржевых торгов. Выбор частоты или периода включает слежение."
    keyboard = types.InlineKeyboardMarkup()
    keyboard.row(*(types.InlineKeyboardButton(f"{minutes} мин", callback_data=stock_callback(f"ti_{minutes}", account_id, key))
                   for minutes in (5, 10, 30, 60)))
    keyboard.add(types.InlineKeyboardButton("Своя частота", callback_data=stock_callback("custom", account_id, key)))
    keyboard.row(*(types.InlineKeyboardButton(label, callback_data=stock_callback("tp_" + period, account_id, key))
                   for label, period in (("День", "day"), ("Неделя", "week"), ("Месяц", "month"))))
    if current:
        keyboard.add(types.InlineKeyboardButton("Пауза", callback_data=stock_callback("pause", account_id, key)),
                     types.InlineKeyboardButton("Возобновить", callback_data=stock_callback("resume", account_id, key)),
                     types.InlineKeyboardButton("Отключить", callback_data=stock_callback("disable", account_id, key)))
    bot.send_message(chat_id, text, reply_markup=keyboard)


@bot.callback_query_handler(func=lambda call: call.data.startswith("stk:"))
def stock_action(call):
    bot.answer_callback_query(call.id)
    chat_id = call.message.chat.id
    services = get_telegram_services_or_notify(chat_id)
    if services is None:
        return
    try:
        _, action, account_text, key = call.data.split(":", 3)
        account_id = int(account_text)
        services.account_registry.get_account_context(account_id)
        if action == "card":
            services.stock_market_service.refresh(force=True)
            send_card(chat_id, services, account_id, key)
            return
        account, position = services.stock_market_service.position(account_id, key)
        if not position:
            raise ValueError("Позиция больше не открыта. Сохранённые заметки доступны через /notes.")
        if action == "notes":
            send_notes(chat_id, services, key)
        elif action == "graphs":
            send_stock_chart(chat_id, services, position, account_id, key)
        elif action.startswith("g_"):
            send_stock_chart(chat_id, services, position, account_id, key, action[2:])
        elif action == "tracking":
            tracking_menu(chat_id, services, account_id, key)
        elif action == "custom":
            prompt = bot.send_message(chat_id, "Введите интервал от 5 до 1440 минут. /cancel — отмена.")
            bot.register_next_step_handler(prompt, custom_interval, account_id, key)
        elif action.startswith("ti_") or action.startswith("tp_"):
            services.stock_market_service.refresh(force=True)
            current = services.stock_tracking_service.get(account_id, key)
            services.stock_tracking_service.configure(account_id, key,
                interval_minutes=parse_interval(action[3:]) if action.startswith("ti_") else current.interval_minutes if current else 30,
                chart_range=action[3:] if action.startswith("tp_") else current.chart_range if current else "day")
            tracking_menu(chat_id, services, account_id, key)
        elif action in {"pause", "resume", "disable"}:
            if action == "resume":
                services.stock_market_service.refresh(force=True)
            services.stock_tracking_service.set_status(account_id, key, {"pause": "paused", "resume": "active", "disable": "disabled"}[action])
            tracking_menu(chat_id, services, account_id, key)
    except (ValueError, LookupError) as exc:
        bot.send_message(chat_id, str(exc))
    except Exception:
        bot.send_message(chat_id, "Не удалось выполнить действие. Повторите позже.")


def custom_interval(message, account_id, key):
    services = get_telegram_services_or_notify(message.chat.id)
    if services is None:
        return
    if not message.text or message.text.startswith("/"):
        bot.send_message(message.chat.id, "Настройка отменена.")
        return
    try:
        minutes = parse_interval(message.text)
        services.stock_market_service.refresh(force=True)
        current = services.stock_tracking_service.get(account_id, key)
        services.stock_tracking_service.configure(account_id, key, interval_minutes=minutes,
                                                  chart_range=current.chart_range if current else "day")
        tracking_menu(message.chat.id, services, account_id, key)
    except ValueError as exc:
        prompt = bot.send_message(message.chat.id, str(exc) + " /cancel — отмена.")
        bot.register_next_step_handler(prompt, custom_interval, account_id, key)


def note_instruments(services):
    result = {note.instrument_key: note.ticker for note in services.stock_notes_service.list()}
    for account in services.stock_market_service.snapshots():
        for position in account.positions:
            if position.quantity and (position.instrument_uid or position.figi):
                result[instrument_key(position)] = position.ticker
    return result


def send_notes(chat_id, services, key):
    ticker = note_instruments(services).get(key)
    if not ticker:
        raise ValueError("Инструмент заметки недоступен.")
    notes = services.stock_notes_service.list(key)
    bot.send_message(chat_id, f"📝 {ticker}: общие заметки для всех ваших счетов.")
    for note in notes:
        keyboard = types.InlineKeyboardMarkup()
        keyboard.add(types.InlineKeyboardButton("Редактировать", callback_data=f"note:edit:{note.id}"),
                     types.InlineKeyboardButton("Удалить", callback_data=f"note:delete:{note.id}"))
        bot.send_message(chat_id, f"{utc(note.created_at).astimezone(MOSCOW):%d.%m.%Y %H:%M} МСК\n"
            f"Изменена: {utc(note.updated_at).astimezone(MOSCOW):%d.%m.%Y %H:%M} МСК\n{note.text}", reply_markup=keyboard)
    keyboard = types.InlineKeyboardMarkup()
    keyboard.add(types.InlineKeyboardButton("Добавить заметку", callback_data=f"note:add:{key}"))
    bot.send_message(chat_id, "Заметок пока нет." if not notes else "Добавить ещё одну заметку:", reply_markup=keyboard)


@bot.message_handler(commands=["notes"])
@bot.message_handler(func=lambda message: message.text == "Заметки")
def notes_command(message):
    services = get_telegram_services_or_notify(message.chat.id)
    if services is None:
        return
    instruments = note_instruments(services)
    parts = (message.text or "").split()
    if len(parts) == 2:
        instruments = {key: ticker for key, ticker in instruments.items() if ticker.upper() == parts[1].upper()}
    if len(instruments) == 1:
        send_notes(message.chat.id, services, next(iter(instruments)))
    elif instruments:
        keyboard = types.InlineKeyboardMarkup()
        for key, ticker in sorted(instruments.items(), key=lambda item: item[1]):
            keyboard.add(types.InlineKeyboardButton(ticker, callback_data=f"note:list:{key}"))
        bot.send_message(message.chat.id, "Выберите акцию:", reply_markup=keyboard)
    else:
        bot.send_message(message.chat.id, "Нет сохранённых заметок или позиций. Откройте портфель, затем выберите акцию.")


@bot.callback_query_handler(func=lambda call: call.data.startswith("note:"))
def note_action(call):
    bot.answer_callback_query(call.id)
    chat_id = call.message.chat.id
    services = get_telegram_services_or_notify(chat_id)
    if services is None:
        return
    try:
        _, action, value = call.data.split(":", 2)
        if action == "list":
            send_notes(chat_id, services, value)
            return
        if action == "add":
            ticker = note_instruments(services).get(value)
            if not ticker:
                raise ValueError("Инструмент недоступен.")
            prompt = bot.send_message(chat_id, f"Введите заметку к {ticker} (до 3000 символов). /cancel — отмена.")
            bot.register_next_step_handler(prompt, save_note, "add", value, ticker)
            return
        note = services.stock_notes_service.get(int(value))
        if action == "edit":
            prompt = bot.send_message(chat_id, "Введите новый текст заметки. /cancel — отмена.")
            bot.register_next_step_handler(prompt, save_note, "edit", note.id, note.ticker)
        elif action == "delete":
            keyboard = types.InlineKeyboardMarkup()
            keyboard.add(types.InlineKeyboardButton("Подтвердить удаление", callback_data=f"note:confirm:{note.id}"),
                         types.InlineKeyboardButton("Отмена", callback_data=f"note:list:{note.instrument_key}"))
            bot.send_message(chat_id, "Удалить эту заметку?", reply_markup=keyboard)
        elif action == "confirm":
            services.stock_notes_service.delete(note.id)
            bot.send_message(chat_id, "Заметка удалена.")
    except ValueError as exc:
        bot.send_message(chat_id, str(exc))


def save_note(message, action, value, ticker):
    services = get_telegram_services_or_notify(message.chat.id)
    if services is None:
        return
    if not message.text or message.text.startswith("/"):
        bot.send_message(message.chat.id, "Редактирование отменено.")
        return
    try:
        if action == "add":
            if value not in note_instruments(services):
                raise ValueError("Инструмент недоступен.")
            note = services.stock_notes_service.add(value, ticker, message.text)
        else:
            note = services.stock_notes_service.edit(value, message.text)
        send_notes(message.chat.id, services, note.instrument_key)
    except ValueError as exc:
        prompt = bot.send_message(message.chat.id, str(exc) + " /cancel — отмена.")
        bot.register_next_step_handler(prompt, save_note, action, value, ticker)
