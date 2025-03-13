from typing import Optional
from datetime import datetime
from pydantic import BaseModel


class SchedulerConfigBase(BaseModel):
    collapse_updates: Optional[bool] = None
    collapse_updates_time: Optional[str] = None
    market_updates: Optional[bool] = None
    market_updates_time: Optional[str] = None


class SchedulerConfigCreate(SchedulerConfigBase):
    pass


class SchedulerConfigUpdate(SchedulerConfigBase):
    pass


class SchedulerConfigResponse(SchedulerConfigBase):
    id: int

    class Config:
        orm_mode = True
