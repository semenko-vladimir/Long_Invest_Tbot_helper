from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.backend.models.database import get_db
from app.backend.models.strategy import StrategySignals, StrategySettings
from app.backend.schemas.strategy import (
    StrategySignalsResponse, StrategySettingsResponse
)

router = APIRouter()


# Strategy Signals endpoints
@router.get("/signals/", response_model=StrategySignalsResponse)
def read_strategy_signals(db: Session = Depends(get_db)):
    """
    Получить настройки сигналов стратегии.
    """
    signal = db.query(StrategySignals).first()
    if signal is None:
        raise HTTPException(status_code=404, detail="Strategy signals not found")
    return signal


# Strategy Settings endpoints
@router.get("/settings/", response_model=StrategySettingsResponse)
def read_strategy_settings(db: Session = Depends(get_db)):
    """
    Получить общие настройки стратегии.
    """
    setting = db.query(StrategySettings).first()
    if setting is None:
        raise HTTPException(status_code=404, detail="Strategy settings not found")
    return setting


# Combined endpoints for updating both signals and settings
@router.put("/update-signals/", response_model=StrategySignalsResponse)
def update_strategy_signals_by_first(
    data: dict,
    db: Session = Depends(get_db)
):
    """
    Обновить настройки сигналов стратегии или создать, если они не существуют.
    """
    # Validate required fields
    required_fields = [
        "tpls_trigger", "rsi_trigger", "sma_trigger", "alligator_trigger",
        "gpt_trigger", "lstm_trigger", "bollinger_trigger", "macd_trigger",
        "ema_trigger"
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
            ema_trigger=ema_trigger
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
    
    db.commit()
    db.refresh(db_signal)
    return db_signal


@router.put("/update-settings/", response_model=StrategySettingsResponse)
def update_strategy_settings_by_first(
    data: dict,
    db: Session = Depends(get_db)
):
    """
    Обновить общие настройки стратегии или создать, если они не существуют.
    """
    # Validate required fields
    required_fields = ["time", "auto_market", "quantity", "joint"]
    
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
    joint = data["joint"]
    
    # Get sandbox_trigger value (if it exists in the data)
    sandbox_trigger = data.get("sandbox_trigger")
    
    # Try to find the first entry
    db_setting = db.query(StrategySettings).first()
    
    if db_setting is None:
        # Create new entry if it doesn't exist
        db_setting = StrategySettings(
            time=time,
            auto_market=auto_market,
            quantity=quantity,
            joint=joint,
            sandbox_trigger=sandbox_trigger if sandbox_trigger is not None else False
        )
        db.add(db_setting)
    else:
        # Update existing entry
        db_setting.time = time
        db_setting.auto_market = auto_market
        db_setting.quantity = quantity
        db_setting.joint = joint
        if sandbox_trigger is not None:
            db_setting.sandbox_trigger = sandbox_trigger
    
    db.commit()
    db.refresh(db_setting)
    return db_setting
