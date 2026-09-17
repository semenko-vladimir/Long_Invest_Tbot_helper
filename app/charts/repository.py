from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

from app.backend.models.trading import PriceCandleRecord
from app.charts.schemas import ChartCandleInterval, PriceCandle
from app.services.user_database import SessionFactory
from sqlalchemy import func


@dataclass(frozen=True)
class CandleCacheMetadata:
    ticker: str
    interval: ChartCandleInterval
    figi: Optional[str]
    source: Optional[str]
    fetched_at: Optional[datetime]
    as_of_date: Optional[str]
    freshness: Optional[str]
    delay_status: Optional[str]
    candle_count: int


@dataclass(frozen=True)
class CandleCacheSummary:
    ticker_count: int = 0
    candle_count: int = 0
    oldest_candle_at: Optional[datetime] = None
    latest_candle_at: Optional[datetime] = None
    latest_fetched_at: Optional[datetime] = None


class PriceCandleRepository:
    """SQLite-backed candle cache scoped to the selected local user database."""

    def __init__(self, session_factory: SessionFactory):
        self.session_factory = session_factory

    def upsert_candles(
        self,
        *,
        ticker: str,
        interval: ChartCandleInterval,
        candles: list[PriceCandle],
        source: str,
        figi: Optional[str] = None,
        fetched_at: Optional[datetime] = None,
        as_of_date: Optional[str] = None,
        freshness: Optional[str] = None,
        delay_status: Optional[str] = None,
    ) -> int:
        normalized_ticker = self._normalize_ticker(ticker)
        normalized_source = str(source or "").strip() or "unknown"
        fetched_at = self._normalize_datetime(fetched_at)
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        changed = 0

        db = self.session_factory()
        try:
            for candle in candles:
                candle_time = self._normalize_datetime(candle.time)
                row = (
                    db.query(PriceCandleRecord)
                    .filter(
                        PriceCandleRecord.ticker == normalized_ticker,
                        PriceCandleRecord.interval == interval,
                        PriceCandleRecord.time == candle_time,
                    )
                    .first()
                )
                if row is None:
                    row = PriceCandleRecord(
                        ticker=normalized_ticker,
                        interval=interval,
                        time=candle_time,
                        created_at=now,
                    )
                    db.add(row)

                row.figi = figi
                row.open = float(candle.open)
                row.high = float(candle.high)
                row.low = float(candle.low)
                row.close = float(candle.close)
                row.volume = int(candle.volume) if candle.volume is not None else None
                row.source = normalized_source
                row.fetched_at = fetched_at
                row.as_of_date = as_of_date
                row.freshness = freshness
                row.delay_status = delay_status
                row.updated_at = now
                changed += 1

            db.commit()
            return changed
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    def list_candles(
        self,
        *,
        ticker: str,
        interval: ChartCandleInterval,
        from_time: Optional[datetime] = None,
        to_time: Optional[datetime] = None,
    ) -> list[PriceCandle]:
        normalized_ticker = self._normalize_ticker(ticker)
        db = self.session_factory()
        try:
            query = db.query(PriceCandleRecord).filter(
                PriceCandleRecord.ticker == normalized_ticker,
                PriceCandleRecord.interval == interval,
            )
            if from_time is not None:
                query = query.filter(PriceCandleRecord.time >= self._normalize_datetime(from_time))
            if to_time is not None:
                query = query.filter(PriceCandleRecord.time <= self._normalize_datetime(to_time))

            rows = query.order_by(PriceCandleRecord.time.asc()).all()
            return [self._row_to_candle(row) for row in rows]
        finally:
            db.close()

    def latest_candle_time(self, *, ticker: str, interval: ChartCandleInterval) -> Optional[datetime]:
        normalized_ticker = self._normalize_ticker(ticker)
        db = self.session_factory()
        try:
            row = (
                db.query(PriceCandleRecord)
                .filter(
                    PriceCandleRecord.ticker == normalized_ticker,
                    PriceCandleRecord.interval == interval,
                )
                .order_by(PriceCandleRecord.time.desc())
                .first()
            )
            return getattr(row, "time", None) if row is not None else None
        finally:
            db.close()

    def metadata(self, *, ticker: str, interval: ChartCandleInterval) -> CandleCacheMetadata:
        normalized_ticker = self._normalize_ticker(ticker)
        db = self.session_factory()
        try:
            base_query = db.query(PriceCandleRecord).filter(
                PriceCandleRecord.ticker == normalized_ticker,
                PriceCandleRecord.interval == interval,
            )
            latest = base_query.order_by(PriceCandleRecord.time.desc()).first()
            return CandleCacheMetadata(
                ticker=normalized_ticker,
                interval=interval,
                figi=getattr(latest, "figi", None),
                source=getattr(latest, "source", None),
                fetched_at=getattr(latest, "fetched_at", None),
                as_of_date=getattr(latest, "as_of_date", None),
                freshness=getattr(latest, "freshness", None),
                delay_status=getattr(latest, "delay_status", None),
                candle_count=base_query.count(),
            )
        finally:
            db.close()

    def summary(self) -> CandleCacheSummary:
        db = self.session_factory()
        try:
            candle_count = db.query(func.count(PriceCandleRecord.id)).scalar() or 0
            ticker_count = db.query(PriceCandleRecord.ticker).distinct().count()
            oldest_candle_at = db.query(func.min(PriceCandleRecord.time)).scalar()
            latest_candle_at = db.query(func.max(PriceCandleRecord.time)).scalar()
            latest_fetched_at = db.query(func.max(PriceCandleRecord.fetched_at)).scalar()
            return CandleCacheSummary(
                ticker_count=int(ticker_count or 0),
                candle_count=int(candle_count or 0),
                oldest_candle_at=oldest_candle_at,
                latest_candle_at=latest_candle_at,
                latest_fetched_at=latest_fetched_at,
            )
        finally:
            db.close()

    def _row_to_candle(self, row: PriceCandleRecord) -> PriceCandle:
        return PriceCandle(
            time=row.time,
            open=float(row.open),
            high=float(row.high),
            low=float(row.low),
            close=float(row.close),
            volume=row.volume,
        )

    def _normalize_ticker(self, ticker: str) -> str:
        return str(ticker or "").strip().upper()

    def _normalize_datetime(self, value: datetime | None) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is not None:
            return value.astimezone(timezone.utc).replace(tzinfo=None)
        return value
