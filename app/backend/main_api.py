import sys
import os
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

# Добавляем родительскую директорию в sys.path, чтобы можно было импортировать модули из app
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from app.backend.api import api_router
from app.backend.auth import WebAuthMiddleware
from app.backend.models import create_all_tables
from app.backend.web.csrf import WebCsrfCookieMiddleware
from app.backend.web.routes import router as web_router
from app.client.config import validate_web_auth_config

WEB_DIR = Path(__file__).resolve().parent / "web"


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Refuse to expose the API on a non-loopback host without WEB_AUTH configured,
    # regardless of whether app/run.py or `uvicorn app.backend.main_api:app` was used.
    validate_web_auth_config()
    create_all_tables()
    yield


# Create FastAPI app
app = FastAPI(
    title="Long-Term Investor Assistant API",
    description="Sandbox-first API for portfolio, instruments, and manual orders",
    version="1.0.0",
    lifespan=lifespan,
)

# Require the local owner token when WEB_AUTH_ENABLED=true.
app.add_middleware(WebAuthMiddleware)
app.add_middleware(WebCsrfCookieMiddleware)

# Configure CORS
_allowed_origins = [
    "http://127.0.0.1:8000",
    "http://localhost:8000",
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["Content-Type", "Authorization"],
)

# Include routers
app.include_router(api_router, prefix="/api")
app.include_router(web_router)
app.mount("/static", StaticFiles(directory=str(WEB_DIR / "static")), name="static")

@app.get("/api/health")
def read_health():
    return {
        "status": "ok",
        "message": "Long-Term Investor Assistant API is running",
        "docs_url": "/docs",
        "redoc_url": "/redoc",
    }

if __name__ == "__main__":
    import uvicorn
    api_host = os.getenv("API_HOST", "127.0.0.1")
    api_port = int(os.getenv("API_PORT", "8000"))
    uvicorn.run(app, host=api_host, port=api_port)
