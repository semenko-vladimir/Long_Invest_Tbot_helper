from typing import Protocol

from app.charts.schemas import ChartAdapterResult, ChartRange


class ChartDataAdapter(Protocol):
    """Read-only adapter for chart candles; never exposes broker order methods."""

    @property
    def source_name(self) -> str:
        ...

    def fetch_candles(self, ticker: str, range_name: ChartRange) -> ChartAdapterResult:
        ...
