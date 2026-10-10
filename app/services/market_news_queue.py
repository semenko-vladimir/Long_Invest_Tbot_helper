"""Durable hourly intake and shared article work; account work stays explicit."""

import hashlib
import json
import logging
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, replace
from datetime import datetime, timedelta, timezone

from sqlalchemy import or_
from sqlalchemy.exc import IntegrityError

from app.backend.models.accounts import InvestmentAccount, PortfolioSnapshot, PositionSnapshot
from app.backend.models.trading import Instrument

from app.backend.models.monitoring import (
    AnalysisHourlyBudget, ArticleAnalysisJob, MarketRefreshState, MonitoringEvent,
    NewsAnalysisJob, NewsArticle, NewsSourceState,
)
from app.services.article_news_analysis import RuleArticleAnalyzer, market_catalog, matched_tickers, prefilter_priority
from app.services.media_news_sources import fetch_news_source
from app.services.monitoring_config import MonitoringLimits
from app.services.monitoring_settings import MonitoringSettingsService
from app.services.news_article_text import fetch_article_document
from app.services.news_queue import JOB_LEASE, MAX_ATTEMPTS, NewsQueue
from app.services.news_sources import NewsItem
from app.services.news_urls import canonical_news_url


logger = logging.getLogger(__name__)


def utc_naive(value):
    return value.astimezone(timezone.utc).replace(tzinfo=None)


def content_hash(item):
    value = json.dumps([item.title, item.summary, item.full_text], ensure_ascii=False)
    return hashlib.sha256(value.encode()).hexdigest()


def item_from_article(article):
    return NewsItem(article.source, article.title, article.url, article.published_at.replace(tzinfo=timezone.utc),
        article.summary, article.full_text or "", tuple(json.loads(article.categories_json or "[]")),
        article.publication_time_known)


def reserve_budget(factory, now, kind, maximum):
    hour = now.astimezone(timezone.utc).strftime("%Y-%m-%dT%H")
    with factory() as db:
        row = db.query(AnalysisHourlyBudget).filter_by(hour=hour, kind=kind).first()
        if row is None:
            row = AnalysisHourlyBudget(hour=hour, kind=kind, attempts=0)
            db.add(row)
            try:
                db.flush()
            except IntegrityError:
                db.rollback()
                row = db.query(AnalysisHourlyBudget).filter_by(hour=hour, kind=kind).one()
        updated = db.query(AnalysisHourlyBudget).filter(
            AnalysisHourlyBudget.id == row.id, AnalysisHourlyBudget.attempts < maximum,
        ).update({AnalysisHourlyBudget.attempts: AnalysisHourlyBudget.attempts + 1}, synchronize_session=False)
        db.commit()
        return bool(updated)


