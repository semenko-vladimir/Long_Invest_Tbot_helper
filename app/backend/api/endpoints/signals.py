from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.backend.models.database import get_db
from app.backend.models.signals import (
    SignalTPSL, SignalRSI, SignalGPT, SignalSMA, SignalEMA, 
    SignalBollinger, SignalMACD, SignalAlligator
)
from app.backend.schemas.signals import (
    SignalTPSLCreate, SignalTPSLUpdate, SignalTPSLResponse,
    SignalRSICreate, SignalRSIUpdate, SignalRSIResponse,
    SignalGPTCreate, SignalGPTUpdate, SignalGPTResponse,
    SignalSMACreate, SignalSMAUpdate, SignalSMAResponse,
    SignalEMACreate, SignalEMAUpdate, SignalEMAResponse,
    SignalBollingerCreate, SignalBollingerUpdate, SignalBollingerResponse,
    SignalMACDCreate, SignalMACDUpdate, SignalMACDResponse,
    SignalAlligatorCreate, SignalAlligatorUpdate, SignalAlligatorResponse
)

router = APIRouter()

# TPSL Signal endpoints
@router.get("/tpsl/", response_model=SignalTPSLResponse)
def read_tpsl_signal(db: Session = Depends(get_db)):
    """
    Получить настройки сигнала Take Profit/Stop Loss.
    """
    signal = db.query(SignalTPSL).first()
    if signal is None:
        raise HTTPException(status_code=404, detail="TPSL signal not found")
    return signal


@router.post("/tpsl/", response_model=SignalTPSLResponse)
def create_tpsl_signal(signal: SignalTPSLCreate, db: Session = Depends(get_db)):
    """
    Создать новый сигнал Take Profit/Stop Loss.
    """
    db_signal = SignalTPSL(**signal.dict())
    db.add(db_signal)
    db.commit()
    db.refresh(db_signal)
    return db_signal


@router.put("/tpsl/", response_model=SignalTPSLResponse)
def update_tpsl_signal(signal: SignalTPSLUpdate, db: Session = Depends(get_db)):
    """
    Обновить сигнал Take Profit/Stop Loss.
    """
    db_signal = db.query(SignalTPSL).first()
    if db_signal is None:
        raise HTTPException(status_code=404, detail="TPSL signal not found")
    
    update_data = signal.dict(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_signal, key, value)
    
    db.commit()
    db.refresh(db_signal)
    return db_signal


# RSI Signal endpoints
@router.get("/rsi/", response_model=SignalRSIResponse)
def read_rsi_signal(db: Session = Depends(get_db)):
    """
    Получить настройки сигнала RSI.
    """
    signal = db.query(SignalRSI).first()
    if signal is None:
        raise HTTPException(status_code=404, detail="RSI signal not found")
    return signal


@router.post("/rsi/", response_model=SignalRSIResponse)
def create_rsi_signal(signal: SignalRSICreate, db: Session = Depends(get_db)):
    """
    Создать новый сигнал RSI.
    """
    db_signal = SignalRSI(**signal.dict())
    db.add(db_signal)
    db.commit()
    db.refresh(db_signal)
    return db_signal


@router.put("/rsi/", response_model=SignalRSIResponse)
def update_rsi_signal(signal: SignalRSIUpdate, db: Session = Depends(get_db)):
    """
    Обновить сигнал RSI.
    """
    db_signal = db.query(SignalRSI).first()
    if db_signal is None:
        raise HTTPException(status_code=404, detail="RSI signal not found")
    
    update_data = signal.dict(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_signal, key, value)
    
    db.commit()
    db.refresh(db_signal)
    return db_signal


# GPT Signal endpoints
@router.get("/gpt/", response_model=SignalGPTResponse)
def read_gpt_signal(db: Session = Depends(get_db)):
    """
    Получить настройки сигнала GPT.
    """
    signal = db.query(SignalGPT).first()
    if signal is None:
        raise HTTPException(status_code=404, detail="GPT signal not found")
    return signal


@router.post("/gpt/", response_model=SignalGPTResponse)
def create_gpt_signal(signal: SignalGPTCreate, db: Session = Depends(get_db)):
    """
    Создать новый сигнал GPT.
    """
    db_signal = SignalGPT(**signal.dict())
    db.add(db_signal)
    db.commit()
    db.refresh(db_signal)
    return db_signal


@router.put("/gpt/", response_model=SignalGPTResponse)
def update_gpt_signal(signal: SignalGPTUpdate, db: Session = Depends(get_db)):
    """
    Обновить сигнал GPT.
    """
    db_signal = db.query(SignalGPT).first()
    if db_signal is None:
        raise HTTPException(status_code=404, detail="GPT signal not found")
    
    update_data = signal.dict(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_signal, key, value)
    
    db.commit()
    db.refresh(db_signal)
    return db_signal


# SMA Signal endpoints
@router.get("/sma/", response_model=SignalSMAResponse)
def read_sma_signal(db: Session = Depends(get_db)):
    """
    Получить настройки сигнала SMA.
    """
    signal = db.query(SignalSMA).first()
    if signal is None:
        raise HTTPException(status_code=404, detail="SMA signal not found")
    return signal


@router.post("/sma/", response_model=SignalSMAResponse)
def create_sma_signal(signal: SignalSMACreate, db: Session = Depends(get_db)):
    """
    Создать новый сигнал SMA.
    """
    db_signal = SignalSMA(**signal.dict())
    db.add(db_signal)
    db.commit()
    db.refresh(db_signal)
    return db_signal


