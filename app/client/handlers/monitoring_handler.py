"""Telegram control surface for per-user monitoring."""

from datetime import datetime, timezone
from io import BytesIO

from telebot import types

from app.client.bot.bot import bot
from app.client.handlers.user_context import resolve_telegram_user
from app.services.monitoring_settings import MonitoringSettingsService, SOURCE_URLS, validate_source
from app.services.user_context import UnknownUserError
from app.services.user_database import session_factory_for_user


def _service(chat_id):
    user = resolve_telegram_user(chat_id)
    return MonitoringSettingsService(session_factory_for_user(user), user)


def _display(chat_id):
    service = _service(chat_id)
    settings = service.get()
    locked = ", ".join(sorted((service.user.monitoring or {}).keys()))
    sources = "\n".join(f"• {s}" for s in settings.sources) or "• нет"
    bot.send_message(chat_id, (
        "🔔 Мониторинг\n"
        f"Срочные события: {'вкл' if settings.alerts_enabled else 'выкл'}\n"
        f"Дайджест: {'вкл' if settings.digest_enabled else 'выкл'} в {settings.digest_time} МСК, ежедневно\n"
        f"Охват ценовых уведомлений: {'весь рынок MOEX' if settings.scope == 'market' else 'счета + избранное'}\n"
        f"Порог срочного ценового события: {settings.threshold_pct:g}%\n"
        "Ежедневные графики: интересные события всего рынка, независимо от порога.\n"
        f"Сбор новостей: каждый час\nИсточники:\n{sources}\n\n"
        "Команды: /monitor_alerts on|off, /monitor_digest on|off, "
        "/monitor_scope owned|market, /monitor_threshold 5, /monitor_time 09:00, "
        "/monitor_source add|remove имя_или_HTTPS_URL\n"
        "Предпросмотр ежедневного обзора: /digest_preview\n"
        "Имена источников: " + ", ".join(SOURCE_URLS)
        + (f"\nПоля из users.json имеют приоритет: {locked}" if locked else "")
    ))
    bot.send_message(chat_id, _health(service)[:3900])


def _health(service):
    from app.backend.models.monitoring import NewsSourceState, ArticleAnalysisJob, DigestDelivery, MarketRefreshState
    from zoneinfo import ZoneInfo
    def stamp(value):
        return value.replace(tzinfo=timezone.utc).astimezone(ZoneInfo("Europe/Moscow")).strftime("%d.%m %H:%M МСК") if value else "ещё не было"
    lines = ["Состояние сбора и анализа"]
    with service.session_factory() as db:
        for source in service.get().sources:
            row = db.get(NewsSourceState, source)
            if not row:
                lines.append(f"• {source}: ещё не проверен")
            else:
                status = {"ok": "доступен", "partial": "неполный охват", "error": "недоступен"}.get(row.status, row.status)
                lines.append(f"• {source}: {status}; найдено {row.item_count}; успех {stamp(row.last_success_at)}")
        pending = db.query(ArticleAnalysisJob).filter(ArticleAnalysisJob.status.in_(("pending", "running"))).count()
        failed = db.query(ArticleAnalysisJob).filter_by(status="failed").count()
        lines.append(f"Очередь публикаций: {pending}; недоступных разборов: {failed}.")
        market = db.get(MarketRefreshState, 1)
        lines.append("История графиков: " + stamp(market.refreshed_at if market else None))
        delivery = db.query(DigestDelivery).order_by(DigestDelivery.report_date.desc()).first()
        if delivery:
            lines.append(f"Последний выпуск {delivery.report_date}: текст {'доставлен' if delivery.text_sent_at else 'ожидает'}, графики {'доставлены' if delivery.album_sent_at else 'ожидают'}.")
            if delivery.ambiguous:
                lines.append("При доставке был сетевой таймаут; возможен повтор неподтверждённой части.")
    return "\n".join(lines)


