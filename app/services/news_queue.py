"""Persistent, account-scoped news intake and a separate analysis worker."""

import hashlib
import json
import logging
import re
from dataclasses import asdict, replace
from datetime import datetime, timedelta, timezone

from sqlalchemy import or_
from sqlalchemy.exc import IntegrityError

from app.backend.models.accounts import InvestmentAccount, PortfolioSnapshot, PositionSnapshot
from app.backend.models.monitoring import MonitoringEvent, NewsAnalysisJob, NewsArticle
from app.services.accounts import InvestmentAccountContext, StrategyProfileContext, UnknownInvestmentAccountError
from app.services.monitoring_settings import MonitoringSettingsService
from app.services.news_analysis import NewsAssessment, RuleNewsAnalyzer
from app.services.news_sources import NewsItem
from app.services.news_urls import canonical_news_url


logger = logging.getLogger(__name__)
ANALYZER_VERSION = "rules-v1"
MAX_QUEUED_JOBS = 100
MAX_ATTEMPTS = 3
JOB_LEASE = timedelta(minutes=10)


def _utc_naive(value: datetime) -> datetime:
    return value.astimezone(timezone.utc).replace(tzinfo=None)


def _article_key(item: NewsItem) -> str:
    # MOEX publishes the same URL in its main and listing feeds.
    return hashlib.sha256(canonical_news_url(item.url).encode("utf-8")).hexdigest()


def _legacy_event_key(item: NewsItem) -> str:
    return "news:" + hashlib.sha256(item.url.encode("utf-8")).hexdigest()


def _content_signature(item: NewsItem) -> tuple[str, str]:
    return item.title, item.summary


