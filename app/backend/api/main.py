from fastapi import FastAPI
from app.backend.api.endpoints import config, strategy, signals, trading, instruments

app = FastAPI(
    title="Long-Term Investor Assistant API",
    description="Local sandbox-first API for investor assistant operations",
    version="1.0.0",
)

app.include_router(config.router, prefix="/config", tags=["Config"])
app.include_router(strategy.router, prefix="/strategy", tags=["Strategy"])
app.include_router(signals.router, prefix="/signals", tags=["Signals"])
app.include_router(trading.router, prefix="/trading", tags=["Trading"])
app.include_router(instruments.router, prefix="/instruments", tags=["Instruments"])


@app.get("/", tags=["Root"])
def read_root():
    """
    Root endpoint to check API health.
    """
    return {"status": "ok", "message": "Long-Term Investor Assistant API is running"}
