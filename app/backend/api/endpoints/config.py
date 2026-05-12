from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.backend.models.database import get_db
from app.backend.models.config import SchedulerConfig
from app.backend.schemas.config import SchedulerConfigCreate, SchedulerConfigUpdate, SchedulerConfigResponse

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
