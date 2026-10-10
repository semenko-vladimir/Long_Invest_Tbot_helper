"""Read-only corporate context for price observations, without price attribution."""

from dataclasses import replace
from datetime import datetime, time, timedelta, timezone

from app.backend.models.trading import Instrument
from app.client.config import get_invest_mode
from app.client.utils.tinvest import create_tinvest_client


def dividend_note(as_of, dividends):
    for event in dividends:
        last_buy, record = getattr(event, "last_buy_date", None), getattr(event, "record_date", None)
        if not isinstance(last_buy, datetime) or not isinstance(record, datetime):
            continue
        if last_buy.year < 2000 or record.year < 2000:
            continue
        if last_buy.date() < as_of <= record.date() + timedelta(days=2):
            return f"Рядом дивидендная отсечка: последний день покупки {last_buy:%d.%m}, реестр {record:%d.%m}. Причина движения цены не установлена."
    return None


class MarketDividendContext:
    def __init__(self, factory, user, *, client_factory=create_tinvest_client):
        self.factory, self.user, self.client_factory = factory, user, client_factory

    def annotate(self, candidates):
        token = self.user.active_token(get_invest_mode())
        if not token:
            return [replace(candidate, notes=("Корпоративный календарь недоступен.",)) for candidate in candidates]
        result = []
        try:
            with self.client_factory(token) as client:
                for candidate in candidates:
                    try:
                        with self.factory() as db:
                            row = db.query(Instrument).filter_by(ticker=candidate.ticker).first()
                            figi = row.figi if row else None
                        if not figi:
                            found = client.instruments.find_instrument(query=candidate.ticker).instruments
                            matches = {item.figi for item in found if item.ticker == candidate.ticker and item.class_code == "TQBR"}
                            figi = next(iter(matches)) if len(matches) == 1 else None
                        if not figi:
                            raise ValueError("No unambiguous equity identifier")
                        as_of = datetime.fromisoformat(candidate.as_of_date).date()
                        start = datetime.combine(as_of - timedelta(days=14), time.min, tzinfo=timezone.utc)
                        end = start + timedelta(days=28)
                        events = client.instruments.get_dividends(figi=figi, from_=start, to=end).dividends
                        note = dividend_note(as_of, events)
                        result.append(replace(candidate, notes=(note,) if note else ()))
                    except Exception:
                        result.append(replace(candidate, notes=("Корпоративный календарь не удалось проверить.",)))
        except Exception:
            return [replace(candidate, notes=("Корпоративный календарь недоступен.",)) for candidate in candidates]
        return result
