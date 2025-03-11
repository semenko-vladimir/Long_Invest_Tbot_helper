import sys
import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Добавляем родительскую директорию в sys.path, чтобы можно было импортировать модули из app
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from app.backend.api import api_router
from app.backend.models import create_all_tables

# Create FastAPI app
app = FastAPI(
    title="Trading Bot API",
    description="API for the Trading Bot application",
    version="1.0.0",
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins
    allow_credentials=True,
    allow_methods=["*"],  # Allow all methods
    allow_headers=["*"],  # Allow all headers
)

# Include API router
app.include_router(api_router, prefix="/api")

# Create database tables on startup
@app.on_event("startup")
def startup_event():
    create_all_tables()

# Root endpoint
@app.get("/")
def read_root():
    return {
        "message": "Welcome to the Trading Bot API",
        "docs_url": "/docs",
        "redoc_url": "/redoc",
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
