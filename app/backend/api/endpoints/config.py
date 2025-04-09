from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.backend.models.database import get_db
from app.backend.models.config import SchedulerConfig
from app.backend.schemas.config import SchedulerConfigCreate, SchedulerConfigUpdate, SchedulerConfigResponse
from app.backend.models.strategy import StrategySettings

router = APIRouter()


@router.get("/", response_model=SchedulerConfigResponse)
def read_config(db: Session = Depends(get_db)):
    """
    Получение записи конфигурации планировщика.
    
    Примечание: Приложение поддерживает только одну конфигурацию.
    """
    config = db.query(SchedulerConfig).first()
    if config is None:
        raise HTTPException(status_code=404, detail="Configuration not found")
    return config


@router.post("/", response_model=SchedulerConfigResponse)
def create_config(config: SchedulerConfigCreate, db: Session = Depends(get_db)):
    """
    Создание новой записи конфигурации планировщика.
    
    Если конфигурация уже существует, вызывает исключение.
    """
    existing_config = db.query(SchedulerConfig).first()
    if existing_config:
        raise HTTPException(status_code=400, detail="Configuration already exists")
    
    db_config = SchedulerConfig(**config.dict())
    db.add(db_config)
    db.commit()
    db.refresh(db_config)
    return db_config


@router.put("/", response_model=SchedulerConfigResponse)
def update_config(config: SchedulerConfigUpdate, db: Session = Depends(get_db)):
    """
    Обновление записи конфигурации планировщика.
    
    Если конфигурация не существует, вызывает исключение.
    """
    db_config = db.query(SchedulerConfig).first()
    if db_config is None:
        raise HTTPException(status_code=404, detail="Configuration not found")
    
    update_data = config.dict(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_config, key, value)
    
    db.commit()
    db.refresh(db_config)
    return db_config


@router.delete("/", response_model=SchedulerConfigResponse)
def delete_config(db: Session = Depends(get_db)):
    """
    Удаление записи конфигурации планировщика.
    
    Если конфигурация не существует, вызывает исключение.
    """
    db_config = db.query(SchedulerConfig).first()
    if db_config is None:
        raise HTTPException(status_code=404, detail="Configuration not found")
    
    deleted_config = db_config
    db.delete(db_config)
    db.commit()
    return deleted_config


@router.get("/sandbox-trigger/", response_model=bool)
def get_sandbox_trigger(db: Session = Depends(get_db)):
    """
    Получение значения триггера песочницы.
    """
    settings = db.query(StrategySettings).first()
    if settings is None:
        raise HTTPException(status_code=404, detail="Strategy settings not found")
    return settings.sandbox_trigger


@router.put("/sandbox-trigger/", response_model=dict)
def set_sandbox_trigger(data: dict, db: Session = Depends(get_db)):
    """
    Установка значения триггера песочницы.
    """
    if "value" not in data:
        raise HTTPException(status_code=422, detail="Missing 'value' field in request body")
    
    value = data["value"]
    
    # Try to find existing strategy settings
    settings = db.query(StrategySettings).first()
    
    if settings is None:
        raise HTTPException(status_code=404, detail="Strategy settings not found")
    
    # Update the existing settings
    settings.sandbox_trigger = value
    
    db.commit()
    db.refresh(settings)
    return {"id": settings.id, "sandbox_trigger": settings.sandbox_trigger}
