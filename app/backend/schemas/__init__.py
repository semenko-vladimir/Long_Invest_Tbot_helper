# Import all schemas here for easy access
from app.backend.schemas.config import SchedulerConfigBase, SchedulerConfigCreate, SchedulerConfigUpdate, SchedulerConfigResponse
from app.backend.schemas.signals import (
    SignalTPSLBase, SignalTPSLCreate, SignalTPSLUpdate, SignalTPSLResponse,
    SignalRSIBase, SignalRSICreate, SignalRSIUpdate, SignalRSIResponse,
    SignalGPTBase, SignalGPTCreate, SignalGPTUpdate, SignalGPTResponse,
    SignalSMABase, SignalSMACreate, SignalSMAUpdate, SignalSMAResponse,
    SignalEMABase, SignalEMACreate, SignalEMAUpdate, SignalEMAResponse,
    SignalBollingerBase, SignalBollingerCreate, SignalBollingerUpdate, SignalBollingerResponse,
    SignalMACDBase, SignalMACDCreate, SignalMACDUpdate, SignalMACDResponse,
    SignalAlligatorBase, SignalAlligatorCreate, SignalAlligatorUpdate, SignalAlligatorResponse
)
from app.backend.schemas.strategy import (
    StrategySignalsBase, StrategySignalsCreate, StrategySignalsUpdate, StrategySignalsResponse,
    StrategySettingsBase, StrategySettingsCreate, StrategySettingsUpdate, StrategySettingsResponse
)
from app.backend.schemas.trading import (
    MarginBase, MarginCreate, MarginResponse,
    BuyBase, BuyCreate, BuyResponse,
    InstrumentBase, InstrumentCreate, InstrumentUpdate, InstrumentResponse,
    OrderBase, OrderCreate, OrderUpdate, OrderResponse
)
