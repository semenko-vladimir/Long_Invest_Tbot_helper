"""Cached daily market/news drafts and independently acknowledged delivery parts."""

import base64
import json
import logging
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from difflib import SequenceMatcher
from threading import Lock
from zoneinfo import ZoneInfo

from sqlalchemy import or_
from sqlalchemy.exc import IntegrityError

from app.backend.models.accounts import InvestmentAccount, PortfolioSnapshot, PositionSnapshot
from app.backend.models.trading import Instrument
from app.backend.models.monitoring import (
    ArticleAnalysisJob, DigestDelivery, MarketRefreshState, MarketReport,
    MonitoringEvent, MonitoringRun, NewsAnalysisJob, NewsArticle, NewsSourceState,
)
from app.charts.images import ChartImageService
from app.charts.repository import PriceCandleRepository
from app.services.article_news_analysis import market_catalog, prefilter_priority
from app.services.market_news_queue import content_hash, item_from_article, utc_naive
from app.services.market_screening import MarketCandidate, MarketScreeningService
from app.services.monitoring_settings import MonitoringSettingsService
from app.services.ollama_news_analysis import _plain_summary


logger = logging.getLogger(__name__)
MOSCOW = ZoneInfo("Europe/Moscow")


@dataclass(frozen=True)
class DigestChart:
    ticker: str
    png_bytes: bytes
    caption: str


@dataclass(frozen=True)
class DigestDraft:
    report_date: str
    text: str
    charts: tuple[DigestChart, ...]
    coverage: tuple[str, ...] = ()

    def serialize(self):
        return json.dumps({"report_date": self.report_date, "text": self.text, "coverage": self.coverage,
            "charts": [{"ticker": chart.ticker, "caption": chart.caption, "image": base64.b64encode(chart.png_bytes).decode("ascii")}
                       for chart in self.charts]}, ensure_ascii=False)

    @classmethod
    def deserialize(cls, value):
        data = json.loads(value)
        return cls(data["report_date"], data["text"], tuple(DigestChart(chart["ticker"], base64.b64decode(chart["image"]), chart["caption"])
            for chart in data["charts"]), tuple(data.get("coverage", ())))


def owned_interest(factory, now):
    """Only current source-account snapshots contribute ownership facts."""
    tickers, account_names, by_ticker = set(), {}, {}
    with factory() as db:
        tickers.update(row.ticker for row in db.query(Instrument))
        accounts = db.query(InvestmentAccount).filter(InvestmentAccount.enabled.is_(True)).all()
        for account in accounts:
            if str(account.status or "").lower() != "open" or account.broker_connection is None or not account.broker_connection.enabled:
                continue
            account_names[account.id] = account.display_name
            snapshot = db.query(PortfolioSnapshot).filter_by(investment_account_id=account.id).order_by(PortfolioSnapshot.captured_at.desc()).first()
            if not snapshot or snapshot.captured_at < utc_naive(now - timedelta(days=2)):
                continue
            rows = db.query(PositionSnapshot).filter_by(portfolio_snapshot_id=snapshot.id, investment_account_id=account.id)
            for row in rows:
                if not row.quantity:
                    continue
                tickers.add(row.ticker)
                by_ticker.setdefault(row.ticker, []).append(account.id)
    return tickers, account_names, by_ticker


