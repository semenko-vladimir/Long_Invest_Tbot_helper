from app.backend.models.database import Base, engine, get_db, SessionLocal

# Import all models here so that they are registered with SQLAlchemy
from app.backend.models.config import SchedulerConfig
from app.backend.models.signals import (
    SignalTPSL, SignalRSI, SignalGPT, SignalSMA, SignalEMA, 
    SignalBollinger, SignalMACD, SignalAlligator
)
from app.backend.models.strategy import StrategySignals, StrategySettings
from app.backend.models.trading import Margin, Buy, Instrument, Order

# Create all tables in the database
def create_all_tables():
    Base.metadata.create_all(bind=engine)
