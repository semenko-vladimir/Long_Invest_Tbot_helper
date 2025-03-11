from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.backend.models.database import get_db
from app.backend.models.config import Config
from app.backend.schemas.config import ConfigCreate, ConfigUpdate, ConfigResponse

router = APIRouter()


@router.get("/", response_model=List[ConfigResponse])
def read_configs(
    skip: int = 0, limit: int = 100, db: Session = Depends(get_db)
):
    """
    Retrieve all config entries.
    """
    configs = db.query(Config).offset(skip).limit(limit).all()
    return configs


@router.get("/{config_id}", response_model=ConfigResponse)
def read_config(config_id: int, db: Session = Depends(get_db)):
    """
    Get a specific config entry by ID.
    """
    config = db.query(Config).filter(Config.id == config_id).first()
    if config is None:
        raise HTTPException(status_code=404, detail="Config not found")
    return config


@router.get("/key/{key}", response_model=ConfigResponse)
def read_config_by_key(key: str, db: Session = Depends(get_db)):
    """
    Get a specific config entry by key.
    
    Note: This endpoint is kept for backward compatibility,
    but the Config model no longer has a 'key' attribute.
    It will always return the first config entry if it exists.
    """
    config = db.query(Config).first()
    if config is None:
        raise HTTPException(status_code=404, detail="Config not found")
    return config


@router.post("/", response_model=ConfigResponse)
def create_config(config: ConfigCreate, db: Session = Depends(get_db)):
    """
    Create a new config entry.
    """
    db_config = Config(**config.dict())
    db.add(db_config)
    db.commit()
    db.refresh(db_config)
    return db_config


@router.put("/{config_id}", response_model=ConfigResponse)
def update_config(
    config_id: int, config: ConfigUpdate, db: Session = Depends(get_db)
):
    """
    Update a config entry.
    """
    db_config = db.query(Config).filter(Config.id == config_id).first()
    if db_config is None:
        raise HTTPException(status_code=404, detail="Config not found")
    
    update_data = config.dict(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_config, key, value)
    
    db.commit()
    db.refresh(db_config)
    return db_config


@router.delete("/{config_id}", response_model=ConfigResponse)
def delete_config(config_id: int, db: Session = Depends(get_db)):
    """
    Delete a config entry.
    """
    db_config = db.query(Config).filter(Config.id == config_id).first()
    if db_config is None:
        raise HTTPException(status_code=404, detail="Config not found")
    
    db.delete(db_config)
    db.commit()
    return db_config


@router.put("/collapse-updates/", response_model=ConfigResponse)
def update_collapse_config(
    config: ConfigUpdate,
    db: Session = Depends(get_db)
):
    """
    Update collapse updates configuration.
    """
    # Try to find existing config
    db_config = db.query(Config).first()
    
    if db_config is None:
        # Create new config if it doesn't exist
        db_config = Config(
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
    config = db.query(Config).first()
    if config is None:
        return False
    return config.sandbox_trigger


@router.put("/sandbox-trigger/", response_model=ConfigResponse)
def set_sandbox_trigger(data: dict, db: Session = Depends(get_db)):
    """
    Set sandbox trigger value.
    """
    if "value" not in data:
        raise HTTPException(status_code=422, detail="Missing 'value' field in request body")
    
    value = data["value"]
    
    # Try to find existing config
    config = db.query(Config).first()
    
    if config is None:
        # If no config exists, create a new one
        config = Config(
            sandbox_trigger=value,
            collapse_updates=False,
            collapse_updates_time="60",
            market_updates=False,
            market_updates_time="60"
        )
        db.add(config)
    else:
        # Update the existing config
        config.sandbox_trigger = value
    
    db.commit()
    db.refresh(config)
    return config
