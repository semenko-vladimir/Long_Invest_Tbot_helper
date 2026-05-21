from io import BytesIO

import matplotlib

matplotlib.use("Agg")
import matplotlib.dates as mdates
from matplotlib.figure import Figure

from app.charts.schemas import ChartDataGap, ChartHistory, ChartImageResult
from app.charts.services import ChartHistoryService


class ChartImageService:
    """On-demand read-only PNG renderer for chart history."""

    def __init__(self, history_service: ChartHistoryService):
        self.history_service = history_service

    def render_png(self, ticker: str, range_name: str = "month") -> ChartImageResult:
        history = self.history_service.get_history(ticker, range_name)
        if history.errors:
            return ChartImageResult(
                png_bytes=None,
                history=history,
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
                data_gaps=gaps,
                errors=[message],
            )

        try:
            png_bytes = self._render_history(history)
        except Exception as exc:
            return ChartImageResult(
                png_bytes=None,
                history=history,
                data_gaps=list(history.data_gaps)
                + [ChartDataGap("rendering", "Chart image rendering failed.", "medium")],
                errors=[f"Chart rendering failed: {str(exc)}"],
            )

        return ChartImageResult(
            png_bytes=png_bytes,
            history=history,
            data_gaps=list(history.data_gaps),
            errors=[],
        )

    def _render_history(self, history: ChartHistory) -> bytes:
        has_volume = any(candle.volume is not None for candle in history.candles)
        if has_volume:
            figure = Figure(figsize=(9, 5.6), dpi=120)
            price_axis = figure.add_subplot(2, 1, 1)
            volume_axis = figure.add_subplot(2, 1, 2, sharex=price_axis)
        else:
            figure = Figure(figsize=(9, 4.8), dpi=120)
            price_axis = figure.add_subplot(1, 1, 1)
            volume_axis = None

        times = [candle.time for candle in history.candles]
        closes = [candle.close for candle in history.candles]
        price_axis.plot(times, closes, color="#2563eb", linewidth=1.8)
        price_axis.set_title(f"{history.ticker} price history ({history.range})", fontsize=13, pad=12)
        price_axis.set_ylabel("Price")
        price_axis.grid(True, color="#e5e7eb", linewidth=0.8)

        if volume_axis is not None:
            volumes = [candle.volume or 0 for candle in history.candles]
            volume_axis.bar(times, volumes, color="#94a3b8", width=self._bar_width_days(history), align="center")
            volume_axis.set_ylabel("Volume")
            volume_axis.grid(True, axis="y", color="#e5e7eb", linewidth=0.8)
            self._format_time_axis(volume_axis, history)
        else:
            self._format_time_axis(price_axis, history)

        generated = history.generated_at.strftime("%Y-%m-%d %H:%M UTC")
        note = f"Generated: {generated} | Source: {history.source}"
        if history.figi:
            note = f"{note} | FIGI: {history.figi}"
        figure.text(0.01, 0.035, note, fontsize=8, color="#475569")
        figure.text(0.01, 0.01, history.disclaimer, fontsize=7.5, color="#64748b")
        figure.tight_layout(rect=(0, 0.08, 1, 0.96))

        output = BytesIO()
        figure.savefig(output, format="png", bbox_inches="tight")
        return output.getvalue()

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
