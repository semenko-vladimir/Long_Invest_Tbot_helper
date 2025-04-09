from fastapi import APIRouter

from app.backend.api.endpoints import (
    config, signals, strategy, trading, instruments
)

api_router = APIRouter()
api_router.include_router(config.router, prefix="/config", tags=["config"])
api_router.include_router(signals.router, prefix="/signals", tags=["signals"])
api_router.include_router(strategy.router, prefix="/strategy", tags=["strategy"])
api_router.include_router(trading.router, prefix="/trading", tags=["trading"])
api_router.include_router(instruments.router, prefix="/instruments", tags=["instruments"])
