from typing import List, Optional
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.backend.models.database import get_db
from app.backend.models.trading import Margin, Buy, Instrument, Order
from app.backend.schemas.trading import (
    MarginCreate, MarginResponse,
    BuyCreate, BuyResponse,
    InstrumentCreate, InstrumentUpdate, InstrumentResponse,
    OrderCreate, OrderUpdate, OrderResponse
)

router = APIRouter()


# Margin endpoints
@router.get("/margin/", response_model=List[MarginResponse])
def read_margins(
    skip: int = 0, limit: int = 100, db: Session = Depends(get_db)
):
    """
    Retrieve all margin entries.
    """
    margins = db.query(Margin).offset(skip).limit(limit).all()
    return margins


@router.get("/margin/{margin_id}", response_model=MarginResponse)
def read_margin(margin_id: int, db: Session = Depends(get_db)):
    """
    Get a specific margin entry by ID.
    """
    margin = db.query(Margin).filter(Margin.id == margin_id).first()
    if margin is None:
        raise HTTPException(status_code=404, detail="Margin not found")
    return margin


@router.post("/margin/", response_model=MarginResponse)
def create_margin(margin: MarginCreate, db: Session = Depends(get_db)):
    """
    Create a new margin entry.
    """
    db_margin = Margin(**margin.dict())
    db.add(db_margin)
    db.commit()
    db.refresh(db_margin)
    return db_margin


# Buy endpoints
@router.get("/buy/", response_model=List[BuyResponse])
def read_buys(
    skip: int = 0, limit: int = 100, db: Session = Depends(get_db)
):
    """
    Retrieve all buy entries.
    """
    buys = db.query(Buy).offset(skip).limit(limit).all()
    return buys


@router.get("/buy/{buy_id}", response_model=BuyResponse)
def read_buy(buy_id: int, db: Session = Depends(get_db)):
    """
    Get a specific buy entry by ID.
    """
    buy = db.query(Buy).filter(Buy.id == buy_id).first()
    if buy is None:
        raise HTTPException(status_code=404, detail="Buy not found")
    return buy


@router.post("/buy/", response_model=BuyResponse)
def create_buy(buy: BuyCreate, db: Session = Depends(get_db)):
    """
    Create a new buy entry.
    """
    db_buy = Buy(**buy.dict())
    db.add(db_buy)
    db.commit()
    db.refresh(db_buy)
    return db_buy


# Instrument endpoints
@router.get("/instruments/", response_model=List[InstrumentResponse])
def read_instruments(
    skip: int = 0, limit: int = 100, db: Session = Depends(get_db)
):
    """
    Retrieve all instrument entries.
    """
    instruments = db.query(Instrument).offset(skip).limit(limit).all()
    return instruments


@router.get("/instruments/{instrument_id}", response_model=InstrumentResponse)
def read_instrument(instrument_id: int, db: Session = Depends(get_db)):
    """
    Get a specific instrument entry by ID.
    """
    instrument = db.query(Instrument).filter(Instrument.id == instrument_id).first()
    if instrument is None:
        raise HTTPException(status_code=404, detail="Instrument not found")
    return instrument


@router.get("/instruments/ticker/{ticker}", response_model=InstrumentResponse)
def read_instrument_by_ticker(ticker: str, db: Session = Depends(get_db)):
    """
    Get a specific instrument entry by ticker.
    """
    instrument = db.query(Instrument).filter(Instrument.ticker == ticker).first()
    if instrument is None:
        raise HTTPException(status_code=404, detail="Instrument not found")
    return instrument


@router.get("/instruments/figi/{figi}", response_model=InstrumentResponse)
def read_instrument_by_figi(figi: str, db: Session = Depends(get_db)):
    """
    Get a specific instrument entry by FIGI.
    """
    instrument = db.query(Instrument).filter(Instrument.figi == figi).first()
    if instrument is None:
        raise HTTPException(status_code=404, detail="Instrument not found")
    return instrument


@router.post("/instruments/", response_model=InstrumentResponse)
def create_instrument(instrument: InstrumentCreate, db: Session = Depends(get_db)):
    """
    Create a new instrument entry.
    """
    # Check if instrument with this ticker already exists
    existing_instrument = db.query(Instrument).filter(Instrument.ticker == instrument.ticker).first()
    if existing_instrument:
        raise HTTPException(status_code=400, detail="Instrument with this ticker already exists")
    
    db_instrument = Instrument(**instrument.dict())
    db.add(db_instrument)
    db.commit()
    db.refresh(db_instrument)
    return db_instrument


