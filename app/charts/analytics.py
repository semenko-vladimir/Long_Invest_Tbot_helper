from collections.abc import Sequence
import math
import statistics

from app.charts.schemas import (
    ChartAnalytics,
    ChartAnalyticsMarker,
    ChartBandPoint,
    ChartBandSeries,
    ChartDrawdown,
    ChartIndicatorPoint,
    ChartIndicatorSeries,
    ChartMacdPoint,
    ChartMacdSeries,
    ChartRangePosition,
    ChartSmaPoint,
    ChartSmaSeries,
    ChartVolumeStats,
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
            range_return_pct=self._range_return(ordered),
            latest_change_pct=self._latest_change(ordered),
            periodic_volatility_pct=self._periodic_volatility(ordered),
            annualized_volatility_pct=self._annualized_volatility(ordered),
            max_drawdown=self._max_drawdown(ordered),
            range_position=self._range_position(ordered),
            sma20=self._sma(ordered, 20),
            sma50=self._sma(ordered, 50),
            ema12=self._ema(ordered, 12),
            ema26=self._ema(ordered, 26),
            rsi14=self._rsi(ordered, 14),
            atr14=self._atr(ordered, 14),
            bollinger20=self._bollinger(ordered, 20),
            macd=self._macd(ordered),
            volume_stats=self._volume_stats(ordered),
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

    def _range_return(self, candles: Sequence[PriceCandle]) -> float | None:
        if len(candles) < 2:
            return None
        first = float(candles[0].close)
        latest = float(candles[-1].close)
        if first == 0:
            return None
        return self._pct_change(latest, first)

    def _latest_change(self, candles: Sequence[PriceCandle]) -> float | None:
        if len(candles) < 2:
            return None
        previous = float(candles[-2].close)
        latest = float(candles[-1].close)
        if previous == 0:
            return None
        return self._pct_change(latest, previous)

    def _periodic_volatility(self, candles: Sequence[PriceCandle]) -> float | None:
        returns = self._periodic_returns(candles)
        if len(returns) < 2:
            return None
        return statistics.pstdev(returns) * 100

    def _annualized_volatility(self, candles: Sequence[PriceCandle]) -> float | None:
        periodic = self._periodic_volatility(candles)
        if periodic is None:
            return None
        return periodic * math.sqrt(252)

    def _periodic_returns(self, candles: Sequence[PriceCandle]) -> list[float]:
        returns: list[float] = []
        for previous, current in zip(candles, candles[1:]):
            previous_close = float(previous.close)
            if previous_close == 0:
                continue
            returns.append((float(current.close) - previous_close) / previous_close)
        return returns

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

    def _ema(self, candles: Sequence[PriceCandle], window: int) -> ChartIndicatorSeries:
        points: list[ChartIndicatorPoint] = []
        if window <= 0 or len(candles) < window:
            return ChartIndicatorSeries(key=f"ema{window}", label=f"EMA{window}", window=window, points=points)

        closes = [float(candle.close) for candle in candles]
        multiplier = 2 / (window + 1)
        ema_value = sum(closes[:window]) / window
        points.append(ChartIndicatorPoint(time=candles[window - 1].time, value=ema_value))

        for index in range(window, len(candles)):
            ema_value = (closes[index] - ema_value) * multiplier + ema_value
            points.append(ChartIndicatorPoint(time=candles[index].time, value=ema_value))

        return ChartIndicatorSeries(key=f"ema{window}", label=f"EMA{window}", window=window, points=points)

    def _rsi(self, candles: Sequence[PriceCandle], window: int) -> ChartIndicatorSeries:
        points: list[ChartIndicatorPoint] = []
        if window <= 0 or len(candles) <= window:
            return ChartIndicatorSeries(key=f"rsi{window}", label=f"RSI{window}", window=window, points=points)

        closes = [float(candle.close) for candle in candles]
        gains: list[float] = []
        losses: list[float] = []
        for previous, current in zip(closes, closes[1 : window + 1]):
            change = current - previous
            gains.append(max(change, 0.0))
            losses.append(max(-change, 0.0))

        average_gain = sum(gains) / window
        average_loss = sum(losses) / window
        points.append(ChartIndicatorPoint(time=candles[window].time, value=self._rsi_value(average_gain, average_loss)))

        for index in range(window + 1, len(candles)):
            change = closes[index] - closes[index - 1]
            gain = max(change, 0.0)
            loss = max(-change, 0.0)
            average_gain = ((average_gain * (window - 1)) + gain) / window
            average_loss = ((average_loss * (window - 1)) + loss) / window
            points.append(ChartIndicatorPoint(time=candles[index].time, value=self._rsi_value(average_gain, average_loss)))

        return ChartIndicatorSeries(key=f"rsi{window}", label=f"RSI{window}", window=window, points=points)

    def _atr(self, candles: Sequence[PriceCandle], window: int) -> ChartIndicatorSeries:
        points: list[ChartIndicatorPoint] = []
        if window <= 0 or len(candles) < window:
            return ChartIndicatorSeries(key=f"atr{window}", label=f"ATR{window}", window=window, points=points)

        true_ranges = self._true_ranges(candles)
        if len(true_ranges) < window:
            return ChartIndicatorSeries(key=f"atr{window}", label=f"ATR{window}", window=window, points=points)

        atr_value = sum(true_ranges[:window]) / window
        points.append(ChartIndicatorPoint(time=candles[window - 1].time, value=atr_value))
        for index in range(window, len(true_ranges)):
            atr_value = ((atr_value * (window - 1)) + true_ranges[index]) / window
            points.append(ChartIndicatorPoint(time=candles[index].time, value=atr_value))

        return ChartIndicatorSeries(key=f"atr{window}", label=f"ATR{window}", window=window, points=points)

    def _bollinger(self, candles: Sequence[PriceCandle], window: int) -> ChartBandSeries:
        points: list[ChartBandPoint] = []
        if window <= 0 or len(candles) < window:
            return ChartBandSeries(key=f"bollinger{window}", label=f"Bollinger {window}", window=window, points=points)

        closes = [float(candle.close) for candle in candles]
        for index in range(window - 1, len(candles)):
            window_values = closes[index - window + 1 : index + 1]
            middle = sum(window_values) / window
            deviation = statistics.pstdev(window_values)
            points.append(
                ChartBandPoint(
                    time=candles[index].time,
                    middle=middle,
                    upper=middle + 2 * deviation,
                    lower=middle - 2 * deviation,
                )
            )

        return ChartBandSeries(key=f"bollinger{window}", label=f"Bollinger {window}", window=window, points=points)

    def _macd(self, candles: Sequence[PriceCandle]) -> ChartMacdSeries:
        if len(candles) < 35:
            return ChartMacdSeries(points=[])

        closes = [float(candle.close) for candle in candles]
        ema12 = self._ema_values_seeded_from_first(closes, 12)
        ema26 = self._ema_values_seeded_from_first(closes, 26)
        macd_values = [fast - slow for fast, slow in zip(ema12, ema26)]
        signal_values = self._ema_values_seeded_from_first(macd_values, 9)

        points: list[ChartMacdPoint] = []
        for index in range(34, len(candles)):
            macd_value = macd_values[index]
            signal_value = signal_values[index]
            points.append(
                ChartMacdPoint(
                    time=candles[index].time,
                    macd=macd_value,
                    signal=signal_value,
                    histogram=macd_value - signal_value,
                )
            )
        return ChartMacdSeries(points=points)

    def _volume_stats(self, candles: Sequence[PriceCandle]) -> ChartVolumeStats:
        volumes = [int(candle.volume) for candle in candles if candle.volume is not None]
        if not volumes:
            return ChartVolumeStats()

        latest = candles[-1].volume
        average = sum(volumes) / len(volumes)
        latest_vs_average = None
        if latest is not None and average:
            latest_vs_average = (int(latest) - average) / average * 100
        return ChartVolumeStats(
            latest_volume=int(latest) if latest is not None else None,
            average_volume=average,
            latest_vs_average_pct=latest_vs_average,
        )

    def _true_ranges(self, candles: Sequence[PriceCandle]) -> list[float]:
        true_ranges: list[float] = []
        previous_close = None
        for candle in candles:
            high = float(candle.high)
            low = float(candle.low)
            if previous_close is None:
                true_range = high - low
            else:
                true_range = max(high - low, abs(high - previous_close), abs(low - previous_close))
            true_ranges.append(true_range)
            previous_close = float(candle.close)
        return true_ranges

    def _ema_values_seeded_from_first(self, values: Sequence[float], window: int) -> list[float]:
        if not values:
            return []
        multiplier = 2 / (window + 1)
        ema_value = float(values[0])
        result = [ema_value]
        for value in values[1:]:
            ema_value = (float(value) - ema_value) * multiplier + ema_value
            result.append(ema_value)
        return result

    def _rsi_value(self, average_gain: float, average_loss: float) -> float:
        if average_loss == 0:
            return 100.0
        relative_strength = average_gain / average_loss
        return 100 - (100 / (1 + relative_strength))

    def _pct_change(self, value: float, baseline: float) -> float:
        if baseline == 0:
            return 0.0
        return (value - baseline) / baseline * 100
