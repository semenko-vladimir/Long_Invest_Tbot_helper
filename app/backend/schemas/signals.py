from typing import Optional
from pydantic import BaseModel


# SignalTPSL schemas
class SignalTPSLBase(BaseModel):
    take_profit: Optional[float] = None
    stop_loss: Optional[float] = None


class SignalTPSLCreate(SignalTPSLBase):
    take_profit: float
    stop_loss: float


class SignalTPSLUpdate(SignalTPSLBase):
    pass


class SignalTPSLResponse(SignalTPSLBase):
    id: int

    class Config:
        orm_mode = True


# SignalRSI schemas
class SignalRSIBase(BaseModel):
    period: Optional[float] = None
    hightLevel: Optional[float] = None
    lowLevel: Optional[float] = None


class SignalRSICreate(SignalRSIBase):
    period: float
    hightLevel: float
    lowLevel: float


class SignalRSIUpdate(SignalRSIBase):
    pass


class SignalRSIResponse(SignalRSIBase):
    id: int

    class Config:
        orm_mode = True


# SignalGPT schemas
class SignalGPTBase(BaseModel):
    text: Optional[str] = None


class SignalGPTCreate(SignalGPTBase):
    text: str


class SignalGPTUpdate(SignalGPTBase):
    pass


class SignalGPTResponse(SignalGPTBase):
    id: int

    class Config:
        orm_mode = True


# SignalSMA schemas
class SignalSMABase(BaseModel):
    fastLength: Optional[int] = None
    slowLength: Optional[int] = None


class SignalSMACreate(SignalSMABase):
    fastLength: int
    slowLength: int


class SignalSMAUpdate(SignalSMABase):
    pass


class SignalSMAResponse(SignalSMABase):
    id: int

    class Config:
        orm_mode = True


# SignalEMA schemas
class SignalEMABase(BaseModel):
    fastLength: Optional[int] = None
    slowLength: Optional[int] = None


class SignalEMACreate(SignalEMABase):
    fastLength: int
    slowLength: int


class SignalEMAUpdate(SignalEMABase):
    pass


class SignalEMAResponse(SignalEMABase):
    id: int

    class Config:
        orm_mode = True


# SignalBollinger schemas
class SignalBollingerBase(BaseModel):
    period: Optional[int] = None
    deviation: Optional[float] = None
    type_ma: Optional[str] = None


class SignalBollingerCreate(SignalBollingerBase):
    period: int
    deviation: float
    type_ma: str


class SignalBollingerUpdate(SignalBollingerBase):
    pass


class SignalBollingerResponse(SignalBollingerBase):
    id: int

    class Config:
        orm_mode = True


# SignalMACD schemas
class SignalMACDBase(BaseModel):
    fastLength: Optional[int] = None
    slowLength: Optional[int] = None
    signalLength: Optional[int] = None


class SignalMACDCreate(SignalMACDBase):
    fastLength: int
    slowLength: int
    signalLength: int


class SignalMACDUpdate(SignalMACDBase):
    pass


class SignalMACDResponse(SignalMACDBase):
    id: int

    class Config:
        orm_mode = True


# SignalAlligator schemas
class SignalAlligatorBase(BaseModel):
    jaw_period: Optional[int] = None
    jaw_shift: Optional[int] = None
    teeth_period: Optional[int] = None
    teeth_shift: Optional[int] = None
    lips_period: Optional[int] = None
    lips_shift: Optional[int] = None


class SignalAlligatorCreate(SignalAlligatorBase):
    jaw_period: int
    jaw_shift: int
    teeth_period: int
    teeth_shift: int
    lips_period: int
    lips_shift: int


class SignalAlligatorUpdate(SignalAlligatorBase):
    pass


class SignalAlligatorResponse(SignalAlligatorBase):
    id: int

    class Config:
        orm_mode = True
