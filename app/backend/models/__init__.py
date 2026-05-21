from app.backend.models.database import Base, engine, get_db, SessionLocal

# Import all models here so that they are registered with SQLAlchemy
from app.backend.models.research import ResearchSnapshot
from app.backend.models.trading import (
    Buy,
    Instrument,
    InvestmentPlan,
    InvestmentPlanExecution,
    Margin,
    Order,
)

# Create all tables in the database
def create_all_tables():
    from app.services.user_database import configure_runtime_databases

    configure_runtime_databases()
