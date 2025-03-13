from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.backend.models.database import get_db
from app.backend.models.config import SchedulerConfig
from app.backend.schemas.config import SchedulerConfigCreate, SchedulerConfigUpdate, SchedulerConfigResponse
from app.backend.models.strategy import StrategySettings

router = APIRouter()


@router.get("/", response_model=List[SchedulerConfigResponse])
def read_configs(
    skip: int = 0, limit: int = 100, db: Session = Depends(get_db)
):
    """
    Retrieve all scheduler config entries.
    """
    configs = db.query(SchedulerConfig).offset(skip).limit(limit).all()
    return configs


@router.get("/{config_id}", response_model=SchedulerConfigResponse)
def read_config(config_id: int, db: Session = Depends(get_db)):
    """
    Get a specific scheduler config entry by ID.
    """
    config = db.query(SchedulerConfig).filter(SchedulerConfig.id == config_id).first()
    if config is None:
        raise HTTPException(status_code=404, detail="Scheduler config not found")
    return config


@router.get("/key/{key}", response_model=SchedulerConfigResponse)
def read_config_by_key(key: str, db: Session = Depends(get_db)):
    """
    Get a specific scheduler config entry by key.
    
    Note: This endpoint is kept for backward compatibility.
    It will always return the first config entry if it exists.
    """
    config = db.query(SchedulerConfig).first()
    if config is None:
        raise HTTPException(status_code=404, detail="Scheduler config not found")
    return config


@router.post("/", response_model=SchedulerConfigResponse)
def create_config(config: SchedulerConfigCreate, db: Session = Depends(get_db)):
    """
    Create a new scheduler config entry.
    """
    db_config = SchedulerConfig(**config.dict())
    db.add(db_config)
    db.commit()
    db.refresh(db_config)
    return db_config


@router.put("/{config_id}", response_model=SchedulerConfigResponse)
def update_config(
    config_id: int, config: SchedulerConfigUpdate, db: Session = Depends(get_db)
):
    """
    Update a scheduler config entry.
    """
    db_config = db.query(SchedulerConfig).filter(SchedulerConfig.id == config_id).first()
    if db_config is None:
        raise HTTPException(status_code=404, detail="Scheduler config not found")
    
    update_data = config.dict(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_config, key, value)
    
    db.commit()
    db.refresh(db_config)
    return db_config


@router.delete("/{config_id}", response_model=SchedulerConfigResponse)
def delete_config(config_id: int, db: Session = Depends(get_db)):
    """
    Delete a scheduler config entry.
    """
    db_config = db.query(SchedulerConfig).filter(SchedulerConfig.id == config_id).first()
    if db_config is None:
        raise HTTPException(status_code=404, detail="Scheduler config not found")
    
    db.delete(db_config)
    db.commit()
    return db_config


@router.put("/collapse-updates/", response_model=SchedulerConfigResponse)
def update_collapse_config(
    config: SchedulerConfigUpdate,
    db: Session = Depends(get_db)
):
    """
    Update collapse updates configuration.
    """
    # Try to find existing config
    db_config = db.query(SchedulerConfig).first()
    
    if db_config is None:
        # Create new config if it doesn't exist
        db_config = SchedulerConfig(
            collapse_updates=config.collapse_updates,
            collapse_updates_time=config.collapse_updates_time,
            market_updates=config.market_updates,
            market_updates_time=config.market_updates_time
        )
        db.add(db_config)
    else:
        # Update existing config
        if config.collapse_updates is not None:
            db_config.collapse_updates = config.collapse_updates
        if config.collapse_updates_time:
            db_config.collapse_updates_time = config.collapse_updates_time
        if config.market_updates is not None:
            db_config.market_updates = config.market_updates
        if config.market_updates_time:
            db_config.market_updates_time = config.market_updates_time
    
    db.commit()
    db.refresh(db_config)
    return db_config


@router.get("/sandbox-trigger/", response_model=bool)
def get_sandbox_trigger(db: Session = Depends(get_db)):
    """
    Get sandbox trigger value.
    """
    settings = db.query(StrategySettings).first()
    if settings is None:
        return False
    return settings.sandbox_trigger


@router.put("/sandbox-trigger/", response_model=dict)
def set_sandbox_trigger(data: dict, db: Session = Depends(get_db)):
    """
    Set sandbox trigger value.
    """
    if "value" not in data:
        raise HTTPException(status_code=422, detail="Missing 'value' field in request body")
    
    value = data["value"]
    
    # Try to find existing strategy settings
    settings = db.query(StrategySettings).first()
    
    if settings is None:
        # If no settings exist, create new ones
        settings = StrategySettings(
            sandbox_trigger=value,
            time="60",
            auto_market=False,
            quantity=1,
            joint=False
        )
        db.add(settings)
    else:
        # Update the existing settings
        settings.sandbox_trigger = value
    
    db.commit()
    db.refresh(settings)
    return {"id": settings.id, "sandbox_trigger": settings.sandbox_trigger}
