from tinkoff.invest import CandleInterval
from datetime import datetime, timedelta


class Config:
    def __init__(self, period):
        self.period = period
        self.interval = self._get_interval()
        self.start_time, self.end_time = self._get_time_range()

    def _get_interval(self):
        intervals = {
            "10_MIN": CandleInterval.CANDLE_INTERVAL_1_MIN,
            "1_HOUR": CandleInterval.CANDLE_INTERVAL_1_MIN,
            "DAY": CandleInterval.CANDLE_INTERVAL_1_MIN,
            "WEEK": CandleInterval.CANDLE_INTERVAL_DAY,
            "MONTH": CandleInterval.CANDLE_INTERVAL_WEEK,
            "YEAR": CandleInterval.CANDLE_INTERVAL_MONTH
        }
        return intervals.get(self.period)

    def _get_time_range(self):
        now = datetime.utcnow()
        start_time = None
        end_time = None
        if self.period == "10_MIN":
            start_time = now - timedelta(minutes=10)
        elif self.period == "1_HOUR":
            start_time = now - timedelta(hours=1)
        elif self.period == "DAY":
            start_time = now.replace(hour=9, minute=50, second=0, microsecond=0)
            end_time = now
        elif self.period == "WEEK":
            start_time = now - timedelta(weeks=1)
        elif self.period == "MONTH":
            start_time = now - timedelta(days=30)
        elif self.period == "YEAR":
            start_time = now - timedelta(days=365)
        end_time = now if end_time is None else end_time
        return start_time, end_time
