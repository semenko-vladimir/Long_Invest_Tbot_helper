"""User-owned notes and durable, read-only position monitoring state."""

from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint

from app.backend.models.accounts import utc_now
from app.backend.models.database import Base


class StockNote(Base):
    __tablename__ = "stock_notes"
    id = Column(Integer, primary_key=True)
    user_id = Column(String, nullable=False, index=True)
    instrument_key = Column(String, nullable=False, index=True)
    ticker = Column(String, nullable=False)
    text = Column(Text, nullable=False)
    created_at = Column(DateTime, nullable=False, default=utc_now)
    updated_at = Column(DateTime, nullable=False, default=utc_now)


class StockTracking(Base):
    __tablename__ = "stock_tracking"
    __table_args__ = (UniqueConstraint("user_id", "investment_account_id", "instrument_key", name="uq_stock_tracking_position"),)
    id = Column(Integer, primary_key=True)
    user_id = Column(String, nullable=False, index=True)
    investment_account_id = Column(Integer, ForeignKey("investment_accounts.id"), nullable=False)
    instrument_key = Column(String, nullable=False)
    ticker = Column(String, nullable=False)
    interval_minutes = Column(Integer, nullable=False, default=30)
    chart_range = Column(String, nullable=False, default="day")
    status = Column(String, nullable=False, default="active")
    next_due_at = Column(DateTime, nullable=False)
    last_sent_at = Column(DateTime)
    last_sent_price = Column(Float)
    last_message_id = Column(Integer)
    attempt_at = Column(DateTime)
    error_text = Column(String)
    closure_notice_pending = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime, nullable=False, default=utc_now)
    updated_at = Column(DateTime, nullable=False, default=utc_now)


class StockRefreshState(Base):
    __tablename__ = "stock_refresh_state"
    id = Column(Integer, primary_key=True)
    last_attempt_at = Column(DateTime)
    last_success_at = Column(DateTime)
    quotes_checked_at = Column(DateTime)
    quotes_json = Column(Text, nullable=False, default="{}")
    index_json = Column(Text, nullable=False, default="{}")
    account_ids_json = Column(Text)
    error_text = Column(String)


class StockAccountRefresh(Base):
    __tablename__ = "stock_account_refresh"
    investment_account_id = Column(Integer, ForeignKey("investment_accounts.id"), primary_key=True)
    checked_at = Column(DateTime)
    success_at = Column(DateTime)
    error_text = Column(String)


class StockChartCache(Base):
    __tablename__ = "stock_chart_cache"
    __table_args__ = (UniqueConstraint("instrument_key", "interval", name="uq_stock_chart_instrument_interval"),)
    id = Column(Integer, primary_key=True)
    instrument_key = Column(String, nullable=False)
    interval = Column(String, nullable=False)
    candles_json = Column(Text, nullable=False)
    fetched_at = Column(DateTime, nullable=False)
