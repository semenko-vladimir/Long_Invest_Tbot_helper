from dataclasses import dataclass
from typing import Callable, Optional

from sqlalchemy.exc import IntegrityError

from app.backend.models.trading import Instrument
from app.client.config import get_active_invest_token
from app.integrations.tinvest import TInvestBroker
from app.services.user_database import SessionFactory, get_default_session_factory


class WatchlistServiceError(ValueError):
    pass


@dataclass(frozen=True)
class WatchlistItem:
    id: int
    ticker: str
    figi: str
    name: str


@dataclass(frozen=True)
class WatchlistView:
    items: list[WatchlistItem]
    empty: bool
    error: Optional[str] = None
    notice: Optional[str] = None


class WatchlistService:
    def __init__(
        self,
        broker: Optional[TInvestBroker] = None,
        *,
        session_factory: Optional[SessionFactory] = None,
        token_provider: Optional[Callable[[], Optional[str]]] = None,
    ):
        self.broker = broker or TInvestBroker()
        self.session_factory = session_factory or get_default_session_factory()
        self.token_provider = token_provider or get_active_invest_token

    def list_items(self, *, notice: Optional[str] = None, error: Optional[str] = None) -> WatchlistView:
        db = self.session_factory()
        try:
            instruments = db.query(Instrument).order_by(Instrument.ticker.asc()).all()
            items = [
                WatchlistItem(
                    id=instrument.id,
                    ticker=instrument.ticker,
                    figi=instrument.figi,
                    name=instrument.ticker,
                )
                for instrument in instruments
            ]
            return WatchlistView(items=items, empty=len(items) == 0, notice=notice, error=error)
        except Exception:
            return WatchlistView(
                items=[],
                empty=True,
                error=error or "The watchlist could not be loaded right now.",
                notice=notice,
            )
        finally:
            db.close()

    def add_ticker(self, ticker: str) -> WatchlistView:
        normalized_ticker = self._normalize_ticker(ticker)
        token = self.token_provider()
        if not token:
            return self.list_items(error="No broker token is configured for the current mode.")

        try:
            instrument = self.broker.resolve_unique_instrument(token, normalized_ticker)
        except Exception as exc:
            return self.list_items(error=f"Could not add {normalized_ticker}: {str(exc)}")

        db = self.session_factory()
        try:
            existing = db.query(Instrument).filter(Instrument.ticker == instrument.ticker).first()
            if existing:
                return self.list_items(notice=f"{instrument.ticker} is already in the watchlist.")

            db.add(Instrument(ticker=instrument.ticker, figi=instrument.figi))
            db.commit()
            return self.list_items(notice=f"{instrument.ticker} was added to the watchlist.")
        except IntegrityError:
            db.rollback()
            return self.list_items(notice=f"{instrument.ticker} is already in the watchlist.")
        except Exception:
            db.rollback()
            return self.list_items(error="The watchlist could not be updated right now.")
        finally:
            db.close()

    def remove_ticker(self, ticker: str) -> WatchlistView:
        normalized_ticker = self._normalize_ticker(ticker)
        db = self.session_factory()
        try:
            instrument = db.query(Instrument).filter(Instrument.ticker == normalized_ticker).first()
            if instrument is None:
                return self.list_items(error=f"{normalized_ticker} is not in the watchlist.")

            db.delete(instrument)
            db.commit()
            return self.list_items(notice=f"{normalized_ticker} was removed from the watchlist.")
        except Exception:
            db.rollback()
            return self.list_items(error="The watchlist could not be updated right now.")
        finally:
            db.close()

    def clear(self) -> WatchlistView:
        db = self.session_factory()
        try:
            deleted_count = db.query(Instrument).delete()
            db.commit()
            if deleted_count:
                return self.list_items(notice="Watchlist was cleared.")
            return self.list_items(notice="Watchlist is already empty.")
        except Exception:
            db.rollback()
            return self.list_items(error="The watchlist could not be updated right now.")
        finally:
            db.close()

    def _normalize_ticker(self, ticker: str) -> str:
        normalized = str(ticker or "").strip().upper()
        if not normalized or not normalized.replace("-", "").isalnum():
            raise WatchlistServiceError("Enter a ticker using letters and numbers.")
        return normalized