class MarketNewsQueue:
    def __init__(self, session_factory, user, *, analyzer=None, account_queue=None, source_fetcher=None,
                 document_fetcher=None, limits=None):
        self.session_factory, self.user = session_factory, user
        self.analyzer = analyzer or RuleArticleAnalyzer()
        self.account_queue = account_queue
        self.source_fetcher = source_fetcher or fetch_news_source
        self.document_fetcher = document_fetcher or fetch_article_document
        self.limits = limits or MonitoringLimits.from_env()
        self.names, self.accounts_by_ticker, self.accounts = {}, {}, ()

    def catalog(self):
        with self.session_factory() as db:
            state = db.get(MarketRefreshState, 1)
            values = json.loads(state.universe_json) if state else {}
        return market_catalog(values, self.names)

    def _retire_inactive_jobs(self, db, sources):
        """Abandoned model/source tasks must not consume the active queue limit."""
        account_version = self.account_queue.analyzer_version if self.account_queue else None
        for model, version in ((ArticleAnalysisJob, self.analyzer.version), (NewsAnalysisJob, account_version)):
            inactive_articles = db.query(NewsArticle.id).filter(NewsArticle.source.notin_(sources))
            db.query(model).filter(model.status.in_(("pending", "running")),
                or_(model.analyzer_version != version, model.article_id.in_(inactive_articles))).update(
                    {model.status: "superseded", model.error_text: "Inactive source or analyzer version"},
                    synchronize_session=False)

    def cached_assessments(self, now):
        sources = MonitoringSettingsService(self.session_factory, self.user).get().sources
        with self.session_factory() as db:
            rows = db.query(ArticleAnalysisJob, NewsArticle).join(NewsArticle).filter(
                ArticleAnalysisJob.analyzer_version == self.analyzer.version,
                ArticleAnalysisJob.status == "done", ArticleAnalysisJob.result_json.is_not(None),
                NewsArticle.source.in_(sources), NewsArticle.published_at >= utc_naive(now - timedelta(days=2)),
                NewsArticle.published_at <= utc_naive(now + timedelta(minutes=10)),
            ).order_by(ArticleAnalysisJob.completed_at.desc()).limit(100).all()
            values = [json.loads(job.result_json) for job, article in rows
                      if job.content_hash == content_hash(item_from_article(article))]
        return [value for value in values if value.get("relevant")][:10]

    @staticmethod
    def _invalidate_pending_event(db, article):
        db.query(MonitoringEvent).filter_by(event_key="article:" + article.article_key, delivered_at=None).delete(synchronize_session=False)

    def _refresh_account_interests(self, now):
        # Rebuild explicit source-account links after restart without a broker request.
        helper = self.account_queue or NewsQueue(self.session_factory, self.user)
        interests = {ticker: [] for ticker in self.accounts_by_ticker if ticker in self.names}
        accounts = []
        with self.session_factory() as db:
            for instrument in db.query(Instrument):
                interests.setdefault(instrument.ticker, [])
            for row in db.query(InvestmentAccount).filter(InvestmentAccount.enabled.is_(True)):
                try:
                    account = helper._account_context(db, row.id)
                except LookupError:
                    continue
                accounts.append(account)
                snapshot = db.query(PortfolioSnapshot).filter_by(investment_account_id=row.id).order_by(PortfolioSnapshot.captured_at.desc()).first()
                if not snapshot or snapshot.captured_at < utc_naive(now - timedelta(days=2)):
                    continue
                for position in db.query(PositionSnapshot).filter_by(portfolio_snapshot_id=snapshot.id, investment_account_id=row.id):
                    if position.quantity:
                        interests.setdefault(position.ticker, []).append(account)
        self.accounts_by_ticker, self.accounts = interests, tuple(accounts)

    def intake(self, now=None, *, names=None, accounts_by_ticker=None, accounts=()):
        now = now or datetime.now(timezone.utc)
        settings = MonitoringSettingsService(self.session_factory, self.user).get()
        if not (settings.alerts_enabled or settings.digest_enabled):
            return 0
        self.names = names or {}
        self.accounts_by_ticker = accounts_by_ticker or {}
        self.accounts = accounts
        since = {}
        with self.session_factory() as db:
            self._retire_inactive_jobs(db, settings.sources)
            db.commit()
            for source in settings.sources:
                state = db.get(NewsSourceState, source)
                since[source] = state.last_success_at.replace(tzinfo=timezone.utc) if state and state.last_success_at else now - timedelta(days=2)

        def fetch(source):
            try:
                result = self.source_fetcher(source, since=since[source], max_pages=self.limits.section_pages, now=now)
                return source, result, None
            except Exception as exc:
                return source, None, type(exc).__name__

        count = 0
        catalog = self.catalog()
        with ThreadPoolExecutor(max_workers=2) as pool:
            for source, result, failure in pool.map(fetch, settings.sources):
                with self.session_factory() as db:
                    state = db.get(NewsSourceState, source) or NewsSourceState(source=source)
                    db.add(state)
                    state.last_attempt_at = utc_naive(now)
                    state.item_count = len(result.items) if result else 0
                    state.coverage_complete = bool(result and result.coverage_complete)
                    state.error_text = failure or (", ".join(result.errors) if result and result.errors else None)
                    state.status = "error" if failure or (result and not result.items and result.errors) else "ok" if state.coverage_complete else "partial"
                    if state.status != "error":
                        state.last_success_at = utc_naive(now)
                    db.commit()
                if result:
                    for item in result.items:
                        if item.published_at < now - timedelta(days=2) or item.published_at > now + timedelta(minutes=10):
                            continue
                        try:
                            count += self.enqueue(item, now, catalog=catalog)
                        except Exception:
                            logger.exception("Article intake failed user_id=%s source=%s", self.user.user_id, source)
        return count

    def enqueue(self, item, now, *, catalog=None):
        catalog = catalog if catalog is not None else self.catalog()
        url = canonical_news_url(item.url)
        key = hashlib.sha256(url.encode()).hexdigest()
        old_key = hashlib.sha256(item.url.encode()).hexdigest()
        with self.session_factory() as db:
            article = db.query(NewsArticle).filter(NewsArticle.article_key.in_((key, old_key))).first()
            if article is None:
                base_url = url.split("?", 1)[0]
                previous = db.query(NewsArticle).filter(or_(NewsArticle.url == base_url,
                    NewsArticle.url.startswith(base_url + "?", autoescape=True)))
                article = next((row for row in previous if canonical_news_url(row.url) == url), None)
            fresh = article is None
            if fresh:
                article = NewsArticle(article_key=key, source=item.source, url=url, title=item.title, summary=item.summary,
                    published_at=utc_naive(item.published_at), first_seen_at=utc_naive(now))
                db.add(article)
                db.flush()
            changed = not fresh and (article.title != item.title or (bool(item.summary) and article.summary != item.summary))
            if changed:
                article.full_text = None
                article.body_checked_at = None
                self._invalidate_pending_event(db, article)
            article.title = item.title
            article.source = item.source
            article.summary = item.summary or article.summary
            if fresh or item.publication_time_known:
                article.published_at = utc_naive(item.published_at)
                article.publication_time_known = item.publication_time_known
            article.categories_json = json.dumps(sorted(set(item.categories) | set(json.loads(article.categories_json or "[]"))))
            article.last_seen_at = utc_naive(now)
            item = item_from_article(article)
            priority = prefilter_priority(item, catalog, self.accounts_by_ticker)
            article.prefilter_reason = "Рынок РФ: " + str(priority) if priority else "Нет связи с рынком РФ"
            job = db.query(ArticleAnalysisJob).filter_by(article_id=article.id, analyzer_version=self.analyzer.version).first()
            if priority:
                pending = db.query(ArticleAnalysisJob).filter(ArticleAnalysisJob.status.in_(("pending", "running"))).count()
                pending += db.query(NewsAnalysisJob).filter(NewsAnalysisJob.status.in_(("pending", "running"))).count()
                if job is None and pending < self.limits.pending_jobs:
                    job = ArticleAnalysisJob(article_id=article.id, analyzer_version=self.analyzer.version,
                        content_hash=content_hash(item), priority=priority, created_at=utc_naive(now))
                    db.add(job)
                elif job is not None and (changed or job.status == "superseded" or (job.status == "done" and
                        (article.body_checked_at is None or article.body_checked_at <= utc_naive(now - timedelta(hours=1))))):
                    job.status, job.attempts, job.next_attempt_at = "pending", 0, None
                    job.priority = priority
            elif job and job.status != "running":
                job.status = "done"
            db.commit()
            return int(fresh or changed)

    def process_pending(self, now=None, *, limit=1):
        settings = MonitoringSettingsService(self.session_factory, self.user).get()
        if not (settings.alerts_enabled or settings.digest_enabled):
            return 0
        def clock():
            return now or datetime.now(timezone.utc)
        started = clock()
        self._refresh_account_interests(started)
        catalog = self.catalog()
        with self.session_factory() as db:
            self._retire_inactive_jobs(db, settings.sources)
            for job in db.query(ArticleAnalysisJob).filter(
                    ArticleAnalysisJob.analyzer_version == self.analyzer.version,
                    ArticleAnalysisJob.status == "running", ArticleAnalysisJob.started_at < utc_naive(started - JOB_LEASE)):
                job.status = "pending" if job.attempts < MAX_ATTEMPTS else "failed"
                job.error_text = "Interrupted analysis"
            db.commit()
            # Materialize deferred articles after capacity becomes available.
            active_count = db.query(ArticleAnalysisJob).filter(ArticleAnalysisJob.status.in_(("pending", "running"))).count()
            active_count += db.query(NewsAnalysisJob).filter(NewsAnalysisJob.status.in_(("pending", "running"))).count()
            available = max(0, self.limits.pending_jobs - active_count)
            deferred = db.query(NewsArticle).outerjoin(ArticleAnalysisJob, (
                (ArticleAnalysisJob.article_id == NewsArticle.id) & (ArticleAnalysisJob.analyzer_version == self.analyzer.version)
            )).filter(ArticleAnalysisJob.id.is_(None), NewsArticle.published_at >= utc_naive(started - timedelta(days=2)),
                NewsArticle.source.in_(settings.sources)).order_by(NewsArticle.published_at.desc()).limit(1000 if available else 0).all()
            deferred_items = [item_from_article(article) for article in deferred]
            priorities = [(prefilter_priority(item, catalog, self.accounts_by_ticker), item) for item in deferred_items]
            priorities.sort(key=lambda value: (-value[0], -value[1].published_at.timestamp()))
            deferred_items = [item for priority, item in priorities if priority][:available]
            completed = db.query(ArticleAnalysisJob).join(NewsArticle).filter(
                ArticleAnalysisJob.analyzer_version == self.analyzer.version, ArticleAnalysisJob.status == "done",
                NewsArticle.source.in_(settings.sources), NewsArticle.published_at >= utc_naive(started - timedelta(days=2)),
            ).order_by(ArticleAnalysisJob.priority.desc(), ArticleAnalysisJob.completed_at.desc()).limit(100).all()
            # Account follow-ups deferred by capacity are recoverable from completed article facts.
            followups = [item_from_article(db.get(NewsArticle, job.article_id)) for job in completed if job.result_json and
                json.loads(job.result_json).get("relevant") and job.content_hash == content_hash(item_from_article(db.get(NewsArticle, job.article_id)))]
        for item in followups:
            self._enqueue_accounts(item, catalog, started)
        for item in deferred_items:
            self.enqueue(item, started, catalog=catalog)
        processed = 0
        for _ in range(limit):
            with self.session_factory() as db:
                job = db.query(ArticleAnalysisJob).join(NewsArticle).filter(
                    ArticleAnalysisJob.analyzer_version == self.analyzer.version,
                    ArticleAnalysisJob.status == "pending", NewsArticle.source.in_(settings.sources),
                    or_(ArticleAnalysisJob.next_attempt_at.is_(None), ArticleAnalysisJob.next_attempt_at <= utc_naive(clock())),
                ).order_by(ArticleAnalysisJob.priority.desc(), ArticleAnalysisJob.created_at.desc()).first()
                if job is None:
                    break
                job_id, article_id = job.id, job.article_id
                article = db.get(NewsArticle, article_id)
                item = item_from_article(article)
                signature = (item.title, item.summary)
                old_hash, old_result = job.content_hash, job.result_json
                job.status, job.started_at = "running", utc_naive(clock())
                db.commit()
            tick = time.monotonic()
            try:
                try:
                    document = self.document_fetcher(item)
                    if document.text:
                        item = replace(item, full_text=document.text)
                    if document.published_at:
                        item = replace(item, published_at=document.published_at, publication_time_known=True)
                except Exception:
                    logger.warning("Article text unavailable user_id=%s article_id=%s", self.user.user_id, article_id)
                new_hash = content_hash(item)
                with self.session_factory() as db:
                    article, job = db.get(NewsArticle, article_id), db.get(ArticleAnalysisJob, job_id)
                    if (article.title, article.summary) != signature or job.status != "running":
                        continue
                    article.full_text, article.body_checked_at = item.full_text or None, utc_naive(clock())
                    article.published_at, article.publication_time_known = utc_naive(item.published_at), item.publication_time_known
                    if new_hash != old_hash:
                        self._invalidate_pending_event(db, article)
                    if old_result and new_hash == old_hash:
                        job.status, job.completed_at = "done", utc_naive(clock())
                        db.commit()
                        processed += 1
                        continue
                    db.commit()
                if not isinstance(self.analyzer, RuleArticleAnalyzer) and not reserve_budget(
                        self.session_factory, clock(), "article", self.limits.news_per_hour):
                    with self.session_factory() as db:
                        job = db.get(ArticleAnalysisJob, job_id)
                        job.status = "pending"
                        job.next_attempt_at = utc_naive(clock().replace(minute=0, second=0, microsecond=0) + timedelta(hours=1))
                        db.commit()
                    break
                with self.session_factory() as db:
                    job = db.get(ArticleAnalysisJob, job_id)
                    job.attempts += 1
                    db.commit()
                assessment = self.analyzer.assess_article(item, catalog)
                with self.session_factory() as db:
                    article, job = db.get(NewsArticle, article_id), db.get(ArticleAnalysisJob, job_id)
                    if (article.title, article.summary) != signature or job.status != "running":
                        continue
                    job.result_json = json.dumps(asdict(assessment), ensure_ascii=False)
                    job.content_hash = new_hash
                    job.status, job.completed_at, job.error_text = "done", utc_naive(clock()), None
                    job.duration_seconds = time.monotonic() - tick
                    self._record_event(db, article, assessment, clock())
                    db.commit()
                if assessment.relevant:
                    self._enqueue_accounts(item, catalog, clock())
                processed += 1
            except Exception as exc:
                with self.session_factory() as db:
                    job = db.get(ArticleAnalysisJob, job_id)
                    if job.status != "running":
                        continue
                    job.error_text, job.duration_seconds = type(exc).__name__, time.monotonic() - tick
                    job.status = "failed" if job.attempts >= MAX_ATTEMPTS else "pending"
                    job.next_attempt_at = utc_naive(clock() + timedelta(minutes=max(job.attempts, 1)))
                    if job.status == "failed":
                        fallback = RuleArticleAnalyzer().assess_article(item, catalog)
                        job.result_json = json.dumps(asdict(fallback), ensure_ascii=False)
                        job.content_hash = content_hash(item)
                    db.commit()
                logger.warning("Article analysis failed user_id=%s job_id=%s error=%s", self.user.user_id, job_id, type(exc).__name__)
        return processed

    def _record_event(self, db, article, assessment, now):
        key = "article:" + article.article_key
        event = db.query(MonitoringEvent).filter_by(event_key=key).first()
        if not assessment.relevant:
            if event and event.delivered_at is None:
                db.delete(event)
            return
        if event is None:
            previous = db.query(MonitoringEvent).filter(MonitoringEvent.url == article.url,
                MonitoringEvent.kind == "news", MonitoringEvent.delivered_at.is_not(None)).first()
            event = MonitoringEvent(event_key=key, kind="news", title=article.title, source=article.source,
                published_at=article.published_at, observed_at=utc_naive(now), url=article.url,
                delivered_at=previous.delivered_at if previous else None)
            db.add(event)
        ids = sorted({account.investment_account_id for ticker in assessment.tickers
                      for account in self.accounts_by_ticker.get(ticker, ())})
        event.title, event.published_at = article.title, article.published_at
        if event.delivered_at is None:
            event.observed_at = utc_naive(now)
        event.payload_json = json.dumps({"analysis_status": "article_model" if assessment.model != "rules" else "article_rules",
            "importance": assessment.importance, "reason": assessment.reason, "analysis": asdict(assessment),
            "account_ids": ids, "publication_time_known": article.publication_time_known}, ensure_ascii=False)

    def _enqueue_accounts(self, item, catalog, now):
        if self.account_queue is None:
            return
        matches = matched_tickers(item, catalog)
        targets = {}
        for ticker in matches:
            for account in self.accounts_by_ticker.get(ticker, ()):
                names = catalog.get(ticker, "")
                targets.setdefault(account.investment_account_id, {})[ticker] = names if isinstance(names, str) else next(iter(names), "")
        with self.session_factory() as db:
            article = db.query(NewsArticle).filter_by(url=item.url).first()
            if article is None:
                return
            if content_hash(item_from_article(article)) != content_hash(item):
                return
            for account_id, names in targets.items():
                job = db.query(NewsAnalysisJob).filter_by(article_id=article.id, investment_account_id=account_id,
                    analyzer_version=self.account_queue.analyzer_version).first()
                if job and job.content_hash == content_hash(item) and job.status != "superseded":
                    continue
                count = db.query(ArticleAnalysisJob).filter(ArticleAnalysisJob.status.in_(("pending", "running"))).count()
                count += db.query(NewsAnalysisJob).filter(NewsAnalysisJob.status.in_(("pending", "running"))).count()
                if count >= self.limits.pending_jobs and (not job or job.status not in ("pending", "running")):
                    break
                if job is None:
                    job = NewsAnalysisJob(article_id=article.id, investment_account_id=account_id,
                        analyzer_version=self.account_queue.analyzer_version, created_at=utc_naive(now))
                    db.add(job)
                job.content_hash, job.ticker_names_json = content_hash(item), json.dumps(names, ensure_ascii=False)
                job.status, job.attempts, job.result_json, job.error_text, job.next_attempt_at = "pending", 0, None, None, None
                db.flush()
            db.commit()

    def process_account_pending(self, now=None):
        now = now or datetime.now(timezone.utc)
        settings = MonitoringSettingsService(self.session_factory, self.user).get()
        if self.account_queue is None or not (settings.alerts_enabled or settings.digest_enabled):
            return 0
        with self.session_factory() as db:
            self._retire_inactive_jobs(db, settings.sources)
            db.commit()
        self.account_queue.process_pending(now, limit=0)  # Recover interrupted leases before looking for due work.
        with self.session_factory() as db:
            due = db.query(NewsAnalysisJob.id).filter(NewsAnalysisJob.status == "pending",
                NewsAnalysisJob.analyzer_version == self.account_queue.analyzer_version,
                or_(NewsAnalysisJob.next_attempt_at.is_(None), NewsAnalysisJob.next_attempt_at <= utc_naive(now))).first()
        if due and reserve_budget(self.session_factory, now, "account", self.limits.account_analyses_per_hour):
            return self.account_queue.process_pending(now, limit=1)
        return 0
