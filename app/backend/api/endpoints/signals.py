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
@router.get("/tpsl/", response_model=List[SignalTPSLResponse])
def read_tpsl_signals(
    skip: int = 0, limit: int = 100, db: Session = Depends(get_db)
):
    """
    Retrieve all TPSL signal entries.
    """
    signals = db.query(SignalTPSL).offset(skip).limit(limit).all()
    return signals


@router.get("/tpsl/{signal_id}", response_model=SignalTPSLResponse)
def read_tpsl_signal(signal_id: int, db: Session = Depends(get_db)):
    """
    Get a specific TPSL signal by ID.
    """
    signal = db.query(SignalTPSL).filter(SignalTPSL.id == signal_id).first()
    if signal is None:
        raise HTTPException(status_code=404, detail="TPSL signal not found")
    return signal


@router.post("/tpsl/", response_model=SignalTPSLResponse)
def create_tpsl_signal(signal: SignalTPSLCreate, db: Session = Depends(get_db)):
    """
    Create a new TPSL signal.
    """
    db_signal = SignalTPSL(**signal.dict())
    db.add(db_signal)
    db.commit()
    db.refresh(db_signal)
    return db_signal


@router.put("/tpsl/{signal_id}", response_model=SignalTPSLResponse)
def update_tpsl_signal(
    signal_id: int, signal: SignalTPSLUpdate, db: Session = Depends(get_db)
):
    """
    Update a TPSL signal.
    """
    db_signal = db.query(SignalTPSL).filter(SignalTPSL.id == signal_id).first()
    if db_signal is None:
        raise HTTPException(status_code=404, detail="TPSL signal not found")
    
    update_data = signal.dict(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_signal, key, value)
    
    db.commit()
    db.refresh(db_signal)
    return db_signal


# RSI Signal endpoints
@router.get("/rsi/", response_model=List[SignalRSIResponse])
def read_rsi_signals(
    skip: int = 0, limit: int = 100, db: Session = Depends(get_db)
):
    """
    Retrieve all RSI signal entries.
    """
    signals = db.query(SignalRSI).offset(skip).limit(limit).all()
    return signals


@router.get("/rsi/{signal_id}", response_model=SignalRSIResponse)
def read_rsi_signal(signal_id: int, db: Session = Depends(get_db)):
    """
    Get a specific RSI signal by ID.
    """
    signal = db.query(SignalRSI).filter(SignalRSI.id == signal_id).first()
    if signal is None:
        raise HTTPException(status_code=404, detail="RSI signal not found")
    return signal


@router.post("/rsi/", response_model=SignalRSIResponse)
def create_rsi_signal(signal: SignalRSICreate, db: Session = Depends(get_db)):
    """
    Create a new RSI signal.
    """
    db_signal = SignalRSI(**signal.dict())
    db.add(db_signal)
    db.commit()
    db.refresh(db_signal)
    return db_signal


@router.put("/rsi/{signal_id}", response_model=SignalRSIResponse)
def update_rsi_signal(
    signal_id: int, signal: SignalRSIUpdate, db: Session = Depends(get_db)
):
    """
    Update a RSI signal.
    """
    db_signal = db.query(SignalRSI).filter(SignalRSI.id == signal_id).first()
    if db_signal is None:
        raise HTTPException(status_code=404, detail="RSI signal not found")
    
    update_data = signal.dict(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_signal, key, value)
    
    db.commit()
    db.refresh(db_signal)
    return db_signal


# GPT Signal endpoints
@router.get("/gpt/", response_model=List[SignalGPTResponse])
def read_gpt_signals(
    skip: int = 0, limit: int = 100, db: Session = Depends(get_db)
):
    """
    Retrieve all GPT signal entries.
    """
    signals = db.query(SignalGPT).offset(skip).limit(limit).all()
    return signals


@router.get("/gpt/{signal_id}", response_model=SignalGPTResponse)
def read_gpt_signal(signal_id: int, db: Session = Depends(get_db)):
    """
    Get a specific GPT signal by ID.
    """
    signal = db.query(SignalGPT).filter(SignalGPT.id == signal_id).first()
    if signal is None:
        raise HTTPException(status_code=404, detail="GPT signal not found")
    return signal


@router.post("/gpt/", response_model=SignalGPTResponse)
def create_gpt_signal(signal: SignalGPTCreate, db: Session = Depends(get_db)):
    """
    Create a new GPT signal.
    """
    db_signal = SignalGPT(**signal.dict())
    db.add(db_signal)
    db.commit()
    db.refresh(db_signal)
    return db_signal