@router.put("/sma/", response_model=SignalSMAResponse)
def update_sma_signal(signal: SignalSMAUpdate, db: Session = Depends(get_db)):
    """
    Обновить сигнал SMA.
    """
    db_signal = db.query(SignalSMA).first()
    if db_signal is None:
        raise HTTPException(status_code=404, detail="SMA signal not found")
    
    update_data = signal.dict(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_signal, key, value)
    
    db.commit()
    db.refresh(db_signal)
    return db_signal


# EMA Signal endpoints
@router.get("/ema/", response_model=SignalEMAResponse)
def read_ema_signal(db: Session = Depends(get_db)):
    """
    Получить настройки сигнала EMA.
    """
    signal = db.query(SignalEMA).first()
    if signal is None:
        raise HTTPException(status_code=404, detail="EMA signal not found")
    return signal


@router.post("/ema/", response_model=SignalEMAResponse)
def create_ema_signal(signal: SignalEMACreate, db: Session = Depends(get_db)):
    """
    Создать новый сигнал EMA.
    """
    db_signal = SignalEMA(**signal.dict())
    db.add(db_signal)
    db.commit()
    db.refresh(db_signal)
    return db_signal


@router.put("/ema/", response_model=SignalEMAResponse)
def update_ema_signal(signal: SignalEMAUpdate, db: Session = Depends(get_db)):
    """
    Обновить сигнал EMA.
    """
    db_signal = db.query(SignalEMA).first()
    if db_signal is None:
        raise HTTPException(status_code=404, detail="EMA signal not found")
    
    update_data = signal.dict(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_signal, key, value)
    
    db.commit()
    db.refresh(db_signal)
    return db_signal


# Bollinger Signal endpoints
@router.get("/bollinger/", response_model=SignalBollingerResponse)
def read_bollinger_signal(db: Session = Depends(get_db)):
    """
    Получить настройки сигнала Bollinger.
    """
    signal = db.query(SignalBollinger).first()
    if signal is None:
        raise HTTPException(status_code=404, detail="Bollinger signal not found")
    return signal


@router.post("/bollinger/", response_model=SignalBollingerResponse)
def create_bollinger_signal(signal: SignalBollingerCreate, db: Session = Depends(get_db)):
    """
    Создать новый сигнал Bollinger.
    """
    db_signal = SignalBollinger(**signal.dict())
    db.add(db_signal)
    db.commit()
    db.refresh(db_signal)
    return db_signal


@router.put("/bollinger/", response_model=SignalBollingerResponse)
def update_bollinger_signal(signal: SignalBollingerUpdate, db: Session = Depends(get_db)):
    """
    Обновить сигнал Bollinger.
    """
    db_signal = db.query(SignalBollinger).first()
    if db_signal is None:
        raise HTTPException(status_code=404, detail="Bollinger signal not found")
    
    update_data = signal.dict(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_signal, key, value)
    
    db.commit()
    db.refresh(db_signal)
    return db_signal


# MACD Signal endpoints
@router.get("/macd/", response_model=SignalMACDResponse)
def read_macd_signal(db: Session = Depends(get_db)):
    """
    Получить настройки сигнала MACD.
    """
    signal = db.query(SignalMACD).first()
    if signal is None:
        raise HTTPException(status_code=404, detail="MACD signal not found")
    return signal


@router.post("/macd/", response_model=SignalMACDResponse)
def create_macd_signal(signal: SignalMACDCreate, db: Session = Depends(get_db)):
    """
    Создать новый сигнал MACD.
    """
    db_signal = SignalMACD(**signal.dict())
    db.add(db_signal)
    db.commit()
    db.refresh(db_signal)
    return db_signal


@router.put("/macd/", response_model=SignalMACDResponse)
def update_macd_signal(signal: SignalMACDUpdate, db: Session = Depends(get_db)):
    """
    Обновить сигнал MACD.
    """
    db_signal = db.query(SignalMACD).first()
    if db_signal is None:
        raise HTTPException(status_code=404, detail="MACD signal not found")
    
    update_data = signal.dict(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_signal, key, value)
    
    db.commit()
    db.refresh(db_signal)
    return db_signal


# Alligator Signal endpoints
@router.get("/alligator/", response_model=SignalAlligatorResponse)
def read_alligator_signal(db: Session = Depends(get_db)):
    """
    Получить настройки сигнала Alligator.
    """
    signal = db.query(SignalAlligator).first()
    if signal is None:
        raise HTTPException(status_code=404, detail="Alligator signal not found")
    return signal


@router.post("/alligator/", response_model=SignalAlligatorResponse)
def create_alligator_signal(signal: SignalAlligatorCreate, db: Session = Depends(get_db)):
    """
    Создать новый сигнал Alligator.
    """
    db_signal = SignalAlligator(**signal.dict())
    db.add(db_signal)
    db.commit()
    db.refresh(db_signal)
    return db_signal


@router.put("/alligator/", response_model=SignalAlligatorResponse)
def update_alligator_signal(signal: SignalAlligatorUpdate, db: Session = Depends(get_db)):
    """
    Обновить сигнал Alligator.
    """
    db_signal = db.query(SignalAlligator).first()
    if db_signal is None:
        raise HTTPException(status_code=404, detail="Alligator signal not found")
    
    update_data = signal.dict(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_signal, key, value)
    
    db.commit()
    db.refresh(db_signal)
    return db_signal