def send_digest_album(chat_id, charts):
    streams, media = [], []
    for chart in charts:
        stream = BytesIO(chart.png_bytes)
        stream.name = chart.ticker + ".png"
        streams.append(stream)
        media.append(types.InputMediaPhoto(stream, caption=chart.caption[:1024]))
    if len(media) == 1:
        return bot.send_photo(chat_id, streams[0], caption=charts[0].caption[:1024])
    return bot.send_media_group(chat_id, media)


@bot.message_handler(commands=["digest_preview"])
def digest_preview_handler(message):
    try:
        from app.services.daily_digest import DigestService
        service = _service(message.chat.id)
        draft = DigestService(service.session_factory, service.user).build()
        bot.send_message(message.chat.id, "Предпросмотр\n\n" + draft.text, disable_web_page_preview=True)
        if draft.charts:
            send_digest_album(message.chat.id, draft.charts)
    except UnknownUserError:
        bot.send_message(message.chat.id, "Этот чат не авторизован.")


@bot.message_handler(commands=["monitor", "monitor_alerts", "monitor_digest", "monitor_scope", "monitor_threshold", "monitor_time", "monitor_source"])
@bot.message_handler(func=lambda message: message.text == "Monitoring")
def monitoring_handler(message):
    chat_id = message.chat.id
    try:
        text = (message.text or "").strip()
        parts = text.split(maxsplit=2)
        command = parts[0].split("@")[0].lower()
        if command in {"/monitor", "monitoring"}:
            _display(chat_id)
            return
        if command in {"/monitor_alerts", "/monitor_digest"}:
            if len(parts) != 2 or parts[1] not in {"on", "off"}:
                raise ValueError("Используйте on или off.")
            field = "alerts_enabled" if command == "/monitor_alerts" else "digest_enabled"
            _service(chat_id).update(**{field: parts[1] == "on"})
        elif command == "/monitor_scope":
            if len(parts) != 2:
                raise ValueError("Используйте owned или market.")
            _service(chat_id).update(scope=parts[1])
        elif command == "/monitor_threshold":
            if len(parts) != 2:
                raise ValueError("Укажите процент, например 5.")
            _service(chat_id).update(threshold_pct=float(parts[1].replace(",", ".")))
        elif command == "/monitor_time":
            if len(parts) != 2:
                raise ValueError("Укажите время HH:MM по Москве.")
            _service(chat_id).update(digest_time=parts[1])
        elif command == "/monitor_source":
            if len(parts) != 3 or parts[1] not in {"add", "remove"}:
                raise ValueError("Используйте /monitor_source add|remove имя_или_HTTPS_URL")
            source = validate_source(parts[2])
            current = list(_service(chat_id).get().sources)
            if parts[1] == "add" and source not in current:
                current.append(source)
            if parts[1] == "remove":
                current = [item for item in current if item != source]
            _service(chat_id).update(sources=tuple(current))
        _display(chat_id)
    except UnknownUserError:
        bot.send_message(chat_id, "Этот чат не авторизован.")
    except (ValueError, TypeError) as exc:
        bot.send_message(chat_id, str(exc))


def send_cached_chart(chat_id: int, ticker: str, caption: str) -> bool:
    """Attach an already cached, fresh intraday chart; never fetch for an alert."""
    from matplotlib.figure import Figure
    from app.charts.repository import PriceCandleRepository

    user = resolve_telegram_user(chat_id)
    candles = PriceCandleRepository(session_factory_for_user(user)).list_candles(ticker=ticker, interval="hour")
    recent = [candle for candle in candles if candle.time.date() == datetime.now(timezone.utc).date()]
    if len(recent) < 2 or len(caption) > 1024:
        return False
    figure = Figure(figsize=(7, 3))
    axis = figure.subplots()
    axis.plot([candle.time for candle in recent], [candle.close for candle in recent])
    axis.set_title(ticker)
    axis.grid(alpha=0.2)
    figure.autofmt_xdate()
    stream = BytesIO()
    figure.savefig(stream, format="png", dpi=110)
    stream.seek(0)
    bot.send_photo(chat_id, stream, caption=caption)
    return True
