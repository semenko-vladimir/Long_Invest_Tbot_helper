from sqlalchemy import Column, Integer, Float, String, Boolean
from app.backend.models.database import Base


class SignalTPSL(Base):
    __tablename__ = "signal_tpsl"

    id = Column(Integer, primary_key=True, index=True)
    take_profit = Column(Float)
    stop_loss = Column(Float)


class SignalRSI(Base):
    __tablename__ = "signal_rsi"

    id = Column(Integer, primary_key=True, index=True)
    period = Column(Float)
    hightLevel = Column(Float)
    lowLevel = Column(Float)


class SignalGPT(Base):
    __tablename__ = "signal_gpt"

    id = Column(Integer, primary_key=True, index=True)
    text = Column(String)


class SignalSMA(Base):
    __tablename__ = "signal_sma"

    id = Column(Integer, primary_key=True, index=True)
    fastLength = Column(Integer)
    slowLength = Column(Integer)


class SignalEMA(Base):
    __tablename__ = "signal_ema"

    id = Column(Integer, primary_key=True, index=True)
    fastLength = Column(Integer)
    slowLength = Column(Integer)


class SignalBollinger(Base):
    __tablename__ = "signal_bollinger"

    id = Column(Integer, primary_key=True, index=True)
    period = Column(Integer)
    deviation = Column(Float)
    type_ma = Column(String)


class SignalMACD(Base):
    __tablename__ = "signal_macd"

    id = Column(Integer, primary_key=True, index=True)
    fastLength = Column(Integer)
    slowLength = Column(Integer)
    signalLength = Column(Integer)


class SignalAlligator(Base):
    __tablename__ = "signal_alligator"

    id = Column(Integer, primary_key=True, index=True)
    jaw_period = Column(Integer)
    jaw_shift = Column(Integer)
    teeth_period = Column(Integer)
    teeth_shift = Column(Integer)
    lips_period = Column(Integer)
    lips_shift = Column(Integer)
