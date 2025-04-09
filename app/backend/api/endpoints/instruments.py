from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.backend.models.database import get_db
from app.backend.models.trading import Instrument
from app.backend.schemas.trading import (
    InstrumentCreate, InstrumentUpdate, InstrumentResponse
)

router = APIRouter()

# Instrument endpoints
@router.get("/", response_model=List[InstrumentResponse])
def read_instruments(
    skip: int = 0, limit: int = 100, db: Session = Depends(get_db)
):
    """
    Получить все инструменты.
    """
    instruments = db.query(Instrument).offset(skip).limit(limit).all()
    return instruments


@router.get("/ticker/{ticker}", response_model=InstrumentResponse)
def read_instrument_by_ticker(ticker: str, db: Session = Depends(get_db)):
    """
    Получить инструмент по тикеру.
    """
    instrument = db.query(Instrument).filter(Instrument.ticker == ticker).first()
    if instrument is None:
        raise HTTPException(status_code=404, detail="Instrument not found")
    return instrument


@router.get("/figi/{figi}", response_model=InstrumentResponse)
def read_instrument_by_figi(figi: str, db: Session = Depends(get_db)):
    """
    Получить инструмент по FIGI.
    """
    instrument = db.query(Instrument).filter(Instrument.figi == figi).first()
    if instrument is None:
        raise HTTPException(status_code=404, detail="Instrument not found")
    return instrument


@router.post("/", response_model=InstrumentResponse)
def create_instrument(instrument: InstrumentCreate, db: Session = Depends(get_db)):
    """
    Создать новый инструмент.
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


@router.delete("/ticker/{ticker}", response_model=InstrumentResponse)
def delete_instrument_by_ticker(ticker: str, db: Session = Depends(get_db)):
    """
    Удалить инструмент по тикеру.
    """
    db_instrument = db.query(Instrument).filter(Instrument.ticker == ticker).first()
    if db_instrument is None:
        raise HTTPException(status_code=404, detail="Instrument not found")
    
    db.delete(db_instrument)
    db.commit()
    return db_instrument


@router.delete("/all", response_model=dict)
def delete_all_instruments(db: Session = Depends(get_db)):
    """
    Удалить все инструменты.
    """
    count = db.query(Instrument).delete()
    db.commit()
    return {"deleted": count}
