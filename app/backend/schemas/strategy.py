from typing import Optional
from pydantic import BaseModel


# StrategySignals schemas
class StrategySignalsBase(BaseModel):
    tpls_trigger: Optional[bool] = None
    rsi_trigger: Optional[bool] = None
    sma_trigger: Optional[bool] = None
    ema_trigger: Optional[bool] = None
    alligator_trigger: Optional[bool] = None
    gpt_trigger: Optional[bool] = None
    lstm_trigger: Optional[bool] = None
    bollinger_trigger: Optional[bool] = None
    macd_trigger: Optional[bool] = None


class StrategySignalsCreate(StrategySignalsBase):
    tpls_trigger: bool
    rsi_trigger: bool
    sma_trigger: bool
    ema_trigger: bool
    alligator_trigger: bool
    gpt_trigger: bool
    lstm_trigger: bool
    bollinger_trigger: bool
    macd_trigger: bool


class StrategySignalsUpdate(StrategySignalsBase):
    pass


class StrategySignalsResponse(StrategySignalsBase):
    id: int

    class Config:
        orm_mode = True


# StrategySettings schemas
class StrategySettingsBase(BaseModel):
    time: Optional[str] = None
    auto_market: Optional[bool] = None
    quantity: Optional[int] = None
    joint: Optional[bool] = None
    sandbox_trigger: Optional[bool] = None


class StrategySettingsCreate(StrategySettingsBase):
    time: str
    auto_market: bool
    quantity: int
    joint: bool
    sandbox_trigger: bool


class StrategySettingsUpdate(StrategySettingsBase):
    pass


class StrategySettingsResponse(StrategySettingsBase):
    id: int

    class Config:
        orm_mode = True
