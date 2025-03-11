from typing import Optional
from datetime import datetime
from pydantic import BaseModel


class ConfigBase(BaseModel):
    collapse_updates: Optional[bool] = None
    collapse_updates_time: Optional[str] = None
    market_updates: Optional[bool] = None
    market_updates_time: Optional[str] = None
    sandbox_trigger: Optional[bool] = None
    chat_id: Optional[str] = None


class ConfigCreate(ConfigBase):
    pass


class ConfigUpdate(ConfigBase):
    pass


class ConfigResponse(ConfigBase):
    id: int

    class Config:
        orm_mode = True