@router.put("/instruments/{instrument_id}", response_model=InstrumentResponse)
def update_instrument(
    instrument_id: int, instrument: InstrumentUpdate, db: Session = Depends(get_db)
):
    """
    Update an instrument entry.
    """
    db_instrument = db.query(Instrument).filter(Instrument.id == instrument_id).first()
    if db_instrument is None:
        raise HTTPException(status_code=404, detail="Instrument not found")
    
    update_data = instrument.dict(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_instrument, key, value)
    
    db.commit()
    db.refresh(db_instrument)
    return db_instrument


@router.delete("/instruments/{instrument_id}", response_model=InstrumentResponse)
def delete_instrument(instrument_id: int, db: Session = Depends(get_db)):
    """
    Delete an instrument entry.
    """
    db_instrument = db.query(Instrument).filter(Instrument.id == instrument_id).first()
    if db_instrument is None:
        raise HTTPException(status_code=404, detail="Instrument not found")
    
    db.delete(db_instrument)
    db.commit()
    return db_instrument


@router.delete("/instruments/ticker/{ticker}", response_model=InstrumentResponse)
def delete_instrument_by_ticker(ticker: str, db: Session = Depends(get_db)):
    """
    Delete an instrument entry by ticker.
    """
    db_instrument = db.query(Instrument).filter(Instrument.ticker == ticker).first()
    if db_instrument is None:
        raise HTTPException(status_code=404, detail="Instrument not found")
    
    db.delete(db_instrument)
    db.commit()
    return db_instrument


@router.delete("/instruments/all", response_model=dict)
def delete_all_instruments(db: Session = Depends(get_db)):
    """
    Delete all instrument entries.
    """
    count = db.query(Instrument).delete()
    db.commit()
    return {"deleted": count}


# Order endpoints
@router.get("/orders/", response_model=List[OrderResponse])
def read_orders(
    skip: int = 0, limit: int = 100, db: Session = Depends(get_db)
):
    """
    Retrieve all order entries.
    """
    orders = db.query(Order).offset(skip).limit(limit).all()
    return orders


@router.get("/orders/{order_id}", response_model=OrderResponse)
def read_order(order_id: int, db: Session = Depends(get_db)):
    """
    Get a specific order entry by ID.
    """
    order = db.query(Order).filter(Order.id == order_id).first()
    if order is None:
        raise HTTPException(status_code=404, detail="Order not found")
    return order


@router.get("/orders/order_id/{order_id}", response_model=OrderResponse)
def read_order_by_order_id(order_id: str, db: Session = Depends(get_db)):
    """
    Get a specific order entry by order_id.
    """
    order = db.query(Order).filter(Order.order_id == order_id).first()
    if order is None:
        raise HTTPException(status_code=404, detail="Order not found")
    return order


@router.post("/orders/", response_model=OrderResponse)
def create_order(order: OrderCreate, db: Session = Depends(get_db)):
    """
    Create a new order entry.
    """
    db_order = Order(**order.dict())
    db.add(db_order)
    db.commit()
    db.refresh(db_order)
    return db_order


@router.put("/orders/{order_id}", response_model=OrderResponse)
def update_order(
    order_id: int, order: OrderUpdate, db: Session = Depends(get_db)
):
    """
    Update an order entry.
    """
    db_order = db.query(Order).filter(Order.id == order_id).first()
    if db_order is None:
        raise HTTPException(status_code=404, detail="Order not found")
    
    update_data = order.dict(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_order, key, value)
    
    db.commit()
    db.refresh(db_order)
    return db_order


@router.delete("/orders/{order_id}", response_model=OrderResponse)
def delete_order(order_id: int, db: Session = Depends(get_db)):
    """
    Delete an order entry.
    """
    db_order = db.query(Order).filter(Order.id == order_id).first()
    if db_order is None:
        raise HTTPException(status_code=404, detail="Order not found")
    
    db.delete(db_order)
    db.commit()
    return db_order


@router.delete("/orders/order_id/{order_id}", response_model=OrderResponse)
def delete_order_by_order_id(order_id: str, db: Session = Depends(get_db)):
    """
    Delete an order entry by order_id.
    """
    db_order = db.query(Order).filter(Order.order_id == order_id).first()
    if db_order is None:
        raise HTTPException(status_code=404, detail="Order not found")
    
    db.delete(db_order)
    db.commit()
    return db_order