class DigestService:
    def __init__(self, factory, user, *, renderer=None, screening=None):
        self.factory, self.user = factory, user
        self.repository = PriceCandleRepository(factory)
        self.renderer = renderer or ChartImageService(history_service=None)
        self.screening = screening or MarketScreeningService(factory)

    def build(self, report_date=None, *, now=None):
        now = now or datetime.now(timezone.utc)
        report_date = report_date or now.astimezone(MOSCOW).date()
        settings = MonitoringSettingsService(self.factory, self.user).get()
        owned, account_names, by_ticker = owned_interest(self.factory, now)
        coverage = []
        with self.factory() as db:
            report = db.get(MarketReport, report_date.isoformat())
            selected = [MarketCandidate(**value) for value in json.loads(report.selected_json or "[]")] if report else []
            selection_status = report.selection_status if report else "algorithm"
            if selection_status == "unavailable":
                coverage.append("Подборка Qwen недоступна; показан алгоритмический отбор.")
            elif selection_status == "pending_model":
                coverage.append("Подборка Qwen ещё не готова; показан алгоритмический отбор.")
            if report:
                coverage.extend(json.loads(report.coverage_json))
            else:
                coverage.append("Рыночная подборка ещё не подготовлена; используются доступные сохранённые данные.")
            state = db.get(MarketRefreshState, 1)
            universe = json.loads(state.universe_json) if state else {}
            states = {row.source: row for row in db.query(NewsSourceState).filter(NewsSourceState.source.in_(settings.sources))}
            for source in settings.sources:
                state_row = states.get(source)
                if not state_row:
                    coverage.append(source + ": сбор ещё не выполнен")
                elif state_row.status == "error":
                    coverage.append(source + ": источник недоступен")
                elif state_row.status == "partial":
                    coverage.append(source + ": охват неполный")
                if state_row and state_row.status != "error" and (not state_row.last_success_at or state_row.last_success_at < utc_naive(now - timedelta(hours=2))):
                    coverage.append(source + ": обновление задерживается")
            pending = db.query(ArticleAnalysisJob).filter(ArticleAnalysisJob.status.in_(("pending", "running"))).count()
        if not selected:
            selected = self.screening.scan(report_date, owned_tickers=owned)[:3]
        candles = lambda ticker: [bar for bar in self.repository.list_candles(ticker=ticker, interval="day") if bar.time.date() < report_date]
        index = candles("IMOEX")
        blocks = [f"☀️ Обзор рынка · {report_date:%d.%m.%Y}"]
        if len(index) >= 2:
            change = (index[-1].close / index[-2].close - 1) * 100
            blocks.append(f"Рынок: IMOEX {change:+.2f}% · {index[-1].close:.2f}\nПоследняя завершённая сессия: {index[-1].time:%d.%m.%Y}.")
            with self.factory() as db:
                previous = db.get(MarketReport, (report_date - timedelta(days=1)).isoformat())
                same_session = previous and previous.as_of_date == index[-1].time.date().isoformat()
            if same_session and len(index) >= 6:
                weekly = (index[-1].close / index[-6].close - 1) * 100
                blocks.append(f"Новой завершённой сессии нет. IMOEX за последние пять сессий: {weekly:+.2f}%.")
        else:
            blocks.append("Котировки индекса пока недоступны. Ниже — доступные новости и сохранённые наблюдения.")
        charts, chart_tickers = [], set()
        if selected:
            blocks.append("Интересные движения" + (" · отбор Qwen" if selection_status == "model" else " · алгоритмический отбор"))
        for candidate in selected[:3]:
            reason = candidate.selection_reason or " ".join(candidate.reasons[:2])
            owners = [account_names[account] for account in by_ticker.get(candidate.ticker, ()) if account in account_names]
            text = f"• {candidate.ticker} · {candidate.name}: {candidate.change_pct:+.2f}%\n{reason[:320]}"
            if owners:
                text += "\nВ твоём портфеле: " + ", ".join(owners)
            if candidate.notes:
                text += "\n" + "; ".join(candidate.notes)
            blocks.append(text)
            try:
                chart = self.renderer.render_cached_history_png(candidate.ticker, candles(candidate.ticker), name=candidate.name,
                    reason=reason, range_bounds=(candidate.range_low, candidate.range_high), notes=candidate.notes)
                charts.append(DigestChart(candidate.ticker, chart, text[:1000] + f"\nДанные за {candidate.as_of_date}."))
                chart_tickers.add(candidate.ticker)
            except Exception:
                coverage.append("График " + candidate.ticker + ": недоступен")
        if not selected:
            blocks.append("Обзорные графики: показываем доступную историю рынка без утверждения о необычных событиях.")
        # Fill incomplete selections with distinct, explicitly labelled market overviews.
        for ticker in ["IMOEX", *sorted(universe)]:
            if len(charts) >= 3:
                break
            if ticker in chart_tickers:
                continue
            history = candles(ticker)
            if len(history) < 2:
                continue
            name = "Индекс МосБиржи" if ticker == "IMOEX" else universe[ticker].get("short_name") or universe[ticker]["name"]
            reason = "Обзор сохранённой истории; выраженное необычное событие не выделено."
            try:
                image = self.renderer.render_cached_history_png(ticker, history, name=name, reason=reason)
                charts.append(DigestChart(ticker, image, f"{ticker} · {name}\n{reason}\nПоследняя сессия: {history[-1].time:%d.%m.%Y}."))
                chart_tickers.add(ticker)
            except Exception:
                coverage.append("График " + ticker + ": недоступен")
        news = self.news_lines(settings.sources, now, owned, account_names)
        blocks.append("Новости и экономические события")
        blocks.extend(news or ["Свежих подходящих публикаций в доступных источниках пока нет; обзор рынка приведён выше."])
        if pending:
            blocks.append(f"Ещё {pending} публикаций ожидают анализа; готовая сводка отправляется вовремя.")
        footer = "Полнота данных: " + "; ".join(dict.fromkeys(coverage))[:600] if coverage else ""
        if len(charts) < 3:
            blocks.append(f"Доступно графиков: {len(charts)} из 3; недостающая история не предоставлена источником.")
        text = ""
        for block in blocks:
            if len(text) + len(block) + len(footer) + 4 <= 3900:
                text += ("\n\n" if text else "") + block
        if footer:
            text += "\n\n" + footer
        return DigestDraft(report_date.isoformat(), text, tuple(charts), tuple(dict.fromkeys(coverage)))

    def news_lines(self, sources, now, owned, account_names):
        selected, excluded_urls = [], set()
        with self.factory() as db:
            state = db.get(MarketRefreshState, 1)
            universe = json.loads(state.universe_json) if state else {}
            catalog = market_catalog(universe)
            articles = db.query(NewsArticle).filter(NewsArticle.source.in_(sources),
                NewsArticle.published_at >= utc_naive(now - timedelta(days=2)),
                NewsArticle.published_at <= utc_naive(now + timedelta(minutes=10))).order_by(NewsArticle.published_at.desc()).limit(300).all()
            for article in articles:
                job = db.query(ArticleAnalysisJob).filter_by(article_id=article.id).order_by(ArticleAnalysisJob.created_at.desc()).first()
                result = json.loads(job.result_json) if job and job.result_json and job.content_hash == content_hash(item_from_article(article)) else None
                if result and not result["relevant"]:
                    excluded_urls.add(article.url)
                    continue
                priority = result["importance"] if result else job.priority if job else prefilter_priority(item_from_article(article), catalog, owned)
                if not priority:
                    continue
                tickers = result.get("tickers", ()) if result else ()
                priority += 5 if set(tickers) & owned else 0
                note = "разбор Qwen" if result and result.get("model") != "rules" else "модель недоступна" if job and job.status == "failed" else "без оценки LLM" if result else "анализ ещё не завершён"
                summary = result["summary"] if result else _plain_summary(article.summary)[:350] or article.title
                reason = result.get("reason", "") if result and result.get("model") != "rules" else ""
                body = f"• {_plain_summary(article.title)}\n{summary[:400]}"
                if reason:
                    body += "\n" + reason[:250]
                    if result.get("uncertainty"):
                        body += "\nОграничение: " + result["uncertainty"][:180]
                accounts = db.query(NewsAnalysisJob).filter_by(article_id=article.id, status="done").all()
                for account_job in accounts[:2]:
                    if account_job.content_hash and account_job.content_hash != content_hash(item_from_article(article)):
                        continue
                    if account_job.investment_account_id in account_names and account_job.result_json:
                        details = json.loads(account_job.result_json)
                        if details.get("important"):
                            body += "\n" + account_names[account_job.investment_account_id] + ": " + details.get("reason", "")[:180]
                stamp = article.published_at.replace(tzinfo=timezone.utc).astimezone(MOSCOW).strftime("%d.%m %H:%M МСК") if article.publication_time_known else "время публикации не установлено"
                body += f"\n{article.source} · {stamp} · {note}\n{article.url}"
                selected.append((priority, article.published_at, article.title.casefold(), body))
            # Preserve pre-upgrade events without depending on the new analysis tables being populated.
            article_urls = excluded_urls | {article.url for article in articles if any(article.title.casefold() == item[2] for item in selected)}
            for event in db.query(MonitoringEvent).filter(MonitoringEvent.kind == "news", MonitoringEvent.source.in_(sources),
                    MonitoringEvent.published_at >= utc_naive(now - timedelta(days=1))).order_by(MonitoringEvent.published_at.desc()).limit(20):
                if event.url in article_urls or (event.investment_account_id and event.investment_account_id not in account_names):
                    continue
                selected.append((30, event.published_at, event.title.casefold(), f"• {event.title}\n{event.source} · {event.url}"))
        selected.sort(key=lambda item: (-item[0], -item[1].timestamp()))
        result, titles = [], []
        for _, _, title, body in selected:
            if any(SequenceMatcher(None, title, existing).ratio() >= 0.9 for existing in titles):
                continue
            titles.append(title)
            result.append(body)
            if len(result) == 5:
                break
        return result


