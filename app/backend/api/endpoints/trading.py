from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.backend.models.database import get_db
from app.backend.models.trading import Margin, Buy, Order
from app.backend.schemas.trading import (
    MarginCreate, MarginResponse,
    BuyCreate, BuyResponse,
    OrderCreate, OrderResponse
)

router = APIRouter()


# Margin endpoints
@router.get("/margin/", response_model=List[MarginResponse])
def read_margins(
    skip: int = 0, limit: int = 100, db: Session = Depends(get_db)
):
    """
    Получить все маржинальные позиции.
    """
    margins = db.query(Margin).offset(skip).limit(limit).all()
    return margins


@router.post("/margin/", response_model=MarginResponse)
def create_margin(margin: MarginCreate, db: Session = Depends(get_db)):
    """
    Создать новую маржинальную позицию.
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
    Получить все покупки.
    """
    buys = db.query(Buy).offset(skip).limit(limit).all()
    return buys


@router.post("/buy/", response_model=BuyResponse)
def create_buy(buy: BuyCreate, db: Session = Depends(get_db)):
    """
    Создать новую покупку.
    """
    db_buy = Buy(**buy.dict())
    db.add(db_buy)
    db.commit()
    db.refresh(db_buy)
    return db_buy


# Order endpoints
@router.get("/orders/", response_model=List[OrderResponse])
def read_orders(
    skip: int = 0, limit: int = 100, db: Session = Depends(get_db)
):
    """
    Получить все торговые поручения.
    """
    orders = db.query(Order).offset(skip).limit(limit).all()
    return orders


@router.post("/orders/", response_model=OrderResponse)
def create_order(order: OrderCreate, db: Session = Depends(get_db)):
    """
    Создать новое торговое поручение.
    """
    db_order = Order(**order.dict())
    db.add(db_order)
    db.commit()
    db.refresh(db_order)
    return db_order


@router.delete("/orders/{order_id}", response_model=OrderResponse)
def delete_order(order_id: str, db: Session = Depends(get_db)):
    """
    Удалить заказ по order_id.
    """
    db_order = db.query(Order).filter(Order.order_id == order_id).first()
    if db_order is None:
        raise HTTPException(status_code=404, detail="Order not found")
    
    db.delete(db_order)
    db.commit()
    return db_order
