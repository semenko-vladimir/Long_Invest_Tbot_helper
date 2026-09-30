from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint

from app.backend.models.database import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class MonitoringPreference(Base):
    __tablename__ = "monitoring_preferences"

    id = Column(Integer, primary_key=True)
    alerts_enabled = Column(Boolean, nullable=True)
    digest_enabled = Column(Boolean, nullable=True)
    scope = Column(String, nullable=True)
    threshold_pct = Column(Float, nullable=True)
    digest_time = Column(String, nullable=True)
    sources_json = Column(Text, nullable=True)


class MonitoringEvent(Base):
    __tablename__ = "monitoring_events"
    __table_args__ = (UniqueConstraint("event_key", name="uq_monitoring_event_key"),)

    id = Column(Integer, primary_key=True)
    event_key = Column(String, nullable=False)
    kind = Column(String, nullable=False)
    ticker = Column(String, nullable=True)
    investment_account_id = Column(Integer, ForeignKey("investment_accounts.id", ondelete="SET NULL"), nullable=True)
    title = Column(Text, nullable=False)
    url = Column(Text, nullable=True)
    source = Column(String, nullable=False)
    published_at = Column(DateTime, nullable=False)
    observed_at = Column(DateTime, nullable=False, default=utc_now)
    payload_json = Column(Text, nullable=True)
    delivered_at = Column(DateTime, nullable=True)


class MonitoringRun(Base):
    __tablename__ = "monitoring_runs"

    id = Column(Integer, primary_key=True)
    last_digest_at = Column(DateTime, nullable=True)


class NewsArticle(Base):
    __tablename__ = "news_articles"
    __table_args__ = (UniqueConstraint("article_key", name="uq_news_article_key"),)

    id = Column(Integer, primary_key=True)
    article_key = Column(String, nullable=False)
    source = Column(String, nullable=False)
    title = Column(Text, nullable=False)
    url = Column(Text, nullable=False)
    summary = Column(Text, nullable=False, default="")
    full_text = Column(Text, nullable=True)
    published_at = Column(DateTime, nullable=False)
    first_seen_at = Column(DateTime, nullable=False, default=utc_now)
    prefilter_ticker = Column(String, nullable=True)
    prefilter_name = Column(String, nullable=True)
    prefilter_reason = Column(String, nullable=True)


class NewsAnalysisJob(Base):
    __tablename__ = "news_analysis_jobs"
    __table_args__ = (
        UniqueConstraint("article_id", "investment_account_id", "analyzer_version", name="uq_news_job_article_account_version"),
    )

    id = Column(Integer, primary_key=True)
    article_id = Column(Integer, ForeignKey("news_articles.id", ondelete="CASCADE"), nullable=False)
    investment_account_id = Column(Integer, ForeignKey("investment_accounts.id", ondelete="CASCADE"), nullable=False)
    analyzer_version = Column(String, nullable=False)
    status = Column(String, nullable=False, default="pending")
    attempts = Column(Integer, nullable=False, default=0)
    next_attempt_at = Column(DateTime, nullable=True)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    result_json = Column(Text, nullable=True)
    error_text = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False, default=utc_now)
