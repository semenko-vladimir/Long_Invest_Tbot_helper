from fastapi import APIRouter

from app.backend.api.endpoints import (
    config, trading, instruments, research
)

api_router = APIRouter()
api_router.include_router(config.router, prefix="/config", tags=["config"])
api_router.include_router(trading.router, prefix="/trading", tags=["trading"])
api_router.include_router(instruments.router, prefix="/instruments", tags=["instruments"])
api_router.include_router(research.router, prefix="/research", tags=["research"])
