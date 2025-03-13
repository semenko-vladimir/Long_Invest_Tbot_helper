from sqlalchemy import Column, Integer, String, Boolean, DateTime
from sqlalchemy.sql import func

from app.backend.models.database import Base


class SchedulerConfig(Base):
    __tablename__ = "scheduler_config"

    id = Column(Integer, primary_key=True, index=True)
    collapse_updates = Column(Boolean, default=False)
    collapse_updates_time = Column(String)
    market_updates = Column(Boolean, default=False)
    market_updates_time = Column(String)
