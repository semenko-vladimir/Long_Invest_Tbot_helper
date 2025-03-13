from sqlalchemy import Column, Integer, Boolean, String, DateTime
from app.backend.models.database import Base


class StrategySignals(Base):
    __tablename__ = "strategy_signals"

    id = Column(Integer, primary_key=True, index=True)
    tpls_trigger = Column(Boolean, default=False)
    rsi_trigger = Column(Boolean, default=False)
    sma_trigger = Column(Boolean, default=False)
    ema_trigger = Column(Boolean, default=False)
    alligator_trigger = Column(Boolean, default=False)
    gpt_trigger = Column(Boolean, default=False)
    lstm_trigger = Column(Boolean, default=False)
    bollinger_trigger = Column(Boolean, default=False)
    macd_trigger = Column(Boolean, default=False)


class StrategySettings(Base):
    __tablename__ = "strategy_settings"

    id = Column(Integer, primary_key=True, index=True)
    time = Column(String)  # Using String instead of DateTime for time-only values
    auto_market = Column(Boolean, default=False)
    quantity = Column(Integer, default=1)
    joint = Column(Boolean, default=False)
    sandbox_trigger = Column(Boolean, default=False)
