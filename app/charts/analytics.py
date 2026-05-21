from collections.abc import Sequence

from app.charts.schemas import (
    ChartAnalytics,
    ChartAnalyticsMarker,
    ChartDrawdown,
    ChartRangePosition,
    ChartSmaPoint,
    ChartSmaSeries,
    PriceCandle,
)


ENTRY_LABEL = "Best historical entry in this range"
EXIT_LABEL = "Best historical exit after that point"


class ChartAnalyticsService:
    """Pure hindsight-only calculations over already selected chart candles."""

    def calculate(self, candles: Sequence[PriceCandle]) -> ChartAnalytics:
        ordered = sorted(candles, key=lambda candle: candle.time)
        if not ordered:
            return ChartAnalytics()

        closes = [float(candle.close) for candle in ordered]
        entry_index = min(range(len(ordered)), key=lambda index: closes[index])
        entry_candle = ordered[entry_index]
        entry_marker = ChartAnalyticsMarker(
            kind="historical_entry",
            label=ENTRY_LABEL,
            time=entry_candle.time,
            close=float(entry_candle.close),
        )

        exit_marker = None
        hindsight_return_pct = None
        if entry_index < len(ordered) - 1:
            exit_index = max(range(entry_index + 1, len(ordered)), key=lambda index: closes[index])
            exit_candle = ordered[exit_index]
            exit_marker = ChartAnalyticsMarker(
                kind="historical_exit",
                label=EXIT_LABEL,
                time=exit_candle.time,
                close=float(exit_candle.close),
            )
            if entry_candle.close:
                hindsight_return_pct = (
                    (float(exit_candle.close) - float(entry_candle.close)) / float(entry_candle.close) * 100
                )

        return ChartAnalytics(
            entry_marker=entry_marker,
            exit_marker=exit_marker,
            hindsight_return_pct=hindsight_return_pct,
            max_drawdown=self._max_drawdown(ordered),
            range_position=self._range_position(ordered),
            sma20=self._sma(ordered, 20),
            sma50=self._sma(ordered, 50),
        )

    def _max_drawdown(self, candles: Sequence[PriceCandle]) -> ChartDrawdown | None:
        if len(candles) < 2:
            return None

        peak_index = 0
        peak_close = float(candles[0].close)
        worst_peak_index = 0
        worst_trough_index = 1
        worst_drawdown_pct = 0.0

        for index in range(1, len(candles)):
            close = float(candles[index].close)
            if close > peak_close:
                peak_index = index
                peak_close = close
                continue

            if peak_close == 0:
                continue

            drawdown_pct = (close - peak_close) / peak_close * 100
            if drawdown_pct < worst_drawdown_pct:
                worst_drawdown_pct = drawdown_pct
                worst_peak_index = peak_index
                worst_trough_index = index

        if worst_drawdown_pct == 0:
            return None

        peak_candle = candles[worst_peak_index]
        trough_candle = candles[worst_trough_index]
        return ChartDrawdown(
            peak_time=peak_candle.time,
            peak_close=float(peak_candle.close),
            trough_time=trough_candle.time,
            trough_close=float(trough_candle.close),
            drawdown_pct=worst_drawdown_pct,
        )

    def _range_position(self, candles: Sequence[PriceCandle]) -> ChartRangePosition:
        closes = [float(candle.close) for candle in candles]
        latest = candles[-1]
        latest_close = float(latest.close)
        range_high = max(closes)
        range_low = min(closes)
        return ChartRangePosition(
            latest_time=latest.time,
            latest_close=latest_close,
            range_high_close=range_high,
            range_low_close=range_low,
            vs_range_high_pct=self._pct_change(latest_close, range_high),
            vs_range_low_pct=self._pct_change(latest_close, range_low),
        )

    def _sma(self, candles: Sequence[PriceCandle], window: int) -> ChartSmaSeries:
        points: list[ChartSmaPoint] = []
        if window <= 0:
            return ChartSmaSeries(window=window, label=f"SMA{window}", points=points)

        running_sum = 0.0
        closes: list[float] = []
        for candle in candles:
            close = float(candle.close)
            closes.append(close)
            running_sum += close
            if len(closes) > window:
                running_sum -= closes[-window - 1]
            if len(closes) >= window:
                points.append(ChartSmaPoint(time=candle.time, value=running_sum / window))

        return ChartSmaSeries(window=window, label=f"SMA{window}", points=points)

    def _pct_change(self, value: float, baseline: float) -> float:
        if baseline == 0:
            return 0.0
        return (value - baseline) / baseline * 100
