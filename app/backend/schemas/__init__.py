# Import all schemas here for easy access
from app.backend.schemas.config import SchedulerConfigBase, SchedulerConfigCreate, SchedulerConfigUpdate, SchedulerConfigResponse
from app.backend.schemas.trading import (
    MarginBase, MarginCreate, MarginResponse,
    BuyBase, BuyCreate, BuyResponse,
    InstrumentBase, InstrumentCreate, InstrumentUpdate, InstrumentResponse,
    OrderBase, OrderCreate, OrderUpdate, OrderResponse
)
