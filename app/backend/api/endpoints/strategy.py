from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.backend.models.database import get_db
from app.backend.models.strategy import StrategySignals, StrategySettings
from app.backend.schemas.strategy import (
    StrategySignalsCreate, StrategySignalsUpdate, StrategySignalsResponse,
    StrategySettingsCreate, StrategySettingsUpdate, StrategySettingsResponse
)

router = APIRouter()


# Strategy Signals endpoints
@router.get("/signals/", response_model=List[StrategySignalsResponse])
def read_strategy_signals(
    skip: int = 0, limit: int = 100, db: Session = Depends(get_db)
):
    """
    Retrieve all strategy signals entries.
    """
    signals = db.query(StrategySignals).offset(skip).limit(limit).all()
    return signals


@router.get("/signals/{signal_id}", response_model=StrategySignalsResponse)
def read_strategy_signal(signal_id: int, db: Session = Depends(get_db)):
    """
    Get a specific strategy signals entry by ID.
    """
    signal = db.query(StrategySignals).filter(StrategySignals.id == signal_id).first()
    if signal is None:
        raise HTTPException(status_code=404, detail="Strategy signals not found")
    return signal


@router.post("/signals/", response_model=StrategySignalsResponse)
def create_strategy_signals(signal: StrategySignalsCreate, db: Session = Depends(get_db)):
    """
    Create a new strategy signals entry.
    """
    db_signal = StrategySignals(**signal.dict())
    db.add(db_signal)
    db.commit()
    db.refresh(db_signal)
    return db_signal


@router.put("/signals/{signal_id}", response_model=StrategySignalsResponse)
def update_strategy_signals(
    signal_id: int, signal: StrategySignalsUpdate, db: Session = Depends(get_db)
):
    """
    Update a strategy signals entry.
    """
    db_signal = db.query(StrategySignals).filter(StrategySignals.id == signal_id).first()
    if db_signal is None:
        raise HTTPException(status_code=404, detail="Strategy signals not found")
    
    update_data = signal.dict(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_signal, key, value)
    
    db.commit()
    db.refresh(db_signal)
    return db_signal


# Strategy Settings endpoints
@router.get("/settings/", response_model=List[StrategySettingsResponse])
def read_strategy_settings(
    skip: int = 0, limit: int = 100, db: Session = Depends(get_db)
):
    """
    Retrieve all strategy settings entries.
    """
    settings = db.query(StrategySettings).offset(skip).limit(limit).all()
    return settings


@router.get("/settings/{setting_id}", response_model=StrategySettingsResponse)
def read_strategy_setting(setting_id: int, db: Session = Depends(get_db)):
    """
    Get a specific strategy settings entry by ID.
    """
    setting = db.query(StrategySettings).filter(StrategySettings.id == setting_id).first()
    if setting is None:
        raise HTTPException(status_code=404, detail="Strategy settings not found")
    return setting


@router.post("/settings/", response_model=StrategySettingsResponse)
def create_strategy_settings(setting: StrategySettingsCreate, db: Session = Depends(get_db)):
    """
    Create a new strategy settings entry.
    """
    db_setting = StrategySettings(**setting.dict())
    db.add(db_setting)
    db.commit()
    db.refresh(db_setting)
    return db_setting


@router.put("/settings/{setting_id}", response_model=StrategySettingsResponse)
def update_strategy_settings(
    setting_id: int, setting: StrategySettingsUpdate, db: Session = Depends(get_db)
):
    """
    Update a strategy settings entry.
    """
    db_setting = db.query(StrategySettings).filter(StrategySettings.id == setting_id).first()
    if db_setting is None:
        raise HTTPException(status_code=404, detail="Strategy settings not found")
    
    update_data = setting.dict(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_setting, key, value)
    
    db.commit()
    db.refresh(db_setting)
    return db_setting


# Combined endpoints for updating both signals and settings
@router.put("/update-signals/", response_model=StrategySignalsResponse)
def update_strategy_signals_by_first(
    data: dict,
    db: Session = Depends(get_db)
):
    """
    Update the first strategy signals entry or create if it doesn't exist.
    """
    # Validate required fields
    required_fields = [
        "tpls_trigger", "rsi_trigger", "sma_trigger", "alligator_trigger",
        "gpt_trigger", "lstm_trigger", "bollinger_trigger", "macd_trigger",
        "ema_trigger", "joint"
    ]
    
    for field in required_fields:
        if field not in data:
            raise HTTPException(
                status_code=422, 
                detail=f"Missing required field: {field}"
            )
    
    # Extract values from data
    tpls_trigger = data["tpls_trigger"]
    rsi_trigger = data["rsi_trigger"]
    sma_trigger = data["sma_trigger"]
    alligator_trigger = data["alligator_trigger"]
    gpt_trigger = data["gpt_trigger"]
    lstm_trigger = data["lstm_trigger"]
    bollinger_trigger = data["bollinger_trigger"]
    macd_trigger = data["macd_trigger"]
    ema_trigger = data["ema_trigger"]
    joint = data["joint"]
    
    # Try to find the first entry
    db_signal = db.query(StrategySignals).first()
    
    if db_signal is None:
        # Create new entry if it doesn't exist
        db_signal = StrategySignals(
            tpls_trigger=tpls_trigger,
            rsi_trigger=rsi_trigger,
            sma_trigger=sma_trigger,
            alligator_trigger=alligator_trigger,
            gpt_trigger=gpt_trigger,
            lstm_trigger=lstm_trigger,
            bollinger_trigger=bollinger_trigger,
            macd_trigger=macd_trigger,
            ema_trigger=ema_trigger,
            joint=joint
        )
        db.add(db_signal)
    else:
        # Update existing entry
        db_signal.tpls_trigger = tpls_trigger
        db_signal.rsi_trigger = rsi_trigger
        db_signal.sma_trigger = sma_trigger
        db_signal.alligator_trigger = alligator_trigger
        db_signal.gpt_trigger = gpt_trigger
        db_signal.lstm_trigger = lstm_trigger
        db_signal.bollinger_trigger = bollinger_trigger
        db_signal.macd_trigger = macd_trigger
        db_signal.ema_trigger = ema_trigger
        db_signal.joint = joint
    
    db.commit()
    db.refresh(db_signal)
    return db_signal


@router.put("/update-settings/", response_model=StrategySettingsResponse)
def update_strategy_settings_by_first(
    data: dict,
    db: Session = Depends(get_db)
):
    """
    Update the first strategy settings entry or create if it doesn't exist.
    """
    # Validate required fields
    required_fields = ["time", "auto_market", "quantity"]
    
    for field in required_fields:
        if field not in data:
            raise HTTPException(
                status_code=422, 
                detail=f"Missing required field: {field}"
            )
    
    # Extract values from data
    time = data["time"]
    auto_market = data["auto_market"]
    quantity = data["quantity"]
    
    # Try to find the first entry
    db_setting = db.query(StrategySettings).first()
    
    if db_setting is None:
        # Create new entry if it doesn't exist
        db_setting = StrategySettings(
            time=time,
            auto_market=auto_market,
            quantity=quantity
        )
        db.add(db_setting)
    else:
        # Update existing entry
        db_setting.time = time
        db_setting.auto_market = auto_market
        db_setting.quantity = quantity
    
    db.commit()
    db.refresh(db_setting)
    return db_setting
