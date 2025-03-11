from typing import Optional
from datetime import datetime
from pydantic import BaseModel


# Margin schemas
class MarginBase(BaseModel):
    margin: float
    ticker: str
    signal: str
    time: Optional[datetime] = None


class MarginCreate(MarginBase):
    pass


class MarginResponse(MarginBase):
    id: int

    class Config:
        orm_mode = True


# Buy schemas
class BuyBase(BaseModel):
    price: float
    ticker: str
    signal: str
    time: Optional[datetime] = None


class BuyCreate(BuyBase):
    pass


class BuyResponse(BuyBase):
    id: int

    class Config:
        orm_mode = True


# Instrument schemas
class InstrumentBase(BaseModel):
    ticker: str
    figi: str


class InstrumentCreate(InstrumentBase):
    pass


class InstrumentUpdate(InstrumentBase):
    ticker: Optional[str] = None
    figi: Optional[str] = None


class InstrumentResponse(InstrumentBase):
    id: int

    class Config:
        orm_mode = True


# Order schemas
class OrderBase(BaseModel):
    order_id: int
    ticker: str
    signal: str
    bm_value: float
    operation_type: str


class OrderCreate(OrderBase):
    pass


class OrderUpdate(OrderBase):
    order_id: Optional[int] = None
    ticker: Optional[str] = None
    signal: Optional[str] = None
    bm_value: Optional[float] = None
    operation_type: Optional[str] = None


class OrderResponse(OrderBase):
    id: int

    class Config:
        orm_mode = True
