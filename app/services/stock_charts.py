"""Instrument-identified charts with warmed indicators and bounded cache reads."""

from dataclasses import dataclass, replace, asdict
from datetime import datetime, timedelta
from io import BytesIO
import json
from threading import RLock

from matplotlib.figure import Figure

from app.backend.models.stocks import StockChartCache
from app.charts.analytics import ChartAnalyticsService
from app.charts.schemas import PriceCandle
from app.services.stock_market import MOSCOW, instrument_key, naive, utc


@dataclass(frozen=True)
class StockChart:
    png_bytes: bytes
    summary: str
    fetched_at: datetime
    stale: bool
    candle_count: int


class StockChartService:
    def __init__(self, market):
        self.market = market
        self.lock = RLock()

    def render(self, position, range_name="month", *, now=None):
        if range_name not in {"day", "week", "month"}:
            raise ValueError("Выберите день, неделю или месяц.")
        now = utc(now or self.market.now())
        key = instrument_key(position)
        interval = {"day": "5min", "week": "hour", "month": "day"}[range_name]
        interval_label = {"5min": "5 мин", "hour": "1 час", "day": "1 день"}[interval]
        warm_days = {"day": 7, "week": 20, "month": 120}[range_name]
        with self.lock:
            with self.market.factory() as db:
                row = db.query(StockChartCache).filter_by(instrument_key=key, interval=interval).first()
                data, fetched = (json.loads(row.candles_json), utc(row.fetched_at)) if row else ([], None)
            stale = fetched is None or now - fetched >= timedelta(minutes=5)
            if stale:
                try:
                    token = self.market.token()
                    if not token:
                        raise ValueError("Токен чтения не настроен.")
                    bars = self.market.adapter.candles(token, key, interval, now - timedelta(days=warm_days), now,
                        sandbox=self.market.portfolio.mode_service.current().is_sandbox)
                    if not bars:
                        raise ValueError("Нет завершённых свечей.")
                    data = [{**asdict(bar), "time": utc(bar.time).isoformat()} for bar in bars]
                    fetched, stale = now, False
                    with self.market.factory() as db:
                        row = db.query(StockChartCache).filter_by(instrument_key=key, interval=interval).first() or StockChartCache(
                            instrument_key=key, interval=interval)
                        db.add(row)
                        row.candles_json, row.fetched_at = json.dumps(data), naive(now)
                        db.commit()
                except Exception:
                    if not data:
                        raise ValueError("История графика сейчас недоступна.") from None
            candles = sorted([PriceCandle(**{**bar, "time": utc(datetime.fromisoformat(bar["time"]))}) for bar in data], key=lambda bar: bar.time)
            candles = [bar for bar in candles if utc(bar.time) <= now]
            analytics = ChartAnalyticsService().calculate(candles)
            # This new view contains descriptive indicators, never hindsight trade markers.
            analytics = replace(analytics, entry_marker=None, exit_marker=None, hindsight_return_pct=None)
            start = (now.astimezone(MOSCOW).replace(hour=0, minute=0, second=0, microsecond=0)
                     if range_name == "day" else now - timedelta(days=7 if range_name == "week" else 31))
            visible = [bar for bar in candles if utc(bar.time) >= utc(start)]
            if not visible:
                raise ValueError("Для выбранного периода нет завершённых свечей.")
            figure = Figure(figsize=(9, 8), dpi=110)
            price_axis, volume_axis, rsi_axis, macd_axis = figure.subplots(4, 1, sharex=True,
                gridspec_kw={"height_ratios": [3, 1, 1, 1]})
            times = [utc(bar.time).astimezone(MOSCOW) for bar in visible]
            price_axis.plot(times, [bar.close for bar in visible], label="Цена")
            for series in (analytics.sma20, analytics.sma50):
                points = [p for p in series.points if utc(p.time) >= utc(start)]
                if points:
                    price_axis.plot([utc(p.time).astimezone(MOSCOW) for p in points], [p.value for p in points], label=series.label)
            price_axis.set_title(f"{position.ticker} · {dict(day='день', week='неделя', month='месяц')[range_name]} · {interval_label}")
            price_axis.legend(loc="best", fontsize=8)
            volume_axis.bar(times, [bar.volume or 0 for bar in visible], width={"day": 0.0025, "week": 0.035, "month": 0.7}[range_name])
            volume_axis.set_ylabel("Объём")
            rsi = [p for p in analytics.rsi14.points if utc(p.time) >= utc(start)]
            if rsi:
                rsi_axis.plot([utc(p.time).astimezone(MOSCOW) for p in rsi], [p.value for p in rsi])
                rsi_axis.axhline(30, color="gray", linestyle="--")
                rsi_axis.axhline(70, color="gray", linestyle="--")
            else:
                rsi_axis.text(0.02, 0.4, "Недостаточно истории", transform=rsi_axis.transAxes)
            rsi_axis.set_ylabel("RSI14")
            macd = [p for p in analytics.macd.points if utc(p.time) >= utc(start)]
            if macd:
                macd_times = [utc(p.time).astimezone(MOSCOW) for p in macd]
                macd_axis.plot(macd_times, [p.macd for p in macd], label="MACD")
                macd_axis.plot(macd_times, [p.signal for p in macd], label="Signal")
                macd_axis.bar(macd_times, [p.histogram for p in macd], alpha=0.25,
                              width={"day": 0.0025, "week": 0.035, "month": 0.7}[range_name])
                macd_axis.legend(fontsize=7)
            else:
                macd_axis.text(0.02, 0.4, "Недостаточно истории", transform=macd_axis.transAxes)
            macd_axis.set_ylabel("MACD")
            for axis in (price_axis, volume_axis, rsi_axis, macd_axis):
                axis.grid(alpha=0.2)
            figure.autofmt_xdate()
            atr = analytics.atr14.points[-1].value if analytics.atr14.points else None
            volatility = analytics.periodic_volatility_pct
            summary = f"ATR14: {atr:.2f}" if atr is not None else "ATR14: недостаточно истории"
            summary += f" · волатильность свечей: {volatility:.2f}%" if volatility is not None else " · волатильность недоступна"
            if len(candles) < 50:
                summary += "\nДля части индикаторов недостаточно истории."
            summary += f"\nСвечи {interval_label}; последняя: {utc(visible[-1].time).astimezone(MOSCOW):%d.%m %H:%M} МСК."
            if stale:
                summary += "\nУстаревший кэш: обновить историю не удалось."
            figure.text(0.08, 0.015, summary, fontsize=8)
            figure.subplots_adjust(bottom=0.15, hspace=0.15)
            stream = BytesIO()
            figure.savefig(stream, format="png")
            return StockChart(stream.getvalue(), summary, fetched, stale, len(visible))
