from datetime import UTC, datetime

from sqlalchemy import Column, DateTime, Integer, String, Text

from app.backend.models.database import Base


def _utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


class ResearchSnapshot(Base):
    __tablename__ = "research_snapshots"

    id = Column(Integer, primary_key=True, index=True)
    ticker = Column(String, index=True)
    generated_at = Column(DateTime, index=True)
    source_names = Column(Text, default="[]")
    report_json = Column(Text, nullable=False)
    data_gap_count = Column(Integer, default=0)
    error_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=_utcnow, index=True)