def message_ids(result):
    values = result if isinstance(result, (list, tuple)) else [result]
    return [value.message_id for value in values if getattr(value, "message_id", None) is not None]


class DigestDeliveryService:
    def __init__(self, factory, user, *, send_text, send_album=None):
        self.factory, self.user = factory, user
        self.send_text, self.send_album = send_text, send_album
        self.lock = Lock()

    def deliver(self, draft, now=None):
        now = now or datetime.now(timezone.utc)
        with self.lock:
            with self.factory() as db:
                row = db.get(DigestDelivery, draft.report_date)
                if row is None:
                    row = DigestDelivery(report_date=draft.report_date, payload_json=draft.serialize(), created_at=utc_naive(now))
                    db.add(row)
                    try:
                        db.commit()
                    except IntegrityError:
                        db.rollback()
                        row = db.get(DigestDelivery, draft.report_date)
                saved = DigestDraft.deserialize(row.payload_json)
            for part, sender in (("text", self.send_text), ("album", self.send_album)):
                sent_attr, attempt_attr = part + "_sent_at", part + "_attempt_at"
                with self.factory() as db:
                    if part == "album" and db.get(DigestDelivery, draft.report_date).text_sent_at is None:
                        return False
                    sent_column, attempt_column = getattr(DigestDelivery, sent_attr), getattr(DigestDelivery, attempt_attr)
                    claimed = db.query(DigestDelivery).filter(DigestDelivery.report_date == draft.report_date,
                        sent_column.is_(None), or_(attempt_column.is_(None), attempt_column <= utc_naive(now - timedelta(minutes=5))))
                    if not claimed.update({attempt_column: utc_naive(now)}, synchronize_session=False):
                        db.commit()
                        continue
                    db.commit()
                try:
                    if part == "album" and not saved.charts:
                        result = None
                    elif sender is None:
                        raise ValueError("Digest album sender is unavailable.")
                    else:
                        result = sender(self.user.telegram_chat_id, saved.text if part == "text" else saved.charts)
                    with self.factory() as db:
                        row = db.get(DigestDelivery, draft.report_date)
                        setattr(row, sent_attr, utc_naive(now))
                        setattr(row, part + "_message_ids_json", json.dumps(message_ids(result)))
                        row.error_text = None
                        db.commit()
                except Exception as exc:
                    import requests
                    ambiguous = isinstance(exc, (requests.Timeout, requests.ConnectionError, TimeoutError, ConnectionError))
                    with self.factory() as db:
                        row = db.get(DigestDelivery, draft.report_date)
                        row.error_text, row.ambiguous = type(exc).__name__, row.ambiguous or ambiguous
                        if not ambiguous:
                            setattr(row, attempt_attr, None)
                        db.commit()
                    logger.warning("Digest part failed user_id=%s part=%s ambiguous=%s", self.user.user_id, part, ambiguous)
                    # Text precedes the album, including on retry after a text failure.
                    if part == "text":
                        return False
            with self.factory() as db:
                row = db.get(DigestDelivery, draft.report_date)
                complete = row.text_sent_at is not None and row.album_sent_at is not None
                if complete:
                    run = db.get(MonitoringRun, 1) or MonitoringRun(id=1)
                    db.add(run)
                    run.last_digest_at = utc_naive(now)
                    db.commit()
                return complete
