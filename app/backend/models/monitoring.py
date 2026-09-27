from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, DateTime, Float, Integer, String, Text, UniqueConstraint

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
