from io import BytesIO
from datetime import datetime, timezone

import matplotlib

matplotlib.use("Agg")
import matplotlib.dates as mdates
from matplotlib.figure import Figure

from app.charts.position_values import PositionValueChartService
from app.charts.analytics import ChartAnalyticsService
from app.charts.schemas import (
    ChartAnalytics,
    ChartDataGap,
    ChartHistory,
    ChartImageResult,
    PositionValueChart,
    PriceCandle,
)
from app.charts.services import ChartHistoryService, normalize_chart_mode


class ChartImageService:
    """On-demand read-only PNG renderer for chart history."""

    def __init__(
        self,
        history_service: ChartHistoryService,
        analytics_service: ChartAnalyticsService | None = None,
        position_value_service: PositionValueChartService | None = None,
    ):
        self.history_service = history_service
        self.analytics_service = analytics_service or ChartAnalyticsService()
        self.position_value_service = position_value_service

    def render_png(
        self,
        ticker: str,
        range_name: str = "month",
        include_analytics: bool = True,
        mode: str = "price",
    ) -> ChartImageResult:
        normalized_mode = normalize_chart_mode(mode)
        if normalized_mode is None:
            message = "Unsupported chart mode. Use mode=price or mode=position_value."
            return ChartImageResult(
                png_bytes=None,
                history=self._empty_history(ticker, range_name, [message]),
                errors=[message],
            )

        if normalized_mode == "position_value":
            return self._render_position_value_png(ticker, range_name)

        history = self.history_service.get_history(ticker, range_name)
        if history.errors:
            return ChartImageResult(
                png_bytes=None,
                history=history,
                mode="price",
                data_gaps=list(history.data_gaps),
                errors=list(history.errors),
            )

        if not history.candles:
            message = "No candles are available for chart rendering."
            gaps = list(history.data_gaps)
            if not any(gap.category == "price_history" for gap in gaps):
                gaps.append(ChartDataGap("price_history", message, "low"))
            return ChartImageResult(
                png_bytes=None,
                history=history,
                mode="price",
                data_gaps=gaps,
                errors=[message],
            )

        try:
            analytics = self.analytics_service.calculate(history.candles) if include_analytics else None
            png_bytes = self._render_history(history, analytics=analytics)
        except Exception as exc:
            return ChartImageResult(
                png_bytes=None,
                history=history,
                mode="price",
                data_gaps=list(history.data_gaps)
                + [ChartDataGap("rendering", "Chart image rendering failed.", "medium")],
                errors=[f"Chart rendering failed: {str(exc)}"],
            )

        return ChartImageResult(
            png_bytes=png_bytes,
            history=history,
            mode="price",
            analytics=analytics,
            data_gaps=list(history.data_gaps),
            errors=[],
        )

    def _render_position_value_png(self, ticker: str, range_name: str) -> ChartImageResult:
        if self.position_value_service is None:
            message = "Current quantity value chart service is not configured."
            return ChartImageResult(
                png_bytes=None,
                history=self._empty_history(ticker, range_name, [message]),
                mode="position_value",
                errors=[message],
            )

        position_value = self.position_value_service.get_position_value(ticker, range_name)
        history = self._history_from_position_value(position_value)
        if position_value.errors:
            return ChartImageResult(
                png_bytes=None,
                history=history,
                mode="position_value",
                position_value=position_value,
                data_gaps=list(position_value.data_gaps),
                errors=list(position_value.errors),
            )

        if not position_value.value_series:
            message = "No current quantity value points are available for chart rendering."
            gaps = list(position_value.data_gaps)
            if not any(gap.category == "price_history" for gap in gaps):
                gaps.append(ChartDataGap("price_history", message, "low"))
            return ChartImageResult(
                png_bytes=None,
                history=history,
                mode="position_value",
                position_value=position_value,
                data_gaps=gaps,
                errors=[message],
            )

        try:
            png_bytes = self._render_position_value(position_value)
        except Exception as exc:
            return ChartImageResult(
                png_bytes=None,
                history=history,
                mode="position_value",
                position_value=position_value,
                data_gaps=list(position_value.data_gaps)
                + [ChartDataGap("rendering", "Chart image rendering failed.", "medium")],
                errors=[f"Chart rendering failed: {str(exc)}"],
            )

        return ChartImageResult(
            png_bytes=png_bytes,
            history=history,
            mode="position_value",
            position_value=position_value,
            data_gaps=list(position_value.data_gaps),
            errors=[],
        )

    def _render_history(self, history: ChartHistory, analytics: ChartAnalytics | None = None) -> bytes:
        candles = self._sorted_candles(history.candles)
        has_volume = any(candle.volume is not None for candle in candles)
        if has_volume:
            figure = Figure(figsize=(9, 5.6), dpi=120)
            price_axis = figure.add_subplot(2, 1, 1)
            volume_axis = figure.add_subplot(2, 1, 2, sharex=price_axis)
        else:
            figure = Figure(figsize=(9, 4.8), dpi=120)
            price_axis = figure.add_subplot(1, 1, 1)
            volume_axis = None

        times = [candle.time for candle in candles]
        closes = [candle.close for candle in candles]
        price_axis.plot(times, closes, color="#2563eb", linewidth=1.8, label="Close")
        price_axis.set_title(f"{history.ticker} price history ({history.range})", fontsize=13, pad=12)
        price_axis.set_ylabel("Price")
        price_axis.grid(True, color="#e5e7eb", linewidth=0.8)
        if analytics is not None:
            self._draw_analytics(price_axis, analytics)

        if volume_axis is not None:
            volumes = [candle.volume or 0 for candle in candles]
            volume_axis.bar(times, volumes, color="#94a3b8", width=self._bar_width_days(history), align="center")
            volume_axis.set_ylabel("Volume")
            volume_axis.grid(True, axis="y", color="#e5e7eb", linewidth=0.8)
            self._format_time_axis(volume_axis, history)
        else:
            self._format_time_axis(price_axis, history)

        generated = self._format_metadata_time(history.generated_at)
        fetched = self._format_metadata_time(history.fetched_at)
        note = f"Source: {history.source} | Fetched: {fetched} | Generated: {generated}"
        if history.as_of_date:
            note = f"{note} | As of: {history.as_of_date}"
        if history.delay_status:
            note = f"{note} | Delay: {history.delay_status}"
        if history.figi:
            note = f"{note} | FIGI: {history.figi}"
        figure.text(0.01, 0.035, note, fontsize=8, color="#475569")
        figure.text(0.01, 0.01, history.disclaimer, fontsize=7.5, color="#64748b")
        figure.tight_layout(rect=(0, 0.08, 1, 0.96))

        output = BytesIO()
        figure.savefig(output, format="png", bbox_inches="tight")
        return output.getvalue()

    def _render_position_value(self, position_value: PositionValueChart) -> bytes:
        ordered = sorted(position_value.value_series, key=lambda point: point.time)
        figure = Figure(figsize=(9, 4.8), dpi=120)
        axis = figure.add_subplot(1, 1, 1)

        times = [point.time for point in ordered]
        values = [point.value for point in ordered]
        axis.plot(times, values, color="#1f7a4d", linewidth=1.8, label="Current quantity value")
        axis.set_title(
            f"{position_value.ticker} current position quantity valued at historical prices "
            f"({position_value.range})",
            fontsize=13,
            pad=12,
        )
        axis.set_ylabel("Value (RUB)")
        axis.grid(True, color="#e5e7eb", linewidth=0.8)
        axis.legend(loc="best", fontsize=7.5, frameon=False)
        self._format_time_axis(axis, position_value)

        generated = self._format_metadata_time(position_value.generated_at)
        fetched = self._format_metadata_time(position_value.fetched_at)
        note = (
            f"Source: {position_value.source} | Fetched: {fetched} | "
            f"Generated: {generated} | "
            f"Current quantity: {position_value.quantity:g}"
        )
        if position_value.as_of_date:
            note = f"{note} | As of: {position_value.as_of_date}"
        if position_value.delay_status:
            note = f"{note} | Delay: {position_value.delay_status}"
        if position_value.figi:
            note = f"{note} | FIGI: {position_value.figi}"
        figure.text(0.01, 0.035, note, fontsize=8, color="#475569")
        figure.text(0.01, 0.01, position_value.disclaimer, fontsize=7.5, color="#64748b")
        figure.tight_layout(rect=(0, 0.08, 1, 0.96))

        output = BytesIO()
        figure.savefig(output, format="png", bbox_inches="tight")
        return output.getvalue()

    def _draw_analytics(self, axis, analytics: ChartAnalytics) -> None:
        if analytics.sma20.points:
            axis.plot(
                [point.time for point in analytics.sma20.points],
                [point.value for point in analytics.sma20.points],
                color="#b45309",
                linewidth=1.2,
                label=analytics.sma20.label,
            )
        if analytics.sma50.points:
            axis.plot(
                [point.time for point in analytics.sma50.points],
                [point.value for point in analytics.sma50.points],
                color="#7c3aed",
                linewidth=1.2,
                label=analytics.sma50.label,
            )

        if analytics.entry_marker is not None:
            axis.scatter(
                [analytics.entry_marker.time],
                [analytics.entry_marker.close],
                color="#15803d",
                marker="^",
                s=54,
                zorder=5,
                label="Historical entry",
            )
            self._annotate_marker(axis, analytics.entry_marker.time, analytics.entry_marker.close, analytics.entry_marker.label)

        if analytics.exit_marker is not None:
            label = analytics.exit_marker.label
            if analytics.hindsight_return_pct is not None:
                label = f"{label} ({analytics.hindsight_return_pct:+.1f}%)"
            axis.scatter(
                [analytics.exit_marker.time],
                [analytics.exit_marker.close],
                color="#be123c",
                marker="v",
                s=54,
                zorder=5,
                label="Historical exit",
            )
            self._annotate_marker(axis, analytics.exit_marker.time, analytics.exit_marker.close, label)

        if analytics.max_drawdown is not None:
            drawdown = analytics.max_drawdown
            axis.plot(
                [drawdown.peak_time, drawdown.trough_time],
                [drawdown.peak_close, drawdown.trough_close],
                color="#dc2626",
                linestyle="--",
                linewidth=1.0,
                label="Max drawdown",
            )
            self._annotate_marker(
                axis,
                drawdown.trough_time,
                drawdown.trough_close,
                f"Max drawdown {drawdown.drawdown_pct:.1f}%",
            )

        if analytics.range_position is not None:
            position = analytics.range_position
            text = (
                f"Latest vs range high: {position.vs_range_high_pct:+.1f}%\n"
                f"Latest vs range low: {position.vs_range_low_pct:+.1f}%"
            )
            axis.text(
                0.01,
                0.98,
                text,
                transform=axis.transAxes,
                va="top",
                ha="left",
                fontsize=7.5,
                color="#334155",
                bbox={"facecolor": "#ffffff", "edgecolor": "#cbd5e1", "alpha": 0.86, "pad": 4},
            )

        axis.legend(loc="best", fontsize=7.5, frameon=False)

    def _annotate_marker(self, axis, time, price: float, label: str) -> None:
        axis.annotate(
            label,
            xy=(time, price),
            xytext=(8, 12),
            textcoords="offset points",
            fontsize=7.5,
            color="#334155",
            arrowprops={"arrowstyle": "->", "color": "#64748b", "linewidth": 0.8},
        )

    def _sorted_candles(self, candles: list[PriceCandle]) -> list[PriceCandle]:
        return sorted(candles, key=lambda candle: candle.time)

    def _format_time_axis(self, axis, history: ChartHistory) -> None:
        if history.range == "day":
            axis.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M"))
        elif history.range in {"week", "month"}:
            axis.xaxis.set_major_formatter(mdates.DateFormatter("%d %b"))
        else:
            axis.xaxis.set_major_formatter(mdates.DateFormatter("%b %Y"))
        for label in axis.get_xticklabels():
            label.set_rotation(25)
            label.set_ha("right")

    def _bar_width_days(self, history: ChartHistory) -> float:
        widths = {
            "day": 0.03,
            "week": 0.25,
            "month": 0.75,
            "six_months": 2.0,
            "year": 4.0,
            "all": 10.0,
        }
        return widths.get(history.range, 0.75)

    def _history_from_position_value(self, position_value: PositionValueChart) -> ChartHistory:
        return ChartHistory(
            ticker=position_value.ticker,
            figi=position_value.figi,
            range=position_value.range,
            candles=[],
            generated_at=position_value.generated_at,
            source=position_value.source,
            fetched_at=position_value.fetched_at,
            as_of_date=position_value.as_of_date,
            freshness=position_value.freshness,
            delay_status=position_value.delay_status,
            data_gaps=list(position_value.data_gaps),
            errors=list(position_value.errors),
            disclaimer=position_value.disclaimer,
        )

    def _empty_history(self, ticker: str, range_name: str, errors: list[str]) -> ChartHistory:
        return ChartHistory(
            ticker=str(ticker or "").strip().upper(),
            figi=None,
            range=str(range_name or "").strip(),
            candles=[],
            generated_at=datetime.now(timezone.utc),
            source="chart-renderer",
            fetched_at=datetime.now(timezone.utc),
            as_of_date=datetime.now(timezone.utc).date().isoformat(),
            data_gaps=[],
            errors=list(errors),
        )

    def _format_metadata_time(self, value: datetime | None) -> str:
        if value is None:
            return "unknown"
        if value.tzinfo is not None:
            value = value.astimezone(timezone.utc).replace(tzinfo=None)
        return value.strftime("%Y-%m-%d %H:%M UTC")