class NewsQueue:
    def __init__(self, session_factory, user, *, prefilter=None, analyzer=None,
                 analyzer_version=ANALYZER_VERSION, article_fetcher=None, publish_events=True):
        self.session_factory = session_factory
        self.user = user
        self.prefilter = prefilter or RuleNewsAnalyzer()
        self.analyzer = analyzer or RuleNewsAnalyzer()
        self.analyzer_version = analyzer_version
        self.article_fetcher = article_fetcher
        self.publish_events = publish_events

    def enqueue(self, item, ticker_names, accounts_by_ticker, accounts, scope, now) -> bool:
        """Record a fresh article once and queue relevant account analyses."""
        key = _article_key(item)
        db = self.session_factory()
        try:
            article = db.query(NewsArticle).filter(NewsArticle.article_key == key).first()
            exists = article is not None
            content_changed = exists and (article.title, article.summary) != _content_signature(item)
            assessment = self.prefilter.assess(item, ticker_names, accounts)
            relevant = assessment.important and not (
                scope == "owned" and assessment.ticker and assessment.ticker not in accounts_by_ticker
            )
            if relevant and accounts:
                if scope == "owned" and assessment.ticker and accounts_by_ticker.get(assessment.ticker):
                    targets = tuple(accounts_by_ticker[assessment.ticker])
                else:
                    targets = accounts
                targets = tuple({account.investment_account_id: account for account in targets}.values())
                existing_jobs = {
                    job.investment_account_id: job for job in db.query(NewsAnalysisJob).filter(
                        NewsAnalysisJob.article_id == article.id,
                        NewsAnalysisJob.analyzer_version == self.analyzer_version,
                    )
                } if exists else {}
                if exists and not content_changed and all(
                    account.investment_account_id in existing_jobs for account in targets
                ):
                    return False
                queued = db.query(NewsAnalysisJob).filter(
                    NewsAnalysisJob.status.in_(("pending", "running"))
                ).count()
                new_pending = sum(existing_jobs.get(account.investment_account_id) is None or
                                  (content_changed and existing_jobs[account.investment_account_id].status not in ("pending", "running"))
                                  for account in targets)
                if queued + new_pending > MAX_QUEUED_JOBS:
                    logger.debug("News queue full for user_id=%s", self.user.user_id)
                    return False
            else:
                targets = ()
                existing_jobs = {}
                if exists and not content_changed:
                    return False
            if article is None:
                article = NewsArticle(article_key=key, source=item.source, url=item.url,
                                      first_seen_at=_utc_naive(now))
                db.add(article)
            article.title = item.title
            article.summary = item.summary
            article.categories_json = json.dumps(item.categories, ensure_ascii=False)
            article.publication_time_known = item.publication_time_known
            article.last_seen_at = _utc_naive(now)
            if content_changed:
                article.full_text = None
            article.published_at = _utc_naive(item.published_at)
            article.prefilter_ticker = assessment.ticker
            article.prefilter_name = ticker_names.get(assessment.ticker) if assessment.ticker else None
            article.prefilter_reason = assessment.reason
            db.flush()
            # A pre-upgrade notification must not be delivered again after migration.
            if not exists and db.query(MonitoringEvent.id).filter(MonitoringEvent.event_key == _legacy_event_key(item)).first():
                db.commit()
                return True
            if content_changed and not relevant:
                for job in db.query(NewsAnalysisJob).filter(NewsAnalysisJob.article_id == article.id,
                                                            NewsAnalysisJob.status.in_(("pending", "running"))):
                    job.status = "done"
                    job.completed_at = _utc_naive(now)
                    job.result_json = json.dumps({"important": False, "ticker": None,
                                                  "reason": assessment.reason}, ensure_ascii=False)
            if content_changed and relevant:
                target_ids = {account.investment_account_id for account in targets}
                for job in db.query(NewsAnalysisJob).filter(NewsAnalysisJob.article_id == article.id,
                                                            NewsAnalysisJob.status.in_(("pending", "running"))):
                    if job.investment_account_id not in target_ids:
                        job.status = "done"
                        job.completed_at = _utc_naive(now)
                        job.result_json = json.dumps({"important": False, "ticker": None,
                                                      "reason": "Outside current account scope"})
            for account in targets:
                job = existing_jobs.get(account.investment_account_id)
                if job is not None and not content_changed:
                    continue
                if job is None:
                    job = NewsAnalysisJob(article_id=article.id,
                                          investment_account_id=account.investment_account_id,
                                          analyzer_version=self.analyzer_version, created_at=_utc_naive(now))
                    db.add(job)
                job.status = "pending"
                job.attempts = 0
                job.next_attempt_at = None
                job.result_json = None
                job.error_text = None
            if relevant and not accounts and not exists:
                db.add(MonitoringEvent(
                    event_key=_legacy_event_key(item), kind="news", ticker=assessment.ticker,
                    title=item.title, source=item.source, published_at=_utc_naive(item.published_at),
                    observed_at=_utc_naive(now), url=item.url,
                    payload_json=json.dumps({"reason": assessment.reason}, ensure_ascii=False),
                ))
            db.commit()
            return True
        except IntegrityError:
            db.rollback()
            return False
        finally:
            db.close()

    def process_pending(self, now: datetime | None = None, *, limit: int = 10) -> int:
        """Process a bounded batch; called by its own scheduler job."""
        settings = MonitoringSettingsService(self.session_factory, self.user).get()
        if not (settings.alerts_enabled or settings.digest_enabled):
            return 0

        def current_time():
            return _utc_naive(now or datetime.now(timezone.utc))

        started = current_time()
        db = self.session_factory()
        processed = 0
        try:
            stale = db.query(NewsAnalysisJob).filter(
                NewsAnalysisJob.analyzer_version == self.analyzer_version,
                NewsAnalysisJob.status == "running",
                NewsAnalysisJob.started_at < started - JOB_LEASE,
            ).all()
            for job in stale:
                job.status = "pending" if job.attempts < MAX_ATTEMPTS else "failed"
                job.next_attempt_at = started if job.status == "pending" else None
                job.error_text = "Interrupted analysis"
            db.commit()
            for _ in range(limit):
                job = db.query(NewsAnalysisJob).filter(
                    NewsAnalysisJob.analyzer_version == self.analyzer_version,
                    NewsAnalysisJob.status == "pending",
                    or_(NewsAnalysisJob.next_attempt_at.is_(None), NewsAnalysisJob.next_attempt_at <= current_time()),
                ).order_by(NewsAnalysisJob.id).first()
                if job is None:
                    break
                job_id = job.id
                job.status = "running"
                job.attempts += 1
                job.started_at = current_time()
                db.commit()
                try:
                    article = db.get(NewsArticle, job.article_id)
                    account = self._account_context(db, job.investment_account_id)
                    item = NewsItem(article.source, article.title, article.url,
                                    article.published_at.replace(tzinfo=timezone.utc), article.summary)
                    names = json.loads(job.ticker_names_json) if job.ticker_names_json else {article.prefilter_ticker: article.prefilter_name or ""} if article.prefilter_ticker else {}
                    expected_hash = job.content_hash
                    article_key = article.article_key
                    article_id = article.id
                    content_signature = _content_signature(item)
                    analyzer_version = job.analyzer_version
                    requires_security_match = getattr(self.prefilter, "needs_security_match", lambda _: False)(item)
                    # Release the SQLite read transaction before a potentially slow LLM call.
                    db.commit()
                    if self.article_fetcher is not None:
                        full_text = article.full_text
                        if full_text is None:
                            try:
                                full_text = self.article_fetcher(item)
                            except Exception:
                                logger.warning("Official article text unavailable user_id=%s article_id=%s",
                                               self.user.user_id, article_id, exc_info=True)
                                if requires_security_match:
                                    raise
                                full_text = ""
                            if full_text:
                                article = db.get(NewsArticle, article_id)
                                article.full_text = full_text
                                db.commit()
                        item = replace(item, full_text=full_text or "")
                    if requires_security_match:
                        matched = self._matching_account_ticker(db, account.investment_account_id, item.full_text)
                        if matched is None:
                            assessment = NewsAssessment(False, None, "В тексте нет бумаги этого счёта")
                        else:
                            names = {matched: names.get(matched, "")}
                            db.commit()
                            assessment = self.analyzer.assess(item, names, (account,))
                    else:
                        db.commit()
                        assessment = self.analyzer.assess(item, names, (account,))
                    job = db.get(NewsAnalysisJob, job_id)
                    current_article = db.get(NewsArticle, article_id)
                    db.refresh(current_article)
                    if expected_hash:
                        from app.services.market_news_queue import content_hash, item_from_article
                        if job.content_hash != expected_hash or content_hash(item_from_article(current_article)) != expected_hash:
                            db.commit()
                            continue
                    if _content_signature(NewsItem(current_article.source, current_article.title,
                                                   current_article.url, current_article.published_at.replace(tzinfo=timezone.utc),
                                                   current_article.summary)) != content_signature:
                        db.commit()
                        continue
                    finished = current_time()
                    result = {
                        "important": assessment.important, "ticker": assessment.ticker,
                        "reason": assessment.reason,
                    }
                    if assessment.analysis is not None:
                        result["analysis"] = asdict(assessment.analysis)
                    job.result_json = json.dumps(result, ensure_ascii=False)
                    if assessment.important and self.publish_events:
                        event_key = f"news:{article_key}:{account.investment_account_id}:{analyzer_version}"
                        if not db.query(MonitoringEvent.id).filter(MonitoringEvent.event_key == event_key).first():
                            db.add(MonitoringEvent(
                                event_key=event_key, kind="news", ticker=assessment.ticker,
                                investment_account_id=account.investment_account_id,
                                title=item.title, source=item.source,
                                published_at=_utc_naive(item.published_at), observed_at=finished, url=item.url,
                                payload_json=json.dumps({"reason": assessment.reason,
                                                         "analysis_status": "model" if assessment.analysis else "rules",
                                                         "analysis": asdict(assessment.analysis) if assessment.analysis else None},
                                                        ensure_ascii=False),
                            ))
                    job.status = "done"
                    job.completed_at = finished
                    job.next_attempt_at = None
                    job.error_text = None
                    db.commit()
                    processed += 1
                except Exception as exc:
                    db.rollback()
                    job = db.get(NewsAnalysisJob, job_id)
                    permanent = isinstance(exc, UnknownInvestmentAccountError) or job.attempts >= MAX_ATTEMPTS
                    job.status = "failed" if permanent else "pending"
                    job.next_attempt_at = None if permanent else current_time() + timedelta(minutes=job.attempts)
                    job.error_text = type(exc).__name__
                    if self.publish_events and permanent and self.analyzer_version.startswith("ollama-") and not isinstance(exc, UnknownInvestmentAccountError):
                        article = db.get(NewsArticle, job.article_id)
                        is_security_notice = article is not None and getattr(
                            self.prefilter, "needs_security_match", lambda _: False
                        )(NewsItem(article.source, article.title, article.url,
                                   article.published_at.replace(tzinfo=timezone.utc), article.summary))
                        if article is not None and not is_security_notice:
                            event_key = f"news:{article.article_key}:{job.investment_account_id}:{job.analyzer_version}"
                            if not db.query(MonitoringEvent.id).filter(MonitoringEvent.event_key == event_key).first():
                                db.add(MonitoringEvent(
                                    event_key=event_key, kind="news", ticker=article.prefilter_ticker,
                                    investment_account_id=job.investment_account_id,
                                    title=article.title, source=article.source,
                                    published_at=article.published_at, observed_at=current_time(), url=article.url,
                                    payload_json=json.dumps({"reason": article.prefilter_reason,
                                                             "analysis_status": "unavailable"}, ensure_ascii=False),
                                ))
                    db.commit()
                    logger.exception("News analysis failed user_id=%s job_id=%s", self.user.user_id, job_id)
            return processed
        finally:
            db.close()

    @staticmethod
    def _matching_account_ticker(db, account_id: int, text: str) -> str | None:
        if not text:
            return None
        snapshot = db.query(PortfolioSnapshot).filter(
            PortfolioSnapshot.investment_account_id == account_id,
        ).order_by(PortfolioSnapshot.captured_at.desc()).first()
        if snapshot is None or snapshot.captured_at < datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=2):
            return None
        for (ticker,) in db.query(PositionSnapshot.ticker).filter(
            PositionSnapshot.portfolio_snapshot_id == snapshot.id,
            PositionSnapshot.investment_account_id == account_id,
        ):
            if ticker and re.search(rf"(?<![\w]){re.escape(ticker)}(?![\w])", text, flags=re.IGNORECASE):
                return ticker
        return None

    def _account_context(self, db, account_id: int) -> InvestmentAccountContext:
        account = db.get(InvestmentAccount, account_id)
        if (account is None or not account.enabled or account.broker_connection is None
                or not account.broker_connection.enabled or str(account.status or "").lower() != "open"):
            raise UnknownInvestmentAccountError("Investment account is unavailable or no longer enabled.")
        profile = account.strategy_profile
        strategy = None
        if profile is not None:
            try:
                settings = json.loads(profile.settings_json or "{}")
            except (TypeError, ValueError):
                settings = {}
            strategy = StrategyProfileContext(profile.id, profile.title, profile.strategy_key,
                                              profile.thesis, settings if isinstance(settings, dict) else {},
                                              profile.analysis_profile_key)
        connection = account.broker_connection
        return InvestmentAccountContext(
            self.user.user_id, account.id, connection.id, connection.provider_key,
            connection.connection_key, account.external_account_id, account.display_name,
            account.account_type, account.status, account.access_level, strategy,
        )
