from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import relationship

from app.backend.models.database import Base


class BrokerConnection(Base):
    __tablename__ = "broker_connections"
    __table_args__ = (
        UniqueConstraint("provider_key", "connection_key", name="uq_broker_connections_provider_key"),
    )

    id = Column(Integer, primary_key=True, index=True)
    provider_key = Column(String, nullable=False, index=True)
    connection_key = Column(String, nullable=False)
    display_name = Column(String, nullable=False)
    enabled = Column(Boolean, nullable=False, default=True)
    metadata_json = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    accounts = relationship("InvestmentAccount", back_populates="broker_connection")


class InvestmentAccount(Base):
    __tablename__ = "investment_accounts"
    __table_args__ = (
        UniqueConstraint(
            "broker_connection_id",
            "external_account_id",
            name="uq_investment_accounts_connection_external",
        ),
    )

    id = Column(Integer, primary_key=True, index=True)
    broker_connection_id = Column(
        Integer,
        ForeignKey("broker_connections.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    external_account_id = Column(String, nullable=False)
    display_name = Column(String, nullable=False)
    account_type = Column(String, nullable=True)
    status = Column(String, nullable=True)
    access_level = Column(String, nullable=True)
    enabled = Column(Boolean, nullable=False, default=True)
    discovered_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    last_seen_at = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    broker_connection = relationship("BrokerConnection", back_populates="accounts")
    strategy_profile = relationship(
        "StrategyProfile",
        back_populates="investment_account",
        uselist=False,
    )
    portfolio_snapshots = relationship("PortfolioSnapshot", back_populates="investment_account")


class StrategyProfile(Base):
    __tablename__ = "strategy_profiles"

    id = Column(Integer, primary_key=True, index=True)
    investment_account_id = Column(
        Integer,
        ForeignKey("investment_accounts.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    title = Column(String, nullable=True)
    strategy_key = Column(String, nullable=True)
    thesis = Column(Text, nullable=True)
    settings_json = Column(Text, nullable=True)
    analysis_profile_key = Column(String, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    investment_account = relationship("InvestmentAccount", back_populates="strategy_profile")


class PortfolioSnapshot(Base):
    __tablename__ = "portfolio_snapshots"

    id = Column(Integer, primary_key=True, index=True)
    investment_account_id = Column(
        Integer,
        ForeignKey("investment_accounts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    captured_at = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)
    total_value = Column(Float, nullable=False)
    currency = Column(String, nullable=False, default="RUB")
    source = Column(String, nullable=False)
    freshness = Column(String, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    investment_account = relationship("InvestmentAccount", back_populates="portfolio_snapshots")
    positions = relationship("PositionSnapshot", back_populates="portfolio_snapshot")


class PositionSnapshot(Base):
    __tablename__ = "position_snapshots"

    id = Column(Integer, primary_key=True, index=True)
    portfolio_snapshot_id = Column(
        Integer,
        ForeignKey("portfolio_snapshots.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    investment_account_id = Column(
        Integer,
        ForeignKey("investment_accounts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    instrument_uid = Column(String, nullable=True, index=True)
    figi = Column(String, nullable=True, index=True)
    ticker = Column(String, nullable=False, index=True)
    quantity = Column(Float, nullable=False)
    average_price = Column(Float, nullable=True)
    current_price = Column(Float, nullable=True)
    market_value = Column(Float, nullable=True)
    expected_yield = Column(Float, nullable=True)
    currency = Column(String, nullable=False, default="RUB")
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    portfolio_snapshot = relationship("PortfolioSnapshot", back_populates="positions")