@router.put("/gpt/{signal_id}", response_model=SignalGPTResponse)
def update_gpt_signal(
    signal_id: int, signal: SignalGPTUpdate, db: Session = Depends(get_db)
):
    """
    Update a GPT signal.
    """
    db_signal = db.query(SignalGPT).filter(SignalGPT.id == signal_id).first()
    if db_signal is None:
        raise HTTPException(status_code=404, detail="GPT signal not found")
    
    update_data = signal.dict(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_signal, key, value)
    
    db.commit()
    db.refresh(db_signal)
    return db_signal


# SMA Signal endpoints
@router.get("/sma/", response_model=List[SignalSMAResponse])
def read_sma_signals(
    skip: int = 0, limit: int = 100, db: Session = Depends(get_db)
):
    """
    Retrieve all SMA signal entries.
    """
    signals = db.query(SignalSMA).offset(skip).limit(limit).all()
    return signals


@router.get("/sma/{signal_id}", response_model=SignalSMAResponse)
def read_sma_signal(signal_id: int, db: Session = Depends(get_db)):
    """
    Get a specific SMA signal by ID.
    """
    signal = db.query(SignalSMA).filter(SignalSMA.id == signal_id).first()
    if signal is None:
        raise HTTPException(status_code=404, detail="SMA signal not found")
    return signal


@router.post("/sma/", response_model=SignalSMAResponse)
def create_sma_signal(signal: SignalSMACreate, db: Session = Depends(get_db)):
    """
    Create a new SMA signal.
    """
    db_signal = SignalSMA(**signal.dict())
    db.add(db_signal)
    db.commit()
    db.refresh(db_signal)
    return db_signal


@router.put("/sma/{signal_id}", response_model=SignalSMAResponse)
def update_sma_signal(
    signal_id: int, signal: SignalSMAUpdate, db: Session = Depends(get_db)
):
    """
    Update a SMA signal.
    """
    db_signal = db.query(SignalSMA).filter(SignalSMA.id == signal_id).first()
    if db_signal is None:
        raise HTTPException(status_code=404, detail="SMA signal not found")
    
    update_data = signal.dict(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_signal, key, value)
    
    db.commit()
    db.refresh(db_signal)
    return db_signal


# EMA Signal endpoints
@router.get("/ema/", response_model=List[SignalEMAResponse])
def read_ema_signals(
    skip: int = 0, limit: int = 100, db: Session = Depends(get_db)
):
    """
    Retrieve all EMA signal entries.
    """
    signals = db.query(SignalEMA).offset(skip).limit(limit).all()
    return signals


@router.get("/ema/{signal_id}", response_model=SignalEMAResponse)
def read_ema_signal(signal_id: int, db: Session = Depends(get_db)):
    """
    Get a specific EMA signal by ID.
    """
    signal = db.query(SignalEMA).filter(SignalEMA.id == signal_id).first()
    if signal is None:
        raise HTTPException(status_code=404, detail="EMA signal not found")
    return signal


@router.post("/ema/", response_model=SignalEMAResponse)
def create_ema_signal(signal: SignalEMACreate, db: Session = Depends(get_db)):
    """
    Create a new EMA signal.
    """
    db_signal = SignalEMA(**signal.dict())
    db.add(db_signal)
    db.commit()
    db.refresh(db_signal)
    return db_signal


@router.put("/ema/{signal_id}", response_model=SignalEMAResponse)
def update_ema_signal(
    signal_id: int, signal: SignalEMAUpdate, db: Session = Depends(get_db)
):
    """
    Update a EMA signal.
    """
    db_signal = db.query(SignalEMA).filter(SignalEMA.id == signal_id).first()
    if db_signal is None:
        raise HTTPException(status_code=404, detail="EMA signal not found")
    
    update_data = signal.dict(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_signal, key, value)
    
    db.commit()
    db.refresh(db_signal)
    return db_signal


# Bollinger Signal endpoints
@router.get("/bollinger/", response_model=List[SignalBollingerResponse])
def read_bollinger_signals(
    skip: int = 0, limit: int = 100, db: Session = Depends(get_db)
):
    """
    Retrieve all Bollinger signal entries.
    """
    signals = db.query(SignalBollinger).offset(skip).limit(limit).all()
    return signals


@router.get("/bollinger/{signal_id}", response_model=SignalBollingerResponse)
def read_bollinger_signal(signal_id: int, db: Session = Depends(get_db)):
    """
    Get a specific Bollinger signal by ID.
    """
    signal = db.query(SignalBollinger).filter(SignalBollinger.id == signal_id).first()
    if signal is None:
        raise HTTPException(status_code=404, detail="Bollinger signal not found")
    return signal


