from fastapi import APIRouter

from app.backend.api.endpoints import research

api_router = APIRouter()
api_router.include_router(research.router, prefix="/research", tags=["research"])
