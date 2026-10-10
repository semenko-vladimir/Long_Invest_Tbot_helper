"""Read-only market/news monitoring and per-user Telegram delivery."""

import json
import logging
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from sqlalchemy.exc import IntegrityError

from app.backend.models.accounts import PortfolioSnapshot, PositionSnapshot
from app.backend.models.monitoring import MonitoringEvent, MonitoringRun, DigestDelivery
from app.integrations.moex_market_monitor import fetch_monitoring_quotes
from app.services.monitoring_settings import MonitoringSettingsService
from app.services.news_analysis import RuleNewsAnalyzer
from app.services.news_queue import NewsQueue
from app.services.news_sources import fetch_feed
from app.services.monitoring_config import MonitoringLimits
from app.services.user_context import UserContext
from app.services.user_database import session_factory_for_user


logger = logging.getLogger(__name__)
MOSCOW = ZoneInfo("Europe/Moscow")


def utc_naive(value: datetime) -> datetime:
    return value.astimezone(timezone.utc).replace(tzinfo=None)


def event_payload(event):
    try:
        value = json.loads(event.payload_json or "{}")
    except (ValueError, TypeError):
        return {}
    return value if isinstance(value, dict) else {}


class MonitoringRunner:
    def __init__(self, user: UserContext, *, send_text, send_chart=None, send_album=None, quote_fetcher=None, feed_fetcher=None, analyzer=None):
        self.user = user
        self.session_factory = session_factory_for_user(user)
        self.settings_service = MonitoringSettingsService(self.session_factory, user)
        self.send_text = send_text
        self.send_chart = send_chart
        self.quote_fetcher = quote_fetcher or fetch_monitoring_quotes
        self.feed_fetcher = feed_fetcher or fetch_feed
        self.news_queue = NewsQueue(self.session_factory, user, prefilter=analyzer or RuleNewsAnalyzer())
        from app.services.daily_digest import DigestService, DigestDeliveryService
        self.digest_service = DigestService(self.session_factory, user)
        self.digest_delivery = DigestDeliveryService(self.session_factory, user, send_text=send_text, send_album=send_album)
        self.limits = MonitoringLimits.from_env()

    def run(self, now: datetime | None = None, *, include_news=True) -> None:
        now = now or datetime.now(timezone.utc)
        settings = self.settings_service.get()
        if not (settings.alerts_enabled or settings.digest_enabled):
            return
        failures = []
        try:
            accounts_by_ticker, names, accounts = self._interests()
        except Exception:
            accounts_by_ticker, names, accounts = {}, {}, ()
            failures.append("Счета: данные временно недоступны")
            logger.warning("Monitoring account context unavailable user_id=%s", self.user.user_id)
        try:
            quotes = self.quote_fetcher(now.astimezone(MOSCOW).date())
            self._record_prices(quotes, settings, accounts_by_ticker, now)
            names.update({ticker: quote.name for ticker, quote in quotes.items() if ticker not in names})
        except Exception:
            failures.append("MOEX ISS")
            logger.exception("Market monitor failed for user_id=%s", self.user.user_id)
        if include_news:
            failures.extend(self._record_news(settings, names, accounts_by_ticker, accounts, now))
        if settings.alerts_enabled:
            self._send_alerts(settings, accounts_by_ticker, accounts, now)
        if settings.digest_enabled:
            self._send_digest_if_due(settings, accounts, now, failures)

    def _interests(self):
        # Existing account snapshots preserve account identity and avoid broker reads on each poll.
        from app.client.handlers.user_context import build_telegram_services

        services = build_telegram_services(self.user)
        try:
            discovered = services.account_registry.sync_accounts().accounts
        except Exception:
            logger.warning("Account discovery failed for monitoring user_id=%s", self.user.user_id)
            discovered = services.account_registry.list_enabled_accounts()
        accounts = tuple(account for account in discovered if str(account.status or "").lower() == "open")
        by_ticker = defaultdict(list)
        names = {}
        db = self.session_factory()
        try:
            for account in accounts:
                snapshot = db.query(PortfolioSnapshot).filter(
                    PortfolioSnapshot.investment_account_id == account.investment_account_id
                ).order_by(PortfolioSnapshot.captured_at.desc()).first()
                if snapshot is None or snapshot.captured_at < datetime.utcnow() - timedelta(days=2):
                    view = services.portfolio_service.get_account_portfolio(account)
                    for position in view.positions:
                        if not position.quantity:
                            continue
                        by_ticker[position.ticker].append(account)
                        names[position.ticker] = position.name
                else:
                    for position in db.query(PositionSnapshot).filter(
                        PositionSnapshot.portfolio_snapshot_id == snapshot.id,
                        PositionSnapshot.investment_account_id == account.investment_account_id,
                    ):
                        if not position.quantity:
                            continue
                        by_ticker[position.ticker].append(account)
            for item in services.watchlist_service.list_items().items:
                names[item.ticker] = item.name if item.name != item.ticker else ""
                by_ticker.setdefault(item.ticker, [])
        finally:
            db.close()
        return by_ticker, names, accounts

    def _record_prices(self, quotes, settings, accounts_by_ticker, now):
        for ticker, quote in quotes.items():
            if settings.scope == "owned" and ticker not in accounts_by_ticker:
                continue
            if abs(quote.change_pct) < settings.threshold_pct:
                continue
            direction = "up" if quote.change_pct > 0 else "down"
            key = f"price:{quote.trade_date}:{ticker}:{direction}"
            title = f"{ticker}: {quote.change_pct:+.2f}% к предыдущему закрытию ({quote.last:.2f} ₽)"
            self._record(key, "price", ticker, title, "MOEX ISS", now, None, {"change_pct": quote.change_pct}, now)

    def _record_news(self, settings, names, accounts_by_ticker, accounts, now):
        cutoff = utc_naive(now - timedelta(days=2))
        failures = []
        for source in settings.sources:
            try:
                items = self.feed_fetcher(source)
            except Exception:
                failures.append(source)
                logger.exception("News source failed: source=%s user_id=%s", source, self.user.user_id)
                continue
            for item in items:
                published = utc_naive(item.published_at)
                if published < cutoff or published > utc_naive(now + timedelta(minutes=10)):
                    continue
                try:
                    self.news_queue.enqueue(item, names, accounts_by_ticker, accounts, settings.scope, now)
                except Exception:
                    if source not in failures:
                        failures.append(source)
                    logger.exception("News intake failed: source=%s user_id=%s", source, self.user.user_id)
        return failures

    def _record(self, key, kind, ticker, title, source, published, url, payload, observed):
        db = self.session_factory()
        try:
            db.add(MonitoringEvent(event_key=key, kind=kind, ticker=ticker, title=title, source=source,
                                   published_at=utc_naive(published), observed_at=utc_naive(observed),
                                   url=url, payload_json=json.dumps(payload)))
            db.commit()
        except IntegrityError:
            db.rollback()
        finally:
            db.close()

    def _send_alerts(self, settings, accounts_by_ticker, accounts, now):
        account_by_id = {account.investment_account_id: account for account in accounts}
        db = self.session_factory()
        try:
            pending = db.query(MonitoringEvent).filter(
                MonitoringEvent.delivered_at.is_(None),
                MonitoringEvent.observed_at >= utc_naive(now - timedelta(minutes=10)),
            ).order_by(MonitoringEvent.published_at).all()
            for event in pending:
                if event.kind == "news" and event.source not in settings.sources:
                    continue
                if event.kind == "news" and event.published_at < utc_naive(now - timedelta(hours=3)):
                    continue
                payload = event_payload(event)
                if event.kind == "news" and payload.get("analysis_status", "").startswith("article_"):
                    analysis = payload.get("analysis") or {}
                    if (payload.get("analysis_status") != "article_model" or payload.get("importance", 0) < self.limits.urgent_importance
                            or not payload.get("publication_time_known") or analysis.get("evidence_scope") == "headline"):
                        continue
                    hour_count = db.query(MonitoringEvent).filter(MonitoringEvent.kind == "news",
                        MonitoringEvent.delivered_at >= utc_naive(now - timedelta(hours=1))).count()
                    today = datetime.combine(now.astimezone(MOSCOW).date(), datetime.min.time(), tzinfo=MOSCOW)
                    day_count = db.query(MonitoringEvent).filter(MonitoringEvent.kind == "news", MonitoringEvent.delivered_at >= utc_naive(today)).count()
                    if hour_count >= self.limits.news_alerts_per_hour or day_count >= self.limits.news_alerts_per_day:
                        continue
                if event.investment_account_id and event.investment_account_id not in account_by_id:
                    continue
                if settings.scope == "owned" and event.ticker and event.ticker not in accounts_by_ticker:
                    continue
                text = self._format_event(event, accounts_by_ticker, accounts)
                try:
                    sent_chart = False
                    if event.kind == "price" and self.send_chart:
                        try:
                            sent_chart = self.send_chart(self.user.telegram_chat_id, event.ticker, text)
                        except Exception:
                            logger.warning("Cached chart unavailable for event_id=%s", event.id)
                    if not sent_chart:
                        self.send_text(self.user.telegram_chat_id, text)
                    event.delivered_at = utc_naive(now)
                    db.commit()
                except Exception:
                    db.rollback()
                    logger.exception("Telegram monitoring delivery failed user_id=%s event_id=%s", self.user.user_id, event.id)
                    break
        finally:
            db.close()

    def _format_event(self, event, accounts_by_ticker, accounts=()):
        payload = event_payload(event)
        if event.kind == "news" and payload.get("analysis_status", "").startswith("article_"):
            analysis = payload.get("analysis") or {}
            lines = ["📰 Важная новость · разбор Qwen", event.title, analysis.get("summary", ""), analysis.get("reason", "")]
            names = {account.investment_account_id: account.account_name for account in accounts}
            affected = [names[identifier] for identifier in payload.get("account_ids", ()) if identifier in names]
            if affected:
                lines.append("Затронутые счета: " + ", ".join(affected))
            if analysis.get("uncertainty"):
                lines.append("Ограничение: " + analysis["uncertainty"])
            stamp = event.published_at.replace(tzinfo=timezone.utc).astimezone(MOSCOW)
            lines.append(f"{event.source} · {stamp:%d.%m %H:%M} МСК")
            lines.append(event.url or "")
            return "\n".join(line for line in lines if line)[:3900]
        lines = ["📈 Движение цены" if event.kind == "price" else "📰 Новость", event.title]
        if event.ticker:
            lines.append(f"Бумага: {event.ticker}")
        account_id = getattr(event, "investment_account_id", None)
        if account_id:
            affected = (account for account in accounts if account.investment_account_id == account_id)
        else:
            affected = accounts_by_ticker.get(event.ticker, ())
        for account in affected:
            strategy = account.strategy.title if account.strategy and account.strategy.title else "без стратегии"
            lines.append(f"Счёт: {account.account_name} · {strategy}")
        if event.kind == "news" and event.payload_json:
            try:
                payload = json.loads(event.payload_json)
            except (TypeError, ValueError, AttributeError):
                payload = {}
            reason = payload.get("reason") if isinstance(payload, dict) else None
            if reason:
                label = "Оценка модели" if payload.get("analysis_status") == "model" else "Причина отбора"
                lines.append(f"{label}: {reason}")
            if isinstance(payload, dict) and payload.get("analysis_status") == "model":
                analysis = payload.get("analysis") or {}
                direction = {"positive": "положительное", "negative": "отрицательное",
                             "mixed": "смешанное", "neutral": "нейтральное", "unknown": "неизвестно"}
                lines.append("Разбор Qwen · справочная оценка")
                lines.append("Возможное влияние: " + direction.get(analysis.get("impact"), "неизвестно"))
                for fact in (analysis.get("facts") or [])[:4]:
                    lines.append("• " + str(fact)[:180])
                for limitation in (analysis.get("limitations") or [])[:3]:
                    lines.append("Ограничение: " + str(limitation)[:180])
            elif isinstance(payload, dict) and payload.get("analysis_status") == "unavailable":
                lines.append("Анализ модели недоступен; показан отбор по правилам.")
        lines.append(f"Источник: {event.source} · {event.published_at.strftime('%d.%m %H:%M')} UTC")
        if event.kind == "price":
            lines.append("MOEX ISS: данные могут поступать с задержкой.")
        if event.url:
            lines.append(event.url)
        return "\n".join(lines)

    def _send_digest_if_due(self, settings, accounts, now, failures):
        local = now.astimezone(MOSCOW)
        hour, minute = map(int, settings.digest_time.split(":"))
        if (local.hour, local.minute) < (hour, minute):
            return
        from app.services.daily_digest import DigestDraft
        with self.session_factory() as db:
            run = db.get(MonitoringRun, 1)
            today_start = datetime.combine(local.date(), datetime.min.time(), tzinfo=MOSCOW)
            if run and run.last_digest_at and run.last_digest_at >= utc_naive(today_start):
                return
            delivery = db.get(DigestDelivery, local.date().isoformat())
            saved = delivery.payload_json if delivery else None
        try:
            draft = DigestDraft.deserialize(saved) if saved else self.digest_service.build(local.date(), now=now)
            if failures and not saved:
                text = draft.text[:3500] + "\n\nПолнота текущего опроса: " + ", ".join(failures)[:300]
                draft = DigestDraft(draft.report_date, text, draft.charts, draft.coverage)
            self.digest_delivery.deliver(draft, now)
        except Exception:
            logger.exception("Digest failed for user_id=%s", self.user.user_id)

    @staticmethod
    def _digest_news_line(event, account_names):
        account = f" · {account_names[event.investment_account_id]}" if event.investment_account_id in account_names else ""
        try:
            payload = json.loads(event.payload_json or "{}")
        except (TypeError, ValueError):
            payload = {}
        status = payload.get("analysis_status") if isinstance(payload, dict) else None
        note = " · разбор Qwen по RSS" if status == "model" else " · модель недоступна" if status == "unavailable" else ""
        return f"• {event.title}{account}{note}\nИсточник: {event.source} · {event.url}"