@router.post("/bollinger/", response_model=SignalBollingerResponse)
def create_bollinger_signal(signal: SignalBollingerCreate, db: Session = Depends(get_db)):
    """
    Create a new Bollinger signal.
    """
    db_signal = SignalBollinger(**signal.dict())
    db.add(db_signal)
    db.commit()
    db.refresh(db_signal)
    return db_signal


@router.put("/bollinger/{signal_id}", response_model=SignalBollingerResponse)
def update_bollinger_signal(
    signal_id: int, signal: SignalBollingerUpdate, db: Session = Depends(get_db)
):
    """
    Update a Bollinger signal.
    """
    db_signal = db.query(SignalBollinger).filter(SignalBollinger.id == signal_id).first()
    if db_signal is None:
        raise HTTPException(status_code=404, detail="Bollinger signal not found")
    
    update_data = signal.dict(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_signal, key, value)
    
    db.commit()
    db.refresh(db_signal)
    return db_signal


# MACD Signal endpoints
@router.get("/macd/", response_model=List[SignalMACDResponse])
def read_macd_signals(
    skip: int = 0, limit: int = 100, db: Session = Depends(get_db)
):
    """
    Retrieve all MACD signal entries.
    """
    signals = db.query(SignalMACD).offset(skip).limit(limit).all()
    return signals


@router.get("/macd/{signal_id}", response_model=SignalMACDResponse)
def read_macd_signal(signal_id: int, db: Session = Depends(get_db)):
    """
    Get a specific MACD signal by ID.
    """
    signal = db.query(SignalMACD).filter(SignalMACD.id == signal_id).first()
    if signal is None:
        raise HTTPException(status_code=404, detail="MACD signal not found")
    return signal


@router.post("/macd/", response_model=SignalMACDResponse)
def create_macd_signal(signal: SignalMACDCreate, db: Session = Depends(get_db)):
    """
    Create a new MACD signal.
    """
    db_signal = SignalMACD(**signal.dict())
    db.add(db_signal)
    db.commit()
    db.refresh(db_signal)
    return db_signal


@router.put("/macd/{signal_id}", response_model=SignalMACDResponse)
def update_macd_signal(
    signal_id: int, signal: SignalMACDUpdate, db: Session = Depends(get_db)
):
    """
    Update a MACD signal.
    """
    db_signal = db.query(SignalMACD).filter(SignalMACD.id == signal_id).first()
    if db_signal is None:
        raise HTTPException(status_code=404, detail="MACD signal not found")
    
    update_data = signal.dict(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_signal, key, value)
    
    db.commit()
    db.refresh(db_signal)
    return db_signal


# Alligator Signal endpoints
@router.get("/alligator/", response_model=List[SignalAlligatorResponse])
def read_alligator_signals(
    skip: int = 0, limit: int = 100, db: Session = Depends(get_db)
):
    """
    Retrieve all Alligator signal entries.
    """
    signals = db.query(SignalAlligator).offset(skip).limit(limit).all()
    return signals


@router.get("/alligator/{signal_id}", response_model=SignalAlligatorResponse)
def read_alligator_signal(signal_id: int, db: Session = Depends(get_db)):
    """
    Get a specific Alligator signal by ID.
    """
    signal = db.query(SignalAlligator).filter(SignalAlligator.id == signal_id).first()
    if signal is None:
        raise HTTPException(status_code=404, detail="Alligator signal not found")
    return signal


@router.post("/alligator/", response_model=SignalAlligatorResponse)
def create_alligator_signal(signal: SignalAlligatorCreate, db: Session = Depends(get_db)):
    """
    Create a new Alligator signal.
    """
    db_signal = SignalAlligator(**signal.dict())
    db.add(db_signal)
    db.commit()
    db.refresh(db_signal)
    return db_signal


@router.put("/alligator/{signal_id}", response_model=SignalAlligatorResponse)
def update_alligator_signal(
    signal_id: int, signal: SignalAlligatorUpdate, db: Session = Depends(get_db)
):
    """
    Update an Alligator signal.
    """
    db_signal = db.query(SignalAlligator).filter(SignalAlligator.id == signal_id).first()
    if db_signal is None:
        raise HTTPException(status_code=404, detail="Alligator signal not found")
    
    update_data = signal.dict(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_signal, key, value)
    
    db.commit()
    db.refresh(db_signal)
    return db_signal
