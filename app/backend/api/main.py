from fastapi import FastAPI
from app.backend.api.endpoints import config, strategy, signals, trading, instruments

app = FastAPI(
    title="Trading Bot API",
    description="API for trading bot operations",
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
    return {"status": "ok", "message": "Trading Bot API is running"}
