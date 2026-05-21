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


@dataclass(frozen=True)
class WatchlistSyncResult:
    added: int
    already_present: int
    skipped: int
    errors: int
    added_tickers: tuple[str, ...] = ()
    already_present_tickers: tuple[str, ...] = ()
    skipped_tickers: tuple[str, ...] = ()
    error_messages: tuple[str, ...] = ()

    @property
    def ok(self) -> bool:
        return self.errors == 0


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

    def sync_from_portfolio(self, portfolio_service) -> WatchlistSyncResult:
        portfolio = portfolio_service.get_portfolio_view()
        if portfolio.error:
            return WatchlistSyncResult(
                added=0,
                already_present=0,
                skipped=0,
                errors=1,
                error_messages=(portfolio.error,),
            )

        if portfolio.empty:
            return WatchlistSyncResult(added=0, already_present=0, skipped=0, errors=0)

        db = self.session_factory()
        try:
            existing_rows = db.query(Instrument).all()
            existing_tickers = {str(row.ticker or "").upper() for row in existing_rows}
            existing_figis = {str(row.figi or "") for row in existing_rows}
            added: list[str] = []
            already_present: list[str] = []
            skipped: list[str] = []
            seen: set[str] = set()

            for position in portfolio.positions:
                raw_ticker = str(getattr(position, "ticker", "") or "").strip()
                raw_figi = str(getattr(position, "figi", "") or "").strip()

                try:
                    ticker = self._normalize_ticker(raw_ticker)
                except WatchlistServiceError:
                    skipped.append(raw_ticker or "unknown")
                    continue

                if ticker in seen:
                    continue
                seen.add(ticker)

                if not raw_figi:
                    skipped.append(ticker)
                    continue

                if ticker in existing_tickers:
                    already_present.append(ticker)
                    continue

                if raw_figi in existing_figis:
                    skipped.append(ticker)
                    continue

                db.add(Instrument(ticker=ticker, figi=raw_figi))
                existing_tickers.add(ticker)
                existing_figis.add(raw_figi)
                added.append(ticker)

            db.commit()
            return WatchlistSyncResult(
                added=len(added),
                already_present=len(already_present),
                skipped=len(skipped),
                errors=0,
                added_tickers=tuple(added),
                already_present_tickers=tuple(already_present),
                skipped_tickers=tuple(skipped),
            )
        except IntegrityError:
            db.rollback()
            return WatchlistSyncResult(
                added=0,
                already_present=0,
                skipped=0,
                errors=1,
                error_messages=("The watchlist could not be synced because a ticker or FIGI already exists.",),
            )
        except Exception:
            db.rollback()
            return WatchlistSyncResult(
                added=0,
                already_present=0,
                skipped=0,
                errors=1,
                error_messages=("The watchlist could not be synced right now.",),
            )
        finally:
            db.close()

    def _normalize_ticker(self, ticker: str) -> str:
        normalized = str(ticker or "").strip().upper()
        if not normalized or not normalized.replace("-", "").isalnum():
            raise WatchlistServiceError("Enter a ticker using letters and numbers.")
        return normalized


def format_watchlist_sync_summary(result: WatchlistSyncResult) -> str:
    summary = (
        "Portfolio sync: "
        f"added {result.added}, "
        f"already present {result.already_present}, "
        f"skipped {result.skipped}, "
        f"errors {result.errors}."
    )
    details: list[str] = []
    if result.added_tickers:
        details.append(f"Added: {', '.join(result.added_tickers)}.")
    if result.already_present_tickers:
        details.append(f"Already present: {', '.join(result.already_present_tickers)}.")
    if result.skipped_tickers:
        details.append(f"Skipped: {', '.join(result.skipped_tickers)}.")
    if result.error_messages:
        details.append(" ".join(result.error_messages))
    if details:
        return f"{summary} {' '.join(details)}"
    return summary
