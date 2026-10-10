"""Bounded market-data reads using the SDK's verified official endpoints."""

from collections import namedtuple
from datetime import datetime, time, timedelta, timezone
import math
from zoneinfo import ZoneInfo

import grpc
from t_tech.invest import CandleInterval, Client
from t_tech.invest.schemas import InstrumentClosePriceRequest, LastPriceType

from app.client.utils.tinvest import get_tinvest_target
from app.charts.schemas import PriceCandle


class _CallDetails(namedtuple("CallDetails", "method timeout metadata credentials wait_for_ready compression"), grpc.ClientCallDetails):
    pass


class _Deadline(grpc.UnaryUnaryClientInterceptor):
    def intercept_unary_unary(self, continuation, details, request):
        bounded = _CallDetails(details.method, min(details.timeout or 15, 15), details.metadata,
            details.credentials, getattr(details, "wait_for_ready", None), getattr(details, "compression", None))
        return continuation(bounded, request)


def market_client(token, *, sandbox):
    return Client(token, target=get_tinvest_target(sandbox), interceptors=[_Deadline()])


def quotation(value):
    result = float(value.units) + float(value.nano) / 1_000_000_000
    return result if math.isfinite(result) and result > 0 else None


class StockMarketAdapter:
    def __init__(self, client_factory=market_client):
        self.client_factory = client_factory
        self._reference_closes = {}

    def quotes(self, token, instrument_keys, *, sandbox):
        keys = sorted(set(instrument_keys))
        if not keys:
            return {}
        result = {key: {} for key in keys}
        with self.client_factory(token, sandbox=sandbox) as client:
            # Chunk batch requests; credentials and raw SDK objects never enter the cache.
            for start in range(0, len(keys), 100):
                chunk = keys[start:start + 100]
                prices = client.market_data.get_last_prices(instrument_id=chunk,
                    last_price_type=LastPriceType.LAST_PRICE_EXCHANGE).last_prices
                statuses = client.market_data.get_trading_statuses(instrument_ids=chunk).trading_statuses
                for row in prices:
                    for key in (row.instrument_uid, row.figi):
                        if key in result:
                            result[key].update(price=quotation(row.price), time=row.time.astimezone(timezone.utc).isoformat())
                for row in statuses:
                    for key in (row.instrument_uid, row.figi):
                        if key in result:
                            result[key]["trading"] = int(row.trading_status) == 5
                try:
                    closes = client.market_data.get_close_prices(
                        instruments=[InstrumentClosePriceRequest(instrument_id=key) for key in chunk]).close_prices
                    for row in closes:
                        for key in (row.instrument_uid, row.figi):
                            if key in result:
                                session_day = datetime.fromisoformat(result[key]["time"]).astimezone(ZoneInfo("Europe/Moscow")).date() if result[key].get("time") else None
                                close_day = row.time.astimezone(ZoneInfo("Europe/Moscow")).date()
                                if session_day and close_day < session_day:
                                    result[key]["previous_close"] = quotation(row.price)
                except Exception:
                    # A missing reference close must not prevent prices/status reads.
                    pass
                # After a session closes, GetClosePrices may already describe that
                # same session. Compare against the preceding session, not itself.
                for key in chunk:
                    value = result[key]
                    if not value.get("time") or value.get("previous_close"):
                        continue
                    session_day = datetime.fromisoformat(value["time"]).astimezone(ZoneInfo("Europe/Moscow")).date()
                    cache_key = (key, session_day)
                    if cache_key not in self._reference_closes:
                        try:
                            end = datetime.combine(session_day, time.min, tzinfo=ZoneInfo("Europe/Moscow"))
                            bars = [bar for bar in client.get_all_candles(instrument_id=key,
                                interval=CandleInterval.CANDLE_INTERVAL_DAY, from_=end - timedelta(days=14), to=end)
                                if bar.is_complete and bar.time.astimezone(ZoneInfo("Europe/Moscow")).date() < session_day]
                            if bars:
                                self._reference_closes[cache_key] = quotation(max(bars, key=lambda b: b.time).close)
                        except Exception:
                            pass
                    if cache_key in self._reference_closes:
                        value["previous_close"] = self._reference_closes[cache_key]
        if len(self._reference_closes) > 1000:
            self._reference_closes.clear()
        return result

    def candles(self, token, instrument_key, interval, start, end, *, sandbox):
        intervals = {"5min": CandleInterval.CANDLE_INTERVAL_5_MIN,
                     "hour": CandleInterval.CANDLE_INTERVAL_HOUR, "day": CandleInterval.CANDLE_INTERVAL_DAY}
        with self.client_factory(token, sandbox=sandbox) as client:
            return [PriceCandle(row.time, quotation(row.open), quotation(row.high), quotation(row.low),
                    quotation(row.close), row.volume)
                for row in client.get_all_candles(instrument_id=instrument_key, interval=intervals[interval], from_=start, to=end)
                if row.is_complete and all(quotation(getattr(row, name)) for name in ("open", "high", "low", "close"))]
