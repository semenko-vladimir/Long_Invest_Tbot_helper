"""Read-only market/news monitoring and per-user Telegram delivery."""

import hashlib
import json
import logging
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from sqlalchemy.exc import IntegrityError

from app.backend.models.accounts import PortfolioSnapshot, PositionSnapshot
from app.backend.models.monitoring import MonitoringEvent, MonitoringRun
from app.integrations.moex_iss import MOEXISSClient
from app.integrations.moex_market_monitor import fetch_stock_quotes
from app.services.monitoring_settings import MonitoringSettingsService
from app.services.news_analysis import RuleNewsAnalyzer
from app.services.news_sources import fetch_feed
from app.services.user_context import UserContext
from app.services.user_database import session_factory_for_user


logger = logging.getLogger(__name__)
MOSCOW = ZoneInfo("Europe/Moscow")


def utc_naive(value: datetime) -> datetime:
    return value.astimezone(timezone.utc).replace(tzinfo=None)


class MonitoringRunner:
    def __init__(self, user: UserContext, *, send_text, send_chart=None, quote_fetcher=None, feed_fetcher=None, analyzer=None):
        self.user = user
        self.session_factory = session_factory_for_user(user)
        self.settings_service = MonitoringSettingsService(self.session_factory, user)
        self.send_text = send_text
        self.send_chart = send_chart
        self.quote_fetcher = quote_fetcher or (lambda today: fetch_stock_quotes(MOEXISSClient(), today))
        self.feed_fetcher = feed_fetcher or fetch_feed
        self.analyzer = analyzer or RuleNewsAnalyzer()

    def run(self, now: datetime | None = None) -> None:
        now = now or datetime.now(timezone.utc)
        settings = self.settings_service.get()
        if not (settings.alerts_enabled or settings.digest_enabled):
            return
        accounts_by_ticker, names = self._interests()
        failures = []
        try:
            quotes = self.quote_fetcher(now.astimezone(MOSCOW).date())
            self._record_prices(quotes, settings, accounts_by_ticker, now)
            names.update({ticker: quote.name for ticker, quote in quotes.items() if ticker not in names})
        except Exception:
            failures.append("MOEX ISS")
            logger.exception("Market monitor failed for user_id=%s", self.user.user_id)
        failures.extend(self._record_news(settings, names, accounts_by_ticker, now))
        if settings.alerts_enabled:
            self._send_alerts(settings, accounts_by_ticker, now)
        if settings.digest_enabled:
            self._send_digest_if_due(settings, now, failures)

    def _interests(self):
        # Existing account snapshots preserve account identity and avoid broker reads on each poll.
        from app.client.handlers.user_context import build_telegram_services

        services = build_telegram_services(self.user)
        accounts = tuple(account for account in services.account_registry.list_enabled_accounts()
                         if str(account.status or "").lower() == "open")
        if not accounts:
            try:
                accounts = services.account_registry.sync_accounts().accounts
            except Exception:
                logger.warning("Account discovery failed for monitoring user_id=%s", self.user.user_id)
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
                        by_ticker[position.ticker].append(account)
                        names[position.ticker] = position.name
                else:
                    for position in db.query(PositionSnapshot).filter(
                        PositionSnapshot.portfolio_snapshot_id == snapshot.id
                    ):
                        by_ticker[position.ticker].append(account)
            for item in services.watchlist_service.list_items().items:
                names[item.ticker] = item.name if item.name != item.ticker else ""
                by_ticker.setdefault(item.ticker, [])
        finally:
            db.close()
        return by_ticker, names

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

    def _record_news(self, settings, names, accounts_by_ticker, now):
        cutoff = utc_naive(now - timedelta(days=2))
        contexts = tuple({a.investment_account_id: a for group in accounts_by_ticker.values() for a in group}.values())
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
                assessment = self.analyzer.assess(item, names, contexts)
                if not assessment.important:
                    continue
                if settings.scope == "owned" and assessment.ticker and assessment.ticker not in accounts_by_ticker:
                    continue
                key = "news:" + hashlib.sha256(item.url.encode("utf-8")).hexdigest()
                self._record(key, "news", assessment.ticker, item.title, item.source, item.published_at, item.url,
                             {"reason": assessment.reason}, now)
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

    def _send_alerts(self, settings, accounts_by_ticker, now):
        db = self.session_factory()
        try:
            pending = db.query(MonitoringEvent).filter(
                MonitoringEvent.delivered_at.is_(None),
                MonitoringEvent.observed_at >= utc_naive(now - timedelta(minutes=10)),
            ).order_by(MonitoringEvent.published_at).all()
            for event in pending:
                if event.kind == "news" and event.published_at < utc_naive(now - timedelta(minutes=30)):
                    continue
                if settings.scope == "owned" and event.ticker and event.ticker not in accounts_by_ticker:
                    continue
                text = self._format_event(event, accounts_by_ticker)
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

    def _format_event(self, event, accounts_by_ticker):
        lines = ["📈 Движение цены" if event.kind == "price" else "📰 Новость", event.title]
        if event.ticker:
            lines.append(f"Бумага: {event.ticker}")
        for account in accounts_by_ticker.get(event.ticker, ()):
            strategy = account.strategy.title if account.strategy and account.strategy.title else "без стратегии"
            lines.append(f"Счёт: {account.account_name} · {strategy}")
        lines.append(f"Источник: {event.source} · {event.published_at.strftime('%d.%m %H:%M')} UTC")
        if event.kind == "price":
            lines.append("MOEX ISS: данные могут поступать с задержкой.")
        if event.url:
            lines.append(event.url)
        return "\n".join(lines)

    def _send_digest_if_due(self, settings, now, failures):
        local = now.astimezone(MOSCOW)
        hour, minute = map(int, settings.digest_time.split(":"))
        if (local.hour, local.minute) < (hour, minute):
            return
        db = self.session_factory()
        try:
            run = db.get(MonitoringRun, 1)
            if run is None:
                run = MonitoringRun(id=1)
                db.add(run)
            today_start = datetime.combine(local.date(), datetime.min.time(), tzinfo=MOSCOW)
            if run.last_digest_at and run.last_digest_at >= utc_naive(today_start):
                return
            since = run.last_digest_at or utc_naive(now - timedelta(days=1))
            events = db.query(MonitoringEvent).filter(MonitoringEvent.observed_at > since).order_by(MonitoringEvent.observed_at.desc()).limit(30).all()
            news = [event for event in events if event.kind == "news"][:8]
            prices = [event for event in events if event.kind == "price"][:8]
            lines = [f"☀️ Утренний дайджест · {local:%d.%m.%Y}", "", "Новости:"]
            lines += [f"• {event.title}\n{event.url}" for event in news] or ["• За период важных новостей не найдено."]
            lines += ["", "Движения:"]
            lines += [f"• {event.title}" for event in prices] or ["• Значительных движений не найдено."]
            if failures:
                lines += ["", "⚠️ Данные неполные: недоступны " + ", ".join(failures)]
            self.send_text(self.user.telegram_chat_id, "\n".join(lines)[:3900])
            run.last_digest_at = utc_naive(now)
            db.commit()
        except Exception:
            db.rollback()
            logger.exception("Digest failed for user_id=%s", self.user.user_id)
        finally:
            db.close()
